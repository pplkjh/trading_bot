"""
전체 운용 성과 평가 보고서 생성

종합적인 트레이딩 성과를 분석하여 상세 보고서 생성:
- 전체 거래 통계 및 승률
- 기간별 성과 (일별/주별/월별)
- 전략별 성과 분석
- 종목별 성과 분석
- 리스크 지표 (MDD, 손익비 등)
- 현재 포트폴리오 상태

사용법:
    python performance_report.py
    python performance_report.py --db JackBot1_imi1
    python performance_report.py --period 30  # 최근 30일
    python performance_report.py --output reports/performance.txt
"""

import pymysql
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import argparse
from library.cf import *


def generate_performance_report(db_name: str, period_days: int = None, output_path: str = None):
    """
    종합 성과 평가 보고서 생성

    Args:
        db_name: 데이터베이스 이름
        period_days: 분석 기간 (일). None이면 전체 기간
        output_path: 출력 파일 경로. None이면 자동 생성
    """
    try:
        # 데이터베이스 연결
        con = pymysql.connect(
            user=db_id,
            passwd=db_passwd,
            host=db_ip,
            db=db_name,
            charset='utf8',
            port=int(db_port)
        )

        # 출력 파일 경로 설정
        if output_path is None:
            report_dir = Path("reports")
            report_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = report_dir / f"performance_report_{timestamp}.txt"
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            # ========== 헤더 ==========
            f.write("=" * 100 + "\n")
            f.write("📊 운용 성과 평가 보고서\n")
            f.write("=" * 100 + "\n")
            f.write(f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"데이터베이스: {db_name}\n")
            if period_days:
                f.write(f"분석 기간: 최근 {period_days}일\n")
            else:
                f.write(f"분석 기간: 전체\n")
            f.write("=" * 100 + "\n\n")

            # 기간 조건 설정
            period_condition = ""
            if period_days:
                period_condition = f"AND sell_date >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL {period_days} DAY), '%Y%m%d')"

            # ========== 1. 전체 거래 통계 ==========
            f.write("📈 전체 거래 통계\n")
            f.write("-" * 100 + "\n")

            # 총 거래 수
            query_total = f"""
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN sell_date IS NOT NULL AND sell_date != '' THEN 1 ELSE 0 END) as completed_trades,
                SUM(CASE WHEN sell_date IS NULL OR sell_date = '' THEN 1 ELSE 0 END) as pending_trades
            FROM all_item_db
            """
            df_total = pd.read_sql(query_total, con)

            total_trades = df_total.iloc[0]['total_trades']
            completed_trades = df_total.iloc[0]['completed_trades']
            pending_trades = df_total.iloc[0]['pending_trades']

            f.write(f"  총 거래 수:        {total_trades:>10}건\n")
            f.write(f"  완료된 거래:       {completed_trades:>10}건\n")
            f.write(f"  진행 중인 거래:    {pending_trades:>10}건\n\n")

            # 매도 완료된 거래 분석
            query_stats = f"""
            SELECT
                COUNT(*) as trades,
                SUM(CASE WHEN sell_rate > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN sell_rate < 0 THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN sell_rate = 0 THEN 1 ELSE 0 END) as breakeven,
                AVG(sell_rate) as avg_return,
                MAX(sell_rate) as max_return,
                MIN(sell_rate) as min_return,
                SUM(sell_rate) as total_return
            FROM all_item_db
            WHERE sell_date IS NOT NULL
              AND sell_date != ''
              {period_condition}
            """
            df_stats = pd.read_sql(query_stats, con)

            if not df_stats.empty and df_stats.iloc[0]['trades'] > 0:
                stats = df_stats.iloc[0]
                win_rate = (stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0

                f.write(f"  승리:              {int(stats['wins']):>10}건 ({win_rate:.2f}%)\n")
                f.write(f"  패배:              {int(stats['losses']):>10}건\n")
                f.write(f"  무승부:            {int(stats['breakeven']):>10}건\n\n")

                f.write(f"  평균 수익률:       {stats['avg_return']:>10.2f}%\n")
                f.write(f"  최대 수익률:       {stats['max_return']:>10.2f}%\n")
                f.write(f"  최대 손실률:       {stats['min_return']:>10.2f}%\n")
                f.write(f"  누적 수익률:       {stats['total_return']:>10.2f}%\n\n")

                # 손익비 계산
                query_profit_ratio = f"""
                SELECT
                    AVG(CASE WHEN sell_rate > 0 THEN sell_rate END) as avg_win,
                    AVG(CASE WHEN sell_rate < 0 THEN ABS(sell_rate) END) as avg_loss
                FROM all_item_db
                WHERE sell_date IS NOT NULL
                  AND sell_date != ''
                  {period_condition}
                """
                df_profit_ratio = pd.read_sql(query_profit_ratio, con)

                if not df_profit_ratio.empty:
                    avg_win = df_profit_ratio.iloc[0]['avg_win']
                    avg_loss = df_profit_ratio.iloc[0]['avg_loss']

                    if avg_win and avg_loss and avg_loss > 0:
                        profit_ratio = avg_win / avg_loss
                        f.write(f"  평균 승리 수익률:  {avg_win:>10.2f}%\n")
                        f.write(f"  평균 손실 수익률:  {avg_loss:>10.2f}%\n")
                        f.write(f"  손익비:            {profit_ratio:>10.2f}:1\n\n")

            # ========== 2. 기간별 성과 ==========
            f.write("📅 기간별 성과 분석\n")
            f.write("-" * 100 + "\n")

            # 일별 성과
            query_daily = f"""
            SELECT
                LEFT(sell_date, 8) as date,
                COUNT(*) as trades,
                SUM(CASE WHEN sell_rate > 0 THEN 1 ELSE 0 END) as wins,
                AVG(sell_rate) as avg_return,
                SUM(sell_rate) as daily_return
            FROM all_item_db
            WHERE sell_date IS NOT NULL
              AND sell_date != ''
              {period_condition}
            GROUP BY LEFT(sell_date, 8)
            ORDER BY LEFT(sell_date, 8) DESC
            LIMIT 10
            """
            df_daily = pd.read_sql(query_daily, con)

            if not df_daily.empty:
                f.write(f"\n  최근 일별 성과 (최근 10일)\n")
                f.write("  " + "-" * 95 + "\n")
                f.write(f"  {'날짜':<12} {'거래':<8} {'승률':<10} {'평균수익률':<15} {'일일수익률':<15}\n")
                f.write("  " + "-" * 95 + "\n")

                for _, row in df_daily.iterrows():
                    win_rate = (row['wins'] / row['trades'] * 100) if row['trades'] > 0 else 0
                    date_str = f"{row['date'][:4]}-{row['date'][4:6]}-{row['date'][6:8]}"
                    f.write(f"  {date_str:<12} {int(row['trades']):<8} {win_rate:<10.1f}% "
                           f"{row['avg_return']:<15.2f}% {row['daily_return']:<15.2f}%\n")
                f.write("\n")

            # 주별 성과
            query_weekly = f"""
            SELECT
                DATE_FORMAT(STR_TO_DATE(LEFT(sell_date, 8), '%Y%m%d'), '%Y-W%u') as week,
                COUNT(*) as trades,
                SUM(CASE WHEN sell_rate > 0 THEN 1 ELSE 0 END) as wins,
                AVG(sell_rate) as avg_return,
                SUM(sell_rate) as weekly_return
            FROM all_item_db
            WHERE sell_date IS NOT NULL
              AND sell_date != ''
              {period_condition}
            GROUP BY DATE_FORMAT(STR_TO_DATE(LEFT(sell_date, 8), '%Y%m%d'), '%Y-W%u')
            ORDER BY week DESC
            LIMIT 5
            """
            df_weekly = pd.read_sql(query_weekly, con)

            if not df_weekly.empty:
                f.write(f"  주별 성과 (최근 5주)\n")
                f.write("  " + "-" * 95 + "\n")
                f.write(f"  {'주':<12} {'거래':<8} {'승률':<10} {'평균수익률':<15} {'주간수익률':<15}\n")
                f.write("  " + "-" * 95 + "\n")

                for _, row in df_weekly.iterrows():
                    win_rate = (row['wins'] / row['trades'] * 100) if row['trades'] > 0 else 0
                    f.write(f"  {row['week']:<12} {int(row['trades']):<8} {win_rate:<10.1f}% "
                           f"{row['avg_return']:<15.2f}% {row['weekly_return']:<15.2f}%\n")
                f.write("\n")

            # 월별 성과
            query_monthly = f"""
            SELECT
                LEFT(sell_date, 6) as month,
                COUNT(*) as trades,
                SUM(CASE WHEN sell_rate > 0 THEN 1 ELSE 0 END) as wins,
                AVG(sell_rate) as avg_return,
                SUM(sell_rate) as monthly_return
            FROM all_item_db
            WHERE sell_date IS NOT NULL
              AND sell_date != ''
              {period_condition}
            GROUP BY LEFT(sell_date, 6)
            ORDER BY LEFT(sell_date, 6) DESC
            LIMIT 12
            """
            df_monthly = pd.read_sql(query_monthly, con)

            if not df_monthly.empty:
                f.write(f"  월별 성과 (최근 12개월)\n")
                f.write("  " + "-" * 95 + "\n")
                f.write(f"  {'월':<12} {'거래':<8} {'승률':<10} {'평균수익률':<15} {'월간수익률':<15}\n")
                f.write("  " + "-" * 95 + "\n")

                for _, row in df_monthly.iterrows():
                    win_rate = (row['wins'] / row['trades'] * 100) if row['trades'] > 0 else 0
                    month_str = f"{row['month'][:4]}-{row['month'][4:6]}"
                    f.write(f"  {month_str:<12} {int(row['trades']):<8} {win_rate:<10.1f}% "
                           f"{row['avg_return']:<15.2f}% {row['monthly_return']:<15.2f}%\n")
                f.write("\n")

            # ========== 3. 종목별 성과 ==========
            f.write("📊 종목별 성과 분석\n")
            f.write("-" * 100 + "\n")

            # 가장 많이 거래한 종목
            query_top_traded = f"""
            SELECT
                code,
                code_name,
                COUNT(*) as trades,
                SUM(CASE WHEN sell_rate > 0 THEN 1 ELSE 0 END) as wins,
                AVG(sell_rate) as avg_return,
                SUM(sell_rate) as total_return
            FROM all_item_db
            WHERE sell_date IS NOT NULL
              AND sell_date != ''
              {period_condition}
            GROUP BY code, code_name
            ORDER BY COUNT(*) DESC
            LIMIT 10
            """
            df_top_traded = pd.read_sql(query_top_traded, con)

            if not df_top_traded.empty:
                f.write(f"\n  거래 빈도 TOP 10\n")
                f.write("  " + "-" * 95 + "\n")
                f.write(f"  {'순위':<6} {'종목코드':<10} {'종목명':<25} {'거래':<8} {'승률':<10} {'평균':<12} {'누적':<12}\n")
                f.write("  " + "-" * 95 + "\n")

                for idx, row in df_top_traded.iterrows():
                    win_rate = (row['wins'] / row['trades'] * 100) if row['trades'] > 0 else 0
                    f.write(f"  {idx+1:<6} {row['code']:<10} {row['code_name']:<25} "
                           f"{int(row['trades']):<8} {win_rate:<10.1f}% "
                           f"{row['avg_return']:<12.2f}% {row['total_return']:<12.2f}%\n")
                f.write("\n")

            # 수익률 높은 종목
            query_top_profit = f"""
            SELECT
                code,
                code_name,
                COUNT(*) as trades,
                AVG(sell_rate) as avg_return,
                SUM(sell_rate) as total_return
            FROM all_item_db
            WHERE sell_date IS NOT NULL
              AND sell_date != ''
              {period_condition}
            GROUP BY code, code_name
            HAVING COUNT(*) >= 2
            ORDER BY AVG(sell_rate) DESC
            LIMIT 10
            """
            df_top_profit = pd.read_sql(query_top_profit, con)

            if not df_top_profit.empty:
                f.write(f"  평균 수익률 TOP 10 (2회 이상 거래)\n")
                f.write("  " + "-" * 95 + "\n")
                f.write(f"  {'순위':<6} {'종목코드':<10} {'종목명':<25} {'거래':<8} {'평균수익률':<15} {'누적수익률':<15}\n")
                f.write("  " + "-" * 95 + "\n")

                for idx, row in df_top_profit.iterrows():
                    f.write(f"  {idx+1:<6} {row['code']:<10} {row['code_name']:<25} "
                           f"{int(row['trades']):<8} {row['avg_return']:<15.2f}% {row['total_return']:<15.2f}%\n")
                f.write("\n")

            # ========== 5. 현재 포트폴리오 ==========
            f.write("💼 현재 포트폴리오 상태\n")
            f.write("-" * 100 + "\n")

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
                f.write(f"\n  보유 종목: {len(df_positions)}개\n")
                f.write("  " + "-" * 95 + "\n")
                f.write(f"  {'종목코드':<10} {'매수일':<12} {'매수가':<12} {'현재가':<12} {'수량':<10} {'평가손익':<15} {'수익률':<10}\n")
                f.write("  " + "-" * 95 + "\n")

                total_value = 0
                total_profit = 0

                for _, row in df_positions.iterrows():
                    value = row['present_price'] * row['holding_amount']
                    total_value += value
                    total_profit += row['valuation_profit']

                    f.write(f"  {row['code']:<10} {row['date']:<12} {row['puchase_price']:>12,}원 "
                           f"{row['present_price']:>12,}원 {row['holding_amount']:>10}주 "
                           f"{row['valuation_profit']:>15,}원 {row['rate']:>10.2f}%\n")

                f.write("  " + "-" * 95 + "\n")
                f.write(f"  총 평가금액: {total_value:>20,}원\n")
                f.write(f"  총 평가손익: {total_profit:>20,}원\n")
                f.write(f"  총 수익률:   {(total_profit/total_value*100) if total_value > 0 else 0:>20.2f}%\n")
            else:
                f.write("\n  현재 보유 중인 종목이 없습니다.\n")

            f.write("\n")

            # ========== 6. Best & Worst 거래 ==========
            f.write("🏆 Best & Worst 거래\n")
            f.write("-" * 100 + "\n")

            # Best 거래
            query_best = f"""
            SELECT
                code,
                code_name,
                buy_date,
                sell_date,
                purchase_price,
                sell_price,
                sell_rate
            FROM all_item_db
            WHERE sell_date IS NOT NULL
              AND sell_date != ''
              {period_condition}
            ORDER BY sell_rate DESC
            LIMIT 5
            """
            df_best = pd.read_sql(query_best, con)

            if not df_best.empty:
                f.write(f"\n  TOP 5 수익 거래\n")
                f.write("  " + "-" * 95 + "\n")

                for idx, row in df_best.iterrows():
                    f.write(f"  [{idx+1}] {row['code']} - {row['code_name']}\n")
                    f.write(f"      매수일: {row['buy_date']} / 매도일: {row['sell_date']}\n")
                    f.write(f"      매수가: {row['purchase_price']:,}원 -> 매도가: {row['sell_price']:,}원\n")
                    f.write(f"      수익률: {row['sell_rate']:.2f}%\n\n")

            # Worst 거래
            query_worst = f"""
            SELECT
                code,
                code_name,
                buy_date,
                sell_date,
                purchase_price,
                sell_price,
                sell_rate
            FROM all_item_db
            WHERE sell_date IS NOT NULL
              AND sell_date != ''
              {period_condition}
            ORDER BY sell_rate ASC
            LIMIT 5
            """
            df_worst = pd.read_sql(query_worst, con)

            if not df_worst.empty:
                f.write(f"  TOP 5 손실 거래\n")
                f.write("  " + "-" * 95 + "\n")

                for idx, row in df_worst.iterrows():
                    f.write(f"  [{idx+1}] {row['code']} - {row['code_name']}\n")
                    f.write(f"      매수일: {row['buy_date']} / 매도일: {row['sell_date']}\n")
                    f.write(f"      매수가: {row['purchase_price']:,}원 -> 매도가: {row['sell_price']:,}원\n")
                    f.write(f"      수익률: {row['sell_rate']:.2f}%\n\n")

            # ========== 푸터 ==========
            f.write("=" * 100 + "\n")
            f.write("✅ 성과 평가 보고서 생성 완료\n")
            f.write(f"📁 파일 위치: {output_path}\n")
            f.write("=" * 100 + "\n")

        con.close()

        print(f"\n✅ 성과 평가 보고서 생성 완료!")
        print(f"📁 파일 위치: {output_path}\n")

        return str(output_path)

    except Exception as e:
        print(f"❌ 보고서 생성 오류: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    parser = argparse.ArgumentParser(description='운용 성과 평가 보고서 생성')
    parser.add_argument('--db', type=str, default='JackBot1_imi1',
                        help='데이터베이스 이름 (기본: JackBot1_imi1)')
    parser.add_argument('--period', type=int, default=None,
                        help='분석 기간 (일). 지정하지 않으면 전체 기간 분석')
    parser.add_argument('--output', type=str, default=None,
                        help='출력 파일 경로 (기본: reports/performance_report_YYYYMMDD_HHMMSS.txt)')

    args = parser.parse_args()

    print("\n" + "=" * 100)
    print("📊 운용 성과 평가 보고서 생성")
    print("=" * 100)
    print(f"데이터베이스: {args.db}")
    if args.period:
        print(f"분석 기간: 최근 {args.period}일")
    else:
        print("분석 기간: 전체")
    print("=" * 100 + "\n")

    generate_performance_report(args.db, args.period, args.output)


if __name__ == "__main__":
    main()
