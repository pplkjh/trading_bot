"""
Advanced Risk Management Module
공격적 스윙 트레이딩을 위한 리스크 관리 시스템

주요 기능:
1. ATR 기반 동적 포지션 사이징
2. Kelly Criterion 포지션 사이징
3. 포트폴리오 레벨 리스크 관리
4. 상관관계 기반 포지션 제한
5. 섹터 노출 제한
"""

import pandas as pd
from typing import Dict, List, Tuple, Optional
import pymysql
from library.cf import *
from library.technical_indicators import calculate_atr


class RiskManager:
    """
    공격적 스윙 트레이딩 전략을 위한 리스크 매니저

    Parameters:
    -----------
    portfolio_value : float
        현재 포트폴리오 총 가치
    risk_profile : str
        리스크 프로필 ('conservative', 'moderate', 'aggressive')
    max_position_pct : float
        단일 포지션 최대 비중 (default: 15% for aggressive)
    max_daily_loss_pct : float
        일일 최대 손실 허용치 (default: -8%)
    max_sector_exposure : float
        섹터별 최대 노출 비중 (default: 40%)
    """

    def __init__(
        self,
        portfolio_value: float,
        risk_profile: str = 'aggressive',
        max_position_pct: float = 0.15,
        max_daily_loss_pct: float = -0.05,  # -8% → -5%로 변경
        max_sector_exposure: float = 0.40,
        max_correlation: float = 0.7
    ):
        self.portfolio_value = portfolio_value
        self.risk_profile = risk_profile
        self.max_position_pct = max_position_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_sector_exposure = max_sector_exposure
        self.max_correlation = max_correlation

        # 리스크 프로필별 설정
        self.risk_profiles = {
            'conservative': {
                'position_pct': 0.05,
                'atr_multiplier': 3.0,
                'max_positions': 15,
                'risk_per_trade': 0.01  # 1% per trade
            },
            'moderate': {
                'position_pct': 0.10,
                'atr_multiplier': 2.5,
                'max_positions': 12,
                'risk_per_trade': 0.02  # 2% per trade
            },
            'aggressive': {
                'position_pct': 0.15,
                'atr_multiplier': 2.0,
                'max_positions': 10,
                'risk_per_trade': 0.03  # 3% per trade
            }
        }

        self.config = self.risk_profiles.get(risk_profile, self.risk_profiles['aggressive'])


    def calculate_position_size_atr(
        self,
        current_price: float,
        atr: float,
        stop_loss_atr_multiplier: Optional[float] = None
    ) -> int:
        """
        ATR 기반 포지션 사이징

        리스크를 ATR 단위로 정의하여 변동성에 따라 포지션 크기 조정

        Parameters:
        -----------
        current_price : float
            현재 주가
        atr : float
            Average True Range 값
        stop_loss_atr_multiplier : float
            손절선 ATR 배수 (default: 프로필별 설정값)

        Returns:
        --------
        int : 매수할 주식 수량
        """
        if atr == 0 or current_price == 0:
            return 0

        multiplier = stop_loss_atr_multiplier or self.config['atr_multiplier']
        risk_amount = self.portfolio_value * self.config['risk_per_trade']

        # 포지션 크기 = 리스크 금액 / (ATR * 배수)
        position_value = risk_amount / (atr * multiplier)
        shares = int(position_value / current_price)

        # 최대 포지션 제한 체크
        max_value = self.portfolio_value * self.config['position_pct']
        max_shares = int(max_value / current_price)

        return min(shares, max_shares)


    def calculate_position_size_fixed_fractional(
        self,
        current_price: float,
        risk_pct: Optional[float] = None
    ) -> int:
        """
        Fixed Fractional Position Sizing

        포트폴리오의 고정 비율로 포지션 결정

        Parameters:
        -----------
        current_price : float
            현재 주가
        risk_pct : float
            포지션 비율 (default: 프로필별 설정값)

        Returns:
        --------
        int : 매수할 주식 수량
        """
        if current_price == 0:
            return 0

        pct = risk_pct or self.config['position_pct']
        position_value = self.portfolio_value * pct
        shares = int(position_value / current_price)

        return shares


    def calculate_kelly_criterion(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        kelly_fraction: float = 0.25
    ) -> float:
        """
        Kelly Criterion 포지션 사이징

        f = (p * b - q) / b
        여기서:
        - p = 승률
        - q = 패율 (1 - p)
        - b = 평균 손익비 (avg_win / avg_loss)

        Parameters:
        -----------
        win_rate : float
            승률 (0~1)
        avg_win : float
            평균 수익
        avg_loss : float
            평균 손실 (절대값)
        kelly_fraction : float
            Kelly 값 조정 계수 (과도한 레버리지 방지, default: 0.25)

        Returns:
        --------
        float : 포트폴리오 대비 권장 포지션 비율
        """
        if avg_loss == 0 or win_rate <= 0 or win_rate >= 1:
            return self.config['position_pct']

        b = avg_win / abs(avg_loss)
        q = 1 - win_rate

        kelly_pct = (win_rate * b - q) / b

        # Kelly 값이 음수이거나 과도하게 크면 기본값 사용
        if kelly_pct <= 0:
            return self.config['position_pct']

        # Fractional Kelly로 과도한 레버리지 방지
        adjusted_kelly = kelly_pct * kelly_fraction

        # 최대 포지션 제한
        return min(adjusted_kelly, self.max_position_pct)


    def check_portfolio_risk(
        self,
        current_positions: List[Dict],
        today_pnl: float
    ) -> Tuple[bool, str]:
        """
        포트폴리오 레벨 리스크 체크

        Parameters:
        -----------
        current_positions : List[Dict]
            현재 보유 포지션 리스트
            각 포지션은 {'code', 'value', 'pnl', 'sector'} 포함
        today_pnl : float
            오늘 손익 (음수면 손실)

        Returns:
        --------
        Tuple[bool, str] : (통과 여부, 메시지)
        """
        # 1. 일일 손실 한도 체크
        today_pnl_pct = today_pnl / self.portfolio_value
        if today_pnl_pct <= self.max_daily_loss_pct:
            return False, f"일일 손실 한도 도달: {today_pnl_pct:.2%} (한도: {self.max_daily_loss_pct:.2%})"

        # 2. 최대 포지션 수 체크
        if len(current_positions) >= self.config['max_positions']:
            return False, f"최대 포지션 수 도달: {len(current_positions)}/{self.config['max_positions']}"

        # 3. 섹터 노출 체크
        sector_exposure = {}
        for pos in current_positions:
            sector = pos.get('sector', 'Unknown')
            sector_exposure[sector] = sector_exposure.get(sector, 0) + pos.get('value', 0)

        for sector, exposure in sector_exposure.items():
            exposure_pct = exposure / self.portfolio_value
            if exposure_pct > self.max_sector_exposure:
                return False, f"섹터 노출 한도 초과: {sector} {exposure_pct:.2%} (한도: {self.max_sector_exposure:.2%})"

        return True, "OK"


    def calculate_stop_loss(
        self,
        entry_price: float,
        atr: float,
        method: str = 'atr'
    ) -> float:
        """
        손절가 계산

        Parameters:
        -----------
        entry_price : float
            진입 가격
        atr : float
            ATR 값
        method : str
            손절 방식 ('atr', 'percentage')

        Returns:
        --------
        float : 손절가
        """
        if method == 'atr':
            stop_loss = entry_price - (atr * self.config['atr_multiplier'])
        elif method == 'percentage':
            # 공격적 전략: -6% 고정 손절
            stop_loss = entry_price * 0.94
        else:
            stop_loss = entry_price * 0.94

        return round(stop_loss, 0)


    def calculate_trailing_stop(
        self,
        entry_price: float,
        current_price: float,
        highest_price: float,
        atr: float,
        activation_pct: float = 0.05
    ) -> Optional[float]:
        """
        트레일링 스톱 계산

        수익이 일정 수준 이상 나면 트레일링 스톱 활성화

        Parameters:
        -----------
        entry_price : float
            진입 가격
        current_price : float
            현재 가격
        highest_price : float
            보유 후 최고가
        atr : float
            ATR 값
        activation_pct : float
            트레일링 스톱 활성화 수익률 (default: 5%)

        Returns:
        --------
        Optional[float] : 트레일링 스톱 가격 (미활성화 시 None)
        """
        current_gain = (current_price - entry_price) / entry_price

        # 수익이 activation_pct 이상이면 트레일링 스톱 활성화
        if current_gain >= activation_pct:
            # 최고가에서 ATR * 2 만큼 하락하면 청산
            trailing_stop = highest_price - (atr * 2.0)
            return round(trailing_stop, 0)

        return None


    def calculate_profit_target(
        self,
        entry_price: float,
        atr: float,
        risk_reward_ratio: float = 1.5
    ) -> float:
        """
        목표 수익가 계산

        ATR 기반으로 리스크 대비 보상 비율 설정

        Parameters:
        -----------
        entry_price : float
            진입 가격
        atr : float
            ATR 값
        risk_reward_ratio : float
            리스크 대비 보상 비율 (default: 1.5)

        Returns:
        --------
        float : 목표 수익가
        """
        risk = atr * self.config['atr_multiplier']
        reward = risk * risk_reward_ratio
        profit_target = entry_price + reward

        return round(profit_target, 0)


    def check_correlation_limit(
        self,
        new_stock_code: str,
        current_positions: List[str],
        db_name: str = 'daily_buy_list',
        lookback_days: int = 60
    ) -> Tuple[bool, float]:
        """
        신규 종목과 기존 포지션 간 상관관계 체크

        Parameters:
        -----------
        new_stock_code : str
            신규 매수 예정 종목 코드
        current_positions : List[str]
            현재 보유 종목 코드 리스트
        db_name : str
            데이터베이스 이름
        lookback_days : int
            상관관계 계산 기간

        Returns:
        --------
        Tuple[bool, float] : (통과 여부, 최대 상관계수)
        """
        if not current_positions:
            return True, 0.0

        try:
            con = pymysql.connect(
                user=db_id,
                passwd=db_passwd,
                host=db_ip,
                db=db_name,
                charset='utf8',
                port=int(db_port)
            )

            # 신규 종목 수익률 가져오기
            query_new = f"""
            SELECT ref_date, close
            FROM {new_stock_code}
            ORDER BY ref_date DESC
            LIMIT {lookback_days + 1}
            """
            df_new = pd.read_sql(query_new, con)
            df_new['return'] = df_new['close'].pct_change()

            max_correlation = 0.0

            # 기존 포지션과 상관관계 계산
            for pos_code in current_positions:
                try:
                    query_pos = f"""
                    SELECT ref_date, close
                    FROM {pos_code}
                    ORDER BY ref_date DESC
                    LIMIT {lookback_days + 1}
                    """
                    df_pos = pd.read_sql(query_pos, con)
                    df_pos['return'] = df_pos['close'].pct_change()

                    # 날짜 기준으로 merge
                    merged = pd.merge(df_new, df_pos, on='ref_date', suffixes=('_new', '_pos'))

                    if len(merged) > 10:  # 최소 10일 데이터 필요
                        correlation = merged['return_new'].corr(merged['return_pos'])
                        max_correlation = max(max_correlation, abs(correlation))

                except Exception as e:
                    continue

            con.close()

            # 상관관계가 너무 높으면 거부
            if max_correlation > self.max_correlation:
                return False, max_correlation

            return True, max_correlation

        except Exception as e:
            print(f"상관관계 체크 오류: {e}")
            return True, 0.0  # 오류 시 통과


    def get_position_score(
        self,
        stock_data: Dict,
        current_positions: List[Dict],
        historical_performance: Optional[Dict] = None
    ) -> Dict:
        """
        종합 포지션 스코어 계산 및 권장 사항 제공

        Parameters:
        -----------
        stock_data : Dict
            종목 데이터 (code, price, atr, sector 등)
        current_positions : List[Dict]
            현재 포지션 리스트
        historical_performance : Optional[Dict]
            과거 성과 데이터 (win_rate, avg_win, avg_loss)

        Returns:
        --------
        Dict : {
            'recommended_shares': int,
            'recommended_value': float,
            'stop_loss': float,
            'profit_target': float,
            'position_pct': float,
            'risk_score': float (0-100)
        }
        """
        current_price = stock_data.get('price', 0)
        atr = stock_data.get('atr', 0)

        # ATR 기반 포지션 사이징
        if atr > 0:
            shares = self.calculate_position_size_atr(current_price, atr)
        else:
            shares = self.calculate_position_size_fixed_fractional(current_price)

        # Kelly Criterion 적용 (과거 성과 있을 경우)
        if historical_performance:
            kelly_pct = self.calculate_kelly_criterion(
                historical_performance.get('win_rate', 0.5),
                historical_performance.get('avg_win', 0.05),
                historical_performance.get('avg_loss', 0.03)
            )
            kelly_shares = int((self.portfolio_value * kelly_pct) / current_price)
            shares = min(shares, kelly_shares)

        position_value = shares * current_price
        position_pct = position_value / self.portfolio_value

        # 손절가 및 목표가
        stop_loss = self.calculate_stop_loss(current_price, atr, method='atr')
        profit_target = self.calculate_profit_target(current_price, atr)

        # 리스크 스코어 계산 (0-100, 낮을수록 좋음)
        risk_score = self._calculate_risk_score(stock_data, current_positions, position_pct)

        return {
            'recommended_shares': shares,
            'recommended_value': position_value,
            'stop_loss': stop_loss,
            'profit_target': profit_target,
            'position_pct': position_pct,
            'risk_score': risk_score,
            'risk_reward_ratio': (profit_target - current_price) / (current_price - stop_loss)
        }


    def _calculate_risk_score(
        self,
        stock_data: Dict,
        current_positions: List[Dict],
        position_pct: float
    ) -> float:
        """
        리스크 스코어 계산 (내부 함수)

        Returns:
        --------
        float : 0-100 점수 (낮을수록 안전)
        """
        score = 0.0

        # 1. 포지션 크기 리스크 (최대 30점)
        position_risk = (position_pct / self.max_position_pct) * 30
        score += position_risk

        # 2. 섹터 집중도 리스크 (최대 30점)
        sector = stock_data.get('sector', 'Unknown')
        sector_exposure = sum(
            pos.get('value', 0)
            for pos in current_positions
            if pos.get('sector') == sector
        )
        sector_exposure_pct = sector_exposure / self.portfolio_value
        sector_risk = (sector_exposure_pct / self.max_sector_exposure) * 30
        score += sector_risk

        # 3. 변동성 리스크 (최대 20점)
        atr = stock_data.get('atr', 0)
        price = stock_data.get('price', 1)
        atr_pct = (atr / price) if price > 0 else 0
        # ATR이 가격의 5% 이상이면 고변동성
        volatility_risk = min((atr_pct / 0.05) * 20, 20)
        score += volatility_risk

        # 4. 포지션 수 리스크 (최대 20점)
        position_count_risk = (len(current_positions) / self.config['max_positions']) * 20
        score += position_count_risk

        return min(score, 100)


# 유틸리티 함수
def get_stock_atr(code: str, db_name: str = 'daily_buy_list', period: int = 14) -> float:
    """
    데이터베이스에서 종목의 ATR 계산

    Parameters:
    -----------
    code : str
        종목 코드
    db_name : str
        데이터베이스 이름
    period : int
        ATR 계산 기간

    Returns:
    --------
    float : ATR 값
    """
    try:
        con = pymysql.connect(
            user=db_id,
            passwd=db_passwd,
            host=db_ip,
            db=db_name,
            charset='utf8',
            port=int(db_port)
        )

        query = f"""
        SELECT high, low, close
        FROM {code}
        ORDER BY ref_date DESC
        LIMIT {period + 1}
        """

        df = pd.read_sql(query, con)
        con.close()

        if len(df) < period:
            return 0

        atr = calculate_atr(df['high'], df['low'], df['close'], period)

        return atr

    except Exception as e:
        print(f"ATR 계산 오류 ({code}): {e}")
        return 0


if __name__ == "__main__":
    # 테스트 코드
    print("=== Risk Manager 테스트 ===\n")

    # 공격적 프로필로 리스크 매니저 초기화
    portfolio_value = 10000000  # 1000만원
    rm = RiskManager(
        portfolio_value=portfolio_value,
        risk_profile='aggressive',
        max_position_pct=0.15,
        max_daily_loss_pct=-0.05  # -8% → -5%로 변경
    )

    print(f"포트폴리오 가치: {portfolio_value:,}원")
    print(f"리스크 프로필: {rm.risk_profile}")
    print(f"거래당 리스크: {rm.config['risk_per_trade']:.1%}")
    print(f"최대 포지션 비율: {rm.max_position_pct:.1%}")
    print(f"일일 최대 손실: {rm.max_daily_loss_pct:.1%}\n")

    # 포지션 사이징 테스트
    test_price = 50000
    test_atr = 2000

    shares_atr = rm.calculate_position_size_atr(test_price, test_atr)
    shares_fixed = rm.calculate_position_size_fixed_fractional(test_price)

    print(f"테스트 종목 - 가격: {test_price:,}원, ATR: {test_atr:,}원")
    print(f"ATR 기반 포지션: {shares_atr}주 ({shares_atr * test_price:,}원)")
    print(f"Fixed Fractional: {shares_fixed}주 ({shares_fixed * test_price:,}원)\n")

    # 손절/익절가 계산
    stop_loss = rm.calculate_stop_loss(test_price, test_atr)
    profit_target = rm.calculate_profit_target(test_price, test_atr)

    print(f"손절가: {stop_loss:,}원 ({(stop_loss/test_price-1)*100:.2f}%)")
    print(f"목표가: {profit_target:,}원 ({(profit_target/test_price-1)*100:.2f}%)")
    print(f"손익비: {(profit_target - test_price) / (test_price - stop_loss):.2f}:1\n")

    # Kelly Criterion 테스트
    kelly_pct = rm.calculate_kelly_criterion(
        win_rate=0.55,
        avg_win=0.08,
        avg_loss=0.04,
        kelly_fraction=0.25
    )
    print(f"Kelly Criterion 포지션 비율: {kelly_pct:.2%}\n")

    print("✅ Risk Manager 모듈 생성 완료!")
