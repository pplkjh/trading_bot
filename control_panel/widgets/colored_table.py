"""
수익/손실 컬러 QTableWidget 공통 위젯.
한국 HTS 관례: 수익=빨강(#cc0000), 손실=파랑(#0044bb)
"""
from typing import List
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont


RED  = QColor('#cc0000')
BLUE = QColor('#0044bb')
GRAY = QColor('#888888')


class ColoredTable(QTableWidget):
    """정렬·크기 조정 지원 + 컬러 셀 헬퍼를 내장한 기본 테이블."""

    def __init__(self, headers: List[str], parent=None):
        super().__init__(0, len(headers), parent)
        self.setHorizontalHeaderLabels(headers)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.setFont(QFont('Malgun Gothic', 9))

    def set_rows(self, data: List[list]):
        """data: list of row-lists. 각 셀은 str/int/float 또는 (value, color) 튜플."""
        was_sorting = self.isSortingEnabled()
        self.setSortingEnabled(False)   # 삽입 중 자동 재정렬 방지
        self.setRowCount(len(data))
        for r, row in enumerate(data):
            for c, cell in enumerate(row):
                if isinstance(cell, tuple):
                    val, color = cell
                else:
                    val, color = cell, None
                item = NumericTableItem(val)
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if color:
                    item.setForeground(color)
                self.setItem(r, c, item)
            self.setRowHeight(r, 22)
        self.setSortingEnabled(was_sorting)  # 호출 전 상태로 복원

    @staticmethod
    def pnl_color(value) -> QColor:
        try:
            return RED if float(value) >= 0 else BLUE
        except Exception:
            return GRAY

    def clear_rows(self):
        self.setRowCount(0)


class NumericTableItem(QTableWidgetItem):
    """숫자 문자열도 숫자 순서로 정렬되는 아이템."""

    def __init__(self, value):
        self._raw = value
        display = self._format(value)
        super().__init__(display)

    @staticmethod
    def _format(v) -> str:
        if v is None:
            return ''
        return str(v)

    def __lt__(self, other):
        try:
            return float(str(self._raw).replace(',', '').replace('%', '').replace('원', '').strip()) < \
                   float(str(other._raw).replace(',', '').replace('%', '').replace('원', '').strip())
        except Exception:
            return str(self._raw) < str(other._raw)
