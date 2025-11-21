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
        query_positions = """
        SELECT
            code,
            first_buy_date,
            purchase_price,
            holding_amount,
            present_price,
            valuation_profit,
            rate
        FROM possessed_item
        WHERE holding_amount > 0
        ORDER BY first_buy_date DESC
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
                print(f"  매수일:     {row['first_buy_date']}")
                print(f"  매수가:     {row['purchase_price']:>10,}원")
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
            buy_date,
            buy_price,
            'BUY' as type
        FROM all_item_db
        WHERE buy_date = %s

        UNION ALL

        SELECT
            code,
            sell_date as buy_date,
            sell_price as buy_price,
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
                print(f"[{idx+1}] {action} - {row['code']} @ {row['buy_price']:,}원")

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
        # tasklist로 Python 프로세스 확인
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq python.exe', '/FO', 'CSV'],
            capture_output=True,
            text=True
        )

        if 'python.exe' in result.stdout:
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
        query = f"""
        SELECT
            sell_date,
            COUNT(*) as trades,
            SUM(sell_percent) as total_return,
            AVG(sell_percent) as avg_return,
            SUM(CASE WHEN sell_percent > 0 THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN sell_percent < 0 THEN 1 ELSE 0 END) as losses
        FROM all_item_db
        WHERE sell_date IS NOT NULL
          AND sell_date != ''
          AND sell_date >= DATE_SUB(CURDATE(), INTERVAL {days} DAY)
        GROUP BY sell_date
        ORDER BY sell_date DESC
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
