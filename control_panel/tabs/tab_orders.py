"""Tab 4 — 즉시 주문: 수동 매수/매도 폼 + 전체 청산 + 주문 내역"""
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QSpinBox,
    QPushButton, QGroupBox, QMessageBox, QFrame, QSizePolicy,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

from control_panel.widgets.colored_table import ColoredTable, RED, BLUE, GRAY
from control_panel import db

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from library.cf import invest_unit as cf_invest_unit

ORDER_HEADERS = ['시각', '유형', '종목코드', '종목명', '수량', '상태', '체결시각', '메모']

STATUS_COLOR = {
    'PENDING':   QColor('#e07b00'),
    'EXECUTED':  QColor('#006600'),
    'FAILED':    QColor('#cc0000'),
    'CANCELLED': QColor('#888888'),
}


def _info_row(label: str, value: str = '—', color: str = '') -> tuple:
    """(라벨 QLabel, 값 QLabel) 쌍 반환."""
    lbl = QLabel(label + ':')
    lbl.setFont(QFont('Malgun Gothic', 8))
    lbl.setStyleSheet('color:#666;')
    val = QLabel(value)
    val.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
    val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    val.setTextInteractionFlags(Qt.TextSelectableByMouse)
    val.setCursor(Qt.IBeamCursor)
    if color:
        val.setStyleSheet(f'color:{color};')
    return lbl, val


class _InfoCard(QFrame):
    """종목 정보 표시용 미니 카드."""
    def __init__(self, rows: list, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet('QFrame { border:1px solid #ccc; border-radius:4px; background:#f9f9f9; }')
        grid = QGridLayout(self)
        grid.setContentsMargins(8, 6, 8, 6)
        grid.setSpacing(4)
        self._vals = {}
        for i, (key, label) in enumerate(rows):
            r, c = divmod(i, 2)
            lbl, val = _info_row(label)
            grid.addWidget(lbl, r, c * 2)
            grid.addWidget(val, r, c * 2 + 1)
            self._vals[key] = val

    def set(self, key: str, text: str, color: str = '#111111'):
        if key in self._vals:
            self._vals[key].setText(text)
            self._vals[key].setStyleSheet(f'color:{color};font-weight:bold;')

    def reset(self):
        for v in self._vals.values():
            v.setText('—')
            v.setStyleSheet('color:#111111;font-weight:bold;')


class OrdersTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._positions = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # ── 포트폴리오 요약 바 ────────────────────────────────────────
        self._summary_bar = self._make_summary_bar()
        root.addWidget(self._summary_bar)

        # ── 상단: 매수 / 매도 / 청산 ─────────────────────────────────
        row_top = QHBoxLayout()
        row_top.setSpacing(10)
        row_top.addWidget(self._make_buy_box(), stretch=4)
        row_top.addWidget(self._make_sell_box(), stretch=5)
        row_top.addWidget(self._make_liq_box(), stretch=2)
        root.addLayout(row_top)

        # ── 주문 내역 테이블 ──────────────────────────────────────────
        hdr_row = QHBoxLayout()
        hdr = QLabel('수동 주문 내역')
        hdr.setFont(QFont('Malgun Gothic', 10, QFont.Bold))
        hdr_row.addWidget(hdr)
        hdr_row.addStretch()
        refresh_btn = QPushButton('새로고침')
        refresh_btn.setFixedWidth(80)
        refresh_btn.clicked.connect(self._reload_orders)
        hdr_row.addWidget(refresh_btn)
        root.addLayout(hdr_row)

        self._order_table = ColoredTable(ORDER_HEADERS, self)
        root.addWidget(self._order_table)

    # ── 포트폴리오 요약 바 ────────────────────────────────────────────
    def _make_summary_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFrameShape(QFrame.StyledPanel)
        bar.setStyleSheet('QFrame{border:1px solid #ccc;border-radius:4px;background:#eef2f7;}')
        bar.setFixedHeight(40)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(24)

        def _item(label):
            l = QLabel(label + ':')
            l.setFont(QFont('Malgun Gothic', 8))
            l.setStyleSheet('color:#666;')
            v = QLabel('—')
            v.setFont(QFont('Malgun Gothic', 10, QFont.Bold))
            v.setTextInteractionFlags(Qt.TextSelectableByMouse)
            return l, v

        self._sb = {}
        for key, label in [('count','보유'), ('unrealized','미실현손익'),
                            ('today_pnl','오늘손익'), ('win_rate','승률')]:
            lbl, val = _item(label)
            lay.addWidget(lbl)
            lay.addWidget(val)
            self._sb[key] = val
        lay.addStretch()
        return bar

    def _update_summary(self, kpis: dict):
        cnt = kpis.get('open_count', 0)
        unr = kpis.get('unrealized', 0)
        tpnl= kpis.get('today_pnl', 0)
        wr  = kpis.get('win_rate', 0)
        self._sb['count'].setText(f'{cnt}종목')
        self._sb['unrealized'].setText(f'{unr:+,}원')
        self._sb['unrealized'].setStyleSheet(f'color:{"#cc0000" if unr>=0 else "#0044bb"};font-weight:bold;')
        self._sb['today_pnl'].setText(f'{tpnl:+,}원')
        self._sb['today_pnl'].setStyleSheet(f'color:{"#cc0000" if tpnl>=0 else "#0044bb"};font-weight:bold;')
        self._sb['win_rate'].setText(f'{wr:.1f}%')

    # ── 매수 폼 ──────────────────────────────────────────────────────
    def _make_buy_box(self) -> QGroupBox:
        box = QGroupBox('즉시 매수 (시장가)')
        box.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
        lay = QVBoxLayout(box)
        lay.setSpacing(6)

        form = QGridLayout()
        form.setSpacing(5)

        form.addWidget(QLabel('종목코드:'), 0, 0)
        self._buy_code = QLineEdit()
        self._buy_code.setPlaceholderText('예: 005930')
        self._buy_code.setMaxLength(6)
        self._buy_code.setFixedWidth(80)
        self._buy_code.editingFinished.connect(self._lookup_buy_name)
        form.addWidget(self._buy_code, 0, 1)

        self._buy_name_lbl = QLabel('—')
        self._buy_name_lbl.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
        form.addWidget(self._buy_name_lbl, 0, 2)

        form.addWidget(QLabel('전략:'), 1, 0)
        self._buy_strat = QComboBox()
        self._buy_strat.addItems(['A', 'B'])
        self._buy_strat.setFixedWidth(55)
        form.addWidget(self._buy_strat, 1, 1)

        form.addWidget(QLabel('수량:'), 2, 0)
        self._buy_qty = QSpinBox()
        self._buy_qty.setRange(1, 99999)
        self._buy_qty.setValue(max(1, cf_invest_unit // 10000))
        self._buy_qty.setFixedWidth(80)
        self._buy_qty.valueChanged.connect(self._update_buy_est)
        form.addWidget(self._buy_qty, 2, 1)

        lay.addLayout(form)

        # 종목 정보 카드
        self._buy_info = _InfoCard([
            ('price',  '현재가'),   ('score',  '복합점수'),
            ('strat',  '전략'),     ('rsi',    'RSI'),
            ('vol',    '거래량비율'), ('est',   '예상금액'),
        ], self)
        lay.addWidget(self._buy_info)

        buy_btn = QPushButton('▶  매수 실행')
        buy_btn.setFixedHeight(34)
        buy_btn.setStyleSheet('background:#cc0000;color:white;font-weight:bold;border-radius:4px;font-size:10pt;')
        buy_btn.clicked.connect(self._do_buy)
        lay.addWidget(buy_btn)
        lay.addStretch()
        return box

    def _lookup_buy_name(self):
        code = self._buy_code.text().strip()
        if not code:
            return
        name = db.lookup_code_name(code)
        self._buy_name_lbl.setText(name or '종목 없음')
        self._buy_info.reset()

        # realtime_daily_buy_list에서 점수 정보 조회
        try:
            rows = db._fetch(
                "SELECT close, composite_score, strategy_type, rsi14, vol5, vol20 "
                "FROM realtime_daily_buy_list WHERE code=%s LIMIT 1", (code,))
            if rows:
                r = rows[0]
                price = int(r.get('close') or 0)
                score = int(r.get('composite_score') or 0)
                strat = str(r.get('strategy_type') or '—')
                rsi   = float(r.get('rsi14') or 0)
                v5    = float(r.get('vol5') or 0)
                v20   = float(r.get('vol20') or 1)
                vol_r = v5 / max(v20, 1)
                self._buy_price = price
                self._buy_info.set('price', f'{price:,}원')
                self._buy_info.set('score', str(score),
                                   '#cc0000' if score >= 120 else '#e07b00' if score >= 90 else '#888')
                self._buy_info.set('strat', strat)
                self._buy_info.set('rsi',   f'{rsi:.1f}')
                self._buy_info.set('vol',   f'{vol_r:.2f}x')
                self._update_buy_est()
            else:
                self._buy_price = 0
        except Exception:
            self._buy_price = 0

    def _update_buy_est(self):
        price = getattr(self, '_buy_price', 0)
        qty   = self._buy_qty.value()
        if price > 0:
            est = price * qty
            self._buy_info.set('est', f'{est:,}원')

    # ── 매도 폼 ──────────────────────────────────────────────────────
    def _make_sell_box(self) -> QGroupBox:
        box = QGroupBox('즉시 매도 (시장가)')
        box.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
        lay = QVBoxLayout(box)
        lay.setSpacing(6)

        form = QGridLayout()
        form.setSpacing(5)

        form.addWidget(QLabel('보유 종목:'), 0, 0)
        self._sell_combo = QComboBox()
        self._sell_combo.setMinimumWidth(200)
        self._sell_combo.currentIndexChanged.connect(self._on_sell_select)
        form.addWidget(self._sell_combo, 0, 1, 1, 2)

        form.addWidget(QLabel('매도 구분:'), 1, 0)
        self._sell_type = QComboBox()
        self._sell_type.addItems(['전량매도', '부분매도'])
        self._sell_type.currentTextChanged.connect(self._sell_type_changed)
        self._sell_type.setFixedWidth(90)
        form.addWidget(self._sell_type, 1, 1)

        self._sell_qty = QSpinBox()
        self._sell_qty.setRange(1, 99999)
        self._sell_qty.setFixedWidth(80)
        self._sell_qty.setEnabled(False)
        form.addWidget(self._sell_qty, 1, 2)

        lay.addLayout(form)

        # 포지션 정보 카드
        self._sell_info = _InfoCard([
            ('price',    '현재가'),    ('entry',   '매수가'),
            ('rate',     '수익률'),    ('pnl',     '미실현손익'),
            ('days',     '보유일'),    ('strat',   '전략'),
            ('highest',  '최고가'),    ('tstop',   '트레일링스톱'),
        ], self)
        lay.addWidget(self._sell_info)

        sell_btn = QPushButton('▶  매도 실행')
        sell_btn.setFixedHeight(34)
        sell_btn.setStyleSheet('background:#0044bb;color:white;font-weight:bold;border-radius:4px;font-size:10pt;')
        sell_btn.clicked.connect(self._do_sell)
        lay.addWidget(sell_btn)
        lay.addStretch()
        return box

    def _on_sell_select(self):
        p = self._sell_combo.currentData()
        if not p:
            self._sell_info.reset()
            return

        qty      = int(p.get('holding_amount', 1))
        self._sell_qty.setMaximum(qty)
        self._sell_qty.setValue(qty)

        price    = int(p.get('present_price') or 0)
        entry    = int(p.get('purchase_price') or 0)
        rate     = float(p.get('rate') or 0)
        pnl      = int(p.get('valuation_profit') or 0)
        strat    = str(p.get('strategy_type') or '—')
        highest  = int(p.get('highest_price') or price)

        # 보유일 계산
        buy_date = str(p.get('buy_date', '') or '')
        try:
            bd   = datetime.strptime(buy_date[:8], '%Y%m%d')
            days = (datetime.now() - bd).days
        except Exception:
            days = 0

        # 트레일링 스톱가
        if strat == 'A':
            tstop = max(highest * 0.97, entry * 1.01)
        else:
            tstop = max(highest * 0.95, entry * 1.01)

        profit_color = '#cc0000' if rate >= 0 else '#0044bb'
        self._sell_info.set('price',   f'{price:,}원')
        self._sell_info.set('entry',   f'{entry:,}원')
        self._sell_info.set('rate',    f'{rate:+.2f}%',   profit_color)
        self._sell_info.set('pnl',     f'{pnl:+,}원',     profit_color)
        self._sell_info.set('days',    f'{days}일')
        self._sell_info.set('strat',   strat)
        self._sell_info.set('highest', f'{highest:,}원')
        self._sell_info.set('tstop',   f'{int(tstop):,}원',
                            '#e07b00' if price <= tstop * 1.02 else '#111111')

    # ── 전체 청산 박스 ────────────────────────────────────────────────
    def _make_liq_box(self) -> QGroupBox:
        box = QGroupBox('긴급 전체 청산')
        box.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
        lay = QVBoxLayout(box)

        warn = QLabel('⚠️ 보유 종목 전체를\n시장가 일괄 매도')
        warn.setAlignment(Qt.AlignCenter)
        warn.setFont(QFont('Malgun Gothic', 9))
        warn.setStyleSheet('color:#cc0000;')
        lay.addWidget(warn)

        self._liq_count_lbl = QLabel('보유: 0종목')
        self._liq_count_lbl.setAlignment(Qt.AlignCenter)
        self._liq_count_lbl.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
        lay.addWidget(self._liq_count_lbl)

        liq_btn = QPushButton('⚠️ 전체 청산')
        liq_btn.setFixedHeight(42)
        liq_btn.setStyleSheet(
            'background:#660000;color:white;font-weight:bold;font-size:11px;border-radius:4px;')
        liq_btn.clicked.connect(self._do_liquidate)
        lay.addWidget(liq_btn)
        lay.addStretch()
        return box

    # ── 포지션 목록 갱신 (main에서 호출) ─────────────────────────────
    def update_positions(self, positions: list):
        self._positions = positions
        current_code = ''
        cur_data = self._sell_combo.currentData()
        if cur_data:
            current_code = cur_data.get('code', '')

        self._sell_combo.blockSignals(True)
        self._sell_combo.clear()
        for p in positions:
            rate = float(p.get('rate') or 0)
            sign = '▲' if rate >= 0 else '▼'
            label = (f"{p.get('code_name','')}  [{p.get('strategy_type','?')}]  "
                     f"{int(p.get('holding_amount',0))}주  "
                     f"{sign}{abs(rate):.1f}%")
            self._sell_combo.addItem(label, userData=p)

        # 기존 선택 종목 복원
        restored = False
        if current_code:
            for i in range(self._sell_combo.count()):
                d = self._sell_combo.itemData(i)
                if d and d.get('code') == current_code:
                    self._sell_combo.setCurrentIndex(i)
                    restored = True
                    break
        self._sell_combo.blockSignals(False)

        if not restored:
            self._on_sell_select()

        # 전체 청산 카운트
        self._liq_count_lbl.setText(f'보유: {len(positions)}종목')

    def refresh(self, kpis=None):
        if kpis:
            self._update_summary(kpis)
        self._reload_orders()

    def _reload_orders(self):
        orders = db.get_manual_orders(50)
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

    # ── 액션 ─────────────────────────────────────────────────────────
    def _sell_type_changed(self, text):
        self._sell_qty.setEnabled(text == '부분매도')

    def _do_buy(self):
        code = self._buy_code.text().strip()
        name = self._buy_name_lbl.text()
        qty  = self._buy_qty.value()
        if not code or len(code) != 6:
            QMessageBox.warning(self, '입력 오류', '6자리 종목코드를 입력하세요.')
            return
        if name in ('—', '종목 없음', ''):
            name = code
        price = getattr(self, '_buy_price', 0)
        est   = f'\n예상금액: {price * qty:,}원' if price > 0 else ''
        reply = QMessageBox.question(
            self, '매수 확인',
            f'[{name}]  {qty}주  시장가 매수하겠습니까?{est}',
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
            self, '⚠️ 전체 청산 확인',
            f'보유 종목 {len(self._positions)}건을 전부 시장가 매도합니다.\n'
            f'예상 미실현손익 합계: {total_pnl:+,}원\n\n'
            '이 작업은 되돌릴 수 없습니다. 계속하시겠습니까?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        reply2 = QMessageBox.warning(
            self, '⚠️ 최종 확인',
            '정말로 전체 청산하시겠습니까?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply2 != QMessageBox.Yes:
            return
        for p in self._positions:
            db.insert_manual_order('SELL', p.get('code', ''), p.get('code_name', ''),
                                   int(p.get('holding_amount', 0)))
        QMessageBox.information(self, '주문 접수',
            f'{len(self._positions)}건 전체 청산 주문이 접수되었습니다.')
        self._reload_orders()
