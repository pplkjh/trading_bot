"""이벤트 로그 탭 — jackbot.log 실시간 tail + 중요 이벤트 필터"""
import os
import re
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QCheckBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor

# 로그 파일 경로 (control_panel/tabs/ → 프로젝트 루트/log/)
LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'log', 'jackbot.log'
)

# 로그 라인 파싱 정규식
_LOG_RE = re.compile(
    r'\[(\w+)\|([^\]]+)\] (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ > (.+)'
)

# 매매 관련 키워드
_TRADE_KW  = ['매수', '매도', '체결', '익절', '손절', '트레일링', '청산', '주문', '수익', '주문접수']
_WARN_KW   = ['WARNING', 'WARN', 'ERROR', 'CRITICAL', '오류', '실패', '에러']

# 이벤트 유형 → (배지 텍스트, 행 배경색, 텍스트색)
def _classify(level: str, msg: str):
    lvl = level.upper()
    if lvl in ('ERROR', 'CRITICAL'):
        return '오류', QColor('#fff0f0'), QColor('#cc0000')
    if lvl in ('WARNING', 'WARN'):
        return '경고', QColor('#fff8e8'), QColor('#b85c00')
    # INFO / DEBUG — 키워드로 세분류
    low = msg
    if any(k in low for k in ['매수 체결', '매수완료', '매수 주문', '주문접수']):
        return '매수', QColor('#f0f8ff'), QColor('#0044bb')
    if any(k in low for k in ['익절', '매도 체결', '매도완료', '매도 주문']):
        return '매도', QColor('#fff0f0'), QColor('#cc0000')
    if '손절' in low:
        return '손절', QColor('#fff0f8'), QColor('#990055')
    if '트레일링' in low:
        return '트레일', QColor('#f8f0ff'), QColor('#6600bb')
    if '청산' in low:
        return '청산', QColor('#f5f5f5'), QColor('#555555')
    if lvl == 'INFO':
        return '정보', QColor('#ffffff'), QColor('#444444')
    return None, None, None  # DEBUG — 필터에서 제외


HEADERS = ['시각', '구분', '내용']
MAX_ENTRIES = 600


class LogTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries   = []   # (time_str, badge, msg, bg, fg)
        self._file_pos  = 0
        self._filter    = 'all'   # 'all' | 'trade' | 'warn' | 'error'
        self._build_ui()
        self._init_log()

        self._tail_timer = QTimer(self)
        self._tail_timer.timeout.connect(self._tail)
        self._tail_timer.start(2_000)

    # ── UI ───────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # 필터 바
        bar = QHBoxLayout()
        bar.setSpacing(6)

        self._filter_btns = {}
        for key, label in [('all', '전체'), ('trade', '매매만'),
                            ('warn', '경고+'), ('error', '오류만')]:
            btn = QPushButton(label)
            btn.setFixedHeight(26)
            btn.setFixedWidth(72)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, k=key: self._set_filter(k))
            bar.addWidget(btn)
            self._filter_btns[key] = btn
        self._filter_btns['all'].setChecked(True)

        bar.addSpacing(12)

        self._auto_scroll = QCheckBox('자동 스크롤')
        self._auto_scroll.setChecked(True)
        bar.addWidget(self._auto_scroll)

        bar.addStretch()

        clear_btn = QPushButton('화면 지우기')
        clear_btn.setFixedWidth(88)
        clear_btn.setFixedHeight(26)
        clear_btn.clicked.connect(self._clear)
        bar.addWidget(clear_btn)

        self._count_lbl = QLabel('0건')
        self._count_lbl.setFont(QFont('Malgun Gothic', 8))
        self._count_lbl.setStyleSheet('color:#888;')
        bar.addWidget(self._count_lbl)

        root.addLayout(bar)

        # 테이블
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(HEADERS)
        self._table.horizontalHeader().setFont(QFont('Malgun Gothic', 8, QFont.Bold))
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setAlternatingRowColors(False)
        self._table.setShowGrid(False)
        self._table.setWordWrap(False)
        self._table.setFont(QFont('Malgun Gothic', 8))

        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.setColumnWidth(0, 72)
        self._table.setColumnWidth(1, 58)

        root.addWidget(self._table)

        self._set_filter('all')

    # ── 필터 ─────────────────────────────────────────────────────────
    def _set_filter(self, key: str):
        self._filter = key
        for k, btn in self._filter_btns.items():
            btn.setChecked(k == key)
            btn.setStyleSheet(
                'background:#0044bb;color:white;border-radius:3px;font-weight:bold;'
                if k == key else '')
        self._render()

    def _should_show(self, badge, msg):
        if self._filter == 'error':
            return badge == '오류'
        if self._filter == 'warn':
            return badge in ('오류', '경고')
        if self._filter == 'trade':
            return badge in ('매수', '매도', '손절', '트레일', '청산')
        return badge is not None  # 'all': DEBUG 제외

    # ── 로그 초기 로드 ───────────────────────────────────────────────
    def _init_log(self):
        if not os.path.exists(LOG_PATH):
            return
        try:
            with open(LOG_PATH, 'r', encoding='utf-8', errors='replace') as f:
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(0, size - 80_000))  # 최근 ~80KB
                lines = f.readlines()
                self._file_pos = f.tell()
            for line in lines[-300:]:
                entry = self._parse(line)
                if entry:
                    self._entries.append(entry)
        except Exception:
            pass
        self._render()

    # ── 실시간 tail ──────────────────────────────────────────────────
    def _tail(self):
        if not os.path.exists(LOG_PATH):
            return
        try:
            with open(LOG_PATH, 'r', encoding='utf-8', errors='replace') as f:
                # 파일이 로테이트됐으면 처음부터
                f.seek(0, 2)
                if f.tell() < self._file_pos:
                    self._file_pos = 0
                f.seek(self._file_pos)
                new_lines = f.readlines()
                self._file_pos = f.tell()
        except Exception:
            return

        if not new_lines:
            return

        added = False
        for line in new_lines:
            entry = self._parse(line)
            if entry:
                self._entries.append(entry)
                added = True

        if len(self._entries) > MAX_ENTRIES:
            self._entries = self._entries[-MAX_ENTRIES:]

        if added:
            self._render()

    # ── 파싱 ─────────────────────────────────────────────────────────
    def _parse(self, line: str):
        line = line.strip()
        if not line:
            return None
        m = _LOG_RE.match(line)
        if not m:
            return None
        level, _src, dt_str, msg = m.groups()
        time_str = dt_str[11:]   # HH:MM:SS
        badge, bg, fg = _classify(level, msg)
        return (time_str, badge, msg, bg, fg)

    # ── 렌더링 ───────────────────────────────────────────────────────
    def _render(self):
        visible = [(t, b, m, bg, fg) for t, b, m, bg, fg in self._entries
                   if self._should_show(b, m)]

        tbl = self._table
        tbl.setUpdatesEnabled(False)
        tbl.setRowCount(len(visible))

        for r, (time_str, badge, msg, bg, fg) in enumerate(visible):
            h = 20
            tbl.setRowHeight(r, h)

            t_item = QTableWidgetItem(time_str)
            t_item.setTextAlignment(Qt.AlignCenter)

            b_item = QTableWidgetItem(badge or '')
            b_item.setTextAlignment(Qt.AlignCenter)
            b_item.setFont(QFont('Malgun Gothic', 7, QFont.Bold))

            m_item = QTableWidgetItem(msg)

            for item in (t_item, b_item, m_item):
                if bg:
                    item.setBackground(bg)
                if fg:
                    item.setForeground(fg)

            tbl.setItem(r, 0, t_item)
            tbl.setItem(r, 1, b_item)
            tbl.setItem(r, 2, m_item)

        tbl.setUpdatesEnabled(True)

        if self._auto_scroll.isChecked() and visible:
            tbl.scrollToBottom()

        total_shown = len(visible)
        total_all   = sum(1 for _, b, _, _, _ in self._entries if b is not None)
        self._count_lbl.setText(f'{total_shown}건 표시 / 전체 {total_all}건')

    # ── 외부 refresh (탭 전환 시) ────────────────────────────────────
    def refresh(self, _=None):
        self._tail()

    def _clear(self):
        self._entries.clear()
        self._table.setRowCount(0)
        self._count_lbl.setText('0건')
