"""
실시간 포트폴리오 모니터링 스크립트

현재 상태:
- 보유 종목 및 손익
- 포트폴리오 현황
- 오늘 매매 이력

사용법:
    python monitor.py
    python monitor.py --db JackBot1_imi1
"""

import pymysql
import pandas as pd
from datetime import datetime
import argparse
from library.cf import *


def get_portfolio_status(db_name: str):
    """
    포트폴리오 현황 조회
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

        print("\n" + "="*100)
        print(f"📊 포트폴리오 현황 ({db_name})")
        print("="*100)

        # 1. 보유 종목 조회
        # 주의: puchase_price는 철자 오류지만 실제 DB 컬럼명
        query_positions = """
        SELECT
            code,
            date,
            puchase_price,
            holding_amount,
            present_price,
            valuation_profit,
            rate
        FROM possessed_item
        WHERE holding_amount > 0
        ORDER BY date DESC
        """

        df_positions = pd.read_sql(query_positions, con)

        if not df_positions.empty:
            print(f"\n📈 보유 종목 ({len(df_positions)}개)")
            print("-"*100)

            total_value = 0
            total_profit = 0

            for idx, row in df_positions.iterrows():
                value = row['present_price'] * row['holding_amount']
                total_value += value
                total_profit += row['valuation_profit']

                print(f"\n[{idx+1}] {row['code']}")
                print(f"  매수일:     {row['date']}")
                print(f"  매수가:     {row['puchase_price']:>10,}원")
                print(f"  현재가:     {row['present_price']:>10,}원")
                print(f"  수량:       {row['holding_amount']:>10}주")
                print(f"  평가금액:   {value:>10,}원")
                print(f"  수익률:     {row['rate']:>10.2f}%")
                print(f"  평가손익:   {row['valuation_profit']:>10,}원")

            print("\n" + "-"*100)
            print(f"총 평가금액:  {total_value:>15,}원")
            print(f"총 평가손익:  {total_profit:>15,}원")
            print(f"총 수익률:    {(total_profit/total_value*100) if total_value > 0 else 0:>15.2f}%")

        else:
            print("\n✅ 보유 종목이 없습니다.")

        # 2. 오늘 매매 이력
        today = datetime.today().strftime("%Y%m%d")

        query_today_trades = """
        SELECT
            code,
            code_name,
            buy_date,
            purchase_price,
            'BUY' as type
        FROM all_item_db
        WHERE buy_date = %s

        UNION ALL

        SELECT
            code,
            code_name,
            sell_date as buy_date,
            sell_price as purchase_price,
            'SELL' as type
        FROM all_item_db
        WHERE sell_date = %s

        ORDER BY buy_date DESC
        """

        df_today = pd.read_sql(query_today_trades, con, params=(today, today))

        if not df_today.empty:
            print(f"\n📝 오늘 매매 이력 ({len(df_today)}건)")
            print("-"*100)

            for idx, row in df_today.iterrows():
                action = "매수" if row['type'] == 'BUY' else "매도"
                print(f"[{idx+1}] {action} - {row['code']} ({row['code_name']}) @ {row['purchase_price']:,}원")

        # 3. 설정 정보
        query_settings = """
        SELECT invest_unit, set_invest_unit
        FROM setting_data
        LIMIT 1
        """

        df_settings = pd.read_sql(query_settings, con)

        if not df_settings.empty:
            print(f"\n⚙️  설정 정보")
            print("-"*100)
            print(f"  투자 단위:   {df_settings['invest_unit'].iloc[0]:>10,}원")
            print(f"  설정 날짜:   {df_settings['set_invest_unit'].iloc[0]}")

        # 4. 매수 후보 (realtime_daily_buy_list)
        try:
            # 먼저 모든 컬럼을 가져와서 어떤 컬럼이 있는지 확인
            query_buy_candidates = """
            SELECT *
            FROM realtime_daily_buy_list
            LIMIT 20
            """
            df_candidates = pd.read_sql(query_buy_candidates, con)

            print(f"\n🎯 매수 후보 ({len(df_candidates)}개)")
            print("-"*100)

            if not df_candidates.empty:
                # 사용 가능한 컬럼 확인
                cols = df_candidates.columns.tolist()

                # D1 기준 정렬 (있는 경우)
                if 'd1' in cols:
                    df_candidates = df_candidates.sort_values('d1', ascending=False)

                for idx, row in df_candidates.iterrows():
                    code = row.get('code', 'N/A')
                    code_name = row.get('code_name', 'N/A')
                    print(f"\n[{idx+1}] {code} - {code_name}")

                    # 있는 컬럼만 표시
                    if 'close' in cols and pd.notna(row.get('close')):
                        print(f"  현재가:       {int(row['close']):>12,}원")

                    # 고급 전략 정보 표시
                    if 'strategy_type' in cols and pd.notna(row.get('strategy_type')):
                        strategy_names = {
                            'momentum_breakout': '모멘텀 돌파',
                            'mean_reversion': '평균회귀',
                            'strong_uptrend': '강한 상승',
                            'neutral': '중립',
                            'basic': '기본전략'
                        }
                        strategy = row['strategy_type']
                        strategy_kr = strategy_names.get(strategy, strategy)
                        print(f"  전략:         {strategy_kr}")

                    if 'composite_score' in cols and pd.notna(row.get('composite_score')):
                        score = row['composite_score']
                        print(f"  종합 스코어:  {score:>12.1f}/100")

                    if 'volume_ratio' in cols and pd.notna(row.get('volume_ratio')):
                        vol_ratio = row['volume_ratio']
                        print(f"  거래량 비율:  {vol_ratio:>12.2f}x")

                    # 기존 지표들
                    if 'd1' in cols and pd.notna(row.get('d1')):
                        print(f"  D1:           {row['d1']:>12.2f}")
                    if 'd2' in cols and pd.notna(row.get('d2')):
                        print(f"  D2:           {row['d2']:>12.2f}")
                    if 'check_item' in cols and pd.notna(row.get('check_item')) and 'strategy_type' not in cols:
                        print(f"  전략 ID:      {row['check_item']}")
            else:
                print("  매수 후보가 없습니다.")
                print("\n  💡 collector_v3.py를 실행하여 매수 후보를 생성하세요.")
        except Exception as e:
            print(f"\n🎯 매수 후보")
            print("-"*100)
            print(f"  매수 후보 조회 실패: {e}")

        con.close()

        print("\n" + "="*100)

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


def check_trader_running():
    """
    트레이더 실행 상태 확인 (Windows 전용)
    """
    import subprocess
    import sys

    if sys.platform != 'win32':
        print("⚠️  트레이더 상태 확인은 Windows에서만 지원됩니다.")
        return

    try:
        # wmic로 커맨드라인을 포함한 프로세스 정보 확인
        result = subprocess.run(
            ['wmic', 'process', 'where', 'name="python.exe"', 'get', 'commandline'],
            capture_output=True,
            text=True,
            encoding='cp949',
            errors='ignore'
        )

        # trader_advanced.py가 커맨드라인에 있는지 확인
        if 'trader_advanced.py' in result.stdout:
            print("\n✅ 트레이더가 실행 중입니다.")
        else:
            print("\n⚠️  트레이더가 실행되지 않았습니다.")

    except Exception as e:
        print(f"⚠️  트레이더 상태 확인 실패: {e}")


def get_daily_performance(db_name: str, days: int = 7):
    """
    최근 N일 간의 수익률 조회
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

        print(f"\n📈 최근 {days}일 성과")
        print("-"*100)

        # 매도된 종목 기준 수익률
        # sell_date는 YYYYMMDDHHMM 형식이므로 앞 8자리만 추출해서 비교
        query = f"""
        SELECT
            LEFT(sell_date, 8) as sell_date,
            COUNT(*) as trades,
            SUM(sell_rate) as total_return,
            AVG(sell_rate) as avg_return,
            SUM(CASE WHEN sell_rate > 0 THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN sell_rate < 0 THEN 1 ELSE 0 END) as losses
        FROM all_item_db
        WHERE sell_date IS NOT NULL
          AND sell_date != ''
          AND LEFT(sell_date, 8) >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL {days} DAY), '%Y%m%d')
        GROUP BY LEFT(sell_date, 8)
        ORDER BY LEFT(sell_date, 8) DESC
        """

        df = pd.read_sql(query, con)
        con.close()

        if not df.empty:
            for idx, row in df.iterrows():
                win_rate = (row['wins'] / row['trades'] * 100) if row['trades'] > 0 else 0
                print(f"{row['sell_date']}: {row['trades']:>2}건 | "
                      f"평균 {row['avg_return']:>6.2f}% | "
                      f"승률 {win_rate:>5.1f}% ({row['wins']}승 {row['losses']}패)")

            # 전체 통계
            total_trades = df['trades'].sum()
            total_wins = df['wins'].sum()
            total_losses = df['losses'].sum()
            overall_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0

            print("-"*100)
            print(f"전체: {total_trades}건 | 승률 {overall_win_rate:.1f}% ({total_wins}승 {total_losses}패)")
        else:
            print("최근 매매 이력이 없습니다.")

    except Exception as e:
        print(f"❌ 성과 조회 오류: {e}")
        import traceback
        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(description='포트폴리오 모니터링')
    parser.add_argument('--db', type=str, default='JackBot1_imi1',
                        help='데이터베이스 이름 (기본: JackBot1_imi1)')
    parser.add_argument('--days', type=int, default=7,
                        help='성과 조회 기간 (기본: 7일)')
    parser.add_argument('--no-trader-check', action='store_true',
                        help='트레이더 실행 상태 체크 건너뛰기')

    args = parser.parse_args()

    print("="*100)
    print("🤖 트레이딩 봇 모니터링")
    print(f"시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*100)

    # 트레이더 실행 상태 확인
    if not args.no_trader_check:
        check_trader_running()

    # 포트폴리오 현황
    get_portfolio_status(args.db)

    # 최근 성과
    get_daily_performance(args.db, args.days)

    print("\n✅ 모니터링 완료\n")


if __name__ == "__main__":
    main()
