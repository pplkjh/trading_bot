"""Tab — 즉시 주문: 수동 매수/매도 폼 + 전체 청산 + 주문 내역"""
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QSpinBox,
    QPushButton, QGroupBox, QMessageBox, QFrame, QSizePolicy, QSplitter,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

from control_panel.widgets.colored_table import ColoredTable, RED, BLUE, GRAY
from control_panel.widgets.price_chart import PriceChart
from control_panel import db

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from library.cf import invest_unit as cf_invest_unit

ORDER_HEADERS = ['시각', '유형', '종목코드', '종목명', '수량', '상태', '체결시각', '메모']


# ── 기술적 지표 계산 헬퍼 ─────────────────────────────────────────
def _rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains  = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]
    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        ag = (ag * (period - 1) + gains[i]) / period
        al = (al * (period - 1) + losses[i]) / period
    return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)

def _vol_ratio(volumes, short=5, long=20):
    if len(volumes) < long:
        return None
    v5  = sum(volumes[-short:]) / short
    v20 = sum(volumes[-long:])  / long
    return v5 / v20 if v20 > 0 else None

def _atr_rate(highs, lows, closes, period=14):
    if len(closes) < period + 1:
        return None
    trs = [max(highs[i] - lows[i],
               abs(highs[i] - closes[i-1]),
               abs(lows[i]  - closes[i-1]))
           for i in range(1, len(closes))]
    atr = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
    return atr / closes[-1] if closes[-1] > 0 else None

def _bb(closes, period=20, k=2.0):
    """(bb_position, bb_bandwidth) 반환. 데이터 부족 시 (None, None)."""
    if len(closes) < period:
        return None, None
    w    = closes[-period:]
    mean = sum(w) / period
    std  = (sum((x - mean) ** 2 for x in w) / period) ** 0.5
    upper, lower = mean + k * std, mean - k * std
    bw   = (upper - lower) / mean if mean > 0 else None
    pos  = (closes[-1] - lower) / (upper - lower) if (upper - lower) > 0 else None
    return pos, bw

STATUS_COLOR = {
    'PENDING':   QColor('#e07b00'),
    'EXECUTED':  QColor('#006600'),
    'FAILED':    QColor('#cc0000'),
    'CANCELLED': QColor('#888888'),
}


# ── 수평 정보 스트립 ──────────────────────────────────────────────────
class _InfoStrip(QFrame):
    """
    항목들을 가로로 나열한 정보 표시 바.
    각 항목: 위=레이블(작은 회색), 아래=값(굵은 검정), 세로 구분선으로 분리.
    """
    def __init__(self, items: list, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            'QFrame{border:1px solid #ddd;border-radius:4px;background:#fafafa;}')
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._vals = {}
        for i, (key, label) in enumerate(items):
            if i > 0:
                vline = QFrame()
                vline.setFrameShape(QFrame.VLine)
                vline.setStyleSheet('color:#e0e0e0;max-width:1px;')
                lay.addWidget(vline)

            cell = QWidget()
            cell.setStyleSheet('background:transparent;')
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(10, 5, 10, 5)
            cl.setSpacing(1)

            lbl = QLabel(label)
            lbl.setFont(QFont('Malgun Gothic', 8))
            lbl.setStyleSheet('color:#555;border:none;background:transparent;')
            lbl.setAlignment(Qt.AlignCenter)

            val = QLabel('—')
            val.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
            val.setStyleSheet('color:#111;border:none;background:transparent;')
            val.setAlignment(Qt.AlignCenter)
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)

            cl.addWidget(lbl)
            cl.addWidget(val)
            lay.addWidget(cell, stretch=1)
            self._vals[key] = val

    def set(self, key: str, text: str, color: str = '#111111'):
        if key in self._vals:
            self._vals[key].setText(text)
            self._vals[key].setStyleSheet(
                f'color:{color};font-weight:bold;border:none;background:transparent;')

    def reset(self):
        for v in self._vals.values():
            v.setText('—')
            v.setStyleSheet('color:#111;font-weight:bold;border:none;background:transparent;')


class _MultiRowInfo:
    """여러 _InfoStrip을 묶어 key 기준으로 set()/reset()을 위임하는 래퍼."""
    def __init__(self, *strips):
        self._strips = strips
        self._map = {}
        for s in strips:
            for k in s._vals:
                self._map[k] = s

    def set(self, key: str, text: str, color: str = '#111111'):
        s = self._map.get(key)
        if s:
            s.set(key, text, color)

    def reset(self):
        for s in self._strips:
            s.reset()


class OrdersTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._positions   = []
        self._buy_price   = 0
        self._chart_owner = 'sell'   # 'buy'=매수 조회 후 / 'sell'=매도 콤보 선택 후
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # ── 포트폴리오 요약 바 ────────────────────────────────────────
        self._summary = _InfoStrip([
            ('count',      '보유 종목'),
            ('unrealized', '미실현 손익'),
            ('today_pnl',  '오늘 손익'),
            ('win_rate',   '누적 승률'),
        ])
        self._summary.setFixedHeight(52)
        root.addWidget(self._summary)

        # ── 수평 스플리터 ─────────────────────────────────────────────
        h_split = QSplitter(Qt.Horizontal)
        h_split.setChildrenCollapsible(False)

        # ── 왼쪽: 매수 → 매도 (세로 스택) + 청산 바 ─────────────────
        left_w = QWidget()
        left_w.setMaximumWidth(340)
        left_lay = QVBoxLayout(left_w)
        left_lay.setContentsMargins(0, 0, 4, 0)
        left_lay.setSpacing(6)
        left_lay.addWidget(self._make_buy_box(), stretch=1)
        left_lay.addWidget(self._make_sell_box(), stretch=1)
        left_lay.addWidget(self._make_liq_strip())
        h_split.addWidget(left_w)

        # ── 오른쪽: 차트 + 주문 내역 ─────────────────────────────────
        right_w = QWidget()
        right_lay = QVBoxLayout(right_w)
        right_lay.setContentsMargins(4, 0, 0, 0)
        right_lay.setSpacing(6)

        self._chart = PriceChart()
        right_lay.addWidget(self._chart, stretch=3)

        hdr_row = QHBoxLayout()
        lbl = QLabel('수동 주문 내역')
        lbl.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
        hdr_row.addWidget(lbl)
        hdr_row.addStretch()

        reset_btn = QPushButton('내역 리셋')
        reset_btn.setFixedWidth(80)
        reset_btn.setFixedHeight(26)
        reset_btn.setStyleSheet('color:#cc0000;font-weight:bold;')
        reset_btn.clicked.connect(self._reset_orders)
        hdr_row.addWidget(reset_btn)

        refresh_btn = QPushButton('새로고침')
        refresh_btn.setFixedWidth(80)
        refresh_btn.setFixedHeight(26)
        refresh_btn.clicked.connect(self._reload_orders)
        hdr_row.addWidget(refresh_btn)

        right_lay.addLayout(hdr_row)

        self._order_table = ColoredTable(ORDER_HEADERS, self)
        right_lay.addWidget(self._order_table, stretch=2)

        h_split.addWidget(right_w)
        h_split.setStretchFactor(0, 35)
        h_split.setStretchFactor(1, 65)
        root.addWidget(h_split, stretch=1)

    # ── 요약 바 갱신 ─────────────────────────────────────────────────
    def _update_summary(self, kpis: dict):
        cnt  = kpis.get('open_count', 0)
        unr  = kpis.get('unrealized', 0)
        tpnl = kpis.get('today_pnl', 0)
        wr   = kpis.get('win_rate', 0)
        self._summary.set('count',      f'{cnt}종목')
        self._summary.set('unrealized', f'{unr:+,}원',
                          '#cc0000' if unr >= 0 else '#0044bb')
        self._summary.set('today_pnl',  f'{tpnl:+,}원',
                          '#cc0000' if tpnl >= 0 else '#0044bb')
        self._summary.set('win_rate',   f'{wr:.1f}%',
                          '#cc0000' if wr >= 50 else '#0044bb')

    # ── 매수 폼 ──────────────────────────────────────────────────────
    def _make_buy_box(self) -> QGroupBox:
        box = QGroupBox('즉시 매수 (시장가)')
        box.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
        lay = QVBoxLayout(box)
        lay.setSpacing(6)

        # 입력 폼 — 1행: 종목코드 + 종목명 + 조회버튼
        row1 = QHBoxLayout()
        row1.setSpacing(6)

        row1.addWidget(QLabel('종목코드'))
        self._buy_code = QLineEdit()
        self._buy_code.setPlaceholderText('005930')
        self._buy_code.setMaxLength(6)
        self._buy_code.setFixedWidth(72)
        self._buy_code.editingFinished.connect(self._lookup_name_only)
        row1.addWidget(self._buy_code)

        self._buy_name_lbl = QLabel('—')
        self._buy_name_lbl.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
        self._buy_name_lbl.setMinimumWidth(60)
        row1.addWidget(self._buy_name_lbl, stretch=1)

        lookup_btn = QPushButton('종목 조회')
        lookup_btn.setFixedWidth(72)
        lookup_btn.setFixedHeight(26)
        lookup_btn.setStyleSheet('background:#0044bb;color:white;border-radius:3px;font-weight:bold;')
        lookup_btn.clicked.connect(self._lookup_full)
        row1.addWidget(lookup_btn)

        lay.addLayout(row1)

        # 입력 폼 — 2행: 수량 + 전략
        row2 = QHBoxLayout()
        row2.setSpacing(6)

        row2.addWidget(QLabel('수량'))
        self._buy_qty = QSpinBox()
        self._buy_qty.setRange(1, 99999)
        self._buy_qty.setValue(max(1, cf_invest_unit // 10000))
        self._buy_qty.setFixedWidth(76)
        self._buy_qty.valueChanged.connect(self._update_est)
        row2.addWidget(self._buy_qty)

        row2.addSpacing(8)
        row2.addWidget(QLabel('전략'))
        self._buy_strat = QComboBox()
        self._buy_strat.addItems(['A', 'B'])
        self._buy_strat.setFixedWidth(50)
        row2.addWidget(self._buy_strat)
        row2.addStretch()

        lay.addLayout(row2)

        # 종목 정보 — 2행 스트립
        _buy_r1 = _InfoStrip([
            ('price', '현재가'),
            ('rsi',   'RSI(14)'),
            ('vol',   '거래량비율'),
        ])
        _buy_r1.setFixedHeight(44)
        _buy_r2 = _InfoStrip([
            ('atr',   'ATR비율'),
            ('bbpos', 'BB위치'),
            ('cond',  '조건'),
            ('est',   '예상금액'),
        ])
        _buy_r2.setFixedHeight(44)
        self._buy_info = _MultiRowInfo(_buy_r1, _buy_r2)
        lay.addWidget(_buy_r1)
        lay.addWidget(_buy_r2)

        buy_btn = QPushButton('▶  매수 실행')
        buy_btn.setFixedHeight(34)
        buy_btn.setStyleSheet(
            'background:#cc0000;color:white;font-weight:bold;border-radius:4px;font-size:10pt;')
        buy_btn.clicked.connect(self._do_buy)
        lay.addWidget(buy_btn)
        return box

    def _lookup_name_only(self):
        code = self._buy_code.text().strip()
        if not code:
            return
        name = db.lookup_code_name(code)
        self._buy_name_lbl.setText(name or '—')
        self._buy_info.reset()
        self._buy_price = 0

    def _lookup_full(self):
        """조회 버튼 클릭 시 — daily_craw에서 OHLCV를 가져와 지표를 직접 계산."""
        code = self._buy_code.text().strip()
        if not code:
            QMessageBox.warning(self, '입력 오류', '종목코드를 입력하세요.')
            return

        name = db.lookup_code_name(code)
        self._buy_name_lbl.setText(name or '—')
        self._buy_info.reset()
        self._buy_price = 0

        if not name or name == '—':
            QMessageBox.warning(self, '조회 오류', '종목코드를 찾을 수 없습니다.')
            return

        # OHLCV 가격 이력 (90일)
        try:
            hist = db.get_price_history(name, days=90)
        except Exception:
            hist = []

        if not hist:
            self._buy_info.set('price', '데이터 없음', '#888')
            return

        closes  = [float(r.get('close')  or 0) for r in hist]
        highs   = [float(r.get('high')   or 0) for r in hist]
        lows    = [float(r.get('low')    or 0) for r in hist]
        volumes = [float(r.get('volume') or 0) for r in hist]

        price = closes[-1] if closes else 0
        self._buy_price = int(price)

        # 지표 계산
        rsi_val      = _rsi(closes)
        vol_r        = _vol_ratio(volumes)
        atr_r        = _atr_rate(highs, lows, closes)
        bb_pos, bb_bw = _bb(closes)

        # 현재가 + 전일 대비
        prev = closes[-2] if len(closes) >= 2 else price
        pct  = (price - prev) / prev * 100 if prev > 0 else 0
        price_c = '#cc0000' if pct >= 0 else '#0044bb'

        # RSI: <40 빨강(과매도), >70 파랑(과매수)
        rsi_c = ('#cc0000' if rsi_val is not None and rsi_val < 40
                 else '#0044bb' if rsi_val is not None and rsi_val > 70
                 else '#111')

        # 거래량비율: >1.5 빨강(브레이크아웃 신호)
        vol_c = '#cc0000' if vol_r is not None and vol_r > 1.5 else '#111'

        # ATR비율: >2% 빨강
        atr_c = '#cc0000' if atr_r is not None and atr_r > 0.02 else '#111'

        # BB위치: <0.3 빨강(저점), >0.7 파랑(고점)
        bb_c = ('#cc0000' if bb_pos is not None and bb_pos < 0.3
                else '#0044bb' if bb_pos is not None and bb_pos > 0.7
                else '#111')

        # 전략 조건 요약 (Strategy A 필수 3가지 / Strategy B 주요 2가지)
        a_req = sum([
            vol_r  is not None and vol_r  > 1.5,
            atr_r  is not None and atr_r  > 0.02,
            bb_bw  is not None and bb_bw  > 0.05,
        ])
        b_met = sum([
            bb_pos is not None and bb_pos < 0.3,
            rsi_val is not None and rsi_val < 40,
        ])

        if a_req == 3:
            cond_txt, cond_c = 'A 필수 3/3 ✓', '#cc0000'
        elif a_req == 2:
            cond_txt, cond_c = f'A 필수 2/3', '#e07b00'
        elif b_met == 2:
            cond_txt, cond_c = 'B 조건 2/2 ✓', '#cc0000'
        elif b_met == 1:
            cond_txt, cond_c = f'B 조건 1/2', '#e07b00'
        else:
            cond_txt, cond_c = f'미달 (A{a_req}/3)', '#888'

        self._buy_info.set('price', f'{int(price):,}  {pct:+.1f}%', price_c)
        self._buy_info.set('rsi',   f'{rsi_val:.1f}'  if rsi_val is not None else '—', rsi_c)
        self._buy_info.set('vol',   f'{vol_r:.2f}x'   if vol_r   is not None else '—', vol_c)
        self._buy_info.set('atr',   f'{atr_r*100:.1f}%' if atr_r is not None else '—', atr_c)
        self._buy_info.set('bbpos', f'{bb_pos:.2f}'   if bb_pos  is not None else '—', bb_c)
        self._buy_info.set('cond',  cond_txt, cond_c)

        # 차트 갱신 — 매수 조회가 차트 주도권을 가짐
        self._chart_owner = 'buy'
        self._chart.plot(rows=hist, title=name)

        self._update_est()

    def _update_est(self):
        qty = self._buy_qty.value()
        if self._buy_price > 0:
            self._buy_info.set('est', f'{self._buy_price * qty:,}원')

    # ── 매도 폼 ──────────────────────────────────────────────────────
    def _make_sell_box(self) -> QGroupBox:
        box = QGroupBox('즉시 매도 (시장가)')
        box.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
        lay = QVBoxLayout(box)
        lay.setSpacing(6)

        # 입력 폼 — 1행: 보유 종목 드롭다운
        row1 = QHBoxLayout()
        row1.setSpacing(6)

        row1.addWidget(QLabel('보유 종목'))
        self._sell_combo = QComboBox()
        self._sell_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # 사용자가 직접 콤보를 바꿀 때만 차트 주도권을 sell로 전환
        self._sell_combo.currentIndexChanged.connect(self._on_sell_combo_user_changed)
        row1.addWidget(self._sell_combo, stretch=1)

        lay.addLayout(row1)

        # 입력 폼 — 2행: 구분 + 수량
        row2 = QHBoxLayout()
        row2.setSpacing(6)

        row2.addWidget(QLabel('구분'))
        self._sell_type = QComboBox()
        self._sell_type.addItems(['전량매도', '부분매도'])
        self._sell_type.setFixedWidth(78)
        self._sell_type.currentTextChanged.connect(
            lambda t: self._sell_qty.setEnabled(t == '부분매도'))
        row2.addWidget(self._sell_type)

        self._sell_qty = QSpinBox()
        self._sell_qty.setRange(1, 99999)
        self._sell_qty.setFixedWidth(72)
        self._sell_qty.setEnabled(False)
        row2.addWidget(self._sell_qty)
        row2.addStretch()

        lay.addLayout(row2)

        # 포지션 정보 — 2행 스트립
        _sell_r1 = _InfoStrip([
            ('price', '현재가'),
            ('entry', '매수가'),
            ('rate',  '수익률'),
            ('pnl',   '미실현손익'),
        ])
        _sell_r1.setFixedHeight(44)
        _sell_r2 = _InfoStrip([
            ('days',    '보유일'),
            ('highest', '최고가'),
            ('tstop',   '트레일링스톱'),
            ('strat',   '전략'),
        ])
        _sell_r2.setFixedHeight(44)
        self._sell_info = _MultiRowInfo(_sell_r1, _sell_r2)
        lay.addWidget(_sell_r1)
        lay.addWidget(_sell_r2)

        sell_btn = QPushButton('▶  매도 실행')
        sell_btn.setFixedHeight(34)
        sell_btn.setStyleSheet(
            'background:#0044bb;color:white;font-weight:bold;border-radius:4px;font-size:10pt;')
        sell_btn.clicked.connect(self._do_sell)
        lay.addWidget(sell_btn)
        return box

    def _on_sell_combo_user_changed(self, _idx=None):
        """사용자가 직접 콤보를 바꿨을 때 — 차트 주도권을 sell로 전환 후 갱신."""
        self._chart_owner = 'sell'
        self._on_sell_select()

    def _on_sell_select(self):
        """매도 콤보 info strip 갱신 + 차트 (_chart_owner=='sell' 일 때만)."""
        p = self._sell_combo.currentData()
        if not p:
            self._sell_info.reset()
            return

        qty     = int(p.get('holding_amount', 1))
        self._sell_qty.setMaximum(qty)
        self._sell_qty.setValue(qty)

        price   = int(p.get('present_price') or 0)
        entry   = int(p.get('purchase_price') or 0)
        rate    = (price - entry) / entry * 100 if entry else 0
        pnl     = int(p.get('valuation_profit') or 0)
        strat   = str(p.get('strategy_type') or '—')
        highest = int(p.get('highest_price') or price)

        buy_date = str(p.get('buy_date', '') or '')
        try:
            days = (datetime.now() - datetime.strptime(buy_date[:8], '%Y%m%d')).days
        except Exception:
            days = 0

        tstop = max(highest * (0.97 if strat == 'A' else 0.95), entry * 1.01)
        pc    = '#cc0000' if rate >= 0 else '#0044bb'
        tc    = '#e07b00' if price <= tstop * 1.02 else '#111111'

        self._sell_info.set('price',   f'{price:,}원')
        self._sell_info.set('entry',   f'{entry:,}원')
        self._sell_info.set('rate',    f'{rate:+.2f}%', pc)
        self._sell_info.set('pnl',     f'{pnl:+,}원',   pc)
        self._sell_info.set('days',    f'{days}일')
        self._sell_info.set('highest', f'{highest:,}원')
        self._sell_info.set('tstop',   f'{int(tstop):,}원', tc)
        self._sell_info.set('strat',   strat)

        # 차트: 매수 조회 중(_chart_owner=='buy')이면 건드리지 않음
        if self._chart_owner != 'sell':
            return

        name = p.get('code_name', '')
        if name:
            ohlcv = db.get_price_history(name, days=90)
            if ohlcv:
                buy_d = ''.join(c for c in str(p.get('buy_date', '')) if c.isdigit())[:8]
                self._chart.plot(
                    rows=ohlcv, title=name,
                    entry_price=entry, trailing_stop=int(tstop),
                    buy_date=buy_d, strategy=strat,
                )
            else:
                self._chart._show_placeholder(f'{name} — 데이터 없음')

    # ── 긴급 청산 바 (콤팩트) ────────────────────────────────────────
    def _make_liq_strip(self) -> QFrame:
        strip = QFrame()
        strip.setFrameShape(QFrame.StyledPanel)
        strip.setStyleSheet(
            'QFrame{border:1px solid #e0b0b0;border-radius:4px;background:#fff5f5;}')
        strip.setFixedHeight(36)
        lay = QHBoxLayout(strip)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(10)

        self._liq_count_lbl = QLabel('보유: 0종목')
        self._liq_count_lbl.setFont(QFont('Malgun Gothic', 8, QFont.Bold))
        lay.addWidget(self._liq_count_lbl)

        warn = QLabel('전체 시장가 일괄 매도')
        warn.setFont(QFont('Malgun Gothic', 8))
        warn.setStyleSheet('color:#cc0000;')
        lay.addWidget(warn)
        lay.addStretch()

        liq_btn = QPushButton('⚠ 전체 청산')
        liq_btn.setFixedHeight(24)
        liq_btn.setFixedWidth(100)
        liq_btn.setStyleSheet(
            'background:#660000;color:white;font-weight:bold;font-size:9px;border-radius:3px;')
        liq_btn.clicked.connect(self._do_liquidate)
        lay.addWidget(liq_btn)
        return strip

    # ── 포지션 드롭다운 갱신 ─────────────────────────────────────────
    def update_positions(self, positions: list):
        self._positions = positions
        cur_code = ''
        cur_data = self._sell_combo.currentData()
        if cur_data:
            cur_code = cur_data.get('code', '')

        self._sell_combo.blockSignals(True)
        self._sell_combo.clear()
        for p in positions:
            rate  = float(p.get('rate') or 0)
            sign  = '▲' if rate >= 0 else '▼'
            label = (f"{p.get('code_name','')}  [{p.get('strategy_type','?')}]  "
                     f"{int(p.get('holding_amount',0))}주  {sign}{abs(rate):.1f}%")
            self._sell_combo.addItem(label, userData=p)
        # 이전 선택 복원도 blockSignals 안에서 → currentIndexChanged 미발동
        if cur_code:
            for i in range(self._sell_combo.count()):
                d = self._sell_combo.itemData(i)
                if d and d.get('code') == cur_code:
                    self._sell_combo.setCurrentIndex(i)
                    break
        self._sell_combo.blockSignals(False)

        # info strip만 갱신 (차트는 _chart_owner 가 'sell'일 때만 갱신)
        self._on_sell_select()

        self._liq_count_lbl.setText(f'보유: {len(positions)}종목')

    def refresh(self, kpis=None):
        if kpis:
            self._update_summary(kpis)
        self._reload_orders()

    def _reload_orders(self):
        orders = db.get_manual_orders(100)
        rows = []
        for o in orders:
            st    = str(o.get('status', ''))
            color = STATUS_COLOR.get(st, QColor('#111111'))
            rows.append([
                str(o.get('created_at', ''))[:16],
                str(o.get('order_type', '')),
                str(o.get('code', '')),
                str(o.get('code_name', '')),
                str(o.get('quantity', '')),
                (st, color),
                str(o.get('executed_at', '') or ''),
                str(o.get('result_msg', '') or ''),
            ])
        self._order_table.set_rows(rows)

    def _reset_orders(self):
        reply = QMessageBox.question(
            self, '내역 리셋',
            'PENDING 상태를 제외한 완료/실패/취소 주문 내역을 삭제합니다.\n계속하시겠습니까?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            db.reset_manual_orders()
            self._reload_orders()

    # ── 액션 ─────────────────────────────────────────────────────────
    def _do_buy(self):
        code = self._buy_code.text().strip()
        name = self._buy_name_lbl.text()
        qty  = self._buy_qty.value()
        strat = self._buy_strat.currentText()
        if not code or len(code) != 6:
            QMessageBox.warning(self, '입력 오류', '6자리 종목코드를 입력하세요.')
            return
        if name in ('—', ''):
            name = code
        est = f'\n예상금액: {self._buy_price * qty:,}원' if self._buy_price > 0 else ''
        reply = QMessageBox.question(
            self, '매수 확인',
            f'[{name}]  {qty}주  시장가 매수하겠습니까?\n전략: {strat}{est}',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            db.insert_manual_order('BUY', code, name, qty)
            QMessageBox.information(self, '주문 접수', f'{name} 매수 주문 접수 완료.')
            self._reload_orders()

    def _do_sell(self):
        p = self._sell_combo.currentData()
        if not p:
            QMessageBox.warning(self, '선택 오류', '매도할 종목을 선택하세요.')
            return
        code    = p.get('code', '')
        name    = p.get('code_name', '')
        max_qty = int(p.get('holding_amount', 0))
        is_part = self._sell_type.currentText() == '부분매도'
        qty     = self._sell_qty.value() if is_part else max_qty
        otype   = 'PART_SELL' if (is_part and qty < max_qty) else 'SELL'
        rate    = float(p.get('rate') or 0)
        pnl     = int(p.get('valuation_profit') or 0)
        reply = QMessageBox.question(
            self, '매도 확인',
            f'[{name}]  {qty}주  시장가 매도하겠습니까?\n'
            f'수익률: {rate:+.2f}%  /  미실현손익: {pnl:+,}원',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            db.insert_manual_order(otype, code, name, qty)
            QMessageBox.information(self, '주문 접수', f'{name} 매도 주문 접수 완료.')
            self._reload_orders()

    def _do_liquidate(self):
        if not self._positions:
            QMessageBox.information(self, '알림', '보유 종목이 없습니다.')
            return
        total_pnl = sum(int(p.get('valuation_profit') or 0) for p in self._positions)
        reply = QMessageBox.warning(
            self, '⚠ 전체 청산 확인',
            f'보유 종목 {len(self._positions)}건을 전부 시장가 매도합니다.\n'
            f'예상 미실현손익 합계: {total_pnl:+,}원\n\n'
            '이 작업은 되돌릴 수 없습니다. 계속하시겠습니까?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        if QMessageBox.warning(
            self, '⚠ 최종 확인', '정말로 전체 청산하시겠습니까?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) != QMessageBox.Yes:
            return
        for p in self._positions:
            db.insert_manual_order('SELL', p.get('code', ''), p.get('code_name', ''),
                                   int(p.get('holding_amount', 0)))
        QMessageBox.information(self, '주문 접수',
            f'{len(self._positions)}건 전체 청산 주문이 접수되었습니다.')
        self._reload_orders()
