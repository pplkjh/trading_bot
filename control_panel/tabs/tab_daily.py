"""Tab 5 — 일별 현황: 날짜별 거래 내역 + 당일 손익 + 누적 변화"""
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QDateEdit, QPushButton, QFrame, QSplitter,
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont, QColor

import matplotlib
try:
    matplotlib.use('Qt5Agg')
except Exception:
    pass
matplotlib.rcParams['font.family'] = ['Malgun Gothic', 'sans-serif']
import matplotlib.ticker
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg

from control_panel.widgets.colored_table import ColoredTable, RED, BLUE, GRAY
from control_panel import db

HEADERS_SELL = ['종목명', '전략', '매수점수', '매수가', '매도가', '수익률%', '실현손익', '보유일', '매도사유']
HEADERS_HOLD = ['종목명', '전략', '매수점수', '매수가', '현재가', '수익률%', '미실현손익', '보유일']


def _d8(s):
    return ''.join(c for c in str(s) if c.isdigit())[:8]


def _fmt_time(s):
    digits = ''.join(c for c in str(s) if c.isdigit())
    if len(digits) >= 12:
        t = digits[8:14]
        return f'{t[:2]}:{t[2:4]}'
    return ''


def _hold_days(buy, sell=''):
    try:
        b = datetime.strptime(_d8(buy), '%Y%m%d')
        e = datetime.strptime(_d8(sell), '%Y%m%d') if sell and _d8(sell) else datetime.today()
        return max(0, (e - b).days)
    except Exception:
        return 0


def _kpi_card(label, value='—', color='#111') -> tuple:
    frame = QFrame()
    frame.setFrameShape(QFrame.StyledPanel)
    frame.setStyleSheet(
        'QFrame{border:1px solid #ddd;border-radius:4px;background:#fff;}')
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(10, 4, 10, 4)
    lay.setSpacing(1)
    l = QLabel(label)
    l.setFont(QFont('Malgun Gothic', 7))
    l.setStyleSheet('color:#888;border:none;')
    v = QLabel(value)
    v.setFont(QFont('Malgun Gothic', 11, QFont.Bold))
    v.setStyleSheet(f'color:{color};border:none;')
    v.setTextInteractionFlags(Qt.TextSelectableByMouse)
    lay.addWidget(l)
    lay.addWidget(v)
    return frame, v


class DailyTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_date = datetime.now().strftime('%Y%m%d')
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # ── 날짜 선택 바 ──────────────────────────────────────────────
        nav = QHBoxLayout()
        nav.setSpacing(6)

        prev_btn = QPushButton('◀')
        prev_btn.setFixedWidth(34)
        prev_btn.setFixedHeight(28)
        prev_btn.clicked.connect(self._prev_day)
        nav.addWidget(prev_btn)

        self._date_edit = QDateEdit(QDate.currentDate())
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat('yyyy년 MM월 dd일')
        self._date_edit.setFixedWidth(150)
        self._date_edit.setFixedHeight(28)
        self._date_edit.dateChanged.connect(self._on_date_changed)
        nav.addWidget(self._date_edit)

        next_btn = QPushButton('▶')
        next_btn.setFixedWidth(34)
        next_btn.setFixedHeight(28)
        next_btn.clicked.connect(self._next_day)
        nav.addWidget(next_btn)

        today_btn = QPushButton('오늘')
        today_btn.setFixedWidth(55)
        today_btn.setFixedHeight(28)
        today_btn.clicked.connect(self._go_today)
        nav.addWidget(today_btn)

        nav.addStretch()

        self._date_lbl = QLabel('')
        self._date_lbl.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
        self._date_lbl.setStyleSheet('color:#555;')
        nav.addWidget(self._date_lbl)

        root.addLayout(nav)

        # ── KPI 카드 바 ───────────────────────────────────────────────
        kpi_lay = QHBoxLayout()
        kpi_lay.setSpacing(8)
        self._kpis = {}
        for key, label in [
            ('sell_cnt',   '당일 매도'),
            ('buy_cnt',    '당일 매수'),
            ('daily_pnl',  '당일 실현손익'),
            ('win_rate',   '승률'),
            ('best',       '최대 익절'),
            ('worst',      '최대 손절'),
        ]:
            frame, val = _kpi_card(label)
            self._kpis[key] = val
            kpi_lay.addWidget(frame)
        root.addLayout(kpi_lay)

        # ── 스플리터: 위=테이블들 / 아래=당일 P&L 흐름 차트 ──────────
        splitter = QSplitter(Qt.Vertical)

        # 상단 — 매도 + 매수(보유중) 테이블
        tables_widget = QWidget()
        tlay = QVBoxLayout(tables_widget)
        tlay.setContentsMargins(0, 0, 0, 0)
        tlay.setSpacing(6)

        sell_lbl = QLabel('● 당일 매도 종목')
        sell_lbl.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
        sell_lbl.setStyleSheet('color:#cc0000;')
        tlay.addWidget(sell_lbl)

        self._sell_table = ColoredTable(HEADERS_SELL, tables_widget)
        self._sell_table.setMaximumHeight(200)
        tlay.addWidget(self._sell_table)

        hold_lbl = QLabel('● 당일 매수 (보유중)')
        hold_lbl.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
        hold_lbl.setStyleSheet('color:#0044bb;')
        tlay.addWidget(hold_lbl)

        self._hold_table = ColoredTable(HEADERS_HOLD, tables_widget)
        self._hold_table.setMaximumHeight(180)
        tlay.addWidget(self._hold_table)

        splitter.addWidget(tables_widget)

        # 하단 — 당일 누적 P&L 흐름 차트
        self._fig = Figure(figsize=(8, 2), facecolor='#f8f8f8')
        self._ax  = self._fig.add_axes([0.07, 0.22, 0.90, 0.65], facecolor='#f8f8f8')
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._canvas.setMinimumHeight(140)
        splitter.addWidget(self._canvas)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter)

    # ── 날짜 네비게이션 ───────────────────────────────────────────────
    def _on_date_changed(self, qdate: QDate):
        self._current_date = qdate.toString('yyyyMMdd')
        self._load()

    def _prev_day(self):
        self._date_edit.setDate(self._date_edit.date().addDays(-1))

    def _next_day(self):
        self._date_edit.setDate(self._date_edit.date().addDays(1))

    def _go_today(self):
        self._date_edit.setDate(QDate.currentDate())

    # ── 외부 refresh 호출 (탭 활성화 시) ────────────────────────────
    def refresh(self, _=None):
        self._load()

    # ── 데이터 로드 + 렌더 ───────────────────────────────────────────
    def _load(self):
        d = self._current_date
        trades = db.get_daily_trades(d)

        sold  = [t for t in trades if t.get('action_type') == '매도']
        held  = [t for t in trades if t.get('action_type') == '매수']

        self._render_sold(sold)
        self._render_held(held)
        self._update_kpis(sold, held)
        self._draw_chart(sold)

        dy = d[:4] + '년 ' + d[4:6] + '월 ' + d[6:8] + '일'
        self._date_lbl.setText(
            f'매도 {len(sold)}건 | 매수 {len(held)}건')

    def _render_sold(self, sold: list):
        rows = []
        for t in sorted(sold, key=lambda x: str(x.get('sell_date', '')), reverse=True):
            rate = float(t.get('sell_rate') or 0)
            pnl  = int(t.get('realized_profit') or 0)
            days = _hold_days(t.get('buy_date', ''), t.get('sell_date', ''))
            score= int(t.get('composite_score') or 0)
            col  = RED if rate >= 0 else BLUE
            tm   = _fmt_time(t.get('sell_date', ''))
            rows.append([
                str(t.get('code_name', '')) + (f' {tm}' if tm else ''),
                str(t.get('strategy_type', '')),
                (str(score) if score else '—', None),
                (f"{int(t.get('purchase_price', 0)):,}", None),
                (f"{int(t.get('sell_price', 0)):,}", None),
                (f"{rate:+.2f}%", col),
                (f"{pnl:+,}원", col),
                (f"{days}일", None),
                str(t.get('exit_reason', '') or ''),
            ])
        self._sell_table.set_rows(rows)

    def _render_held(self, held: list):
        rows = []
        for t in sorted(held, key=lambda x: str(x.get('buy_date', '')), reverse=True):
            entry  = int(t.get('purchase_price') or 0)
            price  = int(t.get('present_price') or entry)
            rate   = (price - entry) / entry * 100 if entry else 0
            pnl    = int(t.get('valuation_profit') or 0)
            days   = _hold_days(t.get('buy_date', ''))
            score  = int(t.get('composite_score') or 0)
            col    = RED if rate >= 0 else BLUE
            rows.append([
                str(t.get('code_name', '')),
                str(t.get('strategy_type', '')),
                (str(score) if score else '—', None),
                (f"{entry:,}", None),
                (f"{price:,}", None),
                (f"{rate:+.2f}%", col),
                (f"{pnl:+,}원", col),
                (f"{days}일", None),
            ])
        self._hold_table.set_rows(rows)

    def _update_kpis(self, sold, held):
        n     = len(sold)
        wins  = sum(1 for t in sold if float(t.get('sell_rate') or 0) > 0)
        wr    = wins / n * 100 if n else 0
        dpnl  = sum(int(t.get('realized_profit') or 0) for t in sold)
        rates = [float(t.get('sell_rate') or 0) for t in sold]
        best  = max(rates) if rates else 0
        worst = min(rates) if rates else 0
        pc    = '#cc0000' if dpnl >= 0 else '#0044bb'
        wc    = '#cc0000' if wr >= 50 else '#0044bb'

        self._kpis['sell_cnt'].setText(f'{n}건')
        self._kpis['buy_cnt'].setText(f'{len(held)}건')
        self._kpis['daily_pnl'].setText(f'{dpnl:+,}원')
        self._kpis['daily_pnl'].setStyleSheet(f'color:{pc};font-weight:bold;')
        self._kpis['win_rate'].setText(f'{wr:.1f}%')
        self._kpis['win_rate'].setStyleSheet(f'color:{wc};font-weight:bold;')
        self._kpis['best'].setText(f'{best:+.2f}%' if rates else '—')
        self._kpis['best'].setStyleSheet('color:#cc0000;font-weight:bold;')
        self._kpis['worst'].setText(f'{worst:+.2f}%' if rates else '—')
        self._kpis['worst'].setStyleSheet('color:#0044bb;font-weight:bold;')

    def _draw_chart(self, sold: list):
        ax = self._ax
        ax.clear()
        ax.set_facecolor('#f8f8f8')

        if not sold:
            ax.text(0.5, 0.5, '당일 매도 거래 없음', ha='center', va='center',
                    transform=ax.transAxes, fontsize=10, color='#aaa')
            self._canvas.draw()
            return

        # 매도 시간순 정렬 → 누적 P&L
        ordered = sorted(sold, key=lambda t: str(t.get('sell_date', '')))
        cumul = []
        running = 0
        labels = []
        for t in ordered:
            running += int(t.get('realized_profit') or 0)
            cumul.append(running / 10_000)   # 단위: 만원
            tm = _fmt_time(t.get('sell_date', ''))
            labels.append(tm or t.get('code_name', '')[:4])

        xs = list(range(len(cumul)))
        ax.axhline(0, color='#cccccc', linewidth=0.8)
        ax.fill_between(xs, 0, cumul,
                        where=[v >= 0 for v in cumul],
                        alpha=0.15, color='#cc0000', interpolate=True)
        ax.fill_between(xs, 0, cumul,
                        where=[v < 0 for v in cumul],
                        alpha=0.15, color='#0044bb', interpolate=True)
        lc = '#cc0000' if cumul[-1] >= 0 else '#0044bb'
        ax.plot(xs, cumul, color=lc, linewidth=1.5, marker='o',
                markersize=4, zorder=3)

        # 종목명 레이블
        for i, (x, y, lbl) in enumerate(zip(xs, cumul, labels)):
            ax.annotate(lbl, xy=(x, y), fontsize=6, color='#555',
                        xytext=(0, 6), textcoords='offset points',
                        ha='center', va='bottom')

        ax.yaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:+,.0f}만'))
        ax.tick_params(axis='y', labelsize=7)
        ax.set_xticks([])
        ax.set_title(f'당일 누적 실현손익  (최종: {cumul[-1]:+,.0f}만원)', fontsize=9, pad=3)
        ax.grid(axis='y', color='#e0e0e0', linewidth=0.5)
        self._fig.tight_layout(pad=0.5)
        self._canvas.draw()
