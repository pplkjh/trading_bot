"""
Advanced Trading Strategy System
모든 고급 모듈을 통합한 전략 시스템

통합 기능:
1. Multi-Factor Scoring
2. Hybrid Strategy (Momentum + Mean Reversion)
3. Risk Management (ATR-based Position Sizing)
4. Advanced Exit Strategy (Trailing Stops)
5. Performance Analytics

사용법:
    system = AdvancedStrategySystem(portfolio_value=10000000)
    buy_list = system.generate_buy_signals(stock_codes)
    sell_list = system.generate_sell_signals(positions)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import pymysql

from library.cf import *
from library.multi_factor_scoring import MultiFactorScoring, get_stock_score
from library.hybrid_strategy import HybridStrategy, get_buy_candidates
from library.risk_manager import RiskManager, get_stock_atr
from library.exit_strategy import ExitStrategy, get_exit_signals
from library.performance_analytics import PerformanceAnalytics


class AdvancedStrategySystem:
    """
    고급 트레이딩 전략 통합 시스템

    모든 모듈을 통합하여 매수/매도 시그널 생성 및 포지션 관리
    """

    def __init__(
        self,
        portfolio_value: float,
        risk_profile: str = 'aggressive',
        strategy_config: Optional[Dict] = None
    ):
        """
        Parameters:
        -----------
        portfolio_value : float
            포트폴리오 총 가치
        risk_profile : str
            리스크 프로필 ('conservative', 'moderate', 'aggressive')
        strategy_config : Optional[Dict]
            전략 설정 (커스터마이징 가능)
        """
        self.portfolio_value = portfolio_value
        self.risk_profile = risk_profile

        # 기본 설정
        self.config = strategy_config or {
            'min_factor_score': 70.0,
            'min_hybrid_score': 70.0,
            'max_positions': 10,
            'max_position_pct': 0.15,
            'max_daily_loss_pct': -0.08,
            'atr_stop_multiplier': 2.0,
            'trailing_stop_activation': 0.05,
            'max_holding_days': 10
        }

        # 모듈 초기화
        self.scorer = MultiFactorScoring()
        self.hybrid_strategy = HybridStrategy(
            momentum_weight=0.6,
            mean_reversion_weight=0.4,
            min_score=self.config['min_hybrid_score']
        )
        self.risk_manager = RiskManager(
            portfolio_value=portfolio_value,
            risk_profile=risk_profile,
            max_position_pct=self.config['max_position_pct'],
            max_daily_loss_pct=self.config['max_daily_loss_pct']
        )
        self.exit_strategy = ExitStrategy(
            atr_stop_multiplier=self.config['atr_stop_multiplier'],
            trailing_stop_activation=self.config['trailing_stop_activation'],
            max_holding_days=self.config['max_holding_days']
        )
        self.analytics = PerformanceAnalytics()


    def generate_buy_signals(
        self,
        stock_codes: Optional[List[str]] = None,
        current_positions: Optional[List[Dict]] = None,
        today_pnl: float = 0.0,
        db_name: str = 'daily_buy_list',
        top_n: int = 20
    ) -> pd.DataFrame:
        """
        매수 시그널 생성

        Parameters:
        -----------
        stock_codes : Optional[List[str]]
            스캔할 종목 코드 (없으면 전체 스캔)
        current_positions : Optional[List[Dict]]
            현재 보유 포지션
        today_pnl : float
            오늘 손익
        db_name : str
            데이터베이스 이름
        top_n : int
            선정할 종목 수

        Returns:
        --------
        pd.DataFrame : 매수 추천 종목 리스트
        """
        current_positions = current_positions or []

        # 1. 포트폴리오 리스크 체크
        can_trade, message = self.risk_manager.check_portfolio_risk(
            current_positions,
            today_pnl
        )

        if not can_trade:
            print(f"⚠️  매수 불가: {message}")
            return pd.DataFrame()

        # 2. 종목 스캔
        if stock_codes is None:
            # 전체 스캔
            print("📊 전체 종목 스캔 중...")
            df_candidates = get_buy_candidates(
                db_name=db_name,
                min_score=self.config['min_hybrid_score'],
                top_n=top_n * 2  # 필터링 후 top_n 확보를 위해 2배
            )
        else:
            # 지정된 종목만 스캔
            df_candidates = self.hybrid_strategy.scan_stocks(
                stock_codes,
                db_name=db_name,
                top_n=top_n * 2
            )

        if df_candidates.empty:
            print("❌ 매수 조건을 만족하는 종목이 없습니다.")
            return pd.DataFrame()

        # 3. 리스크 관리 필터링
        buy_recommendations = []

        for _, row in df_candidates.iterrows():
            code = row['code']
            current_price = row['current_price']

            # ATR 계산
            atr = get_stock_atr(code, db_name)

            if atr == 0:
                continue

            # 포지션 사이즈 계산
            position_info = self.risk_manager.get_position_score(
                stock_data={
                    'code': code,
                    'price': current_price,
                    'atr': atr,
                    'sector': 'Unknown'  # TODO: 섹터 정보 추가
                },
                current_positions=current_positions
            )

            # 리스크 스코어 체크 (70점 이하만 허용)
            if position_info['risk_score'] > 70:
                continue

            # 상관관계 체크
            current_codes = [p.get('code') for p in current_positions]
            correlation_ok, max_corr = self.risk_manager.check_correlation_limit(
                code,
                current_codes,
                db_name
            )

            if not correlation_ok:
                print(f"⚠️  {code}: 상관관계 높음 (max: {max_corr:.2f})")
                continue

            # 매수 추천에 추가
            buy_recommendations.append({
                'code': code,
                'current_price': current_price,
                'composite_score': row['score'],
                'strategy_type': row['strategy_type'],
                'recommended_shares': position_info['recommended_shares'],
                'recommended_value': position_info['recommended_value'],
                'position_pct': position_info['position_pct'],
                'stop_loss': position_info['stop_loss'],
                'profit_target': position_info['profit_target'],
                'risk_reward_ratio': position_info['risk_reward_ratio'],
                'risk_score': position_info['risk_score'],
                'atr': atr,
                'momentum_score': row['momentum_score'],
                'mean_reversion_score': row['mean_reversion_score'],
                'rsi': row['rsi'],
                'volume_ratio': row['volume_ratio']
            })

        if not buy_recommendations:
            print("❌ 리스크 필터링 후 매수 가능한 종목이 없습니다.")
            return pd.DataFrame()

        # DataFrame 생성 및 정렬
        df_buy = pd.DataFrame(buy_recommendations)
        df_buy = df_buy.sort_values('composite_score', ascending=False).head(top_n)

        return df_buy


    def generate_sell_signals(
        self,
        positions: List[Dict],
        db_name: str = 'daily_buy_list'
    ) -> List[Dict]:
        """
        매도 시그널 생성

        Parameters:
        -----------
        positions : List[Dict]
            현재 보유 포지션 [{
                'code': str,
                'entry_price': float,
                'entry_date': datetime,
                'shares': int,
                'highest_price': float
            }]
        db_name : str
            데이터베이스 이름

        Returns:
        --------
        List[Dict] : 매도 시그널 리스트
        """
        if not positions:
            return []

        sell_signals = get_exit_signals(positions, db_name)

        # 추가 정보 보강
        for signal in sell_signals:
            # 팩터 스코어 재계산
            try:
                current_score_data = get_stock_score(signal['code'], db_name)
                signal['current_factor_score'] = current_score_data.get('composite_score', 0)
            except:
                signal['current_factor_score'] = 0

        return sell_signals


    def update_position_tracking(
        self,
        positions: List[Dict],
        db_name: str = 'daily_buy_list'
    ) -> List[Dict]:
        """
        포지션 트래킹 업데이트 (최고가, 트레일링 스톱 등)

        Parameters:
        -----------
        positions : List[Dict]
            현재 포지션
        db_name : str
            데이터베이스 이름

        Returns:
        --------
        List[Dict] : 업데이트된 포지션
        """
        updated_positions = []

        for position in positions:
            try:
                code = position['code']

                # 현재 가격 가져오기
                con = pymysql.connect(
                    user=db_id,
                    passwd=db_passwd,
                    host=db_ip,
                    db=db_name,
                    charset='utf8',
                    port=int(db_port)
                )

                query = f"""
                SELECT close
                FROM `{code}`
                ORDER BY ref_date DESC
                LIMIT 1
                """

                df = pd.read_sql(query, con)
                con.close()

                if not df.empty:
                    current_price = df['close'].iloc[0]

                    # 트레일링 스톱 업데이트
                    updated_position = self.exit_strategy.update_trailing_stop(
                        position,
                        current_price
                    )

                    updated_positions.append(updated_position)
                else:
                    updated_positions.append(position)

            except Exception as e:
                print(f"포지션 업데이트 오류 ({position.get('code', 'Unknown')}): {e}")
                updated_positions.append(position)

        return updated_positions


    def backtest_strategy(
        self,
        start_date: str,
        end_date: str,
        initial_capital: float,
        db_name: str = 'daily_buy_list'
    ) -> Dict:
        """
        전략 백테스팅

        Parameters:
        -----------
        start_date : str
            시작일 (YYYYMMDD)
        end_date : str
            종료일 (YYYYMMDD)
        initial_capital : float
            초기 자본금
        db_name : str
            데이터베이스 이름

        Returns:
        --------
        Dict : 백테스트 결과 및 성과 분석
        """
        # TODO: 전체 백테스팅 로직 구현
        # 현재는 기본 틀만 제공

        print(f"🔄 백테스트 시작: {start_date} ~ {end_date}")
        print(f"💰 초기 자본: {initial_capital:,}원")

        # 여기에 백테스팅 루프 구현
        # 1. 날짜별 반복
        # 2. 매일 매도 시그널 체크
        # 3. 매도 시그널 체크
        # 4. 포지션 업데이트
        # 5. 자산 곡선 기록

        result = {
            'equity_curve': [],
            'trades': [],
            'daily_positions': [],
            'performance': {}
        }

        return result


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
        total_position_value = sum(
            p.get('shares', 0) * p.get('current_price', 0)
            for p in positions
        )

        total_asset = cash + total_position_value

        return {
            'total_asset': total_asset,
            'cash': cash,
            'position_value': total_position_value,
            'cash_pct': (cash / total_asset * 100) if total_asset > 0 else 0,
            'position_pct': (total_position_value / total_asset * 100) if total_asset > 0 else 0,
            'num_positions': len(positions)
        }


def create_optimized_buy_list(
    db_name: str = 'daily_buy_list',
    portfolio_value: float = 10000000,
    risk_profile: str = 'aggressive',
    top_n: int = 20
) -> pd.DataFrame:
    """
    최적화된 매수 리스트 생성 (간편 함수)

    Parameters:
    -----------
    db_name : str
        데이터베이스 이름
    portfolio_value : float
        포트폴리오 가치
    risk_profile : str
        리스크 프로필
    top_n : int
        선정 종목 수

    Returns:
    --------
    pd.DataFrame : 매수 추천 리스트
    """
    system = AdvancedStrategySystem(
        portfolio_value=portfolio_value,
        risk_profile=risk_profile
    )

    buy_list = system.generate_buy_signals(
        db_name=db_name,
        top_n=top_n
    )

    return buy_list


def create_optimized_sell_list(
    positions: List[Dict],
    db_name: str = 'daily_buy_list'
) -> List[Dict]:
    """
    최적화된 매도 리스트 생성 (간편 함수)

    Parameters:
    -----------
    positions : List[Dict]
        현재 포지션
    db_name : str
        데이터베이스 이름

    Returns:
    --------
    List[Dict] : 매도 시그널 리스트
    """
    system = AdvancedStrategySystem(portfolio_value=10000000)

    sell_list = system.generate_sell_signals(positions, db_name)

    return sell_list


if __name__ == "__main__":
    # 테스트 코드
    print("=" * 70)
    print("🚀 ADVANCED TRADING STRATEGY SYSTEM")
    print("=" * 70)

    # 시스템 초기화
    portfolio_value = 10000000  # 1000만원
    system = AdvancedStrategySystem(
        portfolio_value=portfolio_value,
        risk_profile='aggressive'
    )

    print(f"\n💼 포트폴리오 설정:")
    print(f"  총 자산: {portfolio_value:,}원")
    print(f"  리스크 프로필: {system.risk_profile}")
    print(f"  최대 포지션 수: {system.config['max_positions']}개")
    print(f"  단일 포지션 최대: {system.config['max_position_pct']*100:.0f}%")
    print(f"  일일 최대 손실: {system.config['max_daily_loss_pct']*100:.0f}%")

    print(f"\n📊 전략 설정:")
    print(f"  모멘텀 가중치: {system.hybrid_strategy.momentum_weight*100:.0f}%")
    print(f"  평균회귀 가중치: {system.hybrid_strategy.mean_reversion_weight*100:.0f}%")
    print(f"  최소 진입 스코어: {system.config['min_hybrid_score']:.0f}점")

    print(f"\n🛡️  리스크 관리:")
    print(f"  ATR 손절 배수: {system.config['atr_stop_multiplier']}x")
    print(f"  트레일링 스톱 활성화: {system.config['trailing_stop_activation']*100:.0f}%")
    print(f"  최대 보유 기간: {system.config['max_holding_days']}일")

    # 샘플 포지션
    sample_positions = []

    # 포트폴리오 현황
    status = system.get_portfolio_status(sample_positions, portfolio_value)

    print(f"\n💰 현재 포트폴리오:")
    print(f"  총 자산: {status['total_asset']:,}원")
    print(f"  현금: {status['cash']:,}원 ({status['cash_pct']:.1f}%)")
    print(f"  포지션: {status['position_value']:,}원 ({status['position_pct']:.1f}%)")
    print(f"  보유 종목 수: {status['num_positions']}개")

    print("\n" + "=" * 70)
    print("✅ Advanced Strategy System 준비 완료!")
    print("=" * 70)
