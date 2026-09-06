"""Tab — Strategy D 긴급 매수/매도 (장중 OPT 스캔 후보 + 보유 D종목)"""
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QMenu, QAction, QDialog, QDialogButtonBox,
    QFormLayout, QSpinBox, QMessageBox, QSplitter, QFrame,
    QHeaderView,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor

from control_panel.widgets.colored_table import ColoredTable, RED, BLUE, GRAY
from control_panel.widgets.price_chart import PriceChart
from control_panel import db

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from library.cf import invest_unit as cf_invest_unit

_CAND_HEADERS = ['종목명', '종목코드', '현재가', '시가대비(%)', '거래량',
                 '기관(백만)', '외국계(백만)', '스캔시간']
_POS_HEADERS  = ['종목명', '종목코드', '매입가', '현재가', '수익률(%)', '평가손익', '매수시간']
_CAND_WIDTHS  = [105, 65, 72, 70, 88, 88, 88, 60]
_POS_WIDTHS   = [105, 65, 72, 72, 72, 95, 60]


class UrgentTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._displayed_cand    = []   # 화면 순서와 1:1 대응
        self._displayed_pos     = []
        self._selected_cand_code = None  # 선택 복원용 (코드 기준)
        self._selected_pos_code  = None
        self._last_active        = None  # 'cand' | 'pos' — 마지막 포커스 테이블
        self._last_chart_code    = None  # 차트 중복 방지
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        banner = QLabel(
            '⚡  20분마다 OPT10028(시가대비등락률) + OPT10063(기관+외국 동시순매수) 교집합  |  '
            'SL -2% / TP +4%'
        )
        banner.setStyleSheet('color:#e07b00; font-weight:bold; padding:4px;')
        root.addWidget(banner)

        # ── 자금 현황 바 ──────────────────────────────────────────────
        fund_bar = QFrame()
        fund_bar.setStyleSheet(
            'QFrame{border:1px solid #e0e0e0;border-radius:4px;background:#fafafa;}')
        fund_bar.setFixedHeight(32)
        fund_lay = QHBoxLayout(fund_bar)
        fund_lay.setContentsMargins(14, 0, 14, 0)
        fund_lay.setSpacing(0)
        self._fund = {}
        for i, (k, label) in enumerate([
            ('deposit', '예수금 (D+2)'),
            ('reserve', '최소 유보금'),
            ('avail',   '운용 가능'),
            ('slots',   '추가 매수 가능'),
        ]):
            if i > 0:
                sep = QLabel('  │  ')
                sep.setStyleSheet('color:#ccc;border:none;')
                fund_lay.addWidget(sep)
            lbl = QLabel(label + '  ')
            lbl.setFont(QFont('Malgun Gothic', 8))
            lbl.setStyleSheet('color:#777;border:none;')
            val = QLabel('—')
            val.setFont(QFont('Malgun Gothic', 8, QFont.Bold))
            val.setStyleSheet('color:#333;border:none;')
            self._fund[k] = val
            fund_lay.addWidget(lbl)
            fund_lay.addWidget(val)
        fund_lay.addStretch()
        root.addWidget(fund_bar)

        btn_row = QHBoxLayout()
        self._refresh_btn = QPushButton('새로고침')
        self._refresh_btn.setFixedWidth(80)
        self._refresh_btn.clicked.connect(self._manual_refresh)
        btn_row.addWidget(self._refresh_btn)
        self._scan_lbl = QLabel('마지막 스캔: —')
        self._scan_lbl.setFont(QFont('Malgun Gothic', 8))
        btn_row.addWidget(self._scan_lbl)
        btn_row.addStretch()
        root.addLayout(btn_row)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)

        # ── 왼쪽 ─────────────────────────────────────────────────────
        left_w = QWidget()
        lv = QVBoxLayout(left_w)
        lv.setContentsMargins(0, 0, 4, 0)
        lv.setSpacing(6)

        grp_cand = QGroupBox('⚡ 긴급 매수 후보  (우클릭 → 즉시매수)')
        cl = QVBoxLayout(grp_cand)
        cl.setSpacing(2)
        self._cand_table = ColoredTable(_CAND_HEADERS, self)
        self._cand_table.setSortingEnabled(False)
        self._cand_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._cand_table.customContextMenuRequested.connect(self._cand_context_menu)
        self._cand_table.itemSelectionChanged.connect(self._on_cand_select)
        _fix_cols(self._cand_table, _CAND_WIDTHS)
        cl.addWidget(self._cand_table)
        self._cand_count_lbl = QLabel('0건')
        self._cand_count_lbl.setFont(QFont('Malgun Gothic', 8))
        cl.addWidget(self._cand_count_lbl)
        lv.addWidget(grp_cand, 3)

        grp_pos = QGroupBox('📂 D전략 보유 종목  (우클릭 → 즉시매도)')
        pl = QVBoxLayout(grp_pos)
        pl.setSpacing(2)
        self._pos_table = ColoredTable(_POS_HEADERS, self)
        self._pos_table.setSortingEnabled(False)
        self._pos_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._pos_table.customContextMenuRequested.connect(self._pos_context_menu)
        self._pos_table.itemSelectionChanged.connect(self._on_pos_select)
        _fix_cols(self._pos_table, _POS_WIDTHS)
        pl.addWidget(self._pos_table)
        self._pos_count_lbl = QLabel('0건')
        self._pos_count_lbl.setFont(QFont('Malgun Gothic', 8))
        pl.addWidget(self._pos_count_lbl)
        lv.addWidget(grp_pos, 2)

        splitter.addWidget(left_w)

        # ── 오른쪽 ───────────────────────────────────────────────────
        splitter.addWidget(self._build_info_panel())
        splitter.setStretchFactor(0, 62)
        splitter.setStretchFactor(1, 38)

    def _build_info_panel(self):
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        v = QVBoxLayout(frame)
        v.setContentsMargins(8, 8, 8, 4)
        v.setSpacing(6)

        self._info_title = QLabel('[ 종목 선택 ]')
        self._info_title.setFont(QFont('Malgun Gothic', 9, QFont.Bold))
        self._info_title.setStyleSheet('color:#333; padding:2px 0;')
        v.addWidget(self._info_title)

        grp = QGroupBox()
        grp.setStyleSheet('QGroupBox{border:1px solid #ddd;border-radius:4px;margin-top:0;}')
        gv = QVBoxLayout(grp)
        gv.setSpacing(3)
        gv.setContentsMargins(6, 6, 6, 6)
        self._info_lbl = {}
        for key, title in [
            ('name',     '종목명'),
            ('code',     '종목코드'),
            ('price',    '현재가'),
            ('rate',     '시가대비'),
            ('volume',   '거래량'),
            ('inst',     '기관순매수'),
            ('foreign',  '외국계순매수'),
            ('entry',    '매입가'),
            ('pnl_rate', '수익률'),
            ('pnl',      '평가손익'),
        ]:
            row = QHBoxLayout()
            row.setSpacing(4)
            t = QLabel(title)
            t.setFixedWidth(62)
            t.setFont(QFont('Malgun Gothic', 8))
            t.setStyleSheet('color:#888;')
            val = QLabel('—')
            val.setFont(QFont('Malgun Gothic', 9))
            row.addWidget(t)
            row.addWidget(val, 1)
            gv.addLayout(row)
            self._info_lbl[key] = val
        v.addWidget(grp)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet('color:#ddd;')
        v.addWidget(sep)

        self._chart = PriceChart()
        self._chart.setMinimumHeight(220)
        v.addWidget(self._chart, 1)

        return frame

    # ── 차트 ──────────────────────────────────────────────────────────
    def _draw_chart(self, code, code_name, entry_price=0, trailing_stop=0,
                    buy_date='', strategy='D'):
        if not code_name:
            return
        if code == self._last_chart_code:
            return
        self._last_chart_code = code
        rows = db.get_price_history(code_name, days=90)
        if not rows:
            self._chart._show_placeholder(f'{code_name} — 차트 없음')
            return
        self._chart.plot(
            rows=rows,
            title=code_name,
            entry_price=entry_price,
            trailing_stop=trailing_stop,
            buy_date=buy_date,
            strategy=strategy,
        )

    # ── 정보 패널 갱신 ────────────────────────────────────────────────
    def _set_info(self, info: dict, title: str = ''):
        if title:
            self._info_title.setText(title)
        for key, lbl in self._info_lbl.items():
            val = info.get(key, '')
            lbl.setText(str(val) if val else '—')
            if key in ('rate', 'pnl_rate'):
                try:
                    v = float(str(val).replace('+', '').replace('%', '').replace(',', ''))
                    lbl.setStyleSheet(
                        'color:#cc0000;font-weight:bold;' if v >= 0
                        else 'color:#0044bb;font-weight:bold;')
                except Exception:
                    lbl.setStyleSheet('')
            elif key == 'pnl':
                try:
                    v = float(str(val).replace('+', '').replace(',', '').replace('원', ''))
                    lbl.setStyleSheet('color:#cc0000;' if v >= 0 else 'color:#0044bb;')
                except Exception:
                    lbl.setStyleSheet('')
            else:
                lbl.setStyleSheet('')

    def _info_from_cand(self, c: dict):
        rate    = float(c.get('change_rate') or 0)
        inst    = int(c.get('inst_net_buy') or 0)
        foreign = int(c.get('foreign_net_buy') or 0)
        self._set_info({
            'name':    c.get('code_name', ''),
            'code':    c.get('code', ''),
            'price':   f"{int(c.get('current_price') or 0):,}원",
            'rate':    f"{rate:+.2f}%",
            'volume':  f"{int(c.get('volume') or 0):,}주",
            'inst':    f"{inst:,}백만원" if inst else "—",
            'foreign': f"{foreign:,}백만원" if foreign else "—",
        }, f'⚡ {c.get("code_name", "")}')

    def _info_from_pos(self, p: dict):
        rate = float(p.get('rate') or 0)
        if rate > 100:
            rate -= 100
        pnl = int(p.get('valuation_profit') or 0)
        self._set_info({
            'name':     p.get('code_name', ''),
            'code':     p.get('code', ''),
            'entry':    f"{int(p.get('purchase_price') or 0):,}원",
            'price':    f"{int(p.get('present_price') or 0):,}원",
            'pnl_rate': f"{rate:+.2f}%",
            'pnl':      f"{pnl:+,}원",
        }, f'📂 {p.get("code_name", "")}')

    # ── 사용자 선택 이벤트 (명시적 클릭 시에만 발동) ────────────────────
    def _on_cand_select(self):
        row = self._cand_table.currentRow()
        if row < 0 or row >= len(self._displayed_cand):
            return
        c = self._displayed_cand[row]
        self._selected_cand_code = c.get('code')
        self._last_active = 'cand'
        self._info_from_cand(c)
        self._draw_chart(c.get('code', ''), c.get('code_name', ''))

    def _on_pos_select(self):
        row = self._pos_table.currentRow()
        if row < 0 or row >= len(self._displayed_pos):
            return
        p = self._displayed_pos[row]
        self._selected_pos_code = p.get('code')
        self._last_active = 'pos'
        self._info_from_pos(p)
        entry = int(p.get('purchase_price') or 0)
        sl    = round(entry * 0.98) if entry > 0 else 0
        bd8   = ''.join(c for c in str(p.get('buy_date', '')) if c.isdigit())[:8]
        self._draw_chart(p.get('code', ''), p.get('code_name', ''),
                         entry_price=entry, trailing_stop=sl,
                         buy_date=bd8, strategy='D')

    # ── 5초 타이머 갱신 ──────────────────────────────────────────────
    def _refresh_fund(self):
        try:
            jango = db._fetch("SELECT d2_deposit FROM jango_data ORDER BY date DESC LIMIT 1")
            deposit = int(jango[0]['d2_deposit'] or 0) if jango else 0
            sd = db._fetch("SELECT invest_unit, limit_money FROM setting_data LIMIT 1")
            invest_unit = int(sd[0]['invest_unit'] or cf_invest_unit) if sd else cf_invest_unit
            limit_money = int(sd[0]['limit_money'] or 0) if sd else 0
            avail = max(0, deposit - limit_money)
            slots = avail // invest_unit if invest_unit > 0 else 0
            dep_c = '#0044bb' if deposit == 0 else '#111'
            av_c  = '#cc0000' if slots > 0 else '#888'
            self._fund['deposit'].setText(f'{deposit:,}원')
            self._fund['deposit'].setStyleSheet(f'color:{dep_c};font-weight:bold;border:none;')
            self._fund['reserve'].setText(f'{limit_money:,}원')
            self._fund['reserve'].setStyleSheet('color:#888;border:none;')
            self._fund['avail'].setText(f'{avail:,}원')
            self._fund['avail'].setStyleSheet(f'color:{av_c};font-weight:bold;border:none;')
            self._fund['slots'].setText(f'{slots}종목')
            self._fund['slots'].setStyleSheet(f'color:{av_c};font-weight:bold;border:none;')
        except Exception:
            pass

    def refresh(self):
        self._refresh_fund()
        candidates = db.get_urgent_candidates()
        positions  = db.get_d_positions()
        self._render_cand(candidates)
        self._render_pos(positions)
        self._refresh_info_panel()
        # 자동·수동 갱신 모두 현재 시각으로 업데이트 (DB scanned_at에 의존하지 않음)
        self._scan_lbl.setText(f'마지막 갱신: {datetime.now().strftime("%H:%M:%S")}')

    def _manual_refresh(self):
        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText('스캔중...')
        self._last_chart_code = None
        try:
            db.request_d_scan()
            self._scan_lbl.setText('마지막 스캔: 요청됨 (5초 후 갱신)')
            QTimer.singleShot(5000, self._delayed_refresh)
        except Exception as e:
            QMessageBox.warning(self, '스캔 요청 오류', str(e))
            self._restore_refresh_btn()

    def _delayed_refresh(self):
        try:
            self.refresh()   # refresh() 내부에서 마지막 갱신 시각 업데이트
        except Exception as e:
            self._scan_lbl.setText('마지막 갱신: 오류 발생')
            QMessageBox.warning(self, '새로고침 오류', str(e))
        finally:
            self._restore_refresh_btn()

    def _restore_refresh_btn(self):
        self._refresh_btn.setText('새로고침')
        self._refresh_btn.setEnabled(True)

    def _render_cand(self, data: list):
        self._displayed_cand = list(data)
        rows = self._build_cand_rows(data)

        # blockSignals 블록 안에 selectRow까지 포함 → 타이머 갱신 시 시그널 발동 없음
        self._cand_table.blockSignals(True)
        self._cand_table.set_rows(rows)
        if self._selected_cand_code:
            for i, c in enumerate(self._displayed_cand):
                if c.get('code') == self._selected_cand_code:
                    self._cand_table.selectRow(i)
                    break
        self._cand_table.blockSignals(False)

        self._cand_count_lbl.setText(f'{len(data)}건')

    def _render_pos(self, data: list):
        self._displayed_pos = list(data)
        rows = self._build_pos_rows(data)

        self._pos_table.blockSignals(True)
        self._pos_table.set_rows(rows)
        if self._selected_pos_code:
            for i, p in enumerate(self._displayed_pos):
                if p.get('code') == self._selected_pos_code:
                    self._pos_table.selectRow(i)
                    break
        self._pos_table.blockSignals(False)

        self._pos_count_lbl.setText(f'{len(data)}건')

    def _refresh_info_panel(self):
        """시그널 없이 렌더링 완료 후 info 패널을 마지막 포커스 기준으로 갱신."""
        if self._last_active == 'pos' and self._selected_pos_code:
            for p in self._displayed_pos:
                if p.get('code') == self._selected_pos_code:
                    self._info_from_pos(p)   # 현재가·수익률 최신화
                    return
        if self._last_active == 'cand' and self._selected_cand_code:
            for c in self._displayed_cand:
                if c.get('code') == self._selected_cand_code:
                    self._info_from_cand(c)
                    return

    # ── 행 데이터 빌더 ────────────────────────────────────────────────
    def _build_cand_rows(self, data):
        rows = []
        for c in data:
            rate    = float(c.get('change_rate') or 0)
            inst    = int(c.get('inst_net_buy') or 0)
            foreign = int(c.get('foreign_net_buy') or 0)
            scanned = str(c.get('scanned_at') or '')[-8:]
            rate_color = RED if rate >= 3.0 else (QColor('#e07b00') if rate >= 2.0 else None)
            # 외국계: 값이 있으면 파랑(기관과 색상 구분), 없으면 회색
            f_color = QColor('#0044bb') if foreign > 0 else GRAY
            rows.append([
                (str(c.get('code_name', '')), None),
                (str(c.get('code', '')), GRAY),
                (f"{int(c.get('current_price') or 0):,}", None),
                (f"{rate:+.2f}", rate_color),
                (f"{int(c.get('volume') or 0):,}", None),
                (f"{inst:,}", RED if inst > 0 else GRAY),
                (f"{foreign:,}" if foreign else "—", f_color),
                (scanned, GRAY),
            ])
        return rows

    def _build_pos_rows(self, data):
        rows = []
        for p in data:
            rate = float(p.get('rate') or 0)
            if rate > 100:
                rate -= 100
            pnl = int(p.get('valuation_profit') or 0)
            rc = RED if rate >= 0 else BLUE
            rows.append([
                (str(p.get('code_name', '')), None),
                (str(p.get('code', '')), GRAY),
                (f"{int(p.get('purchase_price') or 0):,}", None),
                (f"{int(p.get('present_price') or 0):,}", None),
                (f"{rate:+.2f}", rc),
                (f"{pnl:+,}", rc),
                (str(p.get('buy_date') or '')[8:12], GRAY),
            ])
        return rows

    # ── 우클릭 메뉴 ───────────────────────────────────────────────────
    def _cand_context_menu(self, pos):
        row = self._cand_table.rowAt(pos.y())
        if row < 0 or row >= len(self._displayed_cand):
            return
        c = self._displayed_cand[row]
        menu = QMenu(self)
        act = QAction(f"즉시 매수  ({c.get('code_name', '')})", self)
        menu.addAction(act)
        if menu.exec_(self._cand_table.viewport().mapToGlobal(pos)) == act:
            self._buy_dialog(c.get('code', ''), c.get('code_name', ''),
                             int(c.get('current_price') or 0))

    def _pos_context_menu(self, pos):
        row = self._pos_table.rowAt(pos.y())
        if row < 0 or row >= len(self._displayed_pos):
            return
        p = self._displayed_pos[row]
        menu = QMenu(self)
        act = QAction(f"즉시 매도  ({p.get('code_name', '')})", self)
        menu.addAction(act)
        if menu.exec_(self._pos_table.viewport().mapToGlobal(pos)) == act:
            self._sell_dialog(p.get('code', ''), p.get('code_name', ''))

    # ── 매수/매도 다이얼로그 ──────────────────────────────────────────
    def _buy_dialog(self, code, code_name, price):
        dlg = QDialog(self)
        dlg.setWindowTitle(f'D전략 긴급 매수 — {code_name} ({code})')
        dlg.setFixedWidth(320)
        form = QFormLayout(dlg)
        default_qty = max(1, cf_invest_unit // price) if price > 0 else 1
        spin = QSpinBox()
        spin.setRange(1, 9999)
        spin.setValue(default_qty)
        form.addRow('매수 수량:', spin)
        form.addRow('현재가:', QLabel(f'{price:,}원  (시장가)'))
        est = QLabel(f'예상 금액: {default_qty * price:,}원')
        form.addRow('', est)
        spin.valueChanged.connect(lambda v: est.setText(f'예상 금액: {v * price:,}원'))
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec_() == QDialog.Accepted:
            qty = spin.value()
            if QMessageBox.question(
                self, '매수 확인',
                f'[D전략] {code_name}  {qty}주  시장가 매수?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            ) == QMessageBox.Yes:
                db.insert_manual_order('BUY', code, code_name, qty, strategy_type='D')
                QMessageBox.information(self, '접수',
                    f'{code_name} D전략 매수 접수 완료\n(strategy_type=D 저장)')

    def _sell_dialog(self, code, code_name):
        if QMessageBox.question(
            self, '매도 확인',
            f'[D전략] {code_name} ({code})  전량 시장가 매도?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) == QMessageBox.Yes:
            db.insert_manual_order('SELL', code, code_name, 0)
            QMessageBox.information(self, '접수', f'{code_name} 긴급 매도 접수')


# ── 모듈 레벨 헬퍼 ─────────────────────────────────────────────────────
def _fix_cols(table, widths):
    hdr = table.horizontalHeader()
    hdr.setSectionResizeMode(QHeaderView.Interactive)
    hdr.setStretchLastSection(False)
    for i, w in enumerate(widths):
        hdr.resizeSection(i, w)
