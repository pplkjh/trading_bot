"""Tab 0 — 대시보드: KPI 카드 + 매수 중지 토글"""
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QGroupBox,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from control_panel import db

TODAY = datetime.now().strftime('%Y%m%d')


def _kpi_card(label: str, value: str = '—', sub: str = '') -> QFrame:
    card = QFrame()
    card.setFrameShape(QFrame.StyledPanel)
    card.setStyleSheet("""
        QFrame {
            border: 1px solid #d0d0d0;
            border-radius: 6px;
            background: #fafafa;
            padding: 4px;
        }
    """)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(10, 8, 10, 8)
    lay.setSpacing(2)

    lbl = QLabel(label)
    lbl.setFont(QFont('Malgun Gothic', 8))
    lbl.setStyleSheet('color: #888;')

    val = QLabel(value)
    val.setFont(QFont('Malgun Gothic', 14, QFont.Bold))
    val.setObjectName('kpi_value')

    lay.addWidget(lbl)
    lay.addWidget(val)

    if sub:
        s = QLabel(sub)
        s.setFont(QFont('Malgun Gothic', 8))
        s.setStyleSheet('color: #555;')
        lay.addWidget(s)

    return card


class DashboardTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(12)

        # ── KPI 그리드 ────────────────────────────────────────────
        grid = QGridLayout()
        grid.setSpacing(10)

        self._cards = {}
        kpi_defs = [
            ('total_asset', '추정 총자산',     '',   0, 0),
            ('total_ret',   '총 수익률',        '',   0, 1),
            ('today_pnl',   '오늘 손익',        '',   0, 2),
            ('unrealized',  '미실현 손익',      '',   0, 3),
            ('open_count',  '보유 종목',        '',   1, 0),
            ('win_rate',    '승률',             '',   1, 1),
            ('pf',          '손익비 (R)',       '',   1, 2),
            ('cand_count',  '매수 후보',        '',   1, 3),
        ]
        for key, label, sub, row, col in kpi_defs:
            card = _kpi_card(label, '—', sub)
            self._cards[key] = card.findChild(QLabel, 'kpi_value')
            grid.addWidget(card, row, col)

        root.addLayout(grid)

        # ── 트레이더 상태 + 매수 중지 토글 ───────────────────────
        ctrl_box = QGroupBox('트레이더 제어')
        ctrl_box.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
        ctrl_lay = QHBoxLayout(ctrl_box)

        self._status_lbl = QLabel('상태: —')
        self._status_lbl.setFont(QFont('Malgun Gothic', 10, QFont.Bold))

        self._toggle_btn = QPushButton('매수 중지')
        self._toggle_btn.setFixedWidth(130)
        self._toggle_btn.setFixedHeight(34)
        self._toggle_btn.setFont(QFont('Malgun Gothic', 10, QFont.Bold))
        self._toggle_btn.clicked.connect(self._toggle_buy_stop)

        ctrl_lay.addWidget(self._status_lbl)
        ctrl_lay.addStretch()
        ctrl_lay.addWidget(self._toggle_btn)

        root.addWidget(ctrl_box)

        # ── 자산 구성 상세 ────────────────────────────────────────
        detail_box = QGroupBox('자산 구성 상세')
        detail_box.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
        detail_lay = QGridLayout(detail_box)
        detail_lay.setSpacing(6)

        self._detail_labels = {}
        detail_items = [
            ('initial',    '초기 자금'),
            ('realized',   '실현 손익 누계'),
            ('unrealized2','미실현 손익 합계'),
            ('invest_unit','종목당 투자금'),
            ('total_trades','총 거래 수'),
            ('win_loss',   '승 / 패'),
            ('avg_win',    '평균 익절률'),
            ('avg_loss',   '평균 손절률'),
        ]
        for i, (k, label) in enumerate(detail_items):
            row, col = divmod(i, 2)
            lbl = QLabel(f'{label}:')
            lbl.setFont(QFont('Malgun Gothic', 9))
            lbl.setStyleSheet('color: #555;')
            val = QLabel('—')
            val.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._detail_labels[k] = val
            detail_lay.addWidget(lbl, row, col * 2)
            detail_lay.addWidget(val, row, col * 2 + 1)

        root.addWidget(detail_box)
        root.addStretch()

        self._buy_stop_val = '0'

    def refresh(self, kpis: dict):
        ic = 50_000_000  # initial_capital

        def fmt_won(v):
            if v is None: return '—'
            v = int(v)
            color = '#cc0000' if v >= 0 else '#0044bb'
            return f'<span style="color:{color}">{v:+,}원</span>'

        def fmt_pct(v):
            if v is None: return '—'
            color = '#cc0000' if float(v) >= 0 else '#0044bb'
            return f'<span style="color:{color}">{float(v):+.2f}%</span>'

        self._cards['total_asset'].setText(f"{kpis['total_asset']:,}원")
        self._cards['total_ret'].setText(fmt_pct(kpis['total_ret']))
        self._cards['total_ret'].setTextFormat(Qt.RichText)
        self._cards['today_pnl'].setText(fmt_won(kpis['today_pnl']))
        self._cards['today_pnl'].setTextFormat(Qt.RichText)
        self._cards['unrealized'].setText(fmt_won(kpis['unrealized']))
        self._cards['unrealized'].setTextFormat(Qt.RichText)
        self._cards['open_count'].setText(f"{kpis['open_count']}종목")
        self._cards['win_rate'].setText(f"{kpis['win_rate']:.1f}%")
        self._cards['pf'].setText(f"{kpis['pf']:.2f}")
        self._cards['cand_count'].setText(f"{kpis['cand_count']}건")

        # 트레이더 상태
        self._buy_stop_val = kpis.get('buy_stop_val', '0')
        is_stopped = self._buy_stop_val == datetime.now().strftime('%Y%m%d')
        self._status_lbl.setText(
            f"상태: {'⛔ 매수 중지' if is_stopped else '🟢 정상 운영'}")
        self._toggle_btn.setText('매수 재개' if is_stopped else '매수 중지')
        self._toggle_btn.setStyleSheet(
            'background:#0044bb;color:white;border-radius:4px;' if is_stopped
            else 'background:#cc0000;color:white;border-radius:4px;')

        # 상세
        self._detail_labels['initial'].setText(f'{ic:,}원')
        self._detail_labels['realized'].setText(
            f'<span style="color:{"#cc0000" if kpis["realized"]>=0 else "#0044bb"}">'
            f'{kpis["realized"]:+,}원</span>')
        self._detail_labels['realized'].setTextFormat(Qt.RichText)
        self._detail_labels['unrealized2'].setText(
            f'<span style="color:{"#cc0000" if kpis["unrealized"]>=0 else "#0044bb"}">'
            f'{kpis["unrealized"]:+,}원</span>')
        self._detail_labels['unrealized2'].setTextFormat(Qt.RichText)
        self._detail_labels['invest_unit'].setText(
            f'{kpis["invest_unit"]:,}원')
        self._detail_labels['total_trades'].setText(f'{kpis["total_trades"]}건')
        self._detail_labels['win_loss'].setText(
            f'{kpis["win_n"]}승 / {kpis["loss_n"]}패')
        self._detail_labels['avg_win'].setText(
            f'{kpis["avg_win"]:+.2f}%' if kpis["avg_win"] else '—')
        self._detail_labels['avg_loss'].setText(
            f'{kpis["avg_loss"]:+.2f}%' if kpis["avg_loss"] else '—')

    def _toggle_buy_stop(self):
        is_stopped = self._buy_stop_val == datetime.now().strftime('%Y%m%d')
        db.set_buy_stop(not is_stopped)
