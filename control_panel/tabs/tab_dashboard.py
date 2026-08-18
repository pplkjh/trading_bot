"""Tab 0 — 대시보드: KPI 카드 + 누적 수익률 차트"""
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QSizePolicy,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

import matplotlib
try:
    matplotlib.use('Qt5Agg')
except Exception:
    pass
matplotlib.rcParams['font.family'] = ['Malgun Gothic', 'sans-serif']
import matplotlib.ticker
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg

from control_panel import db

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
try:
    from library.cf import initial_capital as INITIAL_CAPITAL
except Exception:
    INITIAL_CAPITAL = 50_000_000


def _card(label, big=False) -> tuple:
    """통일 KPI 카드. (QFrame, value_QLabel) 반환."""
    card = QFrame()
    card.setFrameShape(QFrame.StyledPanel)
    card.setStyleSheet('QFrame{border:1px solid #ddd;border-radius:5px;background:#fff;}')
    lay = QVBoxLayout(card)
    lay.setContentsMargins(10, 6, 10, 6)
    lay.setSpacing(1)

    lbl = QLabel(label)
    lbl.setFont(QFont('Malgun Gothic', 8))
    lbl.setStyleSheet('color:#555;border:none;')

    val = QLabel('—')
    val.setFont(QFont('Malgun Gothic', 13 if big else 10, QFont.Bold))
    val.setStyleSheet('color:#111;border:none;')
    val.setTextInteractionFlags(Qt.TextSelectableByMouse)

    lay.addWidget(lbl)
    lay.addWidget(val)
    return card, val


class DashboardTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._buy_stop_val = '0'
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(8)

        # ── 상단: 주요 KPI 4개 ───────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(8)
        self._big = {}
        for key, label in [
            ('total_asset', '추정 총자산'),
            ('total_ret',   '총 수익률'),
            ('today_pnl',   '오늘 손익'),
            ('unrealized',  '미실현 손익'),
        ]:
            card, val = _card(label, big=True)
            self._big[key] = val
            top.addWidget(card)
        root.addLayout(top)

        # ── 중단: 보조 KPI 2행 × 4열 ────────────────────────────────
        grid = QGridLayout()
        grid.setSpacing(6)
        self._sub = {}
        sub_defs = [
            # (key, label, row, col)
            ('open_count',   '보유 종목',   0, 0),
            ('win_rate',     '누적 승률',   0, 1),
            ('pf',           '손익비 R',    0, 2),
            ('cand_count',   '매수 후보',   0, 3),
            ('total_trades', '총 거래',     1, 0),
            ('win_loss',     '승 / 패',     1, 1),
            ('avg_win',      '평균 익절',   1, 2),
            ('avg_loss',     '평균 손절',   1, 3),
        ]
        for key, label, r, c in sub_defs:
            card, val = _card(label)
            self._sub[key] = val
            grid.addWidget(card, r, c)
        root.addLayout(grid)

        # ── 자산 상세 인라인 바 ──────────────────────────────────────
        det_bar = QFrame()
        det_bar.setStyleSheet(
            'QFrame{border:1px solid #e8e8e8;border-radius:4px;background:#fafafa;}')
        det_bar.setFixedHeight(34)
        det_lay = QHBoxLayout(det_bar)
        det_lay.setContentsMargins(14, 0, 14, 0)
        det_lay.setSpacing(0)

        self._det = {}
        det_items = [
            ('initial',     '초기 자금'),
            ('deposit',     '예수금 (D+2)'),
            ('total_val',   '총평가금액'),
            ('realized',    '실현 누계'),
            ('unrealized2', '미실현'),
            ('invest_unit', '종목당 투자금'),
        ]
        for i, (k, label) in enumerate(det_items):
            if i > 0:
                sep = QLabel(' │ ')
                sep.setStyleSheet('color:#ccc;border:none;')
                det_lay.addWidget(sep)
            lbl = QLabel(label + ' ')
            lbl.setFont(QFont('Malgun Gothic', 8))
            lbl.setStyleSheet('color:#999;border:none;')
            val = QLabel('—')
            val.setFont(QFont('Malgun Gothic', 8, QFont.Bold))
            val.setStyleSheet('color:#333;border:none;')
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self._det[k] = val
            det_lay.addWidget(lbl)
            det_lay.addWidget(val)
        det_lay.addStretch()
        root.addWidget(det_bar)

        # ── 트레이더 제어 바 ─────────────────────────────────────────
        ctrl = QFrame()
        ctrl.setStyleSheet(
            'QFrame{border:1px solid #ddd;border-radius:4px;background:#f0f4f8;}')
        ctrl.setFixedHeight(40)
        ctrl_lay = QHBoxLayout(ctrl)
        ctrl_lay.setContentsMargins(12, 0, 12, 0)
        ctrl_lay.setSpacing(16)

        self._status_lbl = QLabel('—')
        self._status_lbl.setFont(QFont('Malgun Gothic', 10, QFont.Bold))
        self._status_lbl.setStyleSheet('border:none;')

        self._invest_lbl = QLabel()
        self._invest_lbl.setFont(QFont('Malgun Gothic', 8))
        self._invest_lbl.setStyleSheet('color:#666;border:none;')

        self._toggle_btn = QPushButton('매수 중지')
        self._toggle_btn.setFixedWidth(110)
        self._toggle_btn.setFixedHeight(28)
        self._toggle_btn.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
        self._toggle_btn.clicked.connect(self._toggle_buy_stop)

        ctrl_lay.addWidget(self._status_lbl)
        ctrl_lay.addWidget(self._invest_lbl)
        ctrl_lay.addStretch()
        ctrl_lay.addWidget(self._toggle_btn)
        root.addWidget(ctrl)

        # ── 누적 P&L 차트 ────────────────────────────────────────────
        self._fig = Figure(figsize=(8, 2.2), facecolor='#f8f8f8')
        self._ax  = self._fig.add_axes([0.06, 0.18, 0.91, 0.72], facecolor='#f8f8f8')
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._canvas.setMinimumHeight(150)
        root.addWidget(self._canvas, stretch=1)

    def _draw_pnl_chart(self):
        history = db.get_pnl_history()
        if not history:
            return
        dates  = [h[0] for h in history]
        daily  = [h[1] for h in history]
        cumul  = []
        running = 0
        for d in daily:
            running += d
            cumul.append(running / 1_000_000)

        xs = list(range(len(dates)))
        ax = self._ax
        ax.clear()
        ax.set_facecolor('#f8f8f8')
        ax.axhline(0, color='#cccccc', linewidth=0.8)
        ax.fill_between(xs, 0, cumul,
                        where=[v >= 0 for v in cumul],
                        alpha=0.15, color='#cc0000', interpolate=True)
        ax.fill_between(xs, 0, cumul,
                        where=[v < 0 for v in cumul],
                        alpha=0.15, color='#0044bb', interpolate=True)

        last_val   = cumul[-1]
        line_color = '#cc0000' if last_val >= 0 else '#0044bb'
        ax.plot(xs, cumul, color=line_color, linewidth=1.5, zorder=3)
        ax.annotate(f'{last_val:+,.1f}M',
                    xy=(xs[-1], last_val),
                    xytext=(xs[-1] - 0.5, last_val),
                    fontsize=8, color=line_color, va='center', ha='right')

        n = len(dates)
        step = max(1, n // 6)
        ax.set_xticks(xs[::step])
        ax.set_xticklabels([f"{d[4:6]}/{d[6:8]}" for d in dates[::step]], fontsize=7)
        ax.set_xlim(-0.5, n - 0.5)
        ax.yaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:+,.0f}M'))
        ax.tick_params(axis='y', labelsize=7)
        ax.set_title('누적 실현손익', fontsize=9, pad=3)
        ax.grid(axis='y', color='#e0e0e0', linewidth=0.5)
        self._fig.tight_layout(pad=0.5)
        self._canvas.draw()

    # ── 갱신 ─────────────────────────────────────────────────────────
    def refresh(self, kpis: dict):
        def _c(v):
            return '#cc0000' if float(v) >= 0 else '#0044bb'

        def _won(v, signed=True):
            v = int(v)
            s = f'{v:+,}원' if signed else f'{v:,}원'
            return f'<span style="color:{_c(v)}">{s}</span>'

        # 주요 4개
        self._big['total_asset'].setText(f"{kpis['total_asset']:,}원")

        ret   = kpis['total_ret']
        ret_c = '#cc0000' if ret >= 0 else '#0044bb'
        self._big['total_ret'].setText(f'{ret:+.2f}%')
        self._big['total_ret'].setStyleSheet(f'color:{ret_c};font-weight:bold;border:none;')

        self._big['today_pnl'].setText(_won(kpis['today_pnl']))
        self._big['today_pnl'].setTextFormat(Qt.RichText)
        self._big['unrealized'].setText(_won(kpis['unrealized']))
        self._big['unrealized'].setTextFormat(Qt.RichText)

        # 보조
        self._sub['open_count'].setText(f"{kpis['open_count']}종목")
        wr = kpis['win_rate']
        self._sub['win_rate'].setText(f'{wr:.1f}%')
        self._sub['win_rate'].setStyleSheet(
            f'color:{"#cc0000" if wr>=50 else "#0044bb"};font-weight:bold;border:none;')
        pf = kpis['pf']
        self._sub['pf'].setText(f'{pf:.2f}')
        self._sub['pf'].setStyleSheet(
            f'color:{"#008800" if pf>=1 else "#cc0000"};font-weight:bold;border:none;')
        self._sub['cand_count'].setText(f"{kpis['cand_count']}건")
        self._sub['total_trades'].setText(f"{kpis['total_trades']}건")
        self._sub['win_loss'].setText(f"{kpis['win_n']}승 / {kpis['loss_n']}패")
        self._sub['avg_win'].setText(f"{kpis['avg_win']:+.2f}%" if kpis['avg_win'] else '—')
        self._sub['avg_loss'].setText(f"{kpis['avg_loss']:+.2f}%" if kpis['avg_loss'] else '—')

        # 자산 상세 바
        dep   = kpis.get('d2_deposit', 0)
        tval  = kpis.get('total_value', 0)
        dep_c = '#0044bb' if dep == 0 else '#111'
        self._det['initial'].setText(f'{INITIAL_CAPITAL:,}원')
        self._det['deposit'].setText(f'{dep:,}원')
        self._det['deposit'].setStyleSheet(f'color:{dep_c};font-weight:bold;border:none;')
        self._det['total_val'].setText(f'{tval:,}원')
        self._det['realized'].setText(_won(kpis['realized']))
        self._det['realized'].setTextFormat(Qt.RichText)
        self._det['unrealized2'].setText(_won(kpis['unrealized']))
        self._det['unrealized2'].setTextFormat(Qt.RichText)
        self._det['invest_unit'].setText(f"{kpis.get('invest_unit', 0):,}원")

        # 트레이더 제어
        self._buy_stop_val = kpis.get('buy_stop_val', '0')
        is_stopped = self._buy_stop_val == datetime.now().strftime('%Y%m%d')
        self._status_lbl.setText('⛔ 매수 중지' if is_stopped else '● 정상 운영')
        self._status_lbl.setStyleSheet(
            f'color:{"#cc0000" if is_stopped else "#008800"};font-weight:bold;border:none;')
        self._invest_lbl.setText(f"종목당 투자금  {kpis.get('invest_unit', 0):,}원")
        self._toggle_btn.setText('매수 재개' if is_stopped else '매수 중지')
        self._toggle_btn.setStyleSheet(
            'background:#0044bb;color:white;border-radius:4px;font-weight:bold;' if is_stopped
            else 'background:#cc0000;color:white;border-radius:4px;font-weight:bold;')

        # 차트 (분 단위 갱신)
        now_min = datetime.now().strftime('%H%M')
        if not hasattr(self, '_last_chart_min') or self._last_chart_min != now_min:
            self._last_chart_min = now_min
            try:
                self._draw_pnl_chart()
            except Exception:
                pass

    def _toggle_buy_stop(self):
        is_stopped = self._buy_stop_val == datetime.now().strftime('%Y%m%d')
        db.set_buy_stop(not is_stopped)
