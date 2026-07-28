"""
JackBot Control Panel — PyQt5 데스크탑 HTS
실행: python control_panel/main.py  (py37_32 환경)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget,
    QStatusBar, QLabel, QVBoxLayout,
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont, QIcon

from control_panel import db
from control_panel.tabs.tab_dashboard  import DashboardTab
from control_panel.tabs.tab_positions  import PositionsTab
from control_panel.tabs.tab_candidates import CandidatesTab
from control_panel.tabs.tab_history    import HistoryTab
from control_panel.tabs.tab_orders     import OrdersTab
from control_panel.tabs.tab_settings   import SettingsTab
from control_panel.tabs.tab_daily      import DailyTab

REFRESH_INTERVAL_MS = 5_000   # 5초


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('JackBot Control Panel')
        self.resize(1320, 820)
        self.setFont(QFont('Malgun Gothic', 9))

        # ── manual_orders 테이블 자동 생성 ────────────────────────
        try:
            db.ensure_manual_orders_table()
        except Exception as e:
            print(f'[CP] DB init warning: {e}')

        # ── 탭 위젯 ───────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setFont(QFont('Malgun Gothic', 9))
        self.setCentralWidget(self._tabs)

        self._tab_dash   = DashboardTab(self)
        self._tab_pos    = PositionsTab(self)
        self._tab_cand   = CandidatesTab(self)
        self._tab_hist   = HistoryTab(self)
        self._tab_daily  = DailyTab(self)
        self._tab_orders = OrdersTab(self)
        self._tab_set    = SettingsTab(self)

        self._tabs.addTab(self._tab_dash,   '📊 대시보드')
        self._tabs.addTab(self._tab_pos,    '📂 보유종목')
        self._tabs.addTab(self._tab_cand,   '🎯 매수후보')
        self._tabs.addTab(self._tab_hist,   '📋 거래내역')
        self._tabs.addTab(self._tab_daily,  '📅 일별현황')
        self._tabs.addTab(self._tab_orders, '⚡ 즉시주문')
        self._tabs.addTab(self._tab_set,    '⚙️  설정')

        # ── 상태바 ────────────────────────────────────────────────
        status = QStatusBar()
        self.setStatusBar(status)
        self._status_lbl  = QLabel()
        self._update_lbl  = QLabel()
        status.addWidget(self._status_lbl, 1)
        status.addPermanentWidget(self._update_lbl)

        # ── QTimer: 5초 자동 갱신 ─────────────────────────────────
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_all)
        self._timer.start(REFRESH_INTERVAL_MS)

        # 즉시 첫 갱신
        self._refresh_all()

        # ── 다크모드 기본 스타일 ───────────────────────────────────
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #f5f5f5;
                color: #111111;
            }
            QTabWidget::pane {
                border: 1px solid #cccccc;
                background: #f5f5f5;
            }
            QTabBar::tab {
                background: #e0e0e0;
                color: #333333;
                padding: 6px 14px;
                border: 1px solid #cccccc;
                border-bottom: none;
                min-width: 90px;
            }
            QTabBar::tab:selected {
                background: #f5f5f5;
                color: #000000;
                font-weight: bold;
            }
            QTableWidget {
                background: #ffffff;
                alternate-background-color: #f0f4f8;
                color: #111111;
                gridline-color: #cccccc;
                selection-background-color: #b3d7ff;
                selection-color: #000000;
            }
            QHeaderView::section {
                background: #e0e0e0;
                color: #222222;
                padding: 4px;
                border: 1px solid #cccccc;
                font-weight: bold;
            }
            QGroupBox {
                border: 1px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                color: #222222;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                color: #333333;
            }
            QFrame[frameShape="5"] {
                border: 1px solid #cccccc;
                background: #ffffff;
            }
            QLabel { color: #111111; }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit {
                background: #ffffff;
                color: #111111;
                border: 1px solid #aaaaaa;
                border-radius: 3px;
                padding: 2px 4px;
            }
            QPushButton {
                background: #e0e0e0;
                color: #111111;
                border: 1px solid #aaaaaa;
                border-radius: 4px;
                padding: 4px 10px;
            }
            QPushButton:hover { background: #d0d0d0; }
            QScrollBar:vertical {
                background: #e0e0e0;
                width: 10px;
            }
            QScrollBar::handle:vertical {
                background: #aaaaaa;
                border-radius: 5px;
            }
            QStatusBar { background: #e0e0e0; color: #333333; }
        """)

    # ── 갱신 ─────────────────────────────────────────────────────
    def _refresh_all(self):
        try:
            kpis      = db.get_kpis()
            positions = db.get_positions()
            candidates= db.get_candidates(0, '전체')

            self._tab_dash.refresh(kpis)
            self._tab_pos.refresh(positions)
            self._tab_cand.refresh(candidates)
            self._tab_orders.update_positions(positions)

            # 현재 활성 탭에만 갱신 (인덱스: 4=일별현황 5=즉시주문 6=설정)
            active = self._tabs.currentIndex()
            if active == 4:
                self._tab_daily.refresh()
            elif active == 5:
                self._tab_orders.refresh(kpis)
            elif active == 6:
                self._tab_set.refresh()

            self._status_lbl.setText(
                f'🟢 연결됨  |  보유 {kpis["open_count"]}종목  |  '
                f'오늘손익 {kpis["today_pnl"]:+,}원  |  {kpis["trader_status"]}')
            self._update_lbl.setText(
                f'마지막 갱신: {datetime.now().strftime("%H:%M:%S")}')

        except Exception as e:
            self._status_lbl.setText(f'⛔ DB 오류: {e}')


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont('Malgun Gothic', 9))
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
