"""
고급 전략 통합 매매 엔진 (Advanced Trading Engine)

실전 트레이더와 통합하여 사용할 수 있는 올인원 매매 엔진
- 멀티팩터 스코어링 + 하이브리드 전략 + 리스크 관리 + 고급 청산
- 날짜 기반 전략 통합
- trader.py와 완벽 호환

사용법:
    from library.advanced_trading_engine import AdvancedTradingEngine

    # 엔진 초기화
    engine = AdvancedTradingEngine(
        portfolio_value=10000000,
        db_name='JackBot1_imi1',
        risk_profile='aggressive'
    )

    # 매수 리스트 생성
    buy_list = engine.get_today_buy_list()

    # 매도 리스트 생성
    sell_list = engine.get_today_sell_list(current_positions)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import pymysql
import logging

# 기존 모듈 임포트
from library.cf import *
from library.advanced_strategy_system import AdvancedStrategySystem
from library.date_based_strategy import (
    get_latest_date_table,
    scan_buy_candidates_from_date_table
)
from library.multi_factor_scoring import get_stock_score
from library.hybrid_strategy import get_buy_candidates
from library.risk_manager import RiskManager, get_stock_atr
from library.exit_strategy import ExitStrategy, get_exit_signals

logger = logging.getLogger(__name__)


class AdvancedTradingEngine:
    """
    고급 전략 통합 매매 엔진

    모든 고급 전략 모듈을 통합하여 실전 트레이더에서 사용
    """

    def __init__(
        self,
        portfolio_value: float,
        db_name: str = 'JackBot1_imi1',
        risk_profile: str = 'aggressive',
        use_date_based_strategy: bool = True,
        strategy_config: Optional[Dict] = None
    ):
        """
        Parameters:
        -----------
        portfolio_value : float
            포트폴리오 총 가치
        db_name : str
            데이터베이스 이름
        risk_profile : str
            리스크 프로필 ('conservative', 'moderate', 'aggressive')
        use_date_based_strategy : bool
            날짜 기반 전략 사용 여부
        strategy_config : Optional[Dict]
            전략 설정 (커스터마이징 가능)
        """
        self.portfolio_value = portfolio_value
        self.db_name = db_name
        self.risk_profile = risk_profile
        self.use_date_based_strategy = use_date_based_strategy

        # 기본 설정
        self.config = strategy_config or {
            'min_factor_score': 70.0,
            'min_hybrid_score': 70.0,
            'min_date_score': 70.0,
            'max_positions': 10,
            'max_position_pct': 0.15,
            'max_daily_loss_pct': -0.08,
            'atr_stop_multiplier': 2.0,
            'trailing_stop_activation': 0.05,
            'max_holding_days': 10,
            'date_strategy_weight': 0.3,  # 날짜 기반 전략 가중치 30%
            'hybrid_strategy_weight': 0.7  # 하이브리드 전략 가중치 70%
        }

        # 고급 전략 시스템 초기화
        self.strategy_system = AdvancedStrategySystem(
            portfolio_value=portfolio_value,
            risk_profile=risk_profile,
            strategy_config=self.config
        )

        # 리스크 관리자
        self.risk_manager = RiskManager(
            portfolio_value=portfolio_value,
            risk_profile=risk_profile,
            max_position_pct=self.config['max_position_pct'],
            max_daily_loss_pct=self.config['max_daily_loss_pct']
        )

        # 청산 전략
        self.exit_strategy = ExitStrategy(
            atr_stop_multiplier=self.config['atr_stop_multiplier'],
            trailing_stop_activation=self.config['trailing_stop_activation'],
            max_holding_days=self.config['max_holding_days']
        )

        logger.info(f"✅ 고급 매매 엔진 초기화 완료")
        logger.info(f"  - 포트폴리오: {portfolio_value:,}원")
        logger.info(f"  - DB: {db_name}")
        logger.info(f"  - 리스크 프로필: {risk_profile}")
        logger.info(f"  - 날짜 기반 전략: {'사용' if use_date_based_strategy else '미사용'}")


    def get_today_buy_list(
        self,
        current_positions: Optional[List[Dict]] = None,
        today_pnl: float = 0.0,
        top_n: int = 20,
        force_date_strategy: bool = False
    ) -> List[Dict]:
        """
        오늘의 매수 리스트 생성

        Parameters:
        -----------
        current_positions : Optional[List[Dict]]
            현재 보유 포지션
        today_pnl : float
            오늘 손익
        top_n : int
            선정할 종목 수
        force_date_strategy : bool
            날짜 기반 전략만 사용 (True), 혼합 사용 (False)

        Returns:
        --------
        List[Dict] : 매수 추천 리스트
            [{
                'code': str,
                'name': str,
                'current_price': float,
                'recommended_shares': int,
                'recommended_value': float,
                'stop_loss': float,
                'profit_target': float,
                'strategy_type': str,
                'composite_score': float
            }]
        """
        current_positions = current_positions or []

        logger.info(f"\n{'='*80}")
        logger.info(f"📊 오늘의 매수 리스트 생성")
        logger.info(f"{'='*80}")

        # 1. 포트폴리오 리스크 체크
        can_trade, message = self.risk_manager.check_portfolio_risk(
            current_positions,
            today_pnl
        )

        if not can_trade:
            logger.warning(f"⚠️  매수 불가: {message}")
            return []

        buy_list = []

        try:
            # 2-1. 날짜 기반 전략 사용
            if self.use_date_based_strategy or force_date_strategy:
                logger.info("📅 날짜 기반 전략으로 스캔 중...")

                df_date_based = scan_buy_candidates_from_date_table(
                    min_score=self.config['min_date_score'],
                    top_n=top_n,
                    db_name='daily_buy_list'
                )

                if not df_date_based.empty:
                    logger.info(f"✅ 날짜 기반: {len(df_date_based)}개 발견")

                    # 날짜 기반 전략만 사용하는 경우
                    if force_date_strategy:
                        buy_list = self._convert_to_buy_list(df_date_based)
                        return self._apply_risk_filters(buy_list, current_positions, top_n)

            # 2-2. 하이브리드 전략 사용 (날짜 기반과 혼합)
            if not force_date_strategy:
                logger.info("🔀 하이브리드 전략으로 스캔 중...")

                df_hybrid = self.strategy_system.generate_buy_signals(
                    current_positions=current_positions,
                    today_pnl=today_pnl,
                    db_name=self.db_name,
                    top_n=top_n
                )

                if not df_hybrid.empty:
                    logger.info(f"✅ 하이브리드: {len(df_hybrid)}개 발견")

                    # 혼합 전략: 날짜 기반 + 하이브리드 종목 합치기
                    if self.use_date_based_strategy and not df_date_based.empty:
                        buy_list = self._merge_strategies(
                            df_date_based,
                            df_hybrid,
                            top_n
                        )
                    else:
                        buy_list = self._convert_to_buy_list(df_hybrid)
                else:
                    # 하이브리드에서 못 찾은 경우 날짜 기반만
                    if self.use_date_based_strategy and not df_date_based.empty:
                        buy_list = self._convert_to_buy_list(df_date_based)

            # 3. 리스크 필터 적용
            if buy_list:
                buy_list = self._apply_risk_filters(buy_list, current_positions, top_n)

            logger.info(f"\n✅ 최종 매수 리스트: {len(buy_list)}개")

            return buy_list

        except Exception as e:
            logger.error(f"❌ 매수 리스트 생성 오류: {e}")
            import traceback
            traceback.print_exc()
            return []


    def _convert_to_buy_list(self, df: pd.DataFrame) -> List[Dict]:
        """
        DataFrame을 매수 리스트로 변환
        """
        buy_list = []

        for _, row in df.iterrows():
            buy_list.append({
                'code': row['code'],
                'name': row.get('code_name', row.get('name', '')),
                'current_price': row['current_price'],
                'recommended_shares': row.get('recommended_shares', 0),
                'recommended_value': row.get('recommended_value', 0),
                'stop_loss': row.get('stop_loss', 0),
                'profit_target': row.get('profit_target', 0),
                'strategy_type': row.get('strategy_type', 'unknown'),
                'composite_score': row.get('composite_score', 0),
                'volume_ratio': row.get('volume_ratio', 0),
                'atr': row.get('atr', 0)
            })

        return buy_list


    def _merge_strategies(
        self,
        df_date_based: pd.DataFrame,
        df_hybrid: pd.DataFrame,
        top_n: int
    ) -> List[Dict]:
        """
        날짜 기반 전략과 하이브리드 전략 결과를 합치기

        - 날짜 기반: 30%
        - 하이브리드: 70%
        """
        date_count = int(top_n * self.config['date_strategy_weight'])
        hybrid_count = int(top_n * self.config['hybrid_strategy_weight'])

        # 날짜 기반에서 상위 N개
        date_list = self._convert_to_buy_list(df_date_based.head(date_count))

        # 하이브리드에서 상위 N개
        hybrid_list = self._convert_to_buy_list(df_hybrid.head(hybrid_count))

        # 합치기 (중복 제거)
        merged = {}

        for item in date_list:
            merged[item['code']] = item

        for item in hybrid_list:
            if item['code'] not in merged:
                merged[item['code']] = item
            else:
                # 이미 있으면 스코어 평균
                merged[item['code']]['composite_score'] = (
                    merged[item['code']]['composite_score'] + item['composite_score']
                ) / 2

        # 리스트로 변환 및 정렬
        result = list(merged.values())
        result.sort(key=lambda x: x['composite_score'], reverse=True)

        logger.info(f"🔀 전략 혼합: 날짜 {date_count}개 + 하이브리드 {hybrid_count}개 = 총 {len(result)}개")

        return result


    def _apply_risk_filters(
        self,
        buy_list: List[Dict],
        current_positions: List[Dict],
        top_n: int
    ) -> List[Dict]:
        """
        리스크 필터 적용
        """
        filtered = []
        current_codes = [p.get('code') for p in current_positions]

        for item in buy_list:
            code = item['code']

            # 1. 이미 보유한 종목 제외
            if code in current_codes:
                logger.debug(f"⚠️  {code}: 이미 보유 중")
                continue

            # 2. 상관관계 체크
            correlation_ok, max_corr = self.risk_manager.check_correlation_limit(
                code,
                current_codes,
                self.db_name
            )

            if not correlation_ok:
                logger.debug(f"⚠️  {code}: 상관관계 높음 (max: {max_corr:.2f})")
                continue

            # 3. 포지션 사이즈 재계산
            atr = item.get('atr', 0)
            if atr == 0:
                atr = get_stock_atr(code, self.db_name)

            if atr > 0:
                position_info = self.risk_manager.get_position_score(
                    stock_data={
                        'code': code,
                        'price': item['current_price'],
                        'atr': atr,
                        'sector': 'Unknown'
                    },
                    current_positions=current_positions
                )

                # 리스크 스코어 체크
                if position_info['risk_score'] > 70:
                    logger.debug(f"⚠️  {code}: 리스크 스코어 높음 ({position_info['risk_score']:.1f})")
                    continue

                # 포지션 정보 업데이트
                item['recommended_shares'] = position_info['recommended_shares']
                item['recommended_value'] = position_info['recommended_value']
                item['stop_loss'] = position_info['stop_loss']
                item['profit_target'] = position_info['profit_target']
                item['risk_score'] = position_info['risk_score']

            filtered.append(item)

            # Top N 도달
            if len(filtered) >= top_n:
                break

        return filtered


    def get_today_sell_list(
        self,
        current_positions: List[Dict],
        db_name: Optional[str] = None
    ) -> List[Dict]:
        """
        오늘의 매도 리스트 생성

        Parameters:
        -----------
        current_positions : List[Dict]
            현재 보유 포지션
            [{
                'code': str,
                'entry_price': float,
                'entry_date': datetime or str,
                'shares': int,
                'highest_price': float (optional)
            }]
        db_name : Optional[str]
            데이터베이스 이름 (없으면 self.db_name 사용)

        Returns:
        --------
        List[Dict] : 매도 시그널 리스트
            [{
                'code': str,
                'decision': {
                    'should_exit': bool,
                    'reason': str,
                    'exit_ratio': float,
                    'priority': int
                },
                'current_price': float,
                'pnl_pct': float
            }]
        """
        if not current_positions:
            return []

        db_name = db_name or self.db_name

        logger.info(f"\n{'='*80}")
        logger.info(f"📉 오늘의 매도 리스트 생성")
        logger.info(f"{'='*80}")
        logger.info(f"보유 종목 수: {len(current_positions)}개")

        try:
            # 고급 청산 전략으로 매도 시그널 생성
            sell_signals = get_exit_signals(current_positions, db_name)

            # 매도해야 하는 종목만 필터링
            sell_list = [
                signal for signal in sell_signals
                if signal['decision']['should_exit']
            ]

            # 우선순위 정렬 (높은 우선순위부터)
            sell_list.sort(key=lambda x: x['decision']['priority'], reverse=True)

            logger.info(f"✅ 매도 시그널: {len(sell_list)}개")

            for signal in sell_list:
                logger.info(
                    f"  - {signal['code']}: {signal['decision']['reason']} "
                    f"(우선순위: {signal['decision']['priority']}, "
                    f"손익: {signal.get('pnl_pct', 0):.2f}%)"
                )

            return sell_list

        except Exception as e:
            logger.error(f"❌ 매도 리스트 생성 오류: {e}")
            import traceback
            traceback.print_exc()
            return []


    def update_positions(
        self,
        positions: List[Dict],
        db_name: Optional[str] = None
    ) -> List[Dict]:
        """
        포지션 업데이트 (최고가, 트레일링 스톱 등)

        Parameters:
        -----------
        positions : List[Dict]
            현재 포지션
        db_name : Optional[str]
            데이터베이스 이름

        Returns:
        --------
        List[Dict] : 업데이트된 포지션
        """
        db_name = db_name or self.db_name

        return self.strategy_system.update_position_tracking(positions, db_name)


    def get_portfolio_status(
        self,
        positions: List[Dict],
        cash: float
    ) -> Dict:
        """
        포트폴리오 현황 조회

        Parameters:
        -----------
        positions : List[Dict]
            현재 포지션
        cash : float
            현금

        Returns:
        --------
        Dict : 포트폴리오 현황
        """
        return self.strategy_system.get_portfolio_status(positions, cash)


    def print_buy_list(self, buy_list: List[Dict]):
        """
        매수 리스트 출력 (보기 좋게)
        """
        if not buy_list:
            print("\n❌ 매수 후보가 없습니다.")
            return

        print(f"\n{'='*100}")
        print(f"📊 오늘의 매수 리스트 ({len(buy_list)}개)")
        print(f"{'='*100}")

        for idx, item in enumerate(buy_list, 1):
            print(f"\n[{idx}] {item['code']} - {item['name']}")
            print(f"  현재가:         {item['current_price']:>10,}원")
            print(f"  종합 스코어:    {item['composite_score']:>10.1f}/100")
            print(f"  전략 타입:      {item['strategy_type']:>20}")
            print(f"  추천 수량:      {item['recommended_shares']:>10}주")
            print(f"  투자 금액:      {item['recommended_value']:>10,}원")
            print(f"  손절가:         {item['stop_loss']:>10,}원 ({(item['stop_loss']/item['current_price']-1)*100:>6.2f}%)")
            print(f"  목표가:         {item['profit_target']:>10,}원 ({(item['profit_target']/item['current_price']-1)*100:>6.2f}%)")
            if item.get('volume_ratio'):
                print(f"  거래량 비율:    {item['volume_ratio']:>10.2f}x")
            if item.get('risk_score'):
                print(f"  리스크 스코어:  {item['risk_score']:>10.1f}/100")

        print(f"\n{'='*100}")


    def print_sell_list(self, sell_list: List[Dict]):
        """
        매도 리스트 출력 (보기 좋게)
        """
        if not sell_list:
            print("\n✅ 매도할 종목이 없습니다.")
            return

        print(f"\n{'='*100}")
        print(f"📉 오늘의 매도 리스트 ({len(sell_list)}개)")
        print(f"{'='*100}")

        for idx, signal in enumerate(sell_list, 1):
            decision = signal['decision']
            print(f"\n[{idx}] {signal['code']}")
            print(f"  현재가:         {signal.get('current_price', 0):>10,}원")
            print(f"  손익:           {signal.get('pnl_pct', 0):>10.2f}%")
            print(f"  매도 사유:      {decision['reason']}")
            print(f"  매도 비율:      {decision['exit_ratio']*100:>10.0f}%")
            print(f"  우선순위:       {decision['priority']:>10}")

        print(f"\n{'='*100}")


def create_trading_engine(
    portfolio_value: float = 10000000,
    db_name: str = 'JackBot1_imi1',
    risk_profile: str = 'aggressive'
) -> AdvancedTradingEngine:
    """
    간편 생성 함수

    Parameters:
    -----------
    portfolio_value : float
        포트폴리오 가치
    db_name : str
        데이터베이스 이름
    risk_profile : str
        리스크 프로필

    Returns:
    --------
    AdvancedTradingEngine : 매매 엔진
    """
    return AdvancedTradingEngine(
        portfolio_value=portfolio_value,
        db_name=db_name,
        risk_profile=risk_profile
    )


if __name__ == "__main__":
    # 테스트 코드
    print("=" * 100)
    print("🚀 고급 전략 통합 매매 엔진 테스트")
    print("=" * 100)

    # 엔진 생성
    engine = create_trading_engine(
        portfolio_value=10000000,
        db_name='daily_buy_list',
        risk_profile='aggressive'
    )

    # 매수 리스트 생성
    print("\n📊 매수 리스트 생성 중...")
    buy_list = engine.get_today_buy_list(top_n=10)

    # 출력
    engine.print_buy_list(buy_list)

    print("\n" + "=" * 100)
    print("✅ 테스트 완료!")
    print("=" * 100)
