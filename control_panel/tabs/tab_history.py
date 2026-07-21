"""Tab 3 — 거래 내역: 날짜 필터 + 요약 통계"""
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QDateEdit, QPushButton, QSpinBox,
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont

from control_panel.widgets.colored_table import ColoredTable, RED, BLUE
from control_panel import db

HEADERS = ['매도일', '종목명', '전략', '매수가', '매도가',
           '수익률%', '실현손익', '보유일', '매도사유']


def _d8(s):
    digits = ''.join(c for c in str(s) if c.isdigit())
    return digits[:8] if len(digits) >= 8 else ''


def _fmt_date(s):
    d = _d8(s)
    return f'{d[:4]}.{d[4:6]}.{d[6:8]}' if len(d) == 8 else d


def _hold_days(buy, sell):
    try:
        return (datetime.strptime(_d8(sell), '%Y%m%d') -
                datetime.strptime(_d8(buy), '%Y%m%d')).days
    except Exception:
        return 0


class HistoryTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_data = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # 필터 바
        filter_lay = QHBoxLayout()
        filter_lay.setSpacing(8)

        today = QDate.currentDate()
        month_ago = today.addDays(-90)

        filter_lay.addWidget(QLabel('시작일:'))
        self._date_from = QDateEdit(month_ago)
        self._date_from.setCalendarPopup(True)
        self._date_from.setDisplayFormat('yyyy-MM-dd')
        filter_lay.addWidget(self._date_from)

        filter_lay.addWidget(QLabel('종료일:'))
        self._date_to = QDateEdit(today)
        self._date_to.setCalendarPopup(True)
        self._date_to.setDisplayFormat('yyyy-MM-dd')
        filter_lay.addWidget(self._date_to)

        filter_lay.addWidget(QLabel('전략:'))
        self._strat = QComboBox()
        self._strat.addItems(['전체', 'A', 'B'])
        self._strat.setFixedWidth(60)
        filter_lay.addWidget(self._strat)

        filter_lay.addWidget(QLabel('최대:'))
        self._limit = QSpinBox()
        self._limit.setRange(50, 5000)
        self._limit.setValue(200)
        self._limit.setSingleStep(50)
        self._limit.setFixedWidth(70)
        filter_lay.addWidget(self._limit)

        search_btn = QPushButton('조회')
        search_btn.setFixedWidth(60)
        search_btn.clicked.connect(self._search)
        filter_lay.addWidget(search_btn)
        filter_lay.addStretch()

        root.addLayout(filter_lay)

        # 요약 레이블
        self._summary = QLabel()
        self._summary.setFont(QFont('Malgun Gothic', 9))
        root.addWidget(self._summary)

        # 테이블
        self._table = ColoredTable(HEADERS, self)
        root.addWidget(self._table)

        # 초기 로드
        self._search()

    def refresh(self, _=None):
        pass  # 자동 갱신 없음 — 사용자가 조회 버튼으로 수동 갱신

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
        wins = 0
        for t in data:
            rate = float(t.get('sell_rate') or 0)
            pnl  = int(t.get('realized_profit') or 0)
            total_pnl += pnl
            if rate > 0:
                wins += 1
            color = RED if rate >= 0 else BLUE
            hold = _hold_days(t.get('buy_date', ''), t.get('sell_date', ''))
            rows.append([
                _fmt_date(t.get('sell_date', '')),
                str(t.get('code_name', '')),
                str(t.get('strategy_type', '')),
                (f"{int(t.get('purchase_price', 0)):,}", None),
                (f"{int(t.get('sell_price', 0)):,}", None),
                (f"{rate:+.2f}%", color),
                (f"{pnl:+,}원", color),
                (str(hold), None),
                str(t.get('exit_reason', '') or ''),
            ])
        self._table.set_rows(rows)

        n = len(data)
        wr = wins / n * 100 if n else 0
        pnl_color = '#cc0000' if total_pnl >= 0 else '#0044bb'
        self._summary.setText(
            f'{n}건  |  승률 {wr:.1f}%  |  '
            f'합계: <span style="color:{pnl_color}">{total_pnl:+,}원</span>')
        self._summary.setTextFormat(Qt.RichText)
