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

HEADERS_SELL = ['종목명', '종목코드', '매도시간', '전략', '매수점수', '매수일',
                '매수가', '매도가', '수익률%', '실현손익', '보유일', '매도사유']
HEADERS_HOLD = ['종목명', '종목코드', '전략', '매수점수', '매수가', '현재가',
                '수익률%', '미실현손익', '보유일']


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
    l.setFont(QFont('Malgun Gothic', 8))
    l.setStyleSheet('color:#555;border:none;')
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
        self._current_date     = datetime.now().strftime('%Y%m%d')
        self._last_loaded_date = None   # 날짜 변경 감지용
        self._sold_sorted      = []     # 현재 sell 테이블 행과 1:1 대응
        self._selected_trade   = None   # 우측 차트에 표시 중인 거래 정보
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

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

        # ── KPI 1행: 기본 지표 ───────────────────────────────────────
        kpi1 = QHBoxLayout()
        kpi1.setSpacing(6)
        self._kpis = {}
        for key, label in [
            ('sell_cnt',  '당일 매도'),
            ('buy_cnt',   '당일 매수'),
            ('daily_pnl', '당일 실현손익'),
            ('win_rate',  '승률'),
            ('best',      '최대 익절'),
            ('worst',     '최대 손절'),
        ]:
            frame, val = _kpi_card(label)
            self._kpis[key] = val
            kpi1.addWidget(frame)
        root.addLayout(kpi1)

        # ── KPI 2행: 평균/분석 지표 ─────────────────────────────────
        kpi2 = QHBoxLayout()
        kpi2.setSpacing(6)
        for key, label in [
            ('avg_win',  '평균 익절'),
            ('avg_loss', '평균 손절'),
            ('pf',       '손익비 R'),
            ('a_pnl',    'A전략 손익'),
            ('b_pnl',    'B전략 손익'),
        ]:
            frame, val = _kpi_card(label)
            self._kpis[key] = val
            kpi2.addWidget(frame)
        root.addLayout(kpi2)

        # ── 스플리터: 위=테이블들 / 아래=차트 ────────────────────────
        v_split = QSplitter(Qt.Vertical)

        # 상단 — 매도 + 매수(보유중) 테이블
        tables_widget = QWidget()
        tlay = QVBoxLayout(tables_widget)
        tlay.setContentsMargins(0, 0, 0, 0)
        tlay.setSpacing(4)

        sell_lbl = QLabel('● 당일 매도 종목  (클릭하면 우측 차트에서 매매 구간 확인)')
        sell_lbl.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
        sell_lbl.setStyleSheet('color:#cc0000;')
        tlay.addWidget(sell_lbl)

        self._sell_table = ColoredTable(HEADERS_SELL, tables_widget)
        self._sell_table.setMaximumHeight(190)
        self._sell_table.setSortingEnabled(False)   # _sold_sorted 인덱스와 동기화 유지
        self._sell_table.itemClicked.connect(self._on_sell_item_clicked)   # 사용자 클릭만 반응
        tlay.addWidget(self._sell_table)

        hold_lbl = QLabel('● 당일 매수 (보유중)')
        hold_lbl.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
        hold_lbl.setStyleSheet('color:#0044bb;')
        tlay.addWidget(hold_lbl)

        self._hold_table = ColoredTable(HEADERS_HOLD, tables_widget)
        self._hold_table.setMaximumHeight(160)
        tlay.addWidget(self._hold_table)

        v_split.addWidget(tables_widget)

        # 하단 — 누적 P&L 차트(좌) + 종목 매매 차트(우)
        chart_widget = QWidget()
        chart_lay = QHBoxLayout(chart_widget)
        chart_lay.setContentsMargins(0, 0, 0, 0)
        chart_lay.setSpacing(4)

        h_split = QSplitter(Qt.Horizontal)
        h_split.setChildrenCollapsible(False)

        # 좌: 당일 누적 P&L
        self._fig = Figure(figsize=(5, 2), facecolor='#f8f8f8')
        self._ax  = self._fig.add_axes([0.10, 0.22, 0.87, 0.65], facecolor='#f8f8f8')
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._canvas.setMinimumHeight(130)
        h_split.addWidget(self._canvas)

        # 우: 클릭된 종목 가격 차트 (매수·매도 시점 표시)
        self._fig2 = Figure(figsize=(5, 2), facecolor='#f8f8f8')
        self._ax2  = self._fig2.add_axes([0.10, 0.22, 0.87, 0.65], facecolor='#f8f8f8')
        self._canvas2 = FigureCanvasQTAgg(self._fig2)
        self._canvas2.setMinimumHeight(130)
        h_split.addWidget(self._canvas2)

        h_split.setStretchFactor(0, 50)
        h_split.setStretchFactor(1, 50)
        chart_lay.addWidget(h_split)

        v_split.addWidget(chart_widget)
        v_split.setStretchFactor(0, 3)
        v_split.setStretchFactor(1, 2)
        root.addWidget(v_split)

        # 초기 우측 차트 안내 문구
        self._stock_chart_placeholder()

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

        # 날짜가 바뀌었으면 우측 차트 선택 초기화
        if d != self._last_loaded_date:
            self._selected_trade = None
        self._last_loaded_date = d

        trades = db.get_daily_trades(d)
        sold  = [t for t in trades if t.get('action_type') == '매도']
        held  = [t for t in trades if t.get('action_type') == '매수']

        self._render_sold(sold)   # 내부에서 선택 행 복원 처리
        self._render_held(held)
        self._update_kpis(sold, held)
        self._draw_pnl_chart(sold)

        # 우측 차트: 선택된 종목 유지, 없으면 placeholder
        if self._selected_trade:
            t = self._selected_trade
            self._draw_stock_chart(
                str(t.get('code_name', '')),
                _d8(t.get('buy_date', '')),
                _d8(t.get('sell_date', '')),
                int(t.get('purchase_price') or 0),
                int(t.get('sell_price') or 0),
                int(t.get('realized_profit') or 0),
            )
        else:
            self._stock_chart_placeholder()

        self._date_lbl.setText(f'매도 {len(sold)}건 | 매수 {len(held)}건')

    def _render_sold(self, sold: list):
        self._sold_sorted = sorted(sold, key=lambda x: str(x.get('sell_date', '')), reverse=True)
        rows = []
        for t in self._sold_sorted:
            rate  = float(t.get('sell_rate') or 0)
            pnl   = int(t.get('realized_profit') or 0)
            days  = _hold_days(t.get('buy_date', ''), t.get('sell_date', ''))
            score = int(t.get('composite_score') or 0)
            col   = RED if rate >= 0 else BLUE
            tm     = _fmt_time(t.get('sell_date', ''))
            buy_d  = _d8(t.get('buy_date', ''))
            buy_fmt = f"{buy_d[4:6]}/{buy_d[6:8]}" if len(buy_d) == 8 else '—'
            rows.append([
                str(t.get('code_name', '')),
                (str(t.get('code', '')), GRAY),
                (tm, GRAY),
                str(t.get('strategy_type', '')),
                (str(score) if score else '—', None),
                (buy_fmt, None),
                (f"{int(t.get('purchase_price', 0)):,}", None),
                (f"{int(t.get('sell_price', 0)):,}", None),
                (f"{rate:+.2f}%", col),
                (f"{pnl:+,}원", col),
                (f"{days}일", None),
                str(t.get('exit_reason', '') or ''),
            ])
        # itemClicked만 연결했으므로 selectRow()는 차트 재렌더를 유발하지 않음
        self._sell_table.set_rows(rows)
        # 이전에 선택된 종목 행 복원
        if self._selected_trade:
            sel_code = str(self._selected_trade.get('code', ''))
            sel_sell = _d8(self._selected_trade.get('sell_date', ''))
            restored = False
            for i, t in enumerate(self._sold_sorted):
                if str(t.get('code', '')) == sel_code and _d8(t.get('sell_date', '')) == sel_sell:
                    self._sell_table.selectRow(i)
                    restored = True
                    break
            if not restored:
                self._selected_trade = None

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
                (str(t.get('code', '')), GRAY),
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
        rates = [float(t.get('sell_rate') or 0) for t in sold]
        wins  = [r for r in rates if r > 0]
        losses = [r for r in rates if r <= 0]
        wr     = len(wins) / n * 100 if n else 0
        dpnl   = sum(int(t.get('realized_profit') or 0) for t in sold)
        best   = max(rates) if rates else 0
        worst  = min(rates) if rates else 0
        avg_win  = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        pf = abs(avg_win / avg_loss) if avg_loss else 0

        a_pnl = sum(int(t.get('realized_profit') or 0)
                    for t in sold if str(t.get('strategy_type', '')) == 'A')
        b_pnl = sum(int(t.get('realized_profit') or 0)
                    for t in sold if str(t.get('strategy_type', '')) == 'B')

        pc  = '#cc0000' if dpnl >= 0 else '#0044bb'
        wc  = '#cc0000' if wr >= 50 else '#0044bb'
        apc = '#cc0000' if a_pnl >= 0 else '#0044bb'
        bpc = '#cc0000' if b_pnl >= 0 else '#0044bb'

        def _set(key, text, color='#111'):
            self._kpis[key].setText(text)
            self._kpis[key].setStyleSheet(
                f'color:{color};font-weight:bold;border:none;')

        _set('sell_cnt',  f'{n}건')
        _set('buy_cnt',   f'{len(held)}건')
        _set('daily_pnl', f'{dpnl:+,}원', pc)
        _set('win_rate',  f'{wr:.1f}%', wc)
        _set('best',      f'{best:+.2f}%' if rates else '—', '#cc0000')
        _set('worst',     f'{worst:+.2f}%' if rates else '—', '#0044bb')
        _set('avg_win',   f'{avg_win:+.2f}%' if wins else '—', '#cc0000')
        _set('avg_loss',  f'{avg_loss:+.2f}%' if losses else '—', '#0044bb')
        _set('pf',        f'{pf:.2f}' if pf else '—',
             '#008800' if pf >= 1 else '#cc0000')
        _set('a_pnl',     f'{a_pnl:+,}원' if a_pnl else '—', apc)
        _set('b_pnl',     f'{b_pnl:+,}원' if b_pnl else '—', bpc)

    # ── 좌측 차트: 당일 누적 P&L 흐름 ───────────────────────────────
    def _draw_pnl_chart(self, sold: list):
        ax = self._ax
        ax.clear()
        ax.set_facecolor('#f8f8f8')

        if not sold:
            ax.text(0.5, 0.5, '당일 매도 거래 없음', ha='center', va='center',
                    transform=ax.transAxes, fontsize=10, color='#aaa')
            self._canvas.draw()
            return

        ordered = sorted(sold, key=lambda t: str(t.get('sell_date', '')))
        cumul   = []
        running = 0
        labels  = []
        for t in ordered:
            running += int(t.get('realized_profit') or 0)
            cumul.append(running / 10_000)
            tm = _fmt_time(t.get('sell_date', ''))
            labels.append(tm or str(t.get('code_name', ''))[:4])

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
        for x, y, lbl in zip(xs, cumul, labels):
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

    # ── 우측 차트: 클릭 종목 매매 구간 ──────────────────────────────
    def _stock_chart_placeholder(self):
        ax = self._ax2
        ax.clear()
        ax.set_facecolor('#f8f8f8')
        ax.text(0.5, 0.5, '매도 종목을 클릭하면\n매수·매도 시점을 표시합니다',
                ha='center', va='center', transform=ax.transAxes,
                fontsize=10, color='#aaa', linespacing=1.8)
        ax.set_xticks([])
        ax.set_yticks([])
        self._fig2.tight_layout(pad=0.5)
        self._canvas2.draw()

    def _on_sell_item_clicked(self, item):
        """사용자가 매도 테이블 셀을 직접 클릭할 때만 발동 (selectRow() 프로그램 복원은 제외)."""
        row = item.row()
        if row < 0 or row >= len(self._sold_sorted):
            return
        t = self._sold_sorted[row]
        self._selected_trade = t   # refresh 시 복원용으로 저장
        name       = str(t.get('code_name', ''))
        buy_d8     = _d8(t.get('buy_date', ''))
        sell_d8    = _d8(t.get('sell_date', ''))
        entry      = int(t.get('purchase_price') or 0)
        sell_price = int(t.get('sell_price') or 0)
        pnl        = int(t.get('realized_profit') or 0)
        if name:
            self._draw_stock_chart(name, buy_d8, sell_d8, entry, sell_price, pnl)

    def _draw_stock_chart(self, name, buy_d8, sell_d8, entry, sell_price, pnl):
        ax = self._ax2
        ax.clear()
        ax.set_facecolor('#f8f8f8')

        # 최대 2달(60 거래일) 기간 표시
        try:
            rows = db.get_price_history(name, days=60)
        except Exception:
            rows = []

        if not rows:
            ax.text(0.5, 0.5, f'{name}\n데이터 없음', ha='center', va='center',
                    transform=ax.transAxes, fontsize=10, color='#aaa')
            self._canvas2.draw()
            return

        raw_dates = [_d8(str(r.get('date', ''))) for r in rows]
        closes    = [float(r.get('close') or 0) for r in rows]
        xs        = list(range(len(raw_dates)))

        ax.plot(xs, closes, color='#444', linewidth=1.3, zorder=2)

        buy_idx  = None
        sell_idx = None
        for i, d in enumerate(raw_dates):
            if d == buy_d8:
                buy_idx = i
            if d == sell_d8:
                sell_idx = i

        # 매수 시점 마커
        if buy_idx is not None:
            ax.axvline(buy_idx, color='#0044bb', linewidth=1.2,
                       linestyle='--', alpha=0.6)
            ax.scatter([buy_idx], [closes[buy_idx]], color='#0044bb',
                       s=70, zorder=5, marker='^')
            ax.annotate(f'매수\n{entry:,}', xy=(buy_idx, closes[buy_idx]),
                        fontsize=6.5, color='#0044bb',
                        xytext=(0, 10), textcoords='offset points',
                        ha='center', va='bottom')

        # 매도 시점 마커
        if sell_idx is not None:
            ax.axvline(sell_idx, color='#cc0000', linewidth=1.2,
                       linestyle='--', alpha=0.6)
            ax.scatter([sell_idx], [closes[sell_idx]], color='#cc0000',
                       s=70, zorder=5, marker='v')
            ax.annotate(f'매도\n{sell_price:,}', xy=(sell_idx, closes[sell_idx]),
                        fontsize=6.5, color='#cc0000',
                        xytext=(0, -22), textcoords='offset points',
                        ha='center', va='top')

        # 보유 구간 음영
        if buy_idx is not None and sell_idx is not None and buy_idx < sell_idx:
            shade = '#cc0000' if pnl >= 0 else '#0044bb'
            ax.axvspan(buy_idx, sell_idx, alpha=0.07, color=shade)

        # 매수가 수평 기준선
        if entry:
            ax.axhline(entry, color='#0044bb', linewidth=0.8,
                       linestyle=':', alpha=0.5)

        # x축 날짜 레이블
        n = len(raw_dates)
        step = max(1, n // 6)
        tick_xs = list(range(0, n, step))
        ax.set_xticks(tick_xs)
        ax.set_xticklabels(
            [raw_dates[i][4:6] + '/' + raw_dates[i][6:8]
             for i in tick_xs if i < n],
            fontsize=6)
        ax.set_xlim(-1, n)
        ax.yaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))
        ax.tick_params(axis='y', labelsize=7)
        ax.grid(axis='y', color='#e0e0e0', linewidth=0.5)

        pnl_str = f'  ({pnl:+,}원)' if pnl else ''
        ax.set_title(f'{name}{pnl_str}', fontsize=9, pad=3)
        self._fig2.tight_layout(pad=0.5)
        self._canvas2.draw()
