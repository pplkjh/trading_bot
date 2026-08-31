"""Tab 5 — 설정: setting_data 즉시 반영 + cf.py 재시작 후 반영"""
import re
import os
import sys
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QSpinBox, QDoubleSpinBox, QPushButton,
    QGroupBox, QMessageBox, QScrollArea,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from control_panel import db

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import library.cf as _cf

CF_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        'library', 'cf.py')


def _patch_cf(key: str, new_val):
    """cf.py에서 key = <value> 한 줄을 숫자 값으로 치환 (주석 보존)."""
    with open(CF_PATH, 'r', encoding='utf-8') as f:
        src = f.read()
    pattern = rf'^({re.escape(key)}\s*=\s*)([^\n#]+)'
    if isinstance(new_val, float):
        replacement = rf'\g<1>{new_val}'
    else:
        replacement = rf'\g<1>{int(new_val)}'
    new_src = re.sub(pattern, replacement, src, flags=re.MULTILINE)
    if new_src == src:
        return False
    with open(CF_PATH, 'w', encoding='utf-8') as f:
        f.write(new_src)
    return True


class SettingsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        root = QVBoxLayout(container)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(14)

        note_immediate = QLabel('🟢 즉시 반영 — 트레이더가 다음 루프에서 읽음')
        note_immediate.setStyleSheet('color: #008800; font-size: 9pt;')
        root.addWidget(note_immediate)

        # ── 즉시 반영: setting_data ────────────────────────────────
        imm_box = QGroupBox('즉시 반영 설정 (setting_data)')
        imm_box.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
        imm_form = QFormLayout(imm_box)
        imm_form.setSpacing(8)

        self._invest_unit = QSpinBox()
        self._invest_unit.setRange(100_000, 50_000_000)
        self._invest_unit.setSingleStep(100_000)
        self._invest_unit.setSuffix(' 원')
        self._invest_unit.setValue(getattr(_cf, 'invest_unit', 1_000_000))
        imm_form.addRow('종목당 투자금:', self._invest_unit)

        self._limit_money = QSpinBox()
        self._limit_money.setRange(0, 10_000_000)
        self._limit_money.setSingleStep(10_000)
        self._limit_money.setSuffix(' 원')
        self._limit_money.setValue(300_000)
        imm_form.addRow('최소 보유 예수금:', self._limit_money)

        save_imm_btn = QPushButton('즉시 반영 저장')
        save_imm_btn.setFixedHeight(30)
        save_imm_btn.setStyleSheet('background:#008800;color:white;border-radius:4px;font-weight:bold;')
        save_imm_btn.clicked.connect(self._save_immediate)
        imm_form.addRow('', save_imm_btn)

        root.addWidget(imm_box)

        note_restart = QLabel('🔁 재시작 후 반영 — 트레이더 재시작 필요 (cf.py 직접 수정)')
        note_restart.setStyleSheet('color: #e07b00; font-size: 9pt;')
        root.addWidget(note_restart)

        # ── 재시작 후 반영: cf.py 점수 임계값 ─────────────────────
        score_box = QGroupBox('매수 점수 임계값 (cf.py → 재시작 후 반영)')
        score_box.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
        score_form = QFormLayout(score_box)
        score_form.setSpacing(8)

        self._score_a = QSpinBox()
        self._score_a.setRange(0, 300)
        self._score_a.setValue(getattr(_cf, 'v4_min_score_a', 110))
        score_form.addRow('Strategy A 최소 점수:', self._score_a)

        self._score_b = QSpinBox()
        self._score_b.setRange(0, 300)
        self._score_b.setValue(getattr(_cf, 'v4_min_score_b', 110))
        score_form.addRow('Strategy B 최소 점수:', self._score_b)

        self._simul_num = QSpinBox()
        self._simul_num.setRange(1, 99)
        self._simul_num.setValue(getattr(_cf, 'imi1_simul_num', 6))
        score_form.addRow('simul_num (imi1):', self._simul_num)

        save_score_btn = QPushButton('점수 임계값 저장')
        save_score_btn.setFixedHeight(30)
        save_score_btn.setStyleSheet('background:#e07b00;color:white;border-radius:4px;font-weight:bold;')
        save_score_btn.clicked.connect(self._save_scores)
        score_form.addRow('', save_score_btn)

        root.addWidget(score_box)

        # ── 재시작 후 반영: 매도 파라미터 ─────────────────────────
        sell_box = QGroupBox('매도 파라미터 (simulator_func_mysql.py 기준 — cf.py 경유 없음)')
        sell_box.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
        sell_form = QFormLayout(sell_box)
        sell_form.setSpacing(8)

        self._losscut = QDoubleSpinBox()
        self._losscut.setRange(-30, 0)
        self._losscut.setSingleStep(0.5)
        self._losscut.setDecimals(1)
        self._losscut.setSuffix(' %')
        self._losscut.setValue(-5.0)
        sell_form.addRow('하드 손절 % (losscut_point):', self._losscut)

        self._trail_act = QDoubleSpinBox()
        self._trail_act.setRange(0, 30)
        self._trail_act.setSingleStep(0.5)
        self._trail_act.setDecimals(1)
        self._trail_act.setSuffix(' %')
        self._trail_act.setValue(3.0)
        sell_form.addRow('트레일링 활성화 수익률 (A/B):', self._trail_act)

        self._trail_pct_a = QDoubleSpinBox()
        self._trail_pct_a.setRange(0, 20)
        self._trail_pct_a.setSingleStep(0.5)
        self._trail_pct_a.setDecimals(1)
        self._trail_pct_a.setSuffix(' %')
        self._trail_pct_a.setValue(3.0)
        sell_form.addRow('트레일링 하락 허용 % (A전략):', self._trail_pct_a)

        self._trail_pct_b = QDoubleSpinBox()
        self._trail_pct_b.setRange(0, 20)
        self._trail_pct_b.setSingleStep(0.5)
        self._trail_pct_b.setDecimals(1)
        self._trail_pct_b.setSuffix(' %')
        self._trail_pct_b.setValue(5.0)
        sell_form.addRow('트레일링 하락 허용 % (B전략):', self._trail_pct_b)

        self._time_stop_a = QSpinBox()
        self._time_stop_a.setRange(1, 90)
        self._time_stop_a.setValue(15)
        self._time_stop_a.setSuffix(' 일')
        sell_form.addRow('시간청산 일수 (A전략):', self._time_stop_a)

        self._time_stop_b = QSpinBox()
        self._time_stop_b.setRange(1, 90)
        self._time_stop_b.setValue(45)
        self._time_stop_b.setSuffix(' 일')
        sell_form.addRow('시간청산 일수 (B전략):', self._time_stop_b)

        note_sell = QLabel('※ 매도 파라미터는 open_api.py의 get_basic_sell_list()에 하드코딩.\n'
                           '   실제 코드를 직접 수정 후 트레이더를 재시작하세요.')
        note_sell.setStyleSheet('color: #888; font-size: 8pt;')
        sell_form.addRow('', note_sell)

        root.addWidget(sell_box)
        root.addStretch()

    def refresh(self, _=None):
        # setting_data 최신값 로드
        try:
            sd = db.get_setting()
            if sd:
                if sd.get('invest_unit'):
                    self._invest_unit.setValue(int(sd['invest_unit']))
                if sd.get('limit_money'):
                    self._limit_money.setValue(int(sd['limit_money']))
        except Exception:
            pass

    def _save_immediate(self):
        invest = self._invest_unit.value()
        limit  = self._limit_money.value()
        try:
            db.set_invest_unit(invest)
            db.set_limit_money(limit)
            QMessageBox.information(self, '저장 완료',
                f'종목당 투자금: {invest:,}원\n'
                f'최소 예수금: {limit:,}원\n\n'
                '트레이더 다음 루프에서 반영됩니다.')
        except Exception as e:
            QMessageBox.critical(self, '저장 실패', str(e))

    def _save_scores(self):
        sa = self._score_a.value()
        sb = self._score_b.value()
        sn = self._simul_num.value()
        try:
            ok_a = _patch_cf('v4_min_score_a', sa)
            ok_b = _patch_cf('v4_min_score_b', sb)
            ok_n = _patch_cf('imi1_simul_num', sn)
            msgs = []
            if ok_a: msgs.append(f'v4_min_score_a = {sa}')
            if ok_b: msgs.append(f'v4_min_score_b = {sb}')
            if ok_n: msgs.append(f'imi1_simul_num = {sn}')
            if msgs:
                QMessageBox.information(self, 'cf.py 저장 완료',
                    '\n'.join(msgs) + '\n\n⚠️ 트레이더 재시작 후 반영됩니다.')
            else:
                QMessageBox.warning(self, '변경 없음', 'cf.py에서 해당 키를 찾지 못했거나 값이 동일합니다.')
        except Exception as e:
            QMessageBox.critical(self, '저장 실패', str(e))
