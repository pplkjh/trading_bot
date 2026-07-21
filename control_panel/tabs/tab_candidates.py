"""Tab 2 — 매수 후보: realtime_daily_buy_list + 우클릭 즉시매수"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QSpinBox, QPushButton,
    QMenu, QAction, QDialog, QDialogButtonBox,
    QFormLayout, QMessageBox,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from control_panel.widgets.colored_table import ColoredTable, RED, BLUE, GRAY
from control_panel import db

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from library.cf import v4_min_score_a, invest_unit as cf_invest_unit

HEADERS = ['종목명', '전략', '복합점수', 'A모멘텀', 'B평균회귀', 'C추세강도',
           'D수급', 'E시장RS', 'F다중TF', 'G패널티', '현재가', '거래량비율', 'RSI']


class CandidatesTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows_cache = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # 필터 바
        filter_lay = QHBoxLayout()
        filter_lay.setSpacing(10)

        filter_lay.addWidget(QLabel('전략:'))
        self._strat_combo = QComboBox()
        self._strat_combo.addItems(['전체', 'A', 'B'])
        self._strat_combo.setFixedWidth(70)
        self._strat_combo.currentTextChanged.connect(self._apply_filter)
        filter_lay.addWidget(self._strat_combo)

        filter_lay.addWidget(QLabel('최소 점수:'))
        self._min_score = QSpinBox()
        self._min_score.setRange(0, 300)
        self._min_score.setValue(v4_min_score_a)
        self._min_score.setFixedWidth(70)
        self._min_score.valueChanged.connect(self._apply_filter)
        filter_lay.addWidget(self._min_score)

        self._refresh_btn = QPushButton('새로고침')
        self._refresh_btn.setFixedWidth(80)
        self._refresh_btn.clicked.connect(self._manual_refresh)
        filter_lay.addWidget(self._refresh_btn)
        filter_lay.addStretch()

        self._count_lbl = QLabel('0건')
        self._count_lbl.setFont(QFont('Malgun Gothic', 9))
        filter_lay.addWidget(self._count_lbl)

        root.addLayout(filter_lay)

        # 테이블
        self._table = ColoredTable(HEADERS, self)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        root.addWidget(self._table)

    def refresh(self, candidates: list):
        self._rows_cache = candidates
        self._render(candidates)

    def _apply_filter(self):
        strat = self._strat_combo.currentText()
        min_s = self._min_score.value()
        filtered = [r for r in self._rows_cache
                    if int(r.get('composite_score') or 0) >= min_s
                    and (strat == '전체' or r.get('strategy_type') == strat)]
        self._render(filtered)

    def _manual_refresh(self):
        strat = self._strat_combo.currentText()
        min_s = self._min_score.value()
        data  = db.get_candidates(min_s, strat)
        self.refresh(data)

    def _render(self, data: list):
        rows = []
        for c in data:
            score = int(c.get('composite_score') or 0)
            sc = RED if score >= 120 else (GRAY if score >= 90 else BLUE)
            rows.append([
                str(c.get('code_name', '')),
                str(c.get('strategy_type', '')),
                (str(score), sc),
                (f"{float(c.get('score_a') or 0):.1f}", None),
                (f"{float(c.get('score_b') or 0):.1f}", None),
                (f"{float(c.get('score_c') or 0):.1f}", None),
                (f"{float(c.get('score_d') or 0):.1f}", None),
                (f"{float(c.get('score_e') or 0):.1f}", None),
                (f"{float(c.get('score_f') or 0):.1f}", None),
                (f"{float(c.get('score_g') or 0):.1f}", None),
                (f"{int(c.get('close') or 0):,}", None),
                (f"{float(c.get('volume_ratio') or 0):.2f}", None),
                (f"{float(c.get('rsi14') or 0):.1f}", None),
            ])
        self._table.set_rows(rows)
        self._count_lbl.setText(f'{len(data)}건')

    def _show_context_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._rows_cache):
            return
        c         = self._rows_cache[row]
        code      = c.get('code', '')
        code_name = c.get('code_name', '')
        price     = int(c.get('close') or 0)

        menu    = QMenu(self)
        act_buy = QAction(f'즉시 매수  ({code_name})', self)
        menu.addAction(act_buy)
        action  = menu.exec_(self._table.viewport().mapToGlobal(pos))

        if action == act_buy:
            self._buy_dialog(code, code_name, price)

    def _buy_dialog(self, code, code_name, price):
        dlg = QDialog(self)
        dlg.setWindowTitle(f'즉시 매수 — {code_name}  ({code})')
        dlg.setFixedWidth(320)
        form = QFormLayout(dlg)

        default_qty = max(1, cf_invest_unit // price) if price > 0 else 1

        spin_qty = QSpinBox()
        spin_qty.setRange(1, 9999)
        spin_qty.setValue(default_qty)
        form.addRow('매수 수량:', spin_qty)

        price_lbl = QLabel(f'{price:,}원  (시장가 주문)')
        form.addRow('현재가:', price_lbl)

        if price > 0:
            est_lbl = QLabel(f'예상 금액: {default_qty * price:,}원')
            form.addRow('', est_lbl)
            spin_qty.valueChanged.connect(
                lambda v: est_lbl.setText(f'예상 금액: {v * price:,}원'))

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        if dlg.exec_() == QDialog.Accepted:
            qty = spin_qty.value()
            reply = QMessageBox.question(
                self, '매수 확인',
                f'[{code_name}]  {qty}주  시장가 매수하겠습니까?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                db.insert_manual_order('BUY', code, code_name, qty)
                QMessageBox.information(self, '주문 접수',
                    f'{code_name} 매수 주문이 접수되었습니다.\n'
                    '트레이더가 다음 루프에서 실행합니다.')
