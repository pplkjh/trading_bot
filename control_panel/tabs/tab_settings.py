"""Tab 5 — 설정: setting_data 즉시 반영 + cf.py 재시작 후 반영"""
import re
import os
import sys
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QSpinBox, QDoubleSpinBox, QPushButton,
    QGroupBox, QMessageBox, QScrollArea, QCheckBox,
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
        self._invest_unit.setFixedWidth(130)
        imm_form.addRow('종목당 투자금:', self._invest_unit)

        self._limit_money = QSpinBox()
        self._limit_money.setRange(0, 10_000_000)
        self._limit_money.setSingleStep(10_000)
        self._limit_money.setSuffix(' 원')
        self._limit_money.setValue(300_000)
        self._limit_money.setFixedWidth(130)
        imm_form.addRow('최소 보유 예수금:', self._limit_money)

        save_imm_btn = QPushButton('즉시 반영 저장')
        save_imm_btn.setFixedHeight(30)
        save_imm_btn.setStyleSheet('background:#008800;color:white;border-radius:4px;font-weight:bold;')
        save_imm_btn.clicked.connect(self._save_immediate)
        imm_form.addRow('', save_imm_btn)

        root.addWidget(imm_box)

        # ── 즉시 반영: 매도 파라미터 (bot_config 테이블) ──────────
        sell_box = QGroupBox('매도 파라미터 — sim=11 (즉시 반영 · 다음 매도 사이클부터 적용)')
        sell_box.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
        sell_form = QFormLayout(sell_box)
        sell_form.setSpacing(6)

        lbl_a = QLabel('── 전략 A (돌파) ──')
        lbl_a.setStyleSheet('color:#0055cc; font-weight:bold;')
        sell_form.addRow(lbl_a)

        self._a_tp = QDoubleSpinBox()
        self._a_tp.setRange(1.0, 50.0); self._a_tp.setSingleStep(0.5)
        self._a_tp.setDecimals(1); self._a_tp.setSuffix(' %'); self._a_tp.setValue(6.0)
        self._a_tp.setFixedWidth(90)
        sell_form.addRow('익절 TP (A):', self._a_tp)

        self._a_sl = QDoubleSpinBox()
        self._a_sl.setRange(-30.0, -0.5); self._a_sl.setSingleStep(0.5)
        self._a_sl.setDecimals(1); self._a_sl.setSuffix(' %'); self._a_sl.setValue(-5.0)
        self._a_sl.setFixedWidth(90)
        sell_form.addRow('하드 SL (A):', self._a_sl)

        self._a_td = QSpinBox()
        self._a_td.setRange(1, 120); self._a_td.setSuffix(' 일'); self._a_td.setValue(20)
        self._a_td.setFixedWidth(90)
        sell_form.addRow('시간청산 (A):', self._a_td)

        lbl_b = QLabel('── 전략 B (반전 · MA20반등이탈 상시 적용) ──')
        lbl_b.setStyleSheet('color:#007700; font-weight:bold;')
        sell_form.addRow(lbl_b)

        self._b_sl = QDoubleSpinBox()
        self._b_sl.setRange(-30.0, -0.5); self._b_sl.setSingleStep(0.5)
        self._b_sl.setDecimals(1); self._b_sl.setSuffix(' %'); self._b_sl.setValue(-8.0)
        self._b_sl.setFixedWidth(90)
        sell_form.addRow('하드 SL (B):', self._b_sl)

        self._b_td = QSpinBox()
        self._b_td.setRange(1, 120); self._b_td.setSuffix(' 일'); self._b_td.setValue(30)
        self._b_td.setFixedWidth(90)
        sell_form.addRow('시간청산 (B):', self._b_td)

        lbl_e = QLabel('── 전략 E (가치) ──')
        lbl_e.setStyleSheet('color:#880088; font-weight:bold;')
        sell_form.addRow(lbl_e)

        self._e_sl = QDoubleSpinBox()
        self._e_sl.setRange(-50.0, -1.0); self._e_sl.setSingleStep(1.0)
        self._e_sl.setDecimals(1); self._e_sl.setSuffix(' %'); self._e_sl.setValue(-15.0)
        self._e_sl.setFixedWidth(90)
        sell_form.addRow('하드 SL % (E):', self._e_sl)

        self._e_sl_on  = QCheckBox('하드 SL 활성화')
        self._e_sl_on.setChecked(True)
        sell_form.addRow('', self._e_sl_on)

        self._e_ma60_on = QCheckBox('MA60 이탈 시 매도')
        self._e_ma60_on.setChecked(True)
        sell_form.addRow('', self._e_ma60_on)

        save_sell_btn = QPushButton('매도 파라미터 저장 (즉시 반영)')
        save_sell_btn.setFixedHeight(30)
        save_sell_btn.setStyleSheet('background:#008800;color:white;border-radius:4px;font-weight:bold;')
        save_sell_btn.clicked.connect(self._save_sell_config)
        sell_form.addRow('', save_sell_btn)

        root.addWidget(sell_box)

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
        self._score_a.setFixedWidth(90)
        score_form.addRow('Strategy A 최소 점수:', self._score_a)

        self._score_b = QSpinBox()
        self._score_b.setRange(0, 300)
        self._score_b.setValue(getattr(_cf, 'v4_min_score_b', 110))
        self._score_b.setFixedWidth(90)
        score_form.addRow('Strategy B 최소 점수:', self._score_b)

        self._simul_num = QSpinBox()
        self._simul_num.setRange(1, 99)
        self._simul_num.setValue(getattr(_cf, 'imi1_simul_num', 6))
        self._simul_num.setFixedWidth(90)
        score_form.addRow('simul_num (imi1):', self._simul_num)

        save_score_btn = QPushButton('점수 임계값 저장')
        save_score_btn.setFixedHeight(30)
        save_score_btn.setStyleSheet('background:#e07b00;color:white;border-radius:4px;font-weight:bold;')
        save_score_btn.clicked.connect(self._save_scores)
        score_form.addRow('', save_score_btn)

        root.addWidget(score_box)

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
        # bot_config 최신값 로드
        try:
            cfg = db.get_sell_config()
            self._a_tp.setValue(float(cfg.get('a_tp_pct', 6.0)))
            self._a_sl.setValue(float(cfg.get('a_sl_pct', -5.0)))
            self._a_td.setValue(int(cfg.get('a_time_stop', 20)))
            self._b_sl.setValue(float(cfg.get('b_sl_pct', -8.0)))
            self._b_td.setValue(int(cfg.get('b_time_stop', 30)))
            self._e_sl.setValue(float(cfg.get('e_sl_pct', -15.0)))
            self._e_sl_on.setChecked(cfg.get('e_sl_hard_on', '1') == '1')
            self._e_ma60_on.setChecked(cfg.get('e_ma60_on', '1') == '1')
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

    def _save_sell_config(self):
        params = {
            'a_tp_pct':     self._a_tp.value(),
            'a_sl_pct':     self._a_sl.value(),
            'a_time_stop':  self._a_td.value(),
            'b_sl_pct':     self._b_sl.value(),
            'b_time_stop':  self._b_td.value(),
            'e_sl_pct':     self._e_sl.value(),
            'e_sl_hard_on': '1' if self._e_sl_on.isChecked() else '0',
            'e_ma60_on':    '1' if self._e_ma60_on.isChecked() else '0',
        }
        try:
            db.ensure_bot_config_table()
            db.save_sell_config(params)
            QMessageBox.information(self, '저장 완료',
                f'A: TP={params["a_tp_pct"]}% / SL={params["a_sl_pct"]}% / {params["a_time_stop"]}일\n'
                f'B: SL={params["b_sl_pct"]}% / {params["b_time_stop"]}일\n'
                f'E: SL={params["e_sl_pct"]}% / '
                f'SL_ON={params["e_sl_hard_on"]} / MA60={params["e_ma60_on"]}\n\n'
                '✅ 다음 매도 사이클부터 즉시 반영됩니다.')
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
