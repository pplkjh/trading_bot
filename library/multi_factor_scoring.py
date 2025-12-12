"""
Multi-Factor Scoring System
종목 선정을 위한 멀티팩터 스코어링 시스템

팩터 카테고리:
1. 기술적 지표 (Technical Indicators)
2. 모멘텀 지표 (Momentum Indicators)
3. 거래량 지표 (Volume Indicators)
4. 변동성 지표 (Volatility Indicators)
5. 추세 지표 (Trend Indicators)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import pymysql
from library.cf import *


class MultiFactorScoring:
    """
    멀티팩터 스코어링 시스템

    각 팩터별로 점수를 계산하고 가중 평균하여 최종 스코어 산출
    """

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None
    ):
        """
        Parameters:
        -----------
        weights : Dict[str, float]
            팩터별 가중치
            기본값: {
                'technical': 0.25,
                'momentum': 0.30,
                'volume': 0.20,
                'volatility': 0.15,
                'trend': 0.10
            }
        """
        self.weights = weights or {
            'technical': 0.25,
            'momentum': 0.30,
            'volume': 0.20,
            'volatility': 0.15,
            'trend': 0.10
        }

        # 가중치 합이 1이 되도록 정규화
        total = sum(self.weights.values())
        self.weights = {k: v/total for k, v in self.weights.items()}


    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """
        RSI (Relative Strength Index) 계산

        Parameters:
        -----------
        prices : pd.Series
            가격 시계열
        period : int
            RSI 계산 기간

        Returns:
        --------
        float : RSI 값 (0-100)
        """
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return rsi.iloc[-1] if not np.isnan(rsi.iloc[-1]) else 50


    def calculate_macd(
        self,
        prices: pd.Series,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Tuple[float, float, float]:
        """
        MACD (Moving Average Convergence Divergence) 계산

        Returns:
        --------
        Tuple[float, float, float] : (MACD, Signal, Histogram)
        """
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        return (
            macd_line.iloc[-1] if not np.isnan(macd_line.iloc[-1]) else 0,
            signal_line.iloc[-1] if not np.isnan(signal_line.iloc[-1]) else 0,
            histogram.iloc[-1] if not np.isnan(histogram.iloc[-1]) else 0
        )


    def calculate_bollinger_bands(
        self,
        prices: pd.Series,
        period: int = 20,
        std_dev: float = 2.0
    ) -> Tuple[float, float, float, float]:
        """
        볼린저 밴드 계산

        Returns:
        --------
        Tuple[float, float, float, float] : (중간선, 상단, 하단, %B)
        """
        middle = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()

        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)

        # %B: 현재 가격이 밴드 내 어디에 위치하는지 (0~1)
        current_price = prices.iloc[-1]
        percent_b = (current_price - lower.iloc[-1]) / (upper.iloc[-1] - lower.iloc[-1])

        return (
            middle.iloc[-1] if not np.isnan(middle.iloc[-1]) else 0,
            upper.iloc[-1] if not np.isnan(upper.iloc[-1]) else 0,
            lower.iloc[-1] if not np.isnan(lower.iloc[-1]) else 0,
            percent_b if not np.isnan(percent_b) else 0.5
        )


    def calculate_stochastic(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14,
        smooth_k: int = 3
    ) -> Tuple[float, float]:
        """
        Stochastic Oscillator 계산

        Returns:
        --------
        Tuple[float, float] : (%K, %D)
        """
        lowest_low = low.rolling(window=period).min()
        highest_high = high.rolling(window=period).max()

        k_raw = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        k = k_raw.rolling(window=smooth_k).mean()
        d = k.rolling(window=3).mean()

        return (
            k.iloc[-1] if not np.isnan(k.iloc[-1]) else 50,
            d.iloc[-1] if not np.isnan(d.iloc[-1]) else 50
        )


    def calculate_obv(self, close: pd.Series, volume: pd.Series) -> float:
        """
        OBV (On-Balance Volume) 계산

        Returns:
        --------
        float : OBV 변화율 (최근 20일 대비)
        """
        obv = pd.Series(index=close.index, dtype=float)
        obv.iloc[0] = volume.iloc[0]

        for i in range(1, len(close)):
            if close.iloc[i] > close.iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] + volume.iloc[i]
            elif close.iloc[i] < close.iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] - volume.iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i-1]

        # 최근 OBV vs 20일 전 OBV 비교
        if len(obv) >= 20:
            obv_change = (obv.iloc[-1] - obv.iloc[-20]) / abs(obv.iloc[-20]) if obv.iloc[-20] != 0 else 0
        else:
            obv_change = 0

        return obv_change


    def calculate_technical_score(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        기술적 지표 스코어 계산 (0-100)

        Parameters:
        -----------
        df : pd.DataFrame
            OHLCV 데이터 (columns: open, high, low, close, volume)

        Returns:
        --------
        Dict : 각 지표별 스코어 및 종합 스코어
        """
        scores = {}

        # RSI 스코어 (30-70 범위를 50점 기준으로 스코어링)
        # 과매도(30 이하) 또는 과매수(70 이상)에서 높은 점수
        rsi = self.calculate_rsi(df['close'])
        if rsi <= 30:
            rsi_score = 100  # 과매도 - 매수 기회
        elif rsi <= 40:
            rsi_score = 80
        elif rsi <= 50:
            rsi_score = 60
        elif rsi <= 60:
            rsi_score = 50
        elif rsi <= 70:
            rsi_score = 40
        else:
            rsi_score = 20  # 과매수 - 위험

        scores['rsi'] = rsi
        scores['rsi_score'] = rsi_score

        # MACD 스코어
        macd, signal, histogram = self.calculate_macd(df['close'])
        # 히스토그램이 양수이고 증가 추세면 높은 점수
        if histogram > 0:
            macd_score = 80
        elif histogram > -100:  # 약간 음수
            macd_score = 50
        else:
            macd_score = 20

        scores['macd'] = macd
        scores['macd_signal'] = signal
        scores['macd_histogram'] = histogram
        scores['macd_score'] = macd_score

        # 볼린저 밴드 스코어
        bb_middle, bb_upper, bb_lower, percent_b = self.calculate_bollinger_bands(df['close'])
        # %B가 0-0.2 (하단 근처) 또는 0.8-1.0 (상단 근처)일 때 기회
        if percent_b <= 0.2:
            bb_score = 90  # 하단 근처 - 반등 기회
        elif percent_b <= 0.4:
            bb_score = 70
        elif percent_b <= 0.6:
            bb_score = 50
        elif percent_b <= 0.8:
            bb_score = 40
        else:
            bb_score = 30  # 상단 근처 - 조정 위험

        scores['bb_percent_b'] = percent_b
        scores['bb_score'] = bb_score

        # Stochastic 스코어
        stoch_k, stoch_d = self.calculate_stochastic(df['high'], df['low'], df['close'])
        # 20 이하 과매도, 80 이상 과매수
        if stoch_k <= 20:
            stoch_score = 90
        elif stoch_k <= 40:
            stoch_score = 70
        elif stoch_k <= 60:
            stoch_score = 50
        elif stoch_k <= 80:
            stoch_score = 40
        else:
            stoch_score = 20

        scores['stochastic_k'] = stoch_k
        scores['stochastic_d'] = stoch_d
        scores['stochastic_score'] = stoch_score

        # 기술적 지표 종합 스코어
        technical_score = np.mean([
            rsi_score,
            macd_score,
            bb_score,
            stoch_score
        ])

        scores['technical_score'] = technical_score

        return scores


    def calculate_momentum_score(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        모멘텀 지표 스코어 계산 (0-100)

        Returns:
        --------
        Dict : 각 모멘텀 지표별 스코어 및 종합 스코어
        """
        scores = {}

        close = df['close']

        # 다양한 기간의 수익률 계산
        if len(close) >= 5:
            ret_5d = (close.iloc[-1] / close.iloc[-5] - 1) * 100
        else:
            ret_5d = 0

        if len(close) >= 20:
            ret_20d = (close.iloc[-1] / close.iloc[-20] - 1) * 100
        else:
            ret_20d = 0

        if len(close) >= 60:
            ret_60d = (close.iloc[-1] / close.iloc[-60] - 1) * 100
        else:
            ret_60d = 0

        scores['return_5d'] = ret_5d
        scores['return_20d'] = ret_20d
        scores['return_60d'] = ret_60d

        # 5일 모멘텀 스코어
        if ret_5d >= 10:
            score_5d = 100
        elif ret_5d >= 5:
            score_5d = 80
        elif ret_5d >= 2:
            score_5d = 60
        elif ret_5d >= 0:
            score_5d = 40
        elif ret_5d >= -5:
            score_5d = 20
        else:
            score_5d = 0

        # 20일 모멘텀 스코어
        if ret_20d >= 20:
            score_20d = 100
        elif ret_20d >= 10:
            score_20d = 80
        elif ret_20d >= 5:
            score_20d = 60
        elif ret_20d >= 0:
            score_20d = 40
        elif ret_20d >= -10:
            score_20d = 20
        else:
            score_20d = 0

        # 60일 모멘텀 스코어
        if ret_60d >= 30:
            score_60d = 100
        elif ret_60d >= 15:
            score_60d = 80
        elif ret_60d >= 5:
            score_60d = 60
        elif ret_60d >= 0:
            score_60d = 40
        elif ret_60d >= -15:
            score_60d = 20
        else:
            score_60d = 0

        # 모멘텀 종합 스코어 (단기에 더 큰 가중치)
        momentum_score = (score_5d * 0.4) + (score_20d * 0.4) + (score_60d * 0.2)

        scores['momentum_score'] = momentum_score

        return scores


    def calculate_volume_score(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        거래량 지표 스코어 계산 (0-100)

        Returns:
        --------
        Dict : 거래량 지표별 스코어 및 종합 스코어
        """
        scores = {}

        volume = df['volume']
        close = df['close']

        # 평균 거래량 대비 현재 거래량
        avg_volume_20 = volume.rolling(window=20).mean()
        current_volume = volume.iloc[-1]
        avg_vol = avg_volume_20.iloc[-1] if not np.isnan(avg_volume_20.iloc[-1]) else 1

        volume_ratio = current_volume / avg_vol if avg_vol > 0 else 1

        scores['volume_ratio'] = volume_ratio

        # 거래량 비율 스코어
        if volume_ratio >= 3.0:
            vol_ratio_score = 100
        elif volume_ratio >= 2.0:
            vol_ratio_score = 90
        elif volume_ratio >= 1.5:
            vol_ratio_score = 80
        elif volume_ratio >= 1.2:
            vol_ratio_score = 70
        elif volume_ratio >= 1.0:
            vol_ratio_score = 60
        elif volume_ratio >= 0.8:
            vol_ratio_score = 40
        else:
            vol_ratio_score = 20

        # OBV 스코어
        obv_change = self.calculate_obv(close, volume)
        scores['obv_change'] = obv_change

        if obv_change >= 0.3:
            obv_score = 100
        elif obv_change >= 0.15:
            obv_score = 80
        elif obv_change >= 0.05:
            obv_score = 60
        elif obv_change >= 0:
            obv_score = 50
        elif obv_change >= -0.1:
            obv_score = 30
        else:
            obv_score = 10

        # 거래량 종합 스코어
        volume_score = (vol_ratio_score * 0.6) + (obv_score * 0.4)

        scores['volume_score'] = volume_score

        return scores


    def calculate_volatility_score(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        변동성 지표 스코어 계산 (0-100)

        적정 변동성: 너무 낮거나 높으면 감점

        Returns:
        --------
        Dict : 변동성 지표별 스코어 및 종합 스코어
        """
        scores = {}

        close = df['close']
        high = df['high']
        low = df['low']

        # ATR 계산
        high_low = high - low
        high_close = np.abs(high - close.shift())
        low_close = np.abs(low - close.shift())

        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        atr = true_range.rolling(window=14).mean().iloc[-1]

        # ATR의 가격 대비 비율
        atr_pct = (atr / close.iloc[-1] * 100) if close.iloc[-1] > 0 else 0
        scores['atr'] = atr
        scores['atr_pct'] = atr_pct

        # 적정 변동성 범위: 2-5%
        if 2.0 <= atr_pct <= 5.0:
            atr_score = 100  # 이상적
        elif 1.5 <= atr_pct < 2.0 or 5.0 < atr_pct <= 7.0:
            atr_score = 80
        elif 1.0 <= atr_pct < 1.5 or 7.0 < atr_pct <= 10.0:
            atr_score = 60
        elif 0.5 <= atr_pct < 1.0 or 10.0 < atr_pct <= 15.0:
            atr_score = 40
        else:
            atr_score = 20  # 너무 낮거나 높음

        # 역사적 변동성 (20일 표준편차)
        returns = close.pct_change()
        hist_vol = returns.rolling(window=20).std().iloc[-1] * np.sqrt(252) * 100
        scores['historical_volatility'] = hist_vol if not np.isnan(hist_vol) else 0

        # 변동성 종합 스코어
        volatility_score = atr_score

        scores['volatility_score'] = volatility_score

        return scores


    def calculate_trend_score(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        추세 지표 스코어 계산 (0-100)

        이동평균선 배열, ADX 등

        Returns:
        --------
        Dict : 추세 지표별 스코어 및 종합 스코어
        """
        scores = {}

        close = df['close']

        # 이동평균선 계산
        ma5 = close.rolling(window=5).mean().iloc[-1] if len(close) >= 5 else close.iloc[-1]
        ma20 = close.rolling(window=20).mean().iloc[-1] if len(close) >= 20 else close.iloc[-1]
        ma60 = close.rolling(window=60).mean().iloc[-1] if len(close) >= 60 else close.iloc[-1]

        scores['ma5'] = ma5
        scores['ma20'] = ma20
        scores['ma60'] = ma60

        current_price = close.iloc[-1]

        # 이동평균선 정배열 체크
        ma_alignment_score = 0

        # 가격 > MA5
        if current_price > ma5:
            ma_alignment_score += 25

        # MA5 > MA20
        if ma5 > ma20:
            ma_alignment_score += 25

        # MA20 > MA60
        if ma20 > ma60:
            ma_alignment_score += 25

        # 가격이 모든 이평선 위에 있음
        if current_price > ma5 and current_price > ma20 and current_price > ma60:
            ma_alignment_score += 25

        # 이동평균선 기울기
        if len(close) >= 25:
            ma20_slope = (ma20 - close.rolling(window=20).mean().iloc[-5]) / ma20 * 100
            scores['ma20_slope'] = ma20_slope

            if ma20_slope > 2:
                slope_score = 100
            elif ma20_slope > 1:
                slope_score = 80
            elif ma20_slope > 0:
                slope_score = 60
            elif ma20_slope > -1:
                slope_score = 40
            else:
                slope_score = 20
        else:
            slope_score = 50

        # 추세 종합 스코어
        trend_score = (ma_alignment_score * 0.6) + (slope_score * 0.4)

        scores['trend_score'] = trend_score

        return scores


    def calculate_composite_score(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        종합 스코어 계산

        모든 팩터를 결합하여 최종 점수 산출

        Parameters:
        -----------
        df : pd.DataFrame
            OHLCV 데이터

        Returns:
        --------
        Dict : 모든 팩터 점수 및 최종 종합 스코어
        """
        all_scores = {}

        # 각 팩터별 스코어 계산
        technical = self.calculate_technical_score(df)
        momentum = self.calculate_momentum_score(df)
        volume = self.calculate_volume_score(df)
        volatility = self.calculate_volatility_score(df)
        trend = self.calculate_trend_score(df)

        # 모든 스코어 통합
        all_scores.update(technical)
        all_scores.update(momentum)
        all_scores.update(volume)
        all_scores.update(volatility)
        all_scores.update(trend)

        # 최종 종합 스코어 (가중 평균)
        composite_score = (
            technical['technical_score'] * self.weights['technical'] +
            momentum['momentum_score'] * self.weights['momentum'] +
            volume['volume_score'] * self.weights['volume'] +
            volatility['volatility_score'] * self.weights['volatility'] +
            trend['trend_score'] * self.weights['trend']
        )

        all_scores['composite_score'] = composite_score

        # 매수 시그널 (종합 스코어 70 이상)
        all_scores['buy_signal'] = composite_score >= 70

        return all_scores


def get_stock_score(code: str, db_name: str = 'daily_buy_list', lookback: int = 120) -> Dict:
    """
    데이터베이스에서 종목 데이터를 가져와 스코어 계산

    Parameters:
    -----------
    code : str
        종목 코드
    db_name : str
        데이터베이스 이름
    lookback : int
        조회할 데이터 기간

    Returns:
    --------
    Dict : 종합 스코어 및 모든 팩터 점수
    """
    try:
        # 1. stock_item_all에서 종목코드로 종목명 조회
        con = pymysql.connect(
            user=db_id,
            passwd=db_passwd,
            host=db_ip,
<<<<<<< Updated upstream
            db=db_name,
=======
            db='daily_buy_list',
            charset='utf8',
            port=int(db_port)
        )

        query_get_name = f"""
        SELECT code_name FROM stock_item_all WHERE code = '{code}' LIMIT 1
        """
        code_name_result = pd.read_sql(query_get_name, con)
        con.close()

        if len(code_name_result) == 0:
            return {'composite_score': 0, 'error': 'Code not found in stock_item_all'}

        code_name = code_name_result.iloc[0]['code_name']

        # 2. daily_craw에서 일봉 데이터 로드 (종목명을 테이블명으로 사용)
        con = pymysql.connect(
            user=db_id,
            passwd=db_passwd,
            host=db_ip,
            db='daily_craw',
>>>>>>> Stashed changes
            charset='utf8',
            port=int(db_port)
        )

        query = f"""
        SELECT date, open, high, low, close, volume
        FROM `{code_name}`
        WHERE code = '{code}'
        ORDER BY date DESC
        LIMIT {lookback}
        """

        df = pd.read_sql(query, con)
        con.close()

        if len(df) < 20:
            return {'composite_score': 0, 'error': 'Insufficient data'}

        # 데이터 정렬 (오래된 것부터, date 컬럼 사용)
        df = df.sort_values('date').reset_index(drop=True)

        # date 컬럼을 ref_date로 이름 변경 (기존 코드 호환성 유지)
        df = df.rename(columns={'date': 'ref_date'})

        # 스코어 계산
        scorer = MultiFactorScoring()
        scores = scorer.calculate_composite_score(df)

        scores['code'] = code
        scores['current_price'] = df['close'].iloc[-1]

        return scores

    except Exception as e:
        return {'composite_score': 0, 'error': str(e)}


if __name__ == "__main__":
    # 테스트 코드
    print("=== Multi-Factor Scoring System 테스트 ===\n")

    # 샘플 데이터 생성
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=100, freq='D')

    # 상승 추세 데이터
    base_price = 50000
    trend = np.linspace(0, 10000, 100)
    noise = np.random.normal(0, 1000, 100)
    close_prices = base_price + trend + noise

    df_test = pd.DataFrame({
        'ref_date': dates,
        'open': close_prices * 0.99,
        'high': close_prices * 1.02,
        'low': close_prices * 0.98,
        'close': close_prices,
        'volume': np.random.randint(100000, 500000, 100)
    })

    # 스코어 계산
    scorer = MultiFactorScoring()
    scores = scorer.calculate_composite_score(df_test)

    print("📊 팩터별 스코어:")
    print(f"  - 기술적 지표: {scores['technical_score']:.1f}/100")
    print(f"  - 모멘텀: {scores['momentum_score']:.1f}/100")
    print(f"  - 거래량: {scores['volume_score']:.1f}/100")
    print(f"  - 변동성: {scores['volatility_score']:.1f}/100")
    print(f"  - 추세: {scores['trend_score']:.1f}/100")
    print(f"\n🎯 종합 스코어: {scores['composite_score']:.1f}/100")
    print(f"📈 매수 시그널: {'✅ YES' if scores['buy_signal'] else '❌ NO'}\n")

    print("세부 지표:")
    print(f"  RSI: {scores['rsi']:.1f}")
    print(f"  MACD 히스토그램: {scores['macd_histogram']:.1f}")
    print(f"  볼린저 %B: {scores['bb_percent_b']:.2f}")
    print(f"  5일 수익률: {scores['return_5d']:.2f}%")
    print(f"  거래량 비율: {scores['volume_ratio']:.2f}x")
    print(f"  ATR %: {scores['atr_pct']:.2f}%")

    print("\n✅ Multi-Factor Scoring 모듈 생성 완료!")
