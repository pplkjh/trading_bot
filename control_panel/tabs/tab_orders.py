"""Tab 4 — 즉시 주문: 수동 매수/매도 폼 + 전체 청산 + 주문 내역"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QSpinBox,
    QPushButton, QGroupBox, QMessageBox, QFrame,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from control_panel.widgets.colored_table import ColoredTable, RED, BLUE, GRAY
from control_panel import db

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from library.cf import invest_unit as cf_invest_unit

ORDER_HEADERS = ['시각', '유형', '종목코드', '종목명', '수량', '상태', '체결시각', '메모']

STATUS_COLOR = {
    'PENDING':  '#e07b00',
    'EXECUTED': '#008800',
    'FAILED':   '#cc0000',
    'CANCELLED':'#888888',
}


class OrdersTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._positions = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(10)

        row_top = QHBoxLayout()
        row_top.setSpacing(12)

        # ── 매수 폼 ──────────────────────────────────────────────
        buy_box = QGroupBox('즉시 매수 (시장가)')
        buy_box.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
        buy_lay = QGridLayout(buy_box)
        buy_lay.setSpacing(6)

        buy_lay.addWidget(QLabel('종목코드:'), 0, 0)
        self._buy_code = QLineEdit()
        self._buy_code.setPlaceholderText('예: 005930')
        self._buy_code.setMaxLength(6)
        self._buy_code.setFixedWidth(90)
        self._buy_code.editingFinished.connect(self._lookup_buy_name)
        buy_lay.addWidget(self._buy_code, 0, 1)

        self._buy_name_lbl = QLabel('—')
        self._buy_name_lbl.setFont(QFont('Malgun Gothic', 9))
        buy_lay.addWidget(self._buy_name_lbl, 0, 2)

        buy_lay.addWidget(QLabel('전략:'), 1, 0)
        self._buy_strat = QComboBox()
        self._buy_strat.addItems(['A', 'B'])
        self._buy_strat.setFixedWidth(60)
        buy_lay.addWidget(self._buy_strat, 1, 1)

        buy_lay.addWidget(QLabel('수량:'), 2, 0)
        self._buy_qty = QSpinBox()
        self._buy_qty.setRange(1, 99999)
        self._buy_qty.setValue(max(1, cf_invest_unit // 10000))
        self._buy_qty.setFixedWidth(90)
        buy_lay.addWidget(self._buy_qty, 2, 1)

        buy_btn = QPushButton('매수 실행')
        buy_btn.setFixedHeight(32)
        buy_btn.setStyleSheet('background:#cc0000;color:white;font-weight:bold;border-radius:4px;')
        buy_btn.clicked.connect(self._do_buy)
        buy_lay.addWidget(buy_btn, 3, 0, 1, 3)

        row_top.addWidget(buy_box)

        # ── 매도 폼 ──────────────────────────────────────────────
        sell_box = QGroupBox('즉시 매도 (시장가)')
        sell_box.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
        sell_lay = QGridLayout(sell_box)
        sell_lay.setSpacing(6)

        sell_lay.addWidget(QLabel('보유 종목:'), 0, 0)
        self._sell_combo = QComboBox()
        self._sell_combo.setMinimumWidth(160)
        self._sell_combo.currentIndexChanged.connect(self._update_sell_qty)
        sell_lay.addWidget(self._sell_combo, 0, 1, 1, 2)

        sell_lay.addWidget(QLabel('매도 구분:'), 1, 0)
        self._sell_type = QComboBox()
        self._sell_type.addItems(['전량매도', '부분매도'])
        self._sell_type.currentTextChanged.connect(self._sell_type_changed)
        self._sell_type.setFixedWidth(90)
        sell_lay.addWidget(self._sell_type, 1, 1)

        self._sell_qty_lbl = QLabel('수량:')
        self._sell_qty = QSpinBox()
        self._sell_qty.setRange(1, 99999)
        self._sell_qty.setFixedWidth(80)
        self._sell_qty.setEnabled(False)
        sell_lay.addWidget(self._sell_qty_lbl, 2, 0)
        sell_lay.addWidget(self._sell_qty, 2, 1)

        sell_btn = QPushButton('매도 실행')
        sell_btn.setFixedHeight(32)
        sell_btn.setStyleSheet('background:#0044bb;color:white;font-weight:bold;border-radius:4px;')
        sell_btn.clicked.connect(self._do_sell)
        sell_lay.addWidget(sell_btn, 3, 0, 1, 3)

        row_top.addWidget(sell_box)

        # ── 전체 청산 ─────────────────────────────────────────────
        liq_box = QGroupBox('긴급 전체 청산')
        liq_box.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
        liq_lay = QVBoxLayout(liq_box)

        warn = QLabel('⚠️ 보유 종목 전체를\n시장가 일괄 매도합니다.')
        warn.setAlignment(Qt.AlignCenter)
        warn.setFont(QFont('Malgun Gothic', 9))
        warn.setStyleSheet('color:#cc0000;')
        liq_lay.addWidget(warn)

        liq_btn = QPushButton('⚠️ 전체 청산')
        liq_btn.setFixedHeight(40)
        liq_btn.setStyleSheet(
            'background:#660000;color:white;font-weight:bold;font-size:12px;border-radius:4px;')
        liq_btn.clicked.connect(self._do_liquidate)
        liq_lay.addWidget(liq_btn)

        row_top.addWidget(liq_box)
        root.addLayout(row_top)

        # ── 주문 내역 테이블 ──────────────────────────────────────
        hdr = QLabel('수동 주문 내역')
        hdr.setFont(QFont('Malgun Gothic', 10, QFont.Bold))
        root.addWidget(hdr)

        self._order_table = ColoredTable(ORDER_HEADERS, self)
        root.addWidget(self._order_table)

        refresh_btn = QPushButton('주문 내역 갱신')
        refresh_btn.setFixedWidth(120)
        refresh_btn.clicked.connect(self._reload_orders)
        root.addWidget(refresh_btn, alignment=Qt.AlignRight)

    # ── 포지션 목록 갱신 (main에서 호출) ─────────────────────────
    def update_positions(self, positions: list):
        self._positions = positions
        current = self._sell_combo.currentText()
        self._sell_combo.blockSignals(True)
        self._sell_combo.clear()
        for p in positions:
            label = f"{p.get('code_name','')}  ({p.get('code','')})  {int(p.get('holding_amount',0))}주"
            self._sell_combo.addItem(label, userData=p)
        # 기존 선택 복원
        for i in range(self._sell_combo.count()):
            if current in self._sell_combo.itemText(i):
                self._sell_combo.setCurrentIndex(i)
                break
        self._sell_combo.blockSignals(False)
        self._update_sell_qty()

    def refresh(self, _=None):
        self._reload_orders()

    def _reload_orders(self):
        orders = db.get_manual_orders(50)
        rows = []
        for o in orders:
            st = str(o.get('status', ''))
            color_hex = STATUS_COLOR.get(st, '#000')
            from PyQt5.QtGui import QColor
            color = QColor(color_hex)
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

    def _lookup_buy_name(self):
        code = self._buy_code.text().strip()
        if code:
            name = db.lookup_code_name(code)
            self._buy_name_lbl.setText(name or '종목 없음')

    def _update_sell_qty(self):
        p = self._sell_combo.currentData()
        if p:
            qty = int(p.get('holding_amount', 1))
            self._sell_qty.setMaximum(qty)
            self._sell_qty.setValue(qty)

    def _sell_type_changed(self, text):
        is_part = text == '부분매도'
        self._sell_qty.setEnabled(is_part)

    def _do_buy(self):
        code = self._buy_code.text().strip()
        name = self._buy_name_lbl.text()
        qty  = self._buy_qty.value()
        if not code or len(code) != 6:
            QMessageBox.warning(self, '입력 오류', '6자리 종목코드를 입력하세요.')
            return
        if name in ('—', '종목 없음', ''):
            name = code
        reply = QMessageBox.question(
            self, '매수 확인',
            f'[{name}] {qty}주 시장가 매수하겠습니까?',
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
        code = p.get('code', '')
        name = p.get('code_name', '')
        max_qty = int(p.get('holding_amount', 0))
        is_part = self._sell_type.currentText() == '부분매도'
        qty = self._sell_qty.value() if is_part else max_qty
        order_type = 'PART_SELL' if (is_part and qty < max_qty) else 'SELL'

        reply = QMessageBox.question(
            self, '매도 확인',
            f'[{name}] {qty}주 시장가 매도하겠습니까?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            db.insert_manual_order(order_type, code, name, qty)
            QMessageBox.information(self, '주문 접수', f'{name} 매도 주문 접수 완료.')
            self._reload_orders()

    def _do_liquidate(self):
        if not self._positions:
            QMessageBox.information(self, '알림', '보유 종목이 없습니다.')
            return
        reply = QMessageBox.warning(
            self, '⚠️ 전체 청산 확인',
            f'보유 종목 {len(self._positions)}건을 전부 시장가 매도합니다.\n'
            '이 작업은 되돌릴 수 없습니다. 계속하시겠습니까?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        # 2차 확인
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
