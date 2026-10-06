"""
보유 종목 주가 차트 위젯.
matplotlib을 PyQt5에 임베드 — 캔들스틱 + MA5/20 + 볼린저밴드 + RSI14 + 거래량 + 매수가/트레일링스톱 라인
"""
import matplotlib
try:
    matplotlib.use('Qt5Agg')
except Exception:
    pass
matplotlib.rcParams['font.family'] = ['Malgun Gothic', 'sans-serif']
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


# ── 컬러 팔레트 ────────────────────────────────────────────────────────
C_UP     = '#cc0000'   # 상승 캔들
C_DOWN   = '#0044bb'   # 하락 캔들
C_MA5    = '#e07b00'   # MA5
C_MA20   = '#6600cc'   # MA20
C_BUY    = '#008800'   # 매수가 라인
C_TSTOP  = '#cc0000'   # 트레일링스톱 라인
C_RSI    = '#0077cc'   # RSI 라인
C_RSI_OB = '#cc0000'   # 과매수 70선
C_RSI_OS = '#0044bb'   # 과매도 30선
C_BB_UP  = '#888888'   # BB 상단
C_BB_LO  = '#888888'   # BB 하단
C_VOL_UP = '#ffaaaa'   # 상승 거래량
C_VOL_DN = '#aabbff'   # 하락 거래량
BG       = '#f8f8f8'


def _ma(closes, n):
    result = [None] * len(closes)
    for i in range(n - 1, len(closes)):
        result[i] = sum(closes[i - n + 1:i + 1]) / n
    return result


def _rsi(closes, period=14):
    """Wilder smoothing RSI."""
    result = [None] * len(closes)
    if len(closes) < period + 1:
        return result

    # 초기 평균 gain/loss
    gains, losses = [], []
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        result[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100 - (100 / (1 + rs))

    # Wilder 스무딩
    for i in range(period + 1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gain = max(diff, 0)
        loss = max(-diff, 0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100 - (100 / (1 + rs))

    return result


def _bb(closes, period=20, k=2.0):
    """볼린저 밴드 — (upper, middle, lower) 각각 len(closes) 크기 리스트."""
    upper  = [None] * len(closes)
    middle = [None] * len(closes)
    lower  = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1:i + 1]
        avg = sum(window) / period
        std = (sum((v - avg) ** 2 for v in window) / period) ** 0.5
        middle[i] = avg
        upper[i]  = avg + k * std
        lower[i]  = avg - k * std
    return upper, middle, lower


class PriceChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self._placeholder = QLabel('← 보유 종목을 클릭하면 차트가 표시됩니다')
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setFont(QFont('Malgun Gothic', 10))
        self._placeholder.setStyleSheet('color:#aaa;')
        lay.addWidget(self._placeholder)

        self._fig = Figure(figsize=(8, 5), facecolor=BG)
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._canvas.setVisible(False)
        lay.addWidget(self._canvas)

    def plot(self, rows, title,
             entry_price=0, trailing_stop=0,
             buy_date='', strategy=''):
        """
        rows: list of dict {date, open, high, low, close, volume}
        3-panel layout — 캔들(55%) / RSI(25%) / 볼륨(20%)
        """
        if not rows:
            self._show_placeholder('데이터 없음')
            return

        rows = sorted(rows, key=lambda r: r['date'])
        dates   = [r['date'] for r in rows]
        opens   = [float(r['open'])   for r in rows]
        highs   = [float(r['high'])   for r in rows]
        lows    = [float(r['low'])    for r in rows]
        closes  = [float(r['close'])  for r in rows]
        volumes = [float(r['volume']) for r in rows]

        xs = list(range(len(dates)))
        n  = len(xs)

        ma5   = _ma(closes, 5)
        ma20  = _ma(closes, 20)
        rsi14 = _rsi(closes, 14)
        bb_upper, bb_mid, bb_lower = _bb(closes, 20, 2.0)

        self._fig.clear()

        # ── 3단 서브플롯 (캔들55% / RSI25% / 볼륨20%) ───────────────
        ax1 = self._fig.add_axes([0.07, 0.37, 0.89, 0.55], facecolor=BG)
        ax2 = self._fig.add_axes([0.07, 0.19, 0.89, 0.16], facecolor=BG,
                                  sharex=ax1)
        ax3 = self._fig.add_axes([0.07, 0.04, 0.89, 0.13], facecolor=BG,
                                  sharex=ax1)

        # ── 캔들스틱 ────────────────────────────────────────────────
        for i in xs:
            o, h, l, c = opens[i], highs[i], lows[i], closes[i]
            color = C_UP if c >= o else C_DOWN
            ax1.plot([i, i], [l, h], color=color, linewidth=0.8, zorder=1)
            body_h = abs(c - o) or (h - l) * 0.01
            rect = mpatches.Rectangle(
                (i - 0.3, min(o, c)), 0.6, body_h,
                facecolor=color, edgecolor=color, linewidth=0, zorder=2)
            ax1.add_patch(rect)

        # ── MA 라인 ─────────────────────────────────────────────────
        ma5_pts  = [(i, v) for i, v in zip(xs, ma5)  if v is not None]
        ma20_pts = [(i, v) for i, v in zip(xs, ma20) if v is not None]
        if ma5_pts:
            ax1.plot(*zip(*ma5_pts),  color=C_MA5,  linewidth=1.2,
                     label='MA5',  zorder=3)
        if ma20_pts:
            ax1.plot(*zip(*ma20_pts), color=C_MA20, linewidth=1.2,
                     label='MA20', zorder=3)

        # ── 볼린저 밴드 ─────────────────────────────────────────────
        bb_u_pts = [(i, v) for i, v in zip(xs, bb_upper) if v is not None]
        bb_l_pts = [(i, v) for i, v in zip(xs, bb_lower) if v is not None]
        if bb_u_pts and bb_l_pts:
            ux, uy = zip(*bb_u_pts)
            lx, ly = zip(*bb_l_pts)
            ax1.plot(ux, uy, color=C_BB_UP, linewidth=0.8, linestyle='--',
                     alpha=0.6, zorder=2, label='BB±2σ')
            ax1.plot(lx, ly, color=C_BB_LO, linewidth=0.8, linestyle='--',
                     alpha=0.6, zorder=2)
            # 밴드 내부 음영
            ax1.fill_between(ux, ly, uy, alpha=0.05, color='#888888', zorder=1)

        # ── 매수가 / 트레일링스톱 수평선 ───────────────────────────
        if entry_price > 0:
            ax1.axhline(entry_price, color=C_BUY, linewidth=1.2,
                        linestyle='--', alpha=0.85, zorder=4,
                        label='매수가 {:,}'.format(int(entry_price)))
        if trailing_stop > 0:
            ax1.axhline(trailing_stop, color=C_TSTOP, linewidth=1.2,
                        linestyle=':', alpha=0.85, zorder=4,
                        label='트레일링스톱 {:,}'.format(int(trailing_stop)))

        # ── 매수일 수직선 ───────────────────────────────────────────
        buy_idx = None
        if buy_date:
            bd8 = ''.join(c for c in str(buy_date) if c.isdigit())[:8]
            if bd8 in dates:
                buy_idx = dates.index(bd8)
                for ax in (ax1, ax2, ax3):
                    ax.axvline(buy_idx, color=C_BUY, linewidth=1.2,
                               linestyle='-', alpha=0.3, zorder=3)
                # 매수 텍스트는 RSI 패널에 표시
                ax2.text(buy_idx + 0.3, 15, '매수',
                         color=C_BUY, fontsize=6, va='bottom',
                         fontproperties=_korean_font())

        # ── 현재가 레이블 ───────────────────────────────────────────
        last_close = closes[-1]
        ax1.annotate('{:,}'.format(int(last_close)),
                     xy=(n - 1, last_close),
                     xytext=(n - 0.3, last_close),
                     fontsize=7, color='#333', va='center',
                     fontproperties=_korean_font())

        ax1.legend(loc='upper left', fontsize=6,
                   prop=_korean_font(size=6), framealpha=0.7)
        ax1.set_title('{title}  [{strat}]'.format(title=title, strat=strategy),
                      fontsize=10, fontproperties=_korean_font(size=10), pad=4)
        ax1.yaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(lambda v, _: '{:,}'.format(int(v))))
        ax1.set_xlim(-0.5, n - 0.5)
        ax1.grid(axis='y', color='#dddddd', linewidth=0.5)
        ax1.tick_params(axis='x', labelbottom=False)
        ax1.tick_params(axis='y', labelsize=7)

        # ── RSI ─────────────────────────────────────────────────────
        rsi_pts = [(i, v) for i, v in zip(xs, rsi14) if v is not None]
        if rsi_pts:
            rx, ry = zip(*rsi_pts)
            # 구간별 색상 채우기: 30~70 사이 배경
            ax2.fill_between(rx, 30, 70, alpha=0.07, color='#888888')
            ax2.plot(rx, ry, color=C_RSI, linewidth=1.3, zorder=3)

            # 현재 RSI 값 오른쪽 레이블
            cur_rsi = ry[-1]
            rsi_color = C_RSI_OB if cur_rsi >= 70 else (
                C_RSI_OS if cur_rsi <= 30 else C_RSI)
            ax2.annotate('{:.0f}'.format(cur_rsi),
                         xy=(rx[-1], cur_rsi),
                         xytext=(rx[-1] + 0.3, cur_rsi),
                         fontsize=7, color=rsi_color, va='center',
                         fontproperties=_korean_font())

        ax2.axhline(70, color=C_RSI_OB, linewidth=0.8, linestyle='--', alpha=0.7)
        ax2.axhline(50, color='#aaaaaa', linewidth=0.6, linestyle=':',  alpha=0.5)
        ax2.axhline(30, color=C_RSI_OS, linewidth=0.8, linestyle='--', alpha=0.7)
        ax2.set_ylim(0, 100)
        ax2.set_yticks([30, 50, 70])
        ax2.tick_params(axis='y', labelsize=6)
        ax2.tick_params(axis='x', labelbottom=False)
        ax2.grid(axis='y', color='#eeeeee', linewidth=0.4)
        ax2.set_ylabel('RSI', fontsize=7, fontproperties=_korean_font(size=7))

        # 과매수/과매도 텍스트
        ax2.text(-0.5, 71, '과매수', fontsize=5, color=C_RSI_OB, va='bottom',
                 fontproperties=_korean_font(size=5))
        ax2.text(-0.5, 28, '과매도', fontsize=5, color=C_RSI_OS, va='top',
                 fontproperties=_korean_font(size=5))

        # ── 거래량 ──────────────────────────────────────────────────
        for i in xs:
            color = C_VOL_UP if closes[i] >= opens[i] else C_VOL_DN
            ax3.bar(i, volumes[i], color=color, width=0.6, zorder=2)
        ax3.yaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(
                lambda v, _: '{:,}만'.format(int(v / 10000)) if v >= 10000 else str(int(v))))
        ax3.tick_params(axis='y', labelsize=6)
        ax3.grid(axis='y', color='#eeeeee', linewidth=0.4)
        ax3.set_ylabel('거래량', fontsize=7, fontproperties=_korean_font(size=7))

        # ── x축 날짜 레이블 (ax3만) ─────────────────────────────────
        step = max(1, n // 8)
        ax3.set_xticks(xs[::step])
        ax3.set_xticklabels(
            ['{}/{}'.format(d[4:6], d[6:8]) for d in dates[::step]],
            fontsize=7, rotation=0)

        self._placeholder.setVisible(False)
        self._canvas.setVisible(True)
        self._canvas.draw()

    def _show_placeholder(self, msg='← 보유 종목을 클릭하면 차트가 표시됩니다'):
        self._placeholder.setText(msg)
        self._placeholder.setVisible(True)
        self._canvas.setVisible(False)


def _korean_font(size=8):
    from matplotlib.font_manager import FontProperties
    return FontProperties(fname=r'C:\Windows\Fonts\malgun.ttf', size=size)
