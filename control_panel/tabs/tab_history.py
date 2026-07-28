"""Tab 3 — 거래 내역: 날짜 필터 + 풍부한 통계"""
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QComboBox, QDateEdit, QPushButton, QSpinBox, QFrame,
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont

from control_panel.widgets.colored_table import ColoredTable, RED, BLUE, GRAY
from control_panel import db

HEADERS = ['매도일', '매도시간', '종목명', '전략', '매수가', '매도가',
           '수익률%', '실현손익', '보유일', '매도사유']


def _d8(s):
    digits = ''.join(c for c in str(s) if c.isdigit())
    return digits[:8] if len(digits) >= 8 else ''


def _fmt_date(s):
    d = _d8(s)
    return f'{d[:4]}.{d[4:6]}.{d[6:8]}' if len(d) == 8 else str(s)


def _fmt_time(s):
    """sell_date 문자열에서 시간 부분 추출 (e.g. '20260101 093015' → '09:30:15')."""
    digits = ''.join(c for c in str(s) if c.isdigit())
    if len(digits) >= 12:   # YYYYMMDDHHMMSS
        t = digits[8:14]
        return f'{t[:2]}:{t[2:4]}:{t[4:6]}'
    elif len(digits) >= 10:  # YYYYMMDDHHMM
        t = digits[8:12]
        return f'{t[:2]}:{t[2:4]}'
    return ''


def _hold_days(buy, sell):
    try:
        return (datetime.strptime(_d8(sell), '%Y%m%d') -
                datetime.strptime(_d8(buy), '%Y%m%d')).days
    except Exception:
        return 0


def _stat_cell(label, value='—', color='#111111') -> tuple:
    frame = QFrame()
    frame.setFrameShape(QFrame.StyledPanel)
    frame.setStyleSheet('QFrame{border:1px solid #ddd;border-radius:4px;background:#fff;}')
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(8, 4, 8, 4)
    lay.setSpacing(0)
    l = QLabel(label)
    l.setFont(QFont('Malgun Gothic', 7))
    l.setStyleSheet('color:#888;border:none;')
    v = QLabel(value)
    v.setFont(QFont('Malgun Gothic', 10, QFont.Bold))
    v.setStyleSheet(f'color:{color};border:none;')
    v.setTextInteractionFlags(Qt.TextSelectableByMouse)
    lay.addWidget(l)
    lay.addWidget(v)
    return frame, v


class HistoryTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_data = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # ── 빠른 날짜 버튼 ────────────────────────────────────────────
        quick_lay = QHBoxLayout()
        quick_lay.setSpacing(6)
        quick_lay.addWidget(QLabel('기간:'))
        for label, days in [('오늘', 0), ('1주일', 7), ('1개월', 30),
                             ('3개월', 90), ('6개월', 180), ('전체', 3650)]:
            btn = QPushButton(label)
            btn.setFixedHeight(26)
            btn.setFixedWidth(55)
            btn.clicked.connect(lambda _, d=days: self._quick_range(d))
            quick_lay.addWidget(btn)
        quick_lay.addSpacing(16)

        # 직접 날짜 선택
        today = QDate.currentDate()
        quick_lay.addWidget(QLabel('직접 입력:'))
        self._date_from = QDateEdit(today.addDays(-90))
        self._date_from.setCalendarPopup(True)
        self._date_from.setDisplayFormat('yyyy.MM.dd')
        self._date_from.setFixedWidth(100)
        quick_lay.addWidget(self._date_from)
        quick_lay.addWidget(QLabel('~'))
        self._date_to = QDateEdit(today)
        self._date_to.setCalendarPopup(True)
        self._date_to.setDisplayFormat('yyyy.MM.dd')
        self._date_to.setFixedWidth(100)
        quick_lay.addWidget(self._date_to)

        quick_lay.addSpacing(8)
        quick_lay.addWidget(QLabel('전략:'))
        self._strat = QComboBox()
        self._strat.addItems(['전체', 'A', 'B'])
        self._strat.setFixedWidth(55)
        quick_lay.addWidget(self._strat)

        quick_lay.addWidget(QLabel('최대:'))
        self._limit = QSpinBox()
        self._limit.setRange(50, 9999)
        self._limit.setValue(500)
        self._limit.setSingleStep(100)
        self._limit.setFixedWidth(65)
        quick_lay.addWidget(self._limit)

        search_btn = QPushButton('조회')
        search_btn.setFixedWidth(55)
        search_btn.setFixedHeight(26)
        search_btn.setStyleSheet('background:#0044bb;color:white;border-radius:3px;font-weight:bold;')
        search_btn.clicked.connect(self._search)
        quick_lay.addWidget(search_btn)
        quick_lay.addStretch()
        root.addLayout(quick_lay)

        # ── 통계 패널 ─────────────────────────────────────────────────
        stats_grid = QGridLayout()
        stats_grid.setSpacing(6)
        self._stats = {}
        stat_defs = [
            ('trades',   '총 거래'),    ('wins',     '익절'),
            ('losses',   '손절'),       ('win_rate', '승률'),
            ('avg_win',  '평균 익절률'), ('avg_loss', '평균 손절률'),
            ('pf',       '손익비 (R)'), ('total_pnl','총 실현손익'),
            ('avg_days', '평균 보유일'), ('best',     '최대 익절'),
            ('worst',    '최대 손절'),  ('a_wr',     'A전략 승률'),
        ]
        for i, (key, label) in enumerate(stat_defs):
            r, c = divmod(i, 6)
            frame, val = _stat_cell(label)
            self._stats[key] = val
            stats_grid.addWidget(frame, r, c)
        root.addLayout(stats_grid)

        # ── 테이블 ────────────────────────────────────────────────────
        self._table = ColoredTable(HEADERS, self)
        root.addWidget(self._table)

        self._search()

    def refresh(self, _=None):
        pass  # 수동 조회

    def _quick_range(self, days: int):
        today = QDate.currentDate()
        self._date_from.setDate(today.addDays(-days))
        self._date_to.setDate(today)
        self._search()

    def _search(self):
        date_from = self._date_from.date().toString('yyyyMMdd')
        date_to   = self._date_to.date().toString('yyyyMMdd')
        strat     = self._strat.currentText()
        limit     = self._limit.value()
        data = db.get_history(date_from, date_to, strat, limit)
        self._render(data)

    def _render(self, data: list):
        rows = []
        total_pnl = 0
        wins = losses = 0
        win_rates_a = win_total_a = 0
        sum_win = sum_loss = 0.0
        best = worst = 0.0
        sum_days = 0

        for t in data:
            rate = float(t.get('sell_rate') or 0)
            pnl  = int(t.get('realized_profit') or 0)
            strat= str(t.get('strategy_type') or '')
            days = _hold_days(t.get('buy_date', ''), t.get('sell_date', ''))
            total_pnl += pnl
            sum_days  += days
            if rate > 0:
                wins += 1
                sum_win += rate
                best = max(best, rate)
                if strat == 'A':
                    win_rates_a += 1
            else:
                losses += 1
                sum_loss += rate
                worst = min(worst, rate)
            if strat == 'A':
                win_total_a += 1

            sell_dt = t.get('sell_date', '')
            color = RED if rate >= 0 else BLUE
            rows.append([
                _fmt_date(sell_dt),
                (_fmt_time(sell_dt), GRAY),
                str(t.get('code_name', '')),
                str(strat),
                (f"{int(t.get('purchase_price', 0)):,}", None),
                (f"{int(t.get('sell_price', 0)):,}", None),
                (f"{rate:+.2f}%", color),
                (f"{pnl:+,}원", color),
                (f"{days}일", None),
                str(t.get('exit_reason', '') or ''),
            ])
        self._table.set_rows(rows)

        n = len(data)
        wr = wins / n * 100 if n else 0
        avg_win  = sum_win  / wins   if wins   else 0
        avg_loss = sum_loss / losses if losses else 0
        pf = abs(avg_win / avg_loss) if avg_loss else 0
        a_wr = win_rates_a / win_total_a * 100 if win_total_a else 0
        avg_days = sum_days / n if n else 0
        pnl_c  = '#cc0000' if total_pnl >= 0 else '#0044bb'
        wr_c   = '#cc0000' if wr >= 50 else '#0044bb'
        best_c = '#cc0000'
        worst_c= '#0044bb'

        self._stats['trades'].setText(f'{n}건')
        self._stats['wins'].setText(f'{wins}건')
        self._stats['wins'].setStyleSheet('color:#cc0000;font-weight:bold;')
        self._stats['losses'].setText(f'{losses}건')
        self._stats['losses'].setStyleSheet('color:#0044bb;font-weight:bold;')
        self._stats['win_rate'].setText(f'{wr:.1f}%')
        self._stats['win_rate'].setStyleSheet(f'color:{wr_c};font-weight:bold;')
        self._stats['avg_win'].setText(f'{avg_win:+.2f}%')
        self._stats['avg_win'].setStyleSheet('color:#cc0000;font-weight:bold;')
        self._stats['avg_loss'].setText(f'{avg_loss:+.2f}%')
        self._stats['avg_loss'].setStyleSheet('color:#0044bb;font-weight:bold;')
        self._stats['pf'].setText(f'{pf:.2f}')
        self._stats['pf'].setStyleSheet(f'color:{"#cc0000" if pf>=1 else "#0044bb"};font-weight:bold;')
        self._stats['total_pnl'].setText(f'{total_pnl:+,}원')
        self._stats['total_pnl'].setStyleSheet(f'color:{pnl_c};font-weight:bold;')
        self._stats['avg_days'].setText(f'{avg_days:.1f}일')
        self._stats['avg_days'].setStyleSheet('color:#111;font-weight:bold;')
        self._stats['best'].setText(f'{best:+.2f}%')
        self._stats['best'].setStyleSheet(f'color:{best_c};font-weight:bold;')
        self._stats['worst'].setText(f'{worst:+.2f}%')
        self._stats['worst'].setStyleSheet(f'color:{worst_c};font-weight:bold;')
        self._stats['a_wr'].setText(f'{a_wr:.1f}%')
        self._stats['a_wr'].setStyleSheet(f'color:{"#cc0000" if a_wr>=50 else "#0044bb"};font-weight:bold;')
