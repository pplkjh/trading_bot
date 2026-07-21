"""Tab 1 — 보유 종목: 실시간 포지션 테이블 + 우클릭 매도"""
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QMenu, QAction, QDialog, QDialogButtonBox,
    QSpinBox, QFormLayout, QMessageBox,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from control_panel.widgets.colored_table import ColoredTable, RED, BLUE
from control_panel import db

HEADERS = ['종목명', '전략', '현재가', '매수가', '수익률%', '미실현손익',
           '수량', '보유일', '최고가', '트레일링스톱가']


def _trailing_stop(strategy, highest, entry):
    try:
        h = int(highest or entry)
        e = int(entry)
        if strategy == 'A':
            return max(int(h * 0.97), int(e * 1.01))
        else:
            return max(int(h * 0.95), int(e * 1.01))
    except Exception:
        return 0


def _hold_days(buy_date_str):
    try:
        digits = ''.join(c for c in str(buy_date_str) if c.isdigit())
        bd = datetime.strptime(digits[:8], '%Y%m%d')
        return (datetime.today() - bd).days
    except Exception:
        return 0


class PositionsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows_cache = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # 상단 요약
        self._summary = QLabel('보유 종목: 0건  |  미실현 손익: —')
        self._summary.setFont(QFont('Malgun Gothic', 10, QFont.Bold))
        root.addWidget(self._summary)

        # 테이블
        self._table = ColoredTable(HEADERS, self)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        root.addWidget(self._table)

    def refresh(self, positions: list):
        self._rows_cache = positions
        rows = []
        total_unreal = 0
        for p in positions:
            rate_raw = float(p.get('rate') or 0)
            rate = rate_raw - 100 if rate_raw > 10 else rate_raw
            unreal = int(p.get('valuation_profit') or 0)
            total_unreal += unreal
            ts = _trailing_stop(p.get('strategy_type', 'A'),
                                 p.get('highest_price'), p.get('purchase_price'))
            color = RED if rate >= 0 else BLUE
            rows.append([
                str(p.get('code_name', '')),
                str(p.get('strategy_type', '')),
                (f"{int(p.get('present_price', 0)):,}", None),
                (f"{int(p.get('purchase_price', 0)):,}", None),
                (f"{rate:+.2f}%", color),
                (f"{unreal:+,}원", color),
                (str(int(p.get('holding_amount', 0))), None),
                (str(_hold_days(p.get('buy_date', ''))), None),
                (f"{int(p.get('highest_price', 0)):,}", None),
                (f"{ts:,}", BLUE if ts else None),
            ])
        self._table.set_rows(rows)

        color_str = '#cc0000' if total_unreal >= 0 else '#0044bb'
        self._summary.setText(
            f'보유 종목: {len(positions)}건  |  '
            f'미실현 손익 합계: <span style="color:{color_str}">{total_unreal:+,}원</span>')
        self._summary.setTextFormat(Qt.RichText)

    def _show_context_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._rows_cache):
            return
        p = self._rows_cache[row]
        code      = p.get('code', '')
        code_name = p.get('code_name', '')
        quantity  = int(p.get('holding_amount', 0))

        menu = QMenu(self)
        act_sell_all  = QAction(f'즉시 전량매도  ({code_name})', self)
        act_sell_part = QAction(f'부분 매도  ({code_name})', self)
        menu.addAction(act_sell_all)
        menu.addAction(act_sell_part)

        action = menu.exec_(self._table.viewport().mapToGlobal(pos))
        if action == act_sell_all:
            self._confirm_sell(code, code_name, quantity, 'SELL')
        elif action == act_sell_part:
            self._partial_sell_dialog(code, code_name, quantity)

    def _confirm_sell(self, code, code_name, quantity, order_type):
        reply = QMessageBox.question(
            self, '매도 확인',
            f'[{code_name}] {quantity}주 전량 시장가 매도하겠습니까?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            db.insert_manual_order(order_type, code, code_name, quantity)
            QMessageBox.information(self, '주문 접수',
                f'{code_name} 매도 주문이 접수되었습니다.\n'
                '트레이더가 다음 루프에서 실행합니다.')

    def _partial_sell_dialog(self, code, code_name, max_qty):
        dlg = QDialog(self)
        dlg.setWindowTitle(f'부분 매도 — {code_name}')
        dlg.setFixedWidth(300)
        form = QFormLayout(dlg)

        spin = QSpinBox()
        spin.setRange(1, max_qty)
        spin.setValue(max_qty // 2 or 1)
        form.addRow(f'매도 수량 (보유: {max_qty}주):', spin)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        if dlg.exec_() == QDialog.Accepted:
            qty = spin.value()
            order_type = 'SELL' if qty >= max_qty else 'PART_SELL'
            db.insert_manual_order(order_type, code, code_name, qty)
            QMessageBox.information(self, '주문 접수',
                f'{code_name} {qty}주 매도 주문이 접수되었습니다.')
