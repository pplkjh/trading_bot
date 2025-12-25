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
