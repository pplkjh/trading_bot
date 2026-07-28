"""Tab 1 — 보유 종목: 실시간 포지션 + 리스크 모니터링 + 주가 차트"""
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QMenu, QAction, QDialog, QDialogButtonBox,
    QSpinBox, QFormLayout, QMessageBox, QFrame, QPushButton,
    QSplitter,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

from control_panel.widgets.colored_table import ColoredTable, RED, BLUE, GRAY
from control_panel.widgets.price_chart import PriceChart
from control_panel import db

HEADERS = ['종목명', '전략', '매수점수', '현재가', '매수가', '수익률%', '미실현손익',
           '수량', '보유일', '최고가', '트레일링스톱', '여유%']

DANGER_PCT = 2.0


def _trailing_stop(strategy, highest, entry):
    try:
        h = float(highest or entry)
        e = float(entry)
        return max(h * 0.97, e * 1.01) if strategy == 'A' else max(h * 0.95, e * 1.01)
    except Exception:
        return 0.0


def _hold_days(buy_date_str):
    try:
        digits = ''.join(c for c in str(buy_date_str) if c.isdigit())
        return (datetime.today() - datetime.strptime(digits[:8], '%Y%m%d')).days
    except Exception:
        return 0


def _kpi(label) -> tuple:
    frame = QFrame()
    frame.setFrameShape(QFrame.StyledPanel)
    frame.setStyleSheet(
        'QFrame{border:1px solid #ccc;border-radius:4px;background:#fff;padding:2px;}')
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(8, 4, 8, 4)
    lay.setSpacing(1)
    l = QLabel(label)
    l.setFont(QFont('Malgun Gothic', 7))
    l.setStyleSheet('color:#888;border:none;')
    v = QLabel('—')
    v.setFont(QFont('Malgun Gothic', 11, QFont.Bold))
    v.setStyleSheet('color:#111;border:none;')
    v.setTextInteractionFlags(Qt.TextSelectableByMouse)
    lay.addWidget(l)
    lay.addWidget(v)
    return frame, v


class PositionsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows_cache     = []   # DB에서 온 전체 보유 목록
        self._displayed_rows = []   # 현재 테이블 행 순서와 1:1 대응
        self._filter_mode    = 'all'    # 'all' | 'danger'
        self._sort_col       = None     # 정렬 컬럼 인덱스 (None=정렬없음)
        self._sort_asc       = True     # 오름차순 여부
        self._selected_code  = None     # 선택 유지용 종목코드
        self._build_ui()

    # ── UI 빌드 ───────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # KPI 카드 바
        kpi_lay = QHBoxLayout()
        kpi_lay.setSpacing(8)
        self._kpis = {}
        for key, label in [
            ('count',      '보유 종목'),
            ('unrealized', '미실현 손익'),
            ('avg_rate',   '평균 수익률'),
            ('avg_days',   '평균 보유일'),
            ('danger',     '트레일링 임박'),
            ('a_count',    '전략 A / B'),
        ]:
            frame, val = _kpi(label)
            self._kpis[key] = val
            kpi_lay.addWidget(frame)
        root.addLayout(kpi_lay)

        # 툴바
        toolbar = QHBoxLayout()
        self._filter_lbl = QLabel('')
        self._filter_lbl.setFont(QFont('Malgun Gothic', 8))
        self._filter_lbl.setStyleSheet('color:#888;')
        toolbar.addWidget(self._filter_lbl)
        toolbar.addStretch()

        self._danger_btn = QPushButton('⚠ 임박 종목만')
        self._danger_btn.setFixedHeight(26)
        self._danger_btn.setFixedWidth(115)
        self._danger_btn.clicked.connect(self._filter_danger)
        toolbar.addWidget(self._danger_btn)

        all_btn = QPushButton('전체 보기')
        all_btn.setFixedHeight(26)
        all_btn.setFixedWidth(70)
        all_btn.clicked.connect(self._show_all)
        toolbar.addWidget(all_btn)

        root.addLayout(toolbar)

        # QSplitter: 위=테이블 / 아래=차트
        splitter = QSplitter(Qt.Vertical)

        table_widget = QWidget()
        tlay = QVBoxLayout(table_widget)
        tlay.setContentsMargins(0, 0, 0, 0)
        self._table = ColoredTable(HEADERS, table_widget)
        self._table.setSortingEnabled(False)   # Qt 자동정렬 끔 — 헤더 클릭은 아래서 직접 처리
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._table.itemSelectionChanged.connect(self._on_row_selected)
        self._table.horizontalHeader().sectionClicked.connect(self._on_header_click)
        tlay.addWidget(self._table)
        splitter.addWidget(table_widget)

        self._chart = PriceChart()
        self._chart.setMinimumHeight(220)
        splitter.addWidget(self._chart)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter)

    # ── 외부에서 호출: 5초마다 새 데이터 수신 ────────────────────────
    def refresh(self, positions: list):
        self._rows_cache = positions
        self._apply_current_view()   # 기존 필터/정렬 상태를 유지한 채 재렌더

    # ── 필터+정렬 상태를 재적용하고 렌더 ─────────────────────────────
    def _apply_current_view(self):
        data = list(self._rows_cache)

        # 필터
        if self._filter_mode == 'danger':
            data = [p for p in data if self._is_danger(p)]

        # 정렬
        if self._sort_col is not None:
            key_fn = self._col_sort_key(self._sort_col)
            data.sort(key=key_fn, reverse=not self._sort_asc)

        self._render(data)

    # ── 실제 렌더링 (선택 행을 종목코드로 복원) ─────────────────────
    def _render(self, positions: list):
        self._displayed_rows = list(positions)

        rows = []
        total_unreal = total_rate = total_days = 0
        danger_cnt = a_cnt = b_cnt = 0

        for p in positions:
            rate_raw = float(p.get('rate') or 0)
            rate    = rate_raw - 100 if rate_raw > 10 else rate_raw
            unreal  = int(p.get('valuation_profit') or 0)
            price   = int(p.get('present_price') or 0)
            entry   = int(p.get('purchase_price') or 0)
            strat   = str(p.get('strategy_type') or 'A')
            highest = float(p.get('highest_price') or price)
            days    = _hold_days(p.get('buy_date', ''))
            ts      = _trailing_stop(strat, highest, entry)
            margin  = ((price - ts) / ts * 100) if ts > 0 else 99.0
            is_dng  = 0 < margin < DANGER_PCT

            total_unreal += unreal
            total_rate   += rate
            total_days   += days
            if is_dng:  danger_cnt += 1
            if strat == 'A': a_cnt += 1
            else:            b_cnt += 1

            pnl_c  = RED if rate >= 0 else BLUE
            ts_c   = QColor('#cc4400') if is_dng else QColor('#888888')
            mg_c   = QColor('#cc4400') if is_dng else (
                     QColor('#008800') if margin > 5 else QColor('#888888'))
            score  = int(p.get('composite_score') or 0)
            sc_c   = RED if score >= 120 else (
                     QColor('#e07b00') if score >= 90 else None)

            rows.append([
                str(p.get('code_name', '')),
                str(strat),
                (str(score) if score else '—', sc_c),
                (f"{price:,}", None),
                (f"{entry:,}", None),
                (f"{rate:+.2f}%", pnl_c),
                (f"{unreal:+,}원", pnl_c),
                (str(int(p.get('holding_amount', 0))), None),
                (f"{days}일", None),
                (f"{int(highest):,}", None),
                (f"{int(ts):,}", ts_c),
                (f"{margin:+.1f}%", mg_c),
            ])

        # set_rows 중 시그널 차단 → 잘못된 인덱스로 차트 로드 방지
        self._table.blockSignals(True)
        self._table.set_rows(rows)
        self._table.blockSignals(False)

        # 선택 행 복원 (종목코드 기준)
        if self._selected_code:
            for i, p in enumerate(self._displayed_rows):
                if p.get('code') == self._selected_code:
                    self._table.selectRow(i)
                    break

        # KPI 카드 갱신
        n = len(positions)
        avg_rate = total_rate / n if n else 0
        avg_days = total_days / n if n else 0
        unr_c  = '#cc0000' if total_unreal >= 0 else '#0044bb'
        rate_c = '#cc0000' if avg_rate >= 0 else '#0044bb'

        self._kpis['count'].setText(f'{n}종목')
        self._kpis['unrealized'].setText(f'{total_unreal:+,}원')
        self._kpis['unrealized'].setStyleSheet(f'color:{unr_c};font-weight:bold;')
        self._kpis['avg_rate'].setText(f'{avg_rate:+.2f}%')
        self._kpis['avg_rate'].setStyleSheet(f'color:{rate_c};font-weight:bold;')
        self._kpis['avg_days'].setText(f'{avg_days:.1f}일')
        self._kpis['avg_days'].setStyleSheet('color:#111;font-weight:bold;')
        self._kpis['danger'].setText(f'{danger_cnt}건')
        self._kpis['danger'].setStyleSheet(
            f'color:{"#cc4400" if danger_cnt else "#008800"};font-weight:bold;')
        self._kpis['a_count'].setText(f'{a_cnt} / {b_cnt}')
        self._kpis['a_count'].setStyleSheet('color:#111;font-weight:bold;')

        mode_txt = '⚠ 임박 필터' if self._filter_mode == 'danger' else '전체'
        self._filter_lbl.setText(f'{mode_txt} — 표시 {n}종목')

    # ── 행 클릭 → 차트 ───────────────────────────────────────────────
    def _on_row_selected(self):
        row = self._table.currentRow()
        if row < 0 or row >= len(self._displayed_rows):
            return
        p = self._displayed_rows[row]
        self._selected_code = p.get('code')
        self._load_chart(p)

    def _load_chart(self, p: dict):
        code_name = str(p.get('code_name', ''))
        entry     = int(p.get('purchase_price') or 0)
        strat     = str(p.get('strategy_type') or 'A')
        highest   = float(p.get('highest_price') or entry)
        buy_date  = str(p.get('buy_date', ''))
        ts        = _trailing_stop(strat, highest, entry)
        bd8       = ''.join(c for c in buy_date if c.isdigit())[:8]

        ohlcv = db.get_price_history(code_name, days=90)
        if not ohlcv:
            self._chart._show_placeholder(f'{code_name} — 가격 데이터 없음')
            return

        self._chart.plot(
            rows=ohlcv,
            title=code_name,
            entry_price=entry,
            trailing_stop=ts,
            buy_date=bd8,
            strategy=strat,
        )

    # ── 헤더 클릭 정렬 ───────────────────────────────────────────────
    def _on_header_click(self, col: int):
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        self._update_sort_indicator()
        self._apply_current_view()

    def _update_sort_indicator(self):
        from PyQt5.QtWidgets import QTableWidgetItem
        for c, label in enumerate(HEADERS):
            txt = label + (' ▲' if (c == self._sort_col and self._sort_asc) else
                           ' ▼' if (c == self._sort_col and not self._sort_asc) else '')
            self._table.setHorizontalHeaderItem(c, QTableWidgetItem(txt))

    # ── 필터 ──────────────────────────────────────────────────────────
    def _filter_danger(self):
        self._filter_mode = 'danger'
        self._apply_current_view()

    def _show_all(self):
        self._filter_mode = 'all'
        self._apply_current_view()

    # ── 헬퍼 ──────────────────────────────────────────────────────────
    def _is_danger(self, p) -> bool:
        price   = int(p.get('present_price') or 0)
        entry   = int(p.get('purchase_price') or 0)
        strat   = str(p.get('strategy_type') or 'A')
        highest = float(p.get('highest_price') or price)
        ts      = _trailing_stop(strat, highest, entry)
        margin  = ((price - ts) / ts * 100) if ts > 0 else 99.0
        return 0 < margin < DANGER_PCT

    @staticmethod
    def _col_sort_key(col):
        """컬럼 인덱스 → 정렬 key 함수 반환."""
        # HEADERS = ['종목명','전략','매수점수','현재가','매수가','수익률%','미실현손익','수량','보유일','최고가','트레일링스톱','여유%']
        def _rate(p):
            r = float(p.get('rate') or 0)
            return r - 100 if r > 10 else r
        mapping = {
            0: lambda p: str(p.get('code_name', '')),
            1: lambda p: str(p.get('strategy_type', '')),
            2: lambda p: int(p.get('composite_score') or 0),
            3: lambda p: int(p.get('present_price') or 0),
            4: lambda p: int(p.get('purchase_price') or 0),
            5: _rate,
            6: lambda p: int(p.get('valuation_profit') or 0),
            7: lambda p: int(p.get('holding_amount') or 0),
            8: lambda p: _hold_days(p.get('buy_date', '')),
            9: lambda p: float(p.get('highest_price') or 0),
        }
        return mapping.get(col, lambda p: 0)

    # ── 우클릭 컨텍스트 메뉴 ──────────────────────────────────────────
    def _show_context_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._displayed_rows):
            return
        p         = self._displayed_rows[row]
        code      = p.get('code', '')
        code_name = p.get('code_name', '')
        quantity  = int(p.get('holding_amount', 0))
        rate      = float(p.get('rate') or 0)
        rate      = rate - 100 if rate > 10 else rate
        pnl       = int(p.get('valuation_profit') or 0)

        menu     = QMenu(self)
        info_act = QAction(f'수익률 {rate:+.2f}%  /  손익 {pnl:+,}원', self)
        info_act.setEnabled(False)
        menu.addAction(info_act)
        menu.addSeparator()

        act_chart     = QAction('📈 차트 보기', self)
        act_sell_all  = QAction('⚡ 즉시 전량매도', self)
        act_sell_part = QAction('✂  부분 매도…', self)
        menu.addAction(act_chart)
        menu.addSeparator()
        menu.addAction(act_sell_all)
        menu.addAction(act_sell_part)

        action = menu.exec_(self._table.viewport().mapToGlobal(pos))
        if action == act_chart:
            self._selected_code = code
            self._load_chart(p)
        elif action == act_sell_all:
            self._confirm_sell(code, code_name, quantity, rate, pnl)
        elif action == act_sell_part:
            self._partial_sell_dialog(code, code_name, quantity)

    def _confirm_sell(self, code, code_name, quantity, rate, pnl):
        reply = QMessageBox.question(
            self, '매도 확인',
            f'[{code_name}]  {quantity}주  전량 시장가 매도\n\n'
            f'수익률: {rate:+.2f}%\n손익: {pnl:+,}원',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            db.insert_manual_order('SELL', code, code_name, quantity)
            QMessageBox.information(self, '주문 접수',
                f'{code_name} 매도 주문이 접수되었습니다.')

    def _partial_sell_dialog(self, code, code_name, max_qty):
        dlg  = QDialog(self)
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
            db.insert_manual_order(
                'SELL' if qty >= max_qty else 'PART_SELL', code, code_name, qty)
            QMessageBox.information(self, '주문 접수',
                f'{code_name} {qty}주 매도 주문이 접수되었습니다.')
