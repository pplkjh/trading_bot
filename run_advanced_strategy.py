"""
고급 매매 전략 실행 스크립트

Usage:
    python run_advanced_strategy.py --mode scan          # 매수 종목 스캔
    python run_advanced_strategy.py --mode backtest      # 백테스트 실행
    python run_advanced_strategy.py --mode analyze       # 성과 분석
"""

import argparse
import sys
from datetime import datetime
import pandas as pd
import pymysql

from library.cf import *
from library.advanced_strategy_system import AdvancedStrategySystem, create_optimized_buy_list
from library.performance_analytics import analyze_backtest_from_db
from library.date_based_strategy import generate_buy_signals as generate_buy_signals_date_based


def scan_buy_candidates(portfolio_value: float = 10000000, top_n: int = 20):
    """
    매수 후보 종목 스캔 (날짜별 테이블 기반)

    Parameters:
    -----------
    portfolio_value : float
        포트폴리오 가치
    top_n : int
        선정 종목 수
    """
    print("=" * 80)
    print("🔍 매수 후보 종목 스캔 시작")
    print("=" * 80)

    print(f"\n💼 포트폴리오 설정:")
    print(f"  총 자산: {portfolio_value:,}원")
    print(f"  리스크 프로필: AGGRESSIVE")
    print(f"  최대 포지션 수: {top_n}개")
    print(f"  일일 최대 손실: -8%")

    # 매수 시그널 생성
    print(f"\n📊 전체 종목 스캔 중... (Top {top_n})")
    print("-" * 80)

    try:
        # 날짜별 테이블 기반 스캔 사용
        buy_list = generate_buy_signals_date_based(
            portfolio_value=portfolio_value,
            top_n=top_n,
            min_score=70.0,
            risk_per_position=0.15
        )

        if buy_list.empty:
            print("\n❌ 매수 조건을 만족하는 종목이 없습니다.")
            return

        print(f"\n✅ 매수 추천 종목: {len(buy_list)}개")
        print("=" * 80)

        # 결과 출력
        for idx, row in buy_list.iterrows():
            print(f"\n[{idx+1}] {row['code']} - {row['code_name']}")
            print(f"  현재가:         {row['current_price']:>10,.0f}원")
            print(f"  종합 스코어:    {row['composite_score']:>10.1f}/100")
            print(f"  전략 타입:      {row['strategy_type']}")
            print(f"  추천 수량:      {row['recommended_shares']:>10,}주")
            print(f"  투자 금액:      {row['recommended_value']:>10,.0f}원 ({row['position_pct']*100:.1f}%)")
            print(f"  손절가:         {row['stop_loss']:>10,.0f}원 ({(row['stop_loss']/row['current_price']-1)*100:.1f}%)")
            print(f"  목표가:         {row['profit_target']:>10,.0f}원 ({(row['profit_target']/row['current_price']-1)*100:.1f}%)")
            print(f"  손익비:         {row['risk_reward_ratio']:>10.2f}:1")
            print(f"  리스크 스코어:  {row['risk_score']:>10.1f}/100")
            print(f"  ATR:            {row['atr']:>10,.0f}원")
            print(f"  모멘텀:         {row['momentum_score']:>10.1f}%")
            print(f"  평균회귀:       {row['mean_reversion_score']:>10.1f}%")
            print(f"  전일 대비:      {row['d1_diff_rate']:>10.2f}%")
            print(f"  거래량 비율:    {row['volume_ratio']:>10.2f}x")

        print("\n" + "=" * 80)

        # CSV 저장
        output_file = f"buy_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        buy_list.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"✅ 결과 저장: {output_file}")

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


def run_backtest(
    start_date: str = "20230101",
    end_date: str = "20241231",
    initial_capital: float = 10000000
):
    """
    백테스트 실행

    Parameters:
    -----------
    start_date : str
        시작일 (YYYYMMDD)
    end_date : str
        종료일 (YYYYMMDD)
    initial_capital : float
        초기 자본금
    """
    print("=" * 80)
    print("🔄 백테스트 실행")
    print("=" * 80)

    print(f"\n📅 기간: {start_date} ~ {end_date}")
    print(f"💰 초기 자본: {initial_capital:,}원")

    # TODO: 전체 백테스팅 로직 구현
    print("\n⚠️  백테스트 기능은 추후 구현 예정입니다.")
    print("   현재는 기존 simulator.py를 사용하거나 아래 함수를 참고하세요:")
    print("   - library/advanced_strategy_system.py의 backtest_strategy()")


def analyze_performance(db_name: str = "JackBot1_imi1"):
    """
    성과 분석

    Parameters:
    -----------
    db_name : str
        분석할 데이터베이스 이름
    """
    print("=" * 80)
    print("📊 성과 분석")
    print("=" * 80)

    print(f"\n데이터베이스: {db_name}")
    print("-" * 80)

    try:
        report = analyze_backtest_from_db(db_name)

        if not report:
            print("\n❌ 분석할 데이터가 없습니다.")
            return

        # 리포트 출력
        from library.performance_analytics import PerformanceAnalytics
        analytics = PerformanceAnalytics()
        analytics.print_report(report)

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


def get_stock_list():
    """데이터베이스에서 활성 종목 리스트 가져오기"""
    try:
        con = pymysql.connect(
            user=db_id,
            passwd=db_passwd,
            host=db_ip,
            db='daily_buy_list',
            charset='utf8',
            port=int(db_port)
        )

        query = """
        SELECT code, code_name
        FROM stock_item_all
        WHERE check_item = 1
        LIMIT 10
        """

        df = pd.read_sql(query, con)
        con.close()

        return df

    except Exception as e:
        print(f"종목 리스트 조회 오류: {e}")
        return pd.DataFrame()


def main():
    parser = argparse.ArgumentParser(description='고급 매매 전략 실행')

    parser.add_argument(
        '--mode',
        type=str,
        choices=['scan', 'backtest', 'analyze', 'info'],
        default='info',
        help='실행 모드'
    )

    parser.add_argument(
        '--portfolio',
        type=float,
        default=10000000,
        help='포트폴리오 가치 (원)'
    )

    parser.add_argument(
        '--top',
        type=int,
        default=20,
        help='매수 후보 선정 개수'
    )

    parser.add_argument(
        '--start-date',
        type=str,
        default='20230101',
        help='백테스트 시작일 (YYYYMMDD)'
    )

    parser.add_argument(
        '--end-date',
        type=str,
        default='20241231',
        help='백테스트 종료일 (YYYYMMDD)'
    )

    parser.add_argument(
        '--db',
        type=str,
        default='JackBot1_imi1',
        help='분석할 데이터베이스 이름'
    )

    args = parser.parse_args()

    if args.mode == 'scan':
        scan_buy_candidates(args.portfolio, args.top)

    elif args.mode == 'backtest':
        run_backtest(args.start_date, args.end_date, args.portfolio)

    elif args.mode == 'analyze':
        analyze_performance(args.db)

    elif args.mode == 'info':
        print("=" * 80)
        print("🚀 고급 매매 전략 시스템")
        print("=" * 80)

        print("\n📚 사용 가능한 모드:")
        print("  1. scan      - 매수 후보 종목 스캔")
        print("  2. backtest  - 백테스트 실행")
        print("  3. analyze   - 성과 분석")
        print("  4. info      - 이 정보 표시")

        print("\n💡 사용 예시:")
        print("  # 매수 종목 스캔 (1000만원 포트폴리오, Top 20)")
        print("  python run_advanced_strategy.py --mode scan --portfolio 10000000 --top 20")
        print()
        print("  # 백테스트 실행")
        print("  python run_advanced_strategy.py --mode backtest --start-date 20230101 --end-date 20241231")
        print()
        print("  # 성과 분석")
        print("  python run_advanced_strategy.py --mode analyze --db JackBot1_imi1")

        print("\n📦 새로 추가된 모듈:")
        print("  ✅ library/risk_manager.py             - ATR 기반 리스크 관리")
        print("  ✅ library/multi_factor_scoring.py     - 멀티팩터 스코어링")
        print("  ✅ library/hybrid_strategy.py          - 하이브리드 전략 (모멘텀 + 평균회귀)")
        print("  ✅ library/exit_strategy.py            - 고급 청산 전략")
        print("  ✅ library/performance_analytics.py    - 성과 분석")
        print("  ✅ library/advanced_strategy_system.py - 통합 전략 시스템")

        print("\n🎯 전략 특징:")
        print("  • 공격적 스윙 트레이딩 (3-10일 보유)")
        print("  • 모멘텀 돌파 60% + 평균회귀 40% 하이브리드")
        print("  • ATR 기반 동적 포지션 사이징")
        print("  • 트레일링 스톱으로 수익 보호")
        print("  • 멀티팩터 스코어링 (기술적/모멘텀/거래량/변동성/추세)")
        print("  • 일일 최대 손실 -8% 제한")

        print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
