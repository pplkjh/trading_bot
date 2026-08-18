"""
Exit Strategy Module — 통합 매도 전략

[백테스트용] ExitStrategy 클래스 + get_exit_signals()
  - ADX/ATR/BB 지표 기반 동적 청산 (daily_craw DB 직접 조회)
  - simulator5(Strategy B 백테스트) 에서 사용

[실전 라이브용] get_live_sell_signals(positions, indicator_map)
  - Strategy A/B 분기, ATR 기반 트레일링, open_api.get_sell_list()에서 호출
  - 새 전략 추가 시 LIVE_EXIT_STRATEGY_MAP 에 등록만 하면 됨

  전략별 로직:
    A (돌파): 하드SL(-5%) → 트레일링(ATR×mult, floor+1%) → 15일 시간청산
    B (반전): 하드SL(-5%) → ATR목표가(primary) → 트레일링(secondary) → 45일 시간청산
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import pymysql
from library.cf import *
from library.technical_indicators import calculate_atr

logger = logging.getLogger(__name__)


class ExitStrategy:
    """
    고급 청산 전략

    다양한 청산 조건을 결합하여 최적의 청산 시점 결정
    """

    def __init__(
        self,
        atr_stop_multiplier: float = 2.0,
        trailing_atr_multiplier: float = 2.0,
        trailing_stop_activation: float = 0.03,
        trailing_stop_distance: float = 0.03,
        trailing_stop_floor_pct: float = 0.01,
        max_holding_days: int = 15,
        time_stop_loss_pct: float = -0.02,
        factor_score_threshold: float = 40.0,
        fixed_stop_loss_pct: float = -0.05,
        emergency_stop_atr_multiplier: float = 3.0,
        losscut_delay_minutes: int = 30
    ):
        """
        청산 우선순위:
          120 긴급손절  — ATR×emergency_stop_atr_multiplier(3.0), 유예 없음
          100 고정손절  — fixed_stop_loss_pct(-5%), losscut_delay_minutes(30분) 유예
           90 트레일링  — trailing_stop_activation(+3%) 이상에서 발동,
                          스톱 = max(entry×1.01, highest - ATR×trailing_atr_multiplier)
           70 ATR목표가 — entry + ATR×atr_stop_multiplier × risk_reward_ratio(1.0)
           60 시간청산  — max_holding_days 초과
           40 팩터스코어 — factor_score_threshold 이하
        """
        self.atr_stop_multiplier = atr_stop_multiplier
        self.trailing_atr_multiplier = trailing_atr_multiplier
        self.trailing_stop_activation = trailing_stop_activation
        self.trailing_stop_distance = trailing_stop_distance
        self.trailing_stop_floor_pct = trailing_stop_floor_pct
        self.max_holding_days = max_holding_days
        self.time_stop_loss_pct = time_stop_loss_pct
        self.factor_score_threshold = factor_score_threshold
        self.fixed_stop_loss_pct = fixed_stop_loss_pct
        self.emergency_stop_atr_multiplier = emergency_stop_atr_multiplier
        self.losscut_delay_minutes = losscut_delay_minutes


    def check_emergency_stop(
        self,
        entry_price: float,
        current_price: float,
        atr: float
    ) -> Tuple[bool, float, str]:
        """
        긴급 손절 체크 (ATR×3, 유예 없음)
        갭다운·서킷브레이커 등 재난적 급락 시 즉시 발동
        """
        stop_price = entry_price - (atr * self.emergency_stop_atr_multiplier)

        if current_price <= stop_price:
            loss_pct = (current_price / entry_price - 1) * 100
            return True, stop_price, f"긴급 손절 도달 ({loss_pct:.2f}%)"

        return False, stop_price, ""


    def check_atr_profit_target(
        self,
        entry_price: float,
        current_price: float,
        atr: float,
        risk_reward_ratio: float = 1.0
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
        # 트레일링 스톱 활성화 체크 — 최고가(highest_price) 기준
        # ⚠️ 버그 수정: current_price → highest_price
        # current_price로 체크하면 고점 달성 후 되돌릴 때 비활성화되어 플로어가 의미없어짐
        # 예) 매수10,000 → 고점10,300(+3%) → 현재10,100(+1%):
        #   잘못된 방식: current_gain=1% < 3% → 비활성화 → 빠져도 안팜
        #   올바른 방식: highest_gain=3% ≥ 3% → 활성화 유지 → 플로어에서 익절
        highest_gain = (highest_price / entry_price - 1)
        if highest_gain < self.trailing_stop_activation:
            return False, 0, ""

        # ATR 기반 또는 고정 비율로 trailing 스톱 계산
        if atr and atr > 0:
            raw_stop = highest_price - (atr * self.trailing_atr_multiplier)
        else:
            raw_stop = highest_price * (1 - self.trailing_stop_distance)

        # floor: 트레일링 발동 후 매수가+1% 이상 보장 (매수가 이하 손절 방지)
        floor = entry_price * (1 + self.trailing_stop_floor_pct)
        trailing_stop_price = max(floor, raw_stop)

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

        # 6일 이상 보유 + 수익 중 → 모멘텀 소진으로 판단, 익절
        if holding_days >= 6 and current_return > 0:
            return True, f"시간 기반 익절 ({holding_days}일, {current_return*100:.2f}%)"

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

        # 0. 긴급 손절 (ATR×3, 유예 없음) — 갭다운·서킷브레이커 등 재난적 급락
        should_emergency, emerg_price, reason = self.check_emergency_stop(
            entry_price, current_price, atr
        )
        result['stop_loss_price'] = emerg_price

        if should_emergency:
            result['should_exit'] = True
            result['reason'] = reason
            result['priority'] = 120
            return result

        # 1. 고정 손절 (-5%, 30분 유예) — 일반 손절
        current_return = (current_price / entry_price - 1)
        if current_return <= self.fixed_stop_loss_pct:
            losscut_active = True
            try:
                elapsed_min = (datetime.now() - entry_date).total_seconds() / 60
                if elapsed_min < self.losscut_delay_minutes:
                    losscut_active = False
            except Exception:
                pass
            if losscut_active:
                loss_pct = current_return * 100
                result['should_exit'] = True
                result['reason'] = f"고정 손절 도달 ({loss_pct:.2f}%)"
                result['priority'] = 100
                result['stop_loss_price'] = entry_price * (1 + self.fixed_stop_loss_pct)
                return result

        # 2. 트레일링 스톱 (+3% 발동, floor=entry×1.01)
        should_trail, trail_price, reason = self.check_trailing_stop(
            entry_price, current_price, highest_price, atr
        )
        result['trailing_stop_price'] = trail_price

        if should_trail:
            result['should_exit'] = True
            result['reason'] = reason
            result['priority'] = 90
            return result

        # 3. ATR 목표가 도달 (RR=1.0)
        should_take_profit, target_price, reason = self.check_atr_profit_target(
            entry_price, current_price, atr
        )
        result['profit_target'] = target_price

        if should_take_profit:
            result['should_exit'] = True
            result['exit_type'] = 'full'
            result['exit_ratio'] = 1.0
            result['reason'] = reason
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

        # 5. 팩터 스코어 청산
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


# 일봉 지표는 장중에 바뀌지 않으므로 날짜 단위로 캐싱
# {date_str: {code: indicators_dict}}
_indicators_cache: Dict[str, Dict] = {}


def _get_stock_indicators(code: str) -> Optional[Dict]:
    """
    daily_buy_list 최신 날짜 테이블에서 종목의 기술 지표 조회.
    ADX 기반 동적 파라미터 설정에 사용.
    일봉 지표는 장중에 바뀌지 않으므로 날짜 단위로 캐싱한다.

    Returns: dict with adx, plus_di, minus_di, atr14, bb_position, macd_histogram
             or None on failure
    """
    today_str = datetime.now().strftime('%Y%m%d')

    # 날짜가 바뀌면 캐시 초기화
    cached_today = _indicators_cache.get('_date')
    if cached_today != today_str:
        _indicators_cache.clear()
        _indicators_cache['_date'] = today_str

    if code in _indicators_cache:
        return _indicators_cache[code]

    try:
        con = pymysql.connect(
            user=db_id, passwd=db_passwd, host=db_ip,
            db='daily_buy_list', charset='utf8', port=int(db_port)
        )
        cursor = con.cursor()

        # 최신 날짜 테이블 찾기 (YYYYMMDD 형식)
        cursor.execute(
            "SELECT TABLE_NAME FROM information_schema.tables "
            "WHERE table_schema='daily_buy_list' AND table_name REGEXP '^[0-9]{8}$' "
            "ORDER BY TABLE_NAME DESC LIMIT 1"
        )
        row = cursor.fetchone()
        if not row:
            con.close()
            return None

        latest_table = row[0]

        cursor.execute(
            f"SELECT adx, plus_di, minus_di, atr14, "
            f"bb_upper, bb_middle, bb_lower, macd_histogram, close "
            f"FROM `{latest_table}` WHERE code = %s LIMIT 1",
            (code,)
        )
        ind = cursor.fetchone()
        con.close()

        if not ind:
            _indicators_cache[code] = None
            return None

        adx, plus_di, minus_di, atr14, bb_upper, bb_middle, bb_lower, macd_histogram, close = ind

        bb_range = (float(bb_upper or 0)) - (float(bb_lower or 0))
        bb_position = ((float(close or 0)) - float(bb_lower or 0)) / bb_range if bb_range > 0 else 0.5

        result = {
            'adx':            float(adx or 0),
            'plus_di':        float(plus_di or 0),
            'minus_di':       float(minus_di or 0),
            'atr14':          float(atr14 or 0),
            'bb_position':    bb_position,
            'macd_histogram': float(macd_histogram or 0),
        }
        _indicators_cache[code] = result
        return result
    except Exception:
        _indicators_cache[code] = None
        return None


def _build_exit_strategy(indicators: Optional[Dict]) -> ExitStrategy:
    """
    ADX 값에 따라 동적으로 ExitStrategy 파라미터를 결정한다.

    공통:
      - 긴급 손절: ATR×3 (유예 없음)
      - 고정 손절: -5% (30분 유예)
      - 트레일링: +3% 발동, floor=entry×1.01
      - ATR 목표가: entry + ATR×배수×1.0 (RR=1.0)

    추세장 (ADX ≥ 25): ATR×2.5, 최대 10일 보유
    중간장 (ADX 20~25): ATR×2.0, 최대 8일 보유
    횡보장 (ADX < 20):  ATR×1.5, 최대 6일 보유
    """
    adx = indicators.get('adx', 0) if indicators else 0

    if adx >= 25:
        strategy = ExitStrategy(
            fixed_stop_loss_pct=-0.05,
            emergency_stop_atr_multiplier=3.0,
            atr_stop_multiplier=2.5,
            trailing_atr_multiplier=2.5,
            trailing_stop_activation=0.03,
            trailing_stop_floor_pct=0.01,
            max_holding_days=10,
            losscut_delay_minutes=30
        )
    elif adx >= 20:
        strategy = ExitStrategy(
            fixed_stop_loss_pct=-0.05,
            emergency_stop_atr_multiplier=3.0,
            atr_stop_multiplier=2.0,
            trailing_atr_multiplier=2.0,
            trailing_stop_activation=0.03,
            trailing_stop_floor_pct=0.01,
            max_holding_days=8,
            losscut_delay_minutes=30
        )
    else:
        strategy = ExitStrategy(
            fixed_stop_loss_pct=-0.05,
            emergency_stop_atr_multiplier=3.0,
            atr_stop_multiplier=1.5,
            trailing_atr_multiplier=1.5,
            trailing_stop_activation=0.03,
            trailing_stop_floor_pct=0.01,
            max_holding_days=6,
            losscut_delay_minutes=30
        )

    if indicators:
        plus_di       = indicators.get('plus_di', 0)
        minus_di      = indicators.get('minus_di', 0)
        bb_position   = indicators.get('bb_position', 0.5)
        macd_histogram = indicators.get('macd_histogram', 0)

        # +DI < -DI: 방향 전환 → 트레일링 즉시 활성화 (수익 여부 무관)
        if plus_di > 0 and minus_di > 0 and plus_di < minus_di:
            strategy.trailing_stop_activation = 0.0

        # BB 상단 근접(>0.85) + MACD 음전환 → 트레일링 거리 축소 (빠른 수익 보호)
        if bb_position > 0.85 and macd_histogram < 0:
            strategy.trailing_atr_multiplier = max(1.0, strategy.trailing_atr_multiplier - 0.5)
            strategy.trailing_stop_activation = 0.0

    return strategy


def get_exit_signals(
    positions: List[Dict],
    db_name: str = 'daily_buy_list',
    current_date: Optional[datetime] = None
) -> List[Dict]:
    """
    모든 포지션에 대해 청산 시그널 생성.
    종목별로 ADX/DI/BB 지표를 조회하여 ExitStrategy 파라미터를 동적으로 결정한다.

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

    # 에러 추적
    error_count = 0
    table_not_found_count = 0
    first_table_error_shown = False

    for position in positions:
        try:
            code = position['code']

            # 0. 종목별 지표 조회 → ADX 기반 동적 ExitStrategy 생성
            indicators = _get_stock_indicators(code)
            exit_strategy = _build_exit_strategy(indicators)

            if indicators:
                logger.debug(
                    f"{code} 매도전략: ADX={indicators['adx']:.1f} "
                    f"+DI={indicators['plus_di']:.1f} -DI={indicators['minus_di']:.1f} "
                    f"BB_pos={indicators['bb_position']:.2f} "
                    f"ATR_stop×{exit_strategy.atr_stop_multiplier} "
                    f"trail_act={exit_strategy.trailing_stop_activation*100:.0f}% "
                    f"max_days={exit_strategy.max_holding_days}"
                )

            # 1. position dict에 code_name이 있으면 바로 사용, 없으면 stock_item_all 조회
            code_name = position.get('code_name')
            if not code_name:
                con = pymysql.connect(
                    user=db_id,
                    passwd=db_passwd,
                    host=db_ip,
                    db='daily_buy_list',
                    charset='utf8',
                    port=int(db_port)
                )
                query_get_name = f"SELECT code_name FROM stock_item_all WHERE code = '{code}' LIMIT 1"
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
                realtime_price = position['current_price']
                exit_signals.append({
                    'code': code,
                    'code_name': code_name,
                    'decision': exit_decision,
                    'current_price': realtime_price,
                    'entry_price': position['entry_price'],
                    'profit_pct': (realtime_price / position['entry_price'] - 1) * 100
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


# ═══════════════════════════════════════════════════════════════════════════════
#  실전 라이브 매도 전략
#  ─ 백테스트용 ExitStrategy 클래스와 완전히 독립
#  ─ open_api.get_sell_list() → get_live_sell_signals() 경로로만 호출
# ═══════════════════════════════════════════════════════════════════════════════

import datetime as _dt

# ── 공통 파라미터 ──────────────────────────────────────────────────────────────
_HARD_SL_PCT        = -0.05   # 하드 손절 -5%
_TRAILING_ACT_PCT   =  0.03   # 트레일링 발동: 고점 +3%
_TRAILING_FLOOR_PCT =  0.01   # 트레일링 플로어: 매입가 +1%
_TRAILING_PCT_CAP   =  0.03   # 최고가 대비 최대 후퇴 허용폭 3%
_LOSSCUT_DELAY_MIN  =  30     # 손절 유예: 매수 후 30분

# ── 전략별 트레일링 배율 ────────────────────────────────────────────────────────
# Strategy A (돌파): ADX 기반 — 강한 추세일수록 넓게 줘서 추세를 끝까지 탐
#   ADX ≥ 25 → 2.5x  /  ADX 20~25 → 2.0x  /  ADX < 20 → 1.5x
# Strategy B (반전): 고정 1.0x — 상승 조짐 꺾이면 빠르게 수익 보호
_B_TRAILING_MULT = 1.0


def _live_atr_mult(adx: float) -> float:
    """Strategy A 전용 — ADX 기반 ATR 배율 (추세 강도에 따라 트레일링 거리 조정)"""
    if adx >= 25:
        return 2.5
    if adx >= 20:
        return 2.0
    return 1.5


def _live_losscut_active(buy_date_str: str) -> bool:
    """매수 후 30분 이내면 손절 유예 반환 (True = 손절 가능)"""
    try:
        buy_dt  = _dt.datetime.strptime(str(buy_date_str)[:12], '%Y%m%d%H%M')
        elapsed = (_dt.datetime.now() - buy_dt).total_seconds() / 60
        return elapsed >= _LOSSCUT_DELAY_MIN
    except Exception:
        return True   # 파싱 실패 → 유예 없이 손절 허용


def _live_holding_days(buy_date_str: str) -> int:
    """보유 일수 계산"""
    try:
        buy_dt = _dt.datetime.strptime(str(buy_date_str)[:8], '%Y%m%d')
        return (_dt.datetime.now() - buy_dt).days
    except Exception:
        return 0


def _live_check_hard_sl(profit_pct: float, losscut_active: bool):
    """공통: 하드 손절 -5%  →  (triggered, reason)"""
    if losscut_active and profit_pct <= (_HARD_SL_PCT * 100):
        return True, f'하드SL({profit_pct:.2f}%)'
    return False, ''


def _live_check_trailing(entry: float, highest: float, current: float,
                          atr: float, mult: float):
    """
    공통: ATR 기반 트레일링 스톱
      발동: highest ≥ entry × (1 + 3%)
      거리: max(highest - ATR×mult,  highest × 0.95)
            → ATR이 크면 5% 고정 추적으로 자동 전환 (최고가 추적 보장)
            → ATR이 작으면 ATR 기반 (더 타이트할 때만 적용)
      플로어: max(stop, entry × 1.01)

    mult: 호출자가 전략에 맞게 결정해서 넘겨줌
          A → _live_atr_mult(adx)   (ADX 기반 가변)
          B → _B_TRAILING_MULT=1.0  (고정 타이트)

    반환: (triggered, stop_price, reason)
    """
    if entry <= 0 or (highest / entry) < (1 + _TRAILING_ACT_PCT):
        return False, 0.0, ''

    pct_stop = highest * (1 - _TRAILING_PCT_CAP)              # 최고가의 5% 이내 추적 보장
    atr_stop = (highest - atr * mult) if atr > 0 else pct_stop
    raw_stop = max(atr_stop, pct_stop)   # 둘 중 높은 쪽 (더 타이트한 쪽) 사용
    stop     = max(raw_stop, entry * (1 + _TRAILING_FLOOR_PCT))

    peak_pct = (highest / entry - 1) * 100
    cur_pct  = (current / entry - 1) * 100

    if current <= stop:
        return True, stop, f'트레일링(고점+{peak_pct:.1f}%→현재{cur_pct:.2f}%)'
    return False, stop, ''


def _live_check_atr_target(entry: float, current: float,
                             atr: float, adx: float):
    """
    Strategy B 전용: ATR 목표가 도달 시 익절
      목표가 = entry + ATR × mult
    반환: (triggered, target_price, reason)
    """
    if entry <= 0 or atr <= 0:
        return False, 0.0, ''

    mult   = _live_atr_mult(adx)
    target = entry + atr * mult
    pct    = (current / entry - 1) * 100

    if current >= target:
        return True, target, f'ATR목표가(+{pct:.2f}%)'
    return False, target, ''


# ── 전략별 매도 함수 ───────────────────────────────────────────────────────────

def strategy_a_exit(pos: dict, ind: dict) -> tuple:
    """
    Strategy A — 돌파 전략 매도
    하드SL(-5%) → 트레일링(ATR×mult, floor+1%) → 15일 시간청산

    pos: {'entry_price', 'highest_price', 'current_price', 'buy_date'}
    ind: {'atr14', 'adx'}
    반환: (should_sell: bool, reason: str, stop_price: float)
    """
    entry    = float(pos.get('entry_price',   0))
    highest  = float(pos.get('highest_price', entry))
    current  = float(pos.get('current_price', entry))
    buy_date = pos.get('buy_date', '')
    atr      = float(ind.get('atr14', 0))
    adx      = float(ind.get('adx',   0))

    profit_pct     = (current / entry - 1) * 100 if entry > 0 else 0
    losscut_active = _live_losscut_active(buy_date)
    holding_days   = _live_holding_days(buy_date)

    # 1. 하드 SL -5%
    hit, reason = _live_check_hard_sl(profit_pct, losscut_active)
    if hit:
        return True, f'A_{reason}', entry * (1 + _HARD_SL_PCT)

    # 2. 트레일링 스톱 (ADX 기반 배율 — 추세 강할수록 넓게)
    hit, stop, reason = _live_check_trailing(entry, highest, current, atr, _live_atr_mult(adx))
    if hit:
        return True, f'A_{reason}', stop

    # 3. 시간청산 15일 (돌파 모멘텀 소멸 기준)
    if holding_days >= 15:
        return True, f'A_시간청산({holding_days}일)', 0.0

    return False, '', 0.0


def strategy_b_exit(pos: dict, ind: dict) -> tuple:
    """
    Strategy B — 반전 전략 매도
    하드SL(-5%) → 트레일링(ATR×1.0 고정, 타이트) → 45일 시간청산

    트레일링 배율 _B_TRAILING_MULT=1.0 고정:
      - 반전 종목은 상승 조짐 꺾이면 빠르게 수익 보호
      - ADX 배율 불필요 (반전 진입 시점은 대부분 ADX < 20, 추세 약함)
      - A(1.5~2.5x)보다 타이트하게 → 수익 더 빨리 확정

    pos: {'entry_price', 'highest_price', 'current_price', 'buy_date'}
    ind: {'atr14', 'adx'}
    반환: (should_sell: bool, reason: str, stop_price: float)
    """
    entry    = float(pos.get('entry_price',   0))
    highest  = float(pos.get('highest_price', entry))
    current  = float(pos.get('current_price', entry))
    buy_date = pos.get('buy_date', '')
    atr      = float(ind.get('atr14', 0))

    profit_pct     = (current / entry - 1) * 100 if entry > 0 else 0
    losscut_active = _live_losscut_active(buy_date)
    holding_days   = _live_holding_days(buy_date)

    # 1. 하드 SL -5%
    hit, reason = _live_check_hard_sl(profit_pct, losscut_active)
    if hit:
        return True, f'B_{reason}', entry * (1 + _HARD_SL_PCT)

    # 2. 트레일링 스톱 (ATR×1.0 고정 — 상승세 꺾이면 빠르게 대응)
    hit, stop, reason = _live_check_trailing(entry, highest, current, atr, _B_TRAILING_MULT)
    if hit:
        return True, f'B_{reason}', stop

    # 3. 시간청산 45일
    if holding_days >= 45:
        return True, f'B_시간청산({holding_days}일)', 0.0

    return False, '', 0.0


def strategy_d_exit(pos: dict, ind: dict) -> tuple:
    """
    Strategy D — 데이트레이딩 매도
    하드SL(-2%) / 트레일링(+5%활성 → 5%트레일 / +1% 플로어)
    손절 유예 없음 — 장중 포지션은 즉각 관리

    트레일링 미활성 구간 (+5% 미달):
      - 하드SL -2% 만 적용, 익절선 없음 (트레일링 발동 기다림)
    트레일링 활성 구간 (최고가 >= 매수가×1.05):
      - trail_stop = max(최고가×0.95, 매수가×1.01)
      - 현재가 <= trail_stop → 트레일링 청산
    """
    entry   = float(pos.get('entry_price',  0))
    current = float(pos.get('current_price', entry))
    highest = float(pos.get('highest_price', current))

    profit_pct = (current / entry - 1) * 100 if entry > 0 else 0

    # 하드 SL -2% (트레일링 활성 여부 무관)
    if profit_pct <= -2.0:
        return True, f'D_하드SL({profit_pct:.2f}%)', entry * 0.98

    # 트레일링 활성: 최고가 >= 매수가 +5%
    if entry > 0 and highest >= entry * 1.05:
        trail_stop = max(highest * 0.95, entry * 1.01)
        if current <= trail_stop:
            peak_pct = (highest / entry - 1) * 100
            return True, f'D_트레일링(고점+{peak_pct:.1f}%→현재{profit_pct:.2f}%)', trail_stop

    return False, '', 0.0


# ── 전략 레지스트리 — 새 전략 추가 시 여기에만 등록 ───────────────────────────
LIVE_EXIT_STRATEGY_MAP = {
    'A': strategy_a_exit,
    'B': strategy_b_exit,
    'D': strategy_d_exit,
}


def get_live_sell_signals(positions: list, indicator_map: dict = None) -> list:
    """
    실전 통합 매도 시그널 생성 — open_api.get_sell_list() 에서 호출

    Parameters
    ----------
    positions : list of dict
        [{ 'code', 'code_name', 'strategy_type',
           'entry_price', 'highest_price', 'current_price', 'buy_date' }, ...]
    indicator_map : dict
        { code: {'atr14': float, 'adx': float}, ... }
        없으면 ATR=0 (트레일링 고정 -5% fallback 자동 적용)

    Returns
    -------
    list of dict
        [{ 'code', 'code_name', 'current_price', 'entry_price',
           'profit_pct', 'reason', 'stop_price', 'strategy_type' }, ...]
    """
    if indicator_map is None:
        indicator_map = {}

    sell_signals = []

    for pos in positions:
        code          = pos.get('code', '')
        strategy_type = pos.get('strategy_type', 'A')
        ind           = indicator_map.get(code, {})

        exit_fn = LIVE_EXIT_STRATEGY_MAP.get(strategy_type, strategy_a_exit)

        try:
            should_sell, reason, stop_price = exit_fn(pos, ind)
        except Exception as e:
            logger.warning(f"[exit_live] {code} 매도 체크 오류: {e}")
            continue

        if should_sell:
            entry   = float(pos.get('entry_price',   0))
            current = float(pos.get('current_price', 0))
            pct     = (current / entry - 1) * 100 if entry > 0 else 0

            sell_signals.append({
                'code':          code,
                'code_name':     pos.get('code_name', code),
                'current_price': current,
                'entry_price':   entry,
                'profit_pct':    pct,
                'reason':        reason,
                'stop_price':    stop_price,
                'strategy_type': strategy_type,
            })
            logger.info(
                f"📉 매도시그널: {pos.get('code_name', code)}({code})"
                f" [{strategy_type}] {reason}  수익: {pct:+.2f}%"
            )

    return sell_signals


# ══════════════════════════════════════════════════════════════════════════════

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
