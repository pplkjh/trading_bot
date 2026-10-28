"""
Hybrid Trading Strategy Engine
모멘텀 브레이크아웃 + 평균회귀 하이브리드 전략

전략 조합:
1. Momentum Breakout (60% 비중)
   - 변동성 돌파
   - 거래량 확인
   - 상대강도 확인

2. Mean Reversion (40% 비중)
   - RSI 과매도 구간
   - 볼린저 밴드 하단
   - 지지선 근처
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import pymysql
from library.cf import *
from library.multi_factor_scoring import MultiFactorScoring
from library.risk_manager import RiskManager


class HybridStrategy:
    """
    하이브리드 매매 전략

    모멘텀과 평균회귀를 결합하여 다양한 시장 환경에 적응
    """

    def __init__(
        self,
        momentum_weight: float = 0.6,
        mean_reversion_weight: float = 0.4,
        min_score: float = 70.0
    ):
        """
        Parameters:
        -----------
        momentum_weight : float
            모멘텀 전략 가중치 (default: 0.6)
        mean_reversion_weight : float
            평균회귀 전략 가중치 (default: 0.4)
        min_score : float
            최소 진입 스코어 (default: 70.0)
        """
        self.momentum_weight = momentum_weight
        self.mean_reversion_weight = mean_reversion_weight
        self.min_score = min_score

        # 가중치 정규화
        total = momentum_weight + mean_reversion_weight
        self.momentum_weight = momentum_weight / total
        self.mean_reversion_weight = mean_reversion_weight / total

        self.scorer = MultiFactorScoring()


    def check_momentum_breakout(
        self,
        df: pd.DataFrame,
        lookback_period: int = 20,
        volume_threshold: float = 1.5,
        price_threshold: float = 0.02
    ) -> Dict[str, any]:
        """
        모멘텀 브레이크아웃 전략 체크

        조건:
        1. 가격이 최근 N일 고점 돌파
        2. 거래량이 평균의 X배 이상
        3. ATR 기반 변동성 돌파

        Parameters:
        -----------
        df : pd.DataFrame
            OHLCV 데이터
        lookback_period : int
            돌파 체크 기간 (default: 20일)
        volume_threshold : float
            거래량 임계값 배수 (default: 1.5배)
        price_threshold : float
            가격 돌파 여유 (default: 2%)

        Returns:
        --------
        Dict : {
            'signal': bool,
            'score': float (0-100),
            'details': dict
        }
        """
        result = {
            'signal': False,
            'score': 0.0,
            'details': {}
        }

        if len(df) < lookback_period + 1:
            return result

        close = df['close']
        high = df['high']
        volume = df['volume']

        current_price = close.iloc[-1]
        current_volume = volume.iloc[-1]

        # 1. 가격 돌파 체크
        highest_high = high.iloc[-lookback_period-1:-1].max()
        breakout_price = highest_high * (1 + price_threshold)

        price_breakout = current_price >= breakout_price
        result['details']['highest_high'] = highest_high
        result['details']['breakout_price'] = breakout_price
        result['details']['price_breakout'] = price_breakout

        # 2. 거래량 확인
        avg_volume = volume.iloc[-lookback_period-1:-1].mean()
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
        volume_confirmed = volume_ratio >= volume_threshold

        result['details']['avg_volume'] = avg_volume
        result['details']['volume_ratio'] = volume_ratio
        result['details']['volume_confirmed'] = volume_confirmed

        # 3. 변동성 돌파 (Larry Williams)
        # 오늘 시가 + (어제 고가 - 어제 저가) * k
        if len(df) >= 2:
            yesterday_range = high.iloc[-2] - df['low'].iloc[-2]
            k = 0.5  # 변동성 계수
            volatility_breakout_price = df['open'].iloc[-1] + (yesterday_range * k)
            volatility_breakout = current_price >= volatility_breakout_price

            result['details']['volatility_breakout_price'] = volatility_breakout_price
            result['details']['volatility_breakout'] = volatility_breakout
        else:
            volatility_breakout = False

        # 4. 상대강도 체크 (20일 대비)
        if len(close) >= 20:
            price_20d_ago = close.iloc[-20]
            momentum_pct = (current_price / price_20d_ago - 1) * 100
            strong_momentum = momentum_pct > 5  # 20일간 5% 이상 상승

            result['details']['momentum_pct'] = momentum_pct
            result['details']['strong_momentum'] = strong_momentum
        else:
            strong_momentum = False
            momentum_pct = 0

        # 스코어 계산 (각 조건별 가중치)
        score = 0.0

        if price_breakout:
            score += 40  # 가격 돌파가 가장 중요
        if volume_confirmed:
            score += 30  # 거래량 확인
        if volatility_breakout:
            score += 20  # 변동성 돌파
        if strong_momentum:
            score += 10  # 강한 모멘텀

        result['score'] = score
        result['signal'] = score >= 70  # 70점 이상이면 시그널

        return result


    def check_mean_reversion(
        self,
        df: pd.DataFrame,
        rsi_oversold: float = 30,
        bb_threshold: float = 0.2,
        support_margin: float = 0.05
    ) -> Dict[str, any]:
        """
        평균회귀 전략 체크

        조건:
        1. RSI 과매도 구간
        2. 볼린저 밴드 하단 근처
        3. 지지선 (이동평균선) 근처
        4. 과도한 하락 후 반등 조짐

        Parameters:
        -----------
        df : pd.DataFrame
            OHLCV 데이터
        rsi_oversold : float
            RSI 과매도 기준 (default: 30)
        bb_threshold : float
            볼린저 밴드 %B 임계값 (default: 0.2)
        support_margin : float
            지지선 여유 (default: 5%)

        Returns:
        --------
        Dict : {
            'signal': bool,
            'score': float (0-100),
            'details': dict
        }
        """
        result = {
            'signal': False,
            'score': 0.0,
            'details': {}
        }

        if len(df) < 60:
            return result

        close = df['close']
        current_price = close.iloc[-1]

        # 1. RSI 과매도 체크
        rsi = self.scorer.calculate_rsi(close)
        is_oversold = rsi <= rsi_oversold

        result['details']['rsi'] = rsi
        result['details']['is_oversold'] = is_oversold

        # 2. 볼린저 밴드 체크
        bb_middle, bb_upper, bb_lower, percent_b = self.scorer.calculate_bollinger_bands(close)
        near_lower_band = percent_b <= bb_threshold

        result['details']['bb_percent_b'] = percent_b
        result['details']['near_lower_band'] = near_lower_band

        # 3. 이동평균선 지지 체크
        ma20 = close.rolling(window=20).mean().iloc[-1]
        ma60 = close.rolling(window=60).mean().iloc[-1]

        near_ma20 = abs(current_price - ma20) / ma20 <= support_margin
        near_ma60 = abs(current_price - ma60) / ma60 <= support_margin
        near_support = near_ma20 or near_ma60

        result['details']['ma20'] = ma20
        result['details']['ma60'] = ma60
        result['details']['near_support'] = near_support

        # 4. 과도한 하락 후 반등 조짐
        # 최근 5일간 급락 (-10% 이상) 후 반등
        if len(close) >= 10:
            price_5d_ago = close.iloc[-6]
            decline_pct = (current_price / price_5d_ago - 1) * 100

            # 5일 전 대비 -5% 이상 하락
            sharp_decline = decline_pct <= -5

            # 최근 2일간 반등 조짐 (양봉)
            if len(close) >= 3:
                yesterday_close = close.iloc[-2]
                today_gain = (current_price / yesterday_close - 1) * 100
                bounce_signal = today_gain > 1  # 어제 대비 1% 이상 상승
            else:
                bounce_signal = False

            result['details']['decline_pct'] = decline_pct
            result['details']['sharp_decline'] = sharp_decline
            result['details']['bounce_signal'] = bounce_signal
        else:
            sharp_decline = False
            bounce_signal = False

        # 5. Stochastic 과매도 확인
        stoch_k, stoch_d = self.scorer.calculate_stochastic(
            df['high'], df['low'], close
        )
        stoch_oversold = stoch_k <= 20

        result['details']['stochastic_k'] = stoch_k
        result['details']['stoch_oversold'] = stoch_oversold

        # 스코어 계산
        score = 0.0

        if is_oversold:
            score += 30  # RSI 과매도
        if near_lower_band:
            score += 25  # 볼린저 하단
        if near_support:
            score += 20  # 지지선 근처
        if sharp_decline and bounce_signal:
            score += 15  # 과도한 하락 후 반등
        if stoch_oversold:
            score += 10  # Stochastic 과매도

        result['score'] = score
        result['signal'] = score >= 60  # 60점 이상이면 시그널

        return result


    def get_hybrid_signal(
        self,
        df: pd.DataFrame,
        strategy_preference: str = 'balanced'
    ) -> Dict[str, any]:
        """
        하이브리드 매매 시그널 생성

        모멘텀과 평균회귀 점수를 결합

        Parameters:
        -----------
        df : pd.DataFrame
            OHLCV 데이터
        strategy_preference : str
            전략 선호도 ('momentum', 'mean_reversion', 'balanced')

        Returns:
        --------
        Dict : {
            'signal': str ('BUY', 'HOLD', 'SELL'),
            'score': float (0-100),
            'strategy_type': str,
            'momentum_result': dict,
            'mean_reversion_result': dict,
            'factor_scores': dict
        }
        """
        result = {
            'signal': 'HOLD',
            'score': 0.0,
            'strategy_type': 'none',
            'momentum_result': {},
            'mean_reversion_result': {},
            'factor_scores': {}
        }

        # 멀티팩터 스코어 계산
        factor_scores = self.scorer.calculate_composite_score(df)
        result['factor_scores'] = factor_scores

        # 모멘텀 브레이크아웃 체크
        momentum_result = self.check_momentum_breakout(df)
        result['momentum_result'] = momentum_result

        # 평균회귀 체크
        mean_reversion_result = self.check_mean_reversion(df)
        result['mean_reversion_result'] = mean_reversion_result

        # 전략 선호도에 따른 가중치 조정
        if strategy_preference == 'momentum':
            mom_weight = 0.8
            mr_weight = 0.2
        elif strategy_preference == 'mean_reversion':
            mom_weight = 0.3
            mr_weight = 0.7
        else:  # balanced
            mom_weight = self.momentum_weight
            mr_weight = self.mean_reversion_weight

        # 하이브리드 스코어 계산
        # 멀티팩터 스코어 (40%) + 전략별 스코어 (60%)
        strategy_score = (
            momentum_result['score'] * mom_weight +
            mean_reversion_result['score'] * mr_weight
        )

        hybrid_score = (
            factor_scores['composite_score'] * 0.4 +
            strategy_score * 0.6
        )

        result['score'] = hybrid_score

        # 매매 시그널 결정
        if hybrid_score >= self.min_score:
            result['signal'] = 'BUY'

            # 어떤 전략이 주도했는지 판단
            if momentum_result['signal'] and not mean_reversion_result['signal']:
                result['strategy_type'] = 'momentum_breakout'
            elif mean_reversion_result['signal'] and not momentum_result['signal']:
                result['strategy_type'] = 'mean_reversion'
            elif momentum_result['signal'] and mean_reversion_result['signal']:
                result['strategy_type'] = 'hybrid_strong'  # 두 시그널 모두 발생
            else:
                result['strategy_type'] = 'factor_based'  # 멀티팩터만 높음

        elif hybrid_score >= 50:
            result['signal'] = 'HOLD'
            result['strategy_type'] = 'neutral'
        else:
            result['signal'] = 'SELL'
            result['strategy_type'] = 'weak'

        return result


    def scan_stocks(
        self,
        stock_codes: List[str],
        db_name: str = 'daily_buy_list',
        top_n: int = 20
    ) -> pd.DataFrame:
        """
        여러 종목 스캔하여 매수 후보 선정

        Parameters:
        -----------
        stock_codes : List[str]
            스캔할 종목 코드 리스트
        db_name : str
            데이터베이스 이름
        top_n : int
            상위 N개 종목 선정

        Returns:
        --------
        pd.DataFrame : 매수 후보 종목 리스트 (스코어 순 정렬)
        """
        results = []

        for code in stock_codes:
            try:
                # 1. stock_item_all에서 종목코드로 종목명 조회
                con = pymysql.connect(
                    user=db_id,
                    passwd=db_passwd,
                    host=db_ip,
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
                    continue

                code_name = code_name_result.iloc[0]['code_name']

                # 2. daily_craw에서 일봉 데이터 로드 (종목명을 테이블명으로 사용)
                con = pymysql.connect(
                    user=db_id,
                    passwd=db_passwd,
                    host=db_ip,
                    db='daily_craw',
                    charset='utf8',
                    port=int(db_port)
                )

                query = f"""
                SELECT date, open, high, low, close, volume
                FROM `{code_name}`
                WHERE code = '{code}'
                ORDER BY date DESC
                LIMIT 120
                """

                df = pd.read_sql(query, con)
                con.close()

                if len(df) < 60:
                    continue

                # 시간순 정렬 (date 컬럼 사용)
                df = df.sort_values('date').reset_index(drop=True)

                # date 컬럼을 ref_date로 이름 변경 (기존 코드 호환성 유지)
                df = df.rename(columns={'date': 'ref_date'})

                # 시그널 생성
                signal_result = self.get_hybrid_signal(df)

                if signal_result['signal'] == 'BUY':
                    results.append({
                        'code': code,
                        'score': signal_result['score'],
                        'strategy_type': signal_result['strategy_type'],
                        'current_price': df['close'].iloc[-1],
                        'momentum_score': signal_result['momentum_result']['score'],
                        'mean_reversion_score': signal_result['mean_reversion_result']['score'],
                        'factor_score': signal_result['factor_scores']['composite_score'],
                        'rsi': signal_result['factor_scores']['rsi'],
                        'volume_ratio': signal_result['factor_scores']['volume_ratio']
                    })

            except Exception as e:
                print(f"종목 {code} 스캔 오류: {e}")
                continue

        # DataFrame 생성 및 정렬
        if results:
            df_results = pd.DataFrame(results)
            df_results = df_results.sort_values('score', ascending=False).head(top_n)
            return df_results
        else:
            return pd.DataFrame()


def get_buy_candidates(
    db_name: str = 'daily_buy_list',
    min_score: float = 70.0,
    top_n: int = 20,
    exclude_codes: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    데이터베이스에서 전체 종목 스캔하여 매수 후보 선정

    Parameters:
    -----------
    db_name : str
        데이터베이스 이름
    min_score : float
        최소 스코어
    top_n : int
        선정할 종목 수
    exclude_codes : List[str]
        제외할 종목 코드 리스트

    Returns:
    --------
    pd.DataFrame : 매수 후보 종목
    """
    try:
        # 전체 종목 리스트 가져오기
        con = pymysql.connect(
            user=db_id,
            passwd=db_passwd,
            host=db_ip,
            db=db_name,
            charset='utf8',
            port=int(db_port)
        )

        # stock_item_all 테이블에서 종목 리스트 가져오기
        query = """
        SELECT code FROM stock_item_all
        WHERE check_item = 1
        """

        df_stocks = pd.read_sql(query, con)
        con.close()

        stock_codes = df_stocks['code'].tolist()

        # 제외 종목 필터링
        if exclude_codes:
            stock_codes = [code for code in stock_codes if code not in exclude_codes]

        print(f"총 {len(stock_codes)}개 종목 스캔 중...")

        # 하이브리드 전략으로 스캔
        strategy = HybridStrategy(min_score=min_score)
        df_candidates = strategy.scan_stocks(stock_codes, db_name, top_n)

        return df_candidates

    except Exception as e:
        print(f"매수 후보 선정 오류: {e}")
        return pd.DataFrame()


if __name__ == "__main__":
    # 테스트 코드
    print("=== Hybrid Strategy Engine 테스트 ===\n")

    # 샘플 데이터 생성 (모멘텀 시나리오)
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=100, freq='D')

    # 변동성 돌파 패턴
    base_price = 50000
    prices = [base_price]

    for i in range(99):
        if i < 80:
            # 횡보
            change = np.random.normal(0, 500)
        else:
            # 돌파
            change = np.random.normal(1000, 500)

        prices.append(prices[-1] + change)

    prices = np.array(prices)

    df_momentum = pd.DataFrame({
        'ref_date': dates,
        'open': prices * 0.995,
        'high': prices * 1.015,
        'low': prices * 0.985,
        'close': prices,
        'volume': np.concatenate([
            np.random.randint(100000, 200000, 80),
            np.random.randint(300000, 500000, 20)  # 돌파 시 거래량 증가
        ])
    })

    # 하이브리드 전략 실행
    strategy = HybridStrategy(momentum_weight=0.6, mean_reversion_weight=0.4)

    print("1️⃣ 모멘텀 돌파 시나리오 테스트")
    result_momentum = strategy.get_hybrid_signal(df_momentum)

    print(f"  시그널: {result_momentum['signal']}")
    print(f"  종합 스코어: {result_momentum['score']:.1f}/100")
    print(f"  전략 타입: {result_momentum['strategy_type']}")
    print(f"  모멘텀 스코어: {result_momentum['momentum_result']['score']:.1f}")
    print(f"  평균회귀 스코어: {result_momentum['mean_reversion_result']['score']:.1f}\n")

    # 평균회귀 시나리오
    prices_mr = [50000]
    for i in range(99):
        if i < 60:
            change = np.random.normal(0, 300)
        elif i < 85:
            # 급락
            change = np.random.normal(-800, 400)
        else:
            # 반등
            change = np.random.normal(500, 300)

        prices_mr.append(prices_mr[-1] + change)

    prices_mr = np.array(prices_mr)

    df_mr = pd.DataFrame({
        'ref_date': dates,
        'open': prices_mr * 0.995,
        'high': prices_mr * 1.01,
        'low': prices_mr * 0.99,
        'close': prices_mr,
        'volume': np.random.randint(100000, 300000, 100)
    })

    print("2️⃣ 평균회귀 시나리오 테스트")
    result_mr = strategy.get_hybrid_signal(df_mr)

    print(f"  시그널: {result_mr['signal']}")
    print(f"  종합 스코어: {result_mr['score']:.1f}/100")
    print(f"  전략 타입: {result_mr['strategy_type']}")
    print(f"  모멘텀 스코어: {result_mr['momentum_result']['score']:.1f}")
    print(f"  평균회귀 스코어: {result_mr['mean_reversion_result']['score']:.1f}\n")

    print("✅ Hybrid Strategy 모듈 생성 완료!")
