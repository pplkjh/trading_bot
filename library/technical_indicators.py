"""
Technical Indicators Module
기술적 지표 계산 (RSI, 볼린저 밴드, ATR 등)
"""
import pandas as pd
import numpy as np
from typing import Tuple


def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
    """
    RSI (Relative Strength Index) 계산

    Parameters:
    -----------
    prices : pd.Series
        종가 데이터
    period : int
        RSI 기간 (default: 14)

    Returns:
    --------
    float : RSI 값 (0-100), 계산 불가 시 50 반환
    """
    if len(prices) < period + 1:
        return 50.0

    try:
        # 가격 변화 계산
        delta = prices.diff()

        # 상승/하락 분리
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        # 평균 계산 (Wilder's smoothing)
        avg_gain = gain.rolling(window=period, min_periods=period).mean().iloc[-1]
        avg_loss = loss.rolling(window=period, min_periods=period).mean().iloc[-1]

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return round(rsi, 2)

    except Exception as e:
        return 50.0


def calculate_bollinger_bands(prices: pd.Series, period: int = 20, std_dev: float = 2.0) -> Tuple[float, float, float]:
    """
    볼린저 밴드 (Bollinger Bands) 계산

    Parameters:
    -----------
    prices : pd.Series
        종가 데이터
    period : int
        이동평균 기간 (default: 20)
    std_dev : float
        표준편차 배수 (default: 2.0)

    Returns:
    --------
    Tuple[float, float, float] : (상단, 중간, 하단), 계산 불가 시 (0, 0, 0)
    """
    if len(prices) < period:
        return (0.0, 0.0, 0.0)

    try:
        # 중간선 (20일 이동평균)
        middle = prices.rolling(window=period).mean().iloc[-1]

        # 표준편차
        std = prices.rolling(window=period).std().iloc[-1]

        # 상단/하단
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)

        return (round(upper, 2), round(middle, 2), round(lower, 2))

    except Exception as e:
        return (0.0, 0.0, 0.0)


def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
    """
    ATR (Average True Range) 계산

    Parameters:
    -----------
    high : pd.Series
        고가 데이터
    low : pd.Series
        저가 데이터
    close : pd.Series
        종가 데이터
    period : int
        ATR 기간 (default: 14)

    Returns:
    --------
    float : ATR 값, 계산 불가 시 0 반환
    """
    if len(high) < period + 1 or len(low) < period + 1 or len(close) < period + 1:
        return 0.0

    try:
        # True Range 계산
        high_low = high - low
        high_close = np.abs(high - close.shift())
        low_close = np.abs(low - close.shift())

        # 세 값 중 최대값이 True Range
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

        # ATR = True Range의 이동평균
        atr = true_range.rolling(window=period, min_periods=period).mean().iloc[-1]

        return round(atr, 2)

    except Exception as e:
        return 0.0


def calculate_ma_cross(prices: pd.Series, short_period: int = 5, long_period: int = 20) -> str:
    """
    이동평균선 교차 상태 확인

    Parameters:
    -----------
    prices : pd.Series
        종가 데이터
    short_period : int
        단기 이동평균 기간
    long_period : int
        장기 이동평균 기간

    Returns:
    --------
    str : 'golden' (골든크로스), 'dead' (데드크로스), 'none' (교차 없음)
    """
    if len(prices) < long_period + 1:
        return 'none'

    try:
        ma_short = prices.rolling(window=short_period).mean()
        ma_long = prices.rolling(window=long_period).mean()

        # 현재와 이전 값 비교
        current_short = ma_short.iloc[-1]
        current_long = ma_long.iloc[-1]
        prev_short = ma_short.iloc[-2]
        prev_long = ma_long.iloc[-2]

        # 골든크로스 (단기가 장기를 상향 돌파)
        if prev_short <= prev_long and current_short > current_long:
            return 'golden'

        # 데드크로스 (단기가 장기를 하향 돌파)
        if prev_short >= prev_long and current_short < current_long:
            return 'dead'

        return 'none'

    except Exception as e:
        return 'none'


def calculate_volume_ratio(volume: pd.Series, period: int = 20) -> float:
    """
    거래량 비율 계산 (현재 거래량 / 평균 거래량)

    Parameters:
    -----------
    volume : pd.Series
        거래량 데이터
    period : int
        평균 기간 (default: 20)

    Returns:
    --------
    float : 거래량 비율, 계산 불가 시 1.0 반환
    """
    if len(volume) < period:
        return 1.0

    try:
        current_volume = volume.iloc[-1]
        avg_volume = volume.rolling(window=period).mean().iloc[-1]

        if avg_volume == 0:
            return 1.0

        ratio = current_volume / avg_volume
        return round(ratio, 2)

    except Exception as e:
        return 1.0


# ===== v2 확장 지표 함수 =====

def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """지수이동평균 (EMA)"""
    return series.ewm(span=period, adjust=False).mean()


def calculate_macd(close_series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD, Signal, Histogram

    Parameters:
    -----------
    close_series : pd.Series (최소 slow+signal 행 이상)
    fast, slow, signal : int

    Returns:
    --------
    Tuple[float, float, float] : (macd값, signal값, histogram값)
    계산 불가 시 (0.0, 0.0, 0.0)
    """
    if len(close_series) < slow + signal:
        return (0.0, 0.0, 0.0)
    try:
        ema_fast = calculate_ema(close_series, fast)
        ema_slow = calculate_ema(close_series, slow)
        macd_line = ema_fast - ema_slow
        signal_line = calculate_ema(macd_line, signal)
        histogram = macd_line - signal_line
        return (round(float(macd_line.iloc[-1]), 2),
                round(float(signal_line.iloc[-1]), 2),
                round(float(histogram.iloc[-1]), 2))
    except Exception:
        return (0.0, 0.0, 0.0)


def calculate_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14):
    """ADX (Average Directional Index) — 추세 강도 0~100

    Returns:
    --------
    Tuple[float, float, float] : (adx, plus_di, minus_di)
    계산 불가 시 (0.0, 0.0, 0.0)
    """
    if len(high) < period * 2:
        return (0.0, 0.0, 0.0)
    try:
        plus_dm = high.diff()
        minus_dm = low.diff() * -1
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.ewm(alpha=1 / period, min_periods=period).mean()
        plus_di = 100 * (plus_dm.ewm(alpha=1 / period, min_periods=period).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(alpha=1 / period, min_periods=period).mean() / atr)

        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1)
        adx_val = dx.ewm(alpha=1 / period, min_periods=period).mean()

        return (round(float(adx_val.iloc[-1]), 2),
                round(float(plus_di.iloc[-1]), 2),
                round(float(minus_di.iloc[-1]), 2))
    except Exception:
        return (0.0, 0.0, 0.0)


def calculate_obv(close_series: pd.Series, volume_series: pd.Series) -> float:
    """On-Balance Volume

    Returns:
    --------
    float : 최신 OBV 값, 계산 불가 시 0.0
    """
    if len(close_series) < 2:
        return 0.0
    try:
        direction = close_series.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
        obv = (volume_series * direction).cumsum()
        return round(float(obv.iloc[-1]), 2)
    except Exception:
        return 0.0


def calculate_mfi(high: pd.Series, low: pd.Series, close: pd.Series,
                  volume: pd.Series, period: int = 14) -> float:
    """Money Flow Index — 거래량 가중 RSI (0~100)

    Returns:
    --------
    float : 최신 MFI 값, 계산 불가 시 50.0
    """
    if len(high) < period + 1:
        return 50.0
    try:
        tp = (high + low + close) / 3
        rmf = tp * volume
        tp_diff = tp.diff()
        pos_flow = rmf.where(tp_diff > 0, 0.0).rolling(period).sum()
        neg_flow = rmf.where(tp_diff <= 0, 0.0).rolling(period).sum()
        mfi = 100 - (100 / (1 + pos_flow / neg_flow.replace(0, 1)))
        return round(float(mfi.iloc[-1]), 2)
    except Exception:
        return 50.0


def calculate_cmf(high: pd.Series, low: pd.Series, close: pd.Series,
                  volume: pd.Series, period: int = 20) -> float:
    """Chaikin Money Flow (-1 ~ +1)

    Returns:
    --------
    float : 최신 CMF 값, 계산 불가 시 0.0
    """
    if len(high) < period:
        return 0.0
    try:
        hl_range = (high - low).replace(0, 1)
        clv = ((close - low) - (high - close)) / hl_range
        cmf = ((clv * volume).rolling(period).sum() /
               volume.rolling(period).sum().replace(0, 1))
        return round(float(cmf.iloc[-1]), 4)
    except Exception:
        return 0.0


def calculate_ichimoku(high: pd.Series, low: pd.Series, close: pd.Series):
    """일목균형표 핵심 4선

    Returns:
    --------
    Tuple[float, float, float, float] : (tenkan, kijun, senkou_a, senkou_b)
    계산 불가 시 (0.0, 0.0, 0.0, 0.0)
    """
    if len(high) < 52:
        return (0.0, 0.0, 0.0, 0.0)
    try:
        tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
        kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
        senkou_a = (tenkan + kijun) / 2
        senkou_b = (high.rolling(52).max() + low.rolling(52).min()) / 2
        return (round(float(tenkan.iloc[-1]), 2),
                round(float(kijun.iloc[-1]), 2),
                round(float(senkou_a.iloc[-1]), 2),
                round(float(senkou_b.iloc[-1]), 2))
    except Exception:
        return (0.0, 0.0, 0.0, 0.0)


def calculate_pivot_points(prev_high: float, prev_low: float, prev_close: float):
    """전일 OHLC 기반 피봇 포인트

    Parameters:
    -----------
    prev_high, prev_low, prev_close : float (전일 고가, 저가, 종가)

    Returns:
    --------
    Tuple[float, float, float, float, float] : (pivot, s1, s2, r1, r2)
    """
    try:
        pivot = (prev_high + prev_low + prev_close) / 3
        s1 = 2 * pivot - prev_high
        s2 = pivot - (prev_high - prev_low)
        r1 = 2 * pivot - prev_low
        r2 = pivot + (prev_high - prev_low)
        return (round(pivot, 2), round(s1, 2), round(s2, 2),
                round(r1, 2), round(r2, 2))
    except Exception:
        return (0.0, 0.0, 0.0, 0.0, 0.0)


def detect_candle_pattern(open_val: float, high_val: float, low_val: float, close_val: float,
                          prev_open: float, prev_high: float, prev_low: float, prev_close: float) -> float:
    """캔들 패턴 감지 — 반전 신호 점수 (0~10)

    Returns:
    --------
    float : pattern_score (0~10)
    """
    try:
        score = 0.0
        body = abs(close_val - open_val)
        total_range = high_val - low_val if high_val != low_val else 1
        lower_shadow = min(open_val, close_val) - low_val
        upper_shadow = high_val - max(open_val, close_val)
        is_bullish = close_val > open_val
        prev_is_bearish = prev_close < prev_open

        # 망치형 (Hammer): 긴 아래꼬리 + 짧은 몸통
        if lower_shadow > body * 2 and upper_shadow < body * 0.3 and is_bullish:
            score += 4

        # 상승 장악형 (Bullish Engulfing)
        if (is_bullish and prev_is_bearish and
                open_val <= prev_close and close_val >= prev_open):
            score += 4

        # 도지 (Doji): 시가 ≈ 종가
        if body / total_range < 0.1:
            score += 2

        return min(10.0, score)
    except Exception:
        return 0.0


def calculate_bollinger_bandwidth(bb_upper: float, bb_middle: float, bb_lower: float) -> float:
    """볼린저 밴드 폭 (스퀴즈 감지용)

    Returns:
    --------
    float : bandwidth, 계산 불가 시 0.0
    """
    if not bb_middle or bb_middle == 0:
        return 0.0
    try:
        return round(float((bb_upper - bb_lower) / bb_middle), 4)
    except Exception:
        return 0.0


def calculate_rs_vs_market(stock_return_20d: float, market_return_20d: float) -> float:
    """상대강도 (RS) — 종목 수익률 / 시장 수익률

    Parameters:
    -----------
    stock_return_20d, market_return_20d : float (예: 0.05 = 5%)

    Returns:
    --------
    float : rs_ratio (>1이면 아웃퍼폼), 계산 불가 시 1.0
    """
    try:
        if market_return_20d == 0:
            return 1.0
        return round((1 + stock_return_20d) / (1 + market_return_20d), 4)
    except Exception:
        return 1.0


# 테스트 코드
if __name__ == "__main__":
    print("=== Technical Indicators 테스트 ===\n")

    # 샘플 데이터 생성
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=50, freq='D')

    # 가격 데이터 (랜덤 워크)
    prices = pd.Series([50000])
    for _ in range(49):
        change = np.random.normal(0, 500)
        prices = pd.concat([prices, pd.Series([prices.iloc[-1] + change])])
    prices.index = dates

    # High/Low 생성
    high = prices * 1.02
    low = prices * 0.98

    # 거래량 데이터
    volume = pd.Series(np.random.randint(100000, 500000, 50), index=dates)

    # 지표 계산
    print(f"현재가: {prices.iloc[-1]:,.0f}원")
    print(f"\n1. RSI(14): {calculate_rsi(prices, 14):.2f}")

    bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(prices, 20)
    print(f"\n2. 볼린저 밴드(20, 2)")
    print(f"   상단: {bb_upper:,.0f}원")
    print(f"   중간: {bb_middle:,.0f}원")
    print(f"   하단: {bb_lower:,.0f}원")

    atr = calculate_atr(high, low, prices, 14)
    print(f"\n3. ATR(14): {atr:,.0f}원")

    ma_cross = calculate_ma_cross(prices, 5, 20)
    print(f"\n4. 이동평균 교차: {ma_cross}")

    vol_ratio = calculate_volume_ratio(volume, 20)
    print(f"\n5. 거래량 비율: {vol_ratio:.2f}배")

    print("\n✅ Technical Indicators 모듈 생성 완료!")
