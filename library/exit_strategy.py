"""
Advanced Exit Strategy Module
고급 청산 전략 시스템

청산 방식:
1. ATR 기반 동적 손절/익절
2. 트레일링 스톱 (수익 보호)
3. 시간 기반 청산 (최대 보유기간)
4. 팩터 스코어 기반 청산 (조건 악화)
5. 부분 청산 (피라미딩)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import pymysql
from library.cf import *
from library.technical_indicators import calculate_atr


class ExitStrategy:
    """
    고급 청산 전략

    다양한 청산 조건을 결합하여 최적의 청산 시점 결정
    """

    def __init__(
        self,
        atr_stop_multiplier: float = 2.0,
        trailing_stop_activation: float = 0.05,
        trailing_stop_distance: float = 0.03,
        max_holding_days: int = 15,
        time_stop_loss_pct: float = -0.02,
        factor_score_threshold: float = 40.0,
        fixed_stop_loss_pct: float = -0.03,
        breakeven_activation: float = 0.03,
        breakeven_buffer: float = -0.005
    ):
        """
        Parameters:
        -----------
        atr_stop_multiplier : float
            ATR 손절 배수 (default: 2.0)
        trailing_stop_activation : float
            트레일링 스톱 활성화 수익률 (default: 5%)
        trailing_stop_distance : float
            트레일링 스톱 거리 (default: 3%)
        max_holding_days : int
            최대 보유 기간 (default: 15일)
        time_stop_loss_pct : float
            시간 경과 후 손절 기준 (default: -2%)
        factor_score_threshold : float
            팩터 스코어 청산 임계값 (default: 40)
        fixed_stop_loss_pct : float
            고정 손절률 (default: -3%)
        breakeven_activation : float
            본전 보장 활성화 수익률 (default: +3% 도달 시 손절선 → 매수가)
        breakeven_buffer : float
            본전 보장 발동 버퍼 (default: -0.5%, 장중 noise 방지)
        """
        self.atr_stop_multiplier = atr_stop_multiplier
        self.trailing_stop_activation = trailing_stop_activation
        self.trailing_stop_distance = trailing_stop_distance
        self.max_holding_days = max_holding_days
        self.time_stop_loss_pct = time_stop_loss_pct
        self.factor_score_threshold = factor_score_threshold
        self.fixed_stop_loss_pct = fixed_stop_loss_pct
        self.breakeven_activation = breakeven_activation
        self.breakeven_buffer = breakeven_buffer


    def check_atr_stop_loss(
        self,
        entry_price: float,
        current_price: float,
        atr: float
    ) -> Tuple[bool, float, str]:
        """
        ATR 기반 손절 체크

        Parameters:
        -----------
        entry_price : float
            진입 가격
        current_price : float
            현재 가격
        atr : float
            ATR 값

        Returns:
        --------
        Tuple[bool, float, str] : (청산 여부, 손절가, 사유)
        """
        stop_loss_price = entry_price - (atr * self.atr_stop_multiplier)

        if current_price <= stop_loss_price:
            loss_pct = (current_price / entry_price - 1) * 100
            return True, stop_loss_price, f"ATR 손절 도달 ({loss_pct:.2f}%)"

        return False, stop_loss_price, ""


    def check_atr_profit_target(
        self,
        entry_price: float,
        current_price: float,
        atr: float,
        risk_reward_ratio: float = 1.5
    ) -> Tuple[bool, float, str]:
        """
        ATR 기반 목표가 도달 체크

        Parameters:
        -----------
        entry_price : float
            진입 가격
        current_price : float
            현재 가격
        atr : float
            ATR 값
        risk_reward_ratio : float
            손익비 (default: 1.5)

        Returns:
        --------
        Tuple[bool, float, str] : (청산 여부, 목표가, 사유)
        """
        risk = atr * self.atr_stop_multiplier
        reward = risk * risk_reward_ratio
        profit_target = entry_price + reward

        if current_price >= profit_target:
            profit_pct = (current_price / entry_price - 1) * 100
            return True, profit_target, f"ATR 목표가 도달 ({profit_pct:.2f}%)"

        return False, profit_target, ""


    def check_trailing_stop(
        self,
        entry_price: float,
        current_price: float,
        highest_price: float,
        atr: Optional[float] = None
    ) -> Tuple[bool, float, str]:
        """
        트레일링 스톱 체크

        수익이 일정 수준 이상 나면 활성화되어 수익 보호

        Parameters:
        -----------
        entry_price : float
            진입 가격
        current_price : float
            현재 가격
        highest_price : float
            보유 후 최고가
        atr : Optional[float]
            ATR 값 (없으면 고정 비율 사용)

        Returns:
        --------
        Tuple[bool, float, str] : (청산 여부, 트레일링 스톱 가격, 사유)
        """
        current_gain = (current_price / entry_price - 1)

        # 트레일링 스톱 활성화 체크
        if current_gain < self.trailing_stop_activation:
            return False, 0, ""

        # ATR 기반 또는 고정 비율
        if atr and atr > 0:
            # ATR 기반: 최고가에서 ATR * 2 만큼 하락
            trailing_stop_price = highest_price - (atr * 2.0)
        else:
            # 고정 비율: 최고가에서 N% 하락
            trailing_stop_price = highest_price * (1 - self.trailing_stop_distance)

        if current_price <= trailing_stop_price:
            profit_pct = (current_price / entry_price - 1) * 100
            return True, trailing_stop_price, f"트레일링 스톱 도달 (수익: {profit_pct:.2f}%)"

        return False, trailing_stop_price, ""


    def check_time_based_exit(
        self,
        entry_date: datetime,
        current_date: datetime,
        current_price: float,
        entry_price: float
    ) -> Tuple[bool, str]:
        """
        시간 기반 청산 체크

        최대 보유기간 초과 시 청산
        또는 일정 기간 후 손실 상태면 청산

        Parameters:
        -----------
        entry_date : datetime
            진입 일자
        current_date : datetime
            현재 일자
        current_price : float
            현재 가격
        entry_price : float
            진입 가격

        Returns:
        --------
        Tuple[bool, str] : (청산 여부, 사유)
        """
        holding_days = (current_date - entry_date).days
        current_return = (current_price / entry_price - 1)

        # 최대 보유기간 초과
        if holding_days >= self.max_holding_days:
            return True, f"최대 보유기간 초과 ({holding_days}일)"

        # 일정 기간(10일) 후 손실 상태면 청산 (5일 → 10일로 완화)
        if holding_days >= 10 and current_return <= self.time_stop_loss_pct:
            return True, f"시간 경과 손절 ({holding_days}일, {current_return*100:.2f}%)"

        return False, ""


    def check_factor_score_exit(
        self,
        current_score: float
    ) -> Tuple[bool, str]:
        """
        팩터 스코어 기반 청산

        매수 조건이 악화되면 청산

        Parameters:
        -----------
        current_score : float
            현재 팩터 스코어

        Returns:
        --------
        Tuple[bool, str] : (청산 여부, 사유)
        """
        if current_score < self.factor_score_threshold:
            return True, f"팩터 스코어 악화 (현재: {current_score:.1f})"

        return False, ""


    def check_technical_exit(
        self,
        df: pd.DataFrame,
        entry_price: float
    ) -> Tuple[bool, str]:
        """
        기술적 지표 기반 청산 체크

        1. 이동평균선 데드크로스
        2. RSI 과매수
        3. MACD 히스토그램 반전

        Parameters:
        -----------
        df : pd.DataFrame
            OHLCV 데이터
        entry_price : float
            진입 가격

        Returns:
        --------
        Tuple[bool, str] : (청산 여부, 사유)
        """
        if len(df) < 60:
            return False, ""

        close = df['close']
        current_price = close.iloc[-1]

        # 1. 이동평균선 데드크로스 (5일선이 20일선 아래로)
        ma5 = close.rolling(window=5).mean()
        ma20 = close.rolling(window=20).mean()

        if len(ma5) >= 2 and len(ma20) >= 2:
            # 어제는 위에 있었는데 오늘 아래로
            yesterday_above = ma5.iloc[-2] > ma20.iloc[-2]
            today_below = ma5.iloc[-1] <= ma20.iloc[-1]

            if yesterday_above and today_below:
                return True, "이동평균 데드크로스"

        # 2. RSI 과매수 (80 이상)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        if not np.isnan(rsi.iloc[-1]) and rsi.iloc[-1] >= 80:
            # 수익 상태에서만 과매수 청산
            if current_price > entry_price:
                profit_pct = (current_price / entry_price - 1) * 100
                return True, f"RSI 과매수 청산 (수익: {profit_pct:.2f}%)"

        # 3. MACD 히스토그램 음전환
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line

        if len(histogram) >= 2:
            # 양에서 음으로 전환
            yesterday_positive = histogram.iloc[-2] > 0
            today_negative = histogram.iloc[-1] <= 0

            if yesterday_positive and today_negative:
                return True, "MACD 히스토그램 음전환"

        return False, ""


    def get_exit_decision(
        self,
        position: Dict,
        current_data: pd.DataFrame,
        current_score: Optional[float] = None,
        current_date: Optional[datetime] = None
    ) -> Dict[str, any]:
        """
        종합 청산 판단

        모든 청산 조건을 체크하여 최종 결정

        Parameters:
        -----------
        position : Dict
            포지션 정보 {
                'code': str,
                'entry_price': float,
                'entry_date': datetime,
                'shares': int,
                'highest_price': float
            }
        current_data : pd.DataFrame
            현재 OHLCV 데이터
        current_score : Optional[float]
            현재 팩터 스코어
        current_date : Optional[datetime]
            현재 날짜 (시뮬레이션 시 필수)

        Returns:
        --------
        Dict : {
            'should_exit': bool,
            'exit_type': str ('full', 'partial'),
            'exit_ratio': float (0-1),
            'reason': str,
            'stop_loss_price': float,
            'profit_target': float,
            'trailing_stop_price': float
        }
        """
        result = {
            'should_exit': False,
            'exit_type': 'full',
            'exit_ratio': 1.0,
            'reason': '',
            'stop_loss_price': 0,
            'profit_target': 0,
            'trailing_stop_price': 0,
            'priority': 0  # 우선순위 (높을수록 긴급)
        }

        entry_price = position['entry_price']
        entry_date = position.get('entry_date', datetime.now())
        highest_price = position.get('highest_price', entry_price)

        # 시뮬레이터는 시가 기준으로 매도하므로, 시가로 체크해야 함
        # position에서 전달된 current_price 사용 (all_item_db의 present_price = 시가)
        current_price = position.get('current_price', current_data['close'].iloc[-1])

        # 시뮬레이션 날짜가 전달되면 사용, 없으면 실제 오늘 날짜 사용
        if current_date is None:
            current_date = datetime.now()

        # ATR 계산
        atr = calculate_atr(
            current_data['high'],
            current_data['low'],
            current_data['close']
        )

        # 0. 고정 손절률 체크 (최우선 - 무조건 -3%에서 손절)
        current_return = (current_price / entry_price - 1)
        if current_return <= self.fixed_stop_loss_pct:
            loss_pct = current_return * 100
            result['should_exit'] = True
            result['reason'] = f"고정 손절 도달 ({loss_pct:.2f}%)"
            result['priority'] = 110  # 최우선
            result['stop_loss_price'] = entry_price * (1 + self.fixed_stop_loss_pct)
            return result

        # 0.5. 본전 보장 손절 (+3% 도달 후 매수가 -0.5% 이하로 하락 시)
        # 한 번이라도 +3% 수익을 봤다면 손절선이 매수가로 상승
        # breakeven_buffer(-0.5%): 매수가를 딱 터치하는 장중 noise 방지
        highest_gain = (highest_price / entry_price - 1)
        if highest_gain >= self.breakeven_activation and current_return <= self.breakeven_buffer:
            result['should_exit'] = True
            result['reason'] = (
                f"본전 보장 손절 (최고 +{highest_gain*100:.1f}% → 현재 {current_return*100:.2f}%)"
            )
            result['priority'] = 105
            result['stop_loss_price'] = entry_price
            return result

        # 1. ATR 손절 체크
        should_stop, stop_price, reason = self.check_atr_stop_loss(
            entry_price, current_price, atr
        )
        result['stop_loss_price'] = stop_price

        if should_stop:
            result['should_exit'] = True
            result['reason'] = reason
            result['priority'] = 100
            return result

        # 2. 트레일링 스톱 체크 (수익 보호)
        should_trail, trail_price, reason = self.check_trailing_stop(
            entry_price, current_price, highest_price, atr
        )
        result['trailing_stop_price'] = trail_price

        if should_trail:
            result['should_exit'] = True
            result['reason'] = reason
            result['priority'] = 90
            return result

        # 3. ATR 목표가 도달 (부분 청산 고려)
        should_take_profit, target_price, reason = self.check_atr_profit_target(
            entry_price, current_price, atr
        )
        result['profit_target'] = target_price

        if should_take_profit:
            # 목표가 도달 시 절반 청산
            result['should_exit'] = True
            result['exit_type'] = 'partial'
            result['exit_ratio'] = 0.5  # 50% 청산
            result['reason'] = reason + " (50% 부분 청산)"
            result['priority'] = 70
            return result

        # 4. 시간 기반 청산
        should_time_exit, reason = self.check_time_based_exit(
            entry_date, current_date, current_price, entry_price
        )

        if should_time_exit:
            result['should_exit'] = True
            result['reason'] = reason
            result['priority'] = 60
            return result

        # 5. 기술적 지표 청산 (비활성화 - 너무 빨리 청산됨)
        # should_tech_exit, reason = self.check_technical_exit(
        #     current_data, entry_price
        # )
        #
        # if should_tech_exit:
        #     result['should_exit'] = True
        #     result['reason'] = reason
        #     result['priority'] = 50
        #     return result

        # 6. 팩터 스코어 청산
        if current_score is not None:
            should_factor_exit, reason = self.check_factor_score_exit(current_score)

            if should_factor_exit:
                result['should_exit'] = True
                result['reason'] = reason
                result['priority'] = 40
                return result

        # 청산 조건 없음
        return result


    def update_trailing_stop(
        self,
        position: Dict,
        current_price: float
    ) -> Dict:
        """
        트레일링 스톱 업데이트

        최고가 갱신 시 트레일링 스톱 가격도 업데이트

        Parameters:
        -----------
        position : Dict
            포지션 정보
        current_price : float
            현재 가격

        Returns:
        --------
        Dict : 업데이트된 포지션 정보
        """
        if current_price > position.get('highest_price', 0):
            position['highest_price'] = current_price

        return position


def get_exit_signals(
    positions: List[Dict],
    db_name: str = 'daily_buy_list',
    current_date: Optional[datetime] = None
) -> List[Dict]:
    """
    모든 포지션에 대해 청산 시그널 생성

    Parameters:
    -----------
    positions : List[Dict]
        포지션 리스트
    db_name : str
        데이터베이스 이름
    current_date : Optional[datetime]
        현재 날짜 (시뮬레이션 시 필수)

    Returns:
    --------
    List[Dict] : 청산 시그널 리스트
    """
    exit_signals = []
    # 균형잡힌 설정: 고정 손절 -5%, ATR 2.0배 손절, 최대 보유 15일
    exit_strategy = ExitStrategy(
        fixed_stop_loss_pct=-0.05,  # 고정 손절 -5% (최우선)
        atr_stop_multiplier=2.0,  # ATR 손절 (약 5-8% 손실에서 손절)
        max_holding_days=15,  # 최대 보유 15일
        time_stop_loss_pct=-0.05  # 시간 손절 (10일 후 -5%)
    )

    # 에러 추적
    error_count = 0
    table_not_found_count = 0
    first_table_error_shown = False

    for position in positions:
        try:
            code = position['code']

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
                print(f"포지션 {code} 종목명을 찾을 수 없습니다 (stock_item_all에 없음)")
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

            # 시뮬레이션 날짜를 YYYYMMDD 형식으로 변환
            if current_date:
                current_date_str = current_date.strftime('%Y%m%d')
                date_filter = f"AND date <= '{current_date_str}'"
            else:
                date_filter = ""

            query = f"""
            SELECT date, open, high, low, close, volume
            FROM `{code_name}`
            WHERE code = '{code}' {date_filter}
            ORDER BY date DESC
            LIMIT 60
            """

            df = pd.read_sql(query, con)
            con.close()

            if len(df) < 20:
                continue

            # 시간순 정렬 (date 컬럼 사용)
            df = df.sort_values('date').reset_index(drop=True)

            # date 컬럼을 ref_date로 이름 변경 (기존 코드 호환성 유지)
            df = df.rename(columns={'date': 'ref_date'})

            # 청산 판단 (current_date 전달)
            exit_decision = exit_strategy.get_exit_decision(position, df, current_date=current_date)

            if exit_decision['should_exit']:
                exit_signals.append({
                    'code': code,
                    'decision': exit_decision,
                    'current_price': df['close'].iloc[-1],
                    'entry_price': position['entry_price'],
                    'profit_pct': (df['close'].iloc[-1] / position['entry_price'] - 1) * 100
                })

        except Exception as e:
            error_count += 1
            error_msg = str(e)

            # 테이블 없음 오류 감지
            if "Table" in error_msg and "doesn't exist" in error_msg:
                table_not_found_count += 1

                # 첫 번째 테이블 없음 오류 시 상세 안내
                if not first_table_error_shown:
                    first_table_error_shown = True
                    print(f"\n⚠️  경고: 일봉 데이터 테이블이 없습니다!")
                    print(f"   종목 코드: {position.get('code', 'Unknown')}")
                    print(f"   오류 메시지: {e}")
                    print(f"\n💡 해결 방법:")
                    print(f"   1. collector_v3.py를 먼저 실행하여 일봉 데이터를 수집하세요")
                    print(f"   2. daily_craw 데이터베이스에 종목 코드별 테이블이 생성되는지 확인하세요\n")
                else:
                    print(f"포지션 {position.get('code', 'Unknown')} 테이블 없음 (스킵)")
            else:
                print(f"포지션 {position.get('code', 'Unknown')} 청산 시그널 생성 오류: {e}")

            continue

    # 전체 에러 요약
    if error_count > 0:
        print(f"\n📊 청산 시그널 생성 결과:")
        print(f"   전체 포지션: {len(positions)}개")
        print(f"   에러 발생: {error_count}개")
        print(f"   테이블 없음: {table_not_found_count}개")
        print(f"   청산 시그널: {len(exit_signals)}개\n")

        if table_not_found_count == len(positions):
            print(f"⚠️  모든 종목의 일봉 데이터가 없습니다!")
            print(f"   반드시 collector_v3.py를 먼저 실행하세요!\n")

    # 우선순위 순으로 정렬
    exit_signals.sort(key=lambda x: x['decision']['priority'], reverse=True)

    return exit_signals


if __name__ == "__main__":
    # 테스트 코드
    print("=== Exit Strategy 테스트 ===\n")

    # 샘플 데이터 생성
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=60, freq='D')

    # 상승 후 조정 패턴
    prices = [50000]
    for i in range(59):
        if i < 30:
            # 상승
            change = np.random.normal(500, 300)
        else:
            # 조정
            change = np.random.normal(-200, 400)

        prices.append(prices[-1] + change)

    prices = np.array(prices)

    df_test = pd.DataFrame({
        'ref_date': dates,
        'open': prices * 0.995,
        'high': prices * 1.015,
        'low': prices * 0.985,
        'close': prices,
        'volume': np.random.randint(100000, 300000, 60)
    })

    # 포지션 정보
    test_position = {
        'code': 'TEST001',
        'entry_price': 50000,
        'entry_date': datetime(2024, 1, 1),
        'shares': 10,
        'highest_price': max(prices)
    }

    # 청산 전략 실행
    exit_strategy = ExitStrategy(
        atr_stop_multiplier=2.0,
        trailing_stop_activation=0.05,
        max_holding_days=15
    )

    decision = exit_strategy.get_exit_decision(test_position, df_test, current_score=65)

    print("📊 포지션 정보:")
    print(f"  진입가: {test_position['entry_price']:,}원")
    print(f"  현재가: {df_test['close'].iloc[-1]:,}원")
    print(f"  최고가: {test_position['highest_price']:,}원")
    print(f"  수익률: {(df_test['close'].iloc[-1] / test_position['entry_price'] - 1) * 100:.2f}%\n")

    print("🎯 청산 판단:")
    print(f"  청산 여부: {'✅ YES' if decision['should_exit'] else '❌ NO'}")

    if decision['should_exit']:
        print(f"  청산 타입: {decision['exit_type']}")
        print(f"  청산 비율: {decision['exit_ratio'] * 100:.0f}%")
        print(f"  사유: {decision['reason']}")
        print(f"  우선순위: {decision['priority']}")

    print(f"\n📍 기준가:")
    print(f"  손절가: {decision['stop_loss_price']:,}원")
    print(f"  목표가: {decision['profit_target']:,}원")
    if decision['trailing_stop_price'] > 0:
        print(f"  트레일링 스톱: {decision['trailing_stop_price']:,}원")

    print("\n✅ Exit Strategy 모듈 생성 완료!")
