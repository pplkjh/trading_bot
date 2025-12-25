"""
데일리 리포트 생성기
collector와 trader의 결과를 요약하여 날짜별 리포트 파일로 저장
"""

import os
import pathlib
from datetime import datetime
import pymysql
import pandas as pd
from library.cf import *


def generate_collector_report(collector_api):
    """
    Collector 실행 결과 요약 리포트 생성

    Args:
        collector_api: collector_api 인스턴스

    Returns:
        str: 생성된 리포트 파일 경로
    """
    try:
        today = datetime.now().strftime('%Y%m%d')
        report_dir = pathlib.Path(__file__).parent.parent.absolute() / 'log' / 'reports'
        os.makedirs(report_dir, exist_ok=True)

        report_path = report_dir / f'collector_report_{today}.txt'

        # daily_buy_list DB 연결
        con_daily_buy = pymysql.connect(
            user=db_id,
            passwd=db_passwd,
            host=db_ip,
            db='daily_buy_list',
            charset='utf8',
            port=int(db_port)
        )

        # daily_craw DB 연결 (일봉 데이터 조회용)
        con_daily_craw = pymysql.connect(
            user=db_id,
            passwd=db_passwd,
            host=db_ip,
            db='daily_craw',
            charset='utf8',
            port=int(db_port)
        )

        # JackBot DB 연결 (realtime_daily_buy_list 조회용)
        con_jackbot = pymysql.connect(
            user=db_id,
            passwd=db_passwd,
            host=db_ip,
            db=imi1_db_name,  # JackBot1_imi1
            charset='utf8',
            port=int(db_port)
        )

        with open(report_path, 'w', encoding='utf-8') as f:
            # 헤더
            f.write("=" * 100 + "\n")
            f.write("📊 데이터 수집 결과 리포트\n")
            f.write("=" * 100 + "\n")
            f.write(f"수집 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 100 + "\n\n")

            # 1. 전체 종목 통계
            f.write("📈 전체 종목 통계\n")
            f.write("-" * 100 + "\n")

            query_total = "SELECT COUNT(*) as total FROM stock_item_all"
            df_total = pd.read_sql(query_total, con_daily_buy)
            total_stocks = df_total.iloc[0]['total']
            f.write(f"  총 수집 종목 수: {total_stocks:,}개\n\n")

            # 2. 시장 동향 분석 (daily_craw 데이터 기반)
            try:
                f.write("📊 시장 동향 분석\n")
                f.write("-" * 100 + "\n")

                # 모든 종목 리스트 가져오기
                query_stocks = "SELECT code_name FROM stock_item_all"
                df_stocks = pd.read_sql(query_stocks, con_daily_buy)

                market_data = []
                processed = 0

                # 각 종목별 최근 데이터 수집
                for stock_name in df_stocks['code_name']:
                    try:
                        # 종목별 테이블에서 최근 2일 데이터 조회
                        query_stock_data = f"""
                        SELECT date, open, close, volume, code
                        FROM `{stock_name}`
                        ORDER BY date DESC
                        LIMIT 2
                        """
                        df_stock = pd.read_sql(query_stock_data, con_daily_craw)

                        if len(df_stock) >= 2:
                            today_data = df_stock.iloc[0]
                            yesterday_data = df_stock.iloc[1]

                            # 등락률 계산
                            if yesterday_data['close'] > 0:
                                change_pct = ((today_data['close'] - yesterday_data['close']) / yesterday_data['close']) * 100

                                market_data.append({
                                    'name': stock_name,
                                    'code': today_data['code'],
                                    'close': today_data['close'],
                                    'change_pct': change_pct,
                                    'volume': today_data['volume']
                                })

                        processed += 1
                        # 진행률 바 표시 (같은 줄에 업데이트)
                        if processed % 100 == 0 or processed == len(df_stocks):
                            progress = (processed / len(df_stocks)) * 100
                            bar_length = 40
                            filled = int(bar_length * processed / len(df_stocks))
                            bar = '█' * filled + '░' * (bar_length - filled)
                            print(f"\r  시장 분석: [{bar}] {progress:.1f}% ({processed}/{len(df_stocks)})", end='', flush=True)

                    except Exception:
                        # 해당 종목 테이블이 없거나 데이터가 없는 경우 무시
                        continue

                # 진행률 바 완료 후 줄바꿈
                print()

                if market_data:
                    df_market = pd.DataFrame(market_data)

                    # 시장 전체 통계
                    rising = len(df_market[df_market['change_pct'] > 0])
                    falling = len(df_market[df_market['change_pct'] < 0])
                    unchanged = len(df_market[df_market['change_pct'] == 0])

                    f.write(f"  분석 종목 수: {len(df_market):,}개\n")
                    f.write(f"  상승: {rising:,}개 ({rising/len(df_market)*100:.1f}%) | ")
                    f.write(f"하락: {falling:,}개 ({falling/len(df_market)*100:.1f}%) | ")
                    f.write(f"보합: {unchanged:,}개 ({unchanged/len(df_market)*100:.1f}%)\n\n")

                    # 급등 TOP 10
                    top_gainers = df_market.nlargest(10, 'change_pct')
                    f.write(f"  {'🔥 급등 TOP 10':^50}\n")
                    f.write("  " + "-" * 95 + "\n")
                    f.write(f"  {'순위':<6} {'종목코드':<10} {'종목명':<25} {'현재가':>12} {'등락률':>10}\n")
                    f.write("  " + "-" * 95 + "\n")

                    for idx, row in top_gainers.iterrows():
                        f.write(f"  {top_gainers.index.get_loc(idx)+1:<6} {row['code']:<10} {row['name']:<25} "
                               f"{int(row['close']):>12,}원 {row['change_pct']:>9.2f}%\n")

                    f.write("\n")

                    # 급락 TOP 10
                    top_losers = df_market.nsmallest(10, 'change_pct')
                    f.write(f"  {'❄️  급락 TOP 10':^50}\n")
                    f.write("  " + "-" * 95 + "\n")
                    f.write(f"  {'순위':<6} {'종목코드':<10} {'종목명':<25} {'현재가':>12} {'등락률':>10}\n")
                    f.write("  " + "-" * 95 + "\n")

                    for idx, row in top_losers.iterrows():
                        f.write(f"  {top_losers.index.get_loc(idx)+1:<6} {row['code']:<10} {row['name']:<25} "
                               f"{int(row['close']):>12,}원 {row['change_pct']:>9.2f}%\n")

                    f.write("\n")

                    # 거래량 TOP 10
                    top_volume = df_market.nlargest(10, 'volume')
                    f.write(f"  {'📊 거래량 TOP 10':^50}\n")
                    f.write("  " + "-" * 95 + "\n")
                    f.write(f"  {'순위':<6} {'종목코드':<10} {'종목명':<25} {'거래량':>15} {'등락률':>10}\n")
                    f.write("  " + "-" * 95 + "\n")

                    for idx, row in top_volume.iterrows():
                        f.write(f"  {top_volume.index.get_loc(idx)+1:<6} {row['code']:<10} {row['name']:<25} "
                               f"{int(row['volume']):>15,}주 {row['change_pct']:>9.2f}%\n")

                    f.write("\n")
                else:
                    f.write("  시장 데이터를 분석할 수 없습니다.\n\n")

            except Exception as e:
                f.write(f"  시장 분석 실패: {e}\n\n")

            # 3. 매수 후보 종목 (realtime_daily_buy_list)
            try:
                # realtime_daily_buy_list에 어떤 컬럼이 있는지 먼저 확인
                query_buy_list = """
                SELECT *
                FROM realtime_daily_buy_list
                LIMIT 20
                """
                df_buy_list = pd.read_sql(query_buy_list, con_jackbot)

                f.write("🎯 내일 매수 후보 종목\n")
                f.write("-" * 100 + "\n")

                if len(df_buy_list) > 0:
                    f.write(f"  총 {len(df_buy_list)}개 종목\n\n")

                    # 컬럼이 있는 것만 사용
                    cols = df_buy_list.columns.tolist()
                    f.write(f"  {'순위':<6} {'종목코드':<10} {'종목명':<20}")

                    if 'close' in cols:
                        f.write(f" {'현재가':>12}")
                    if 'd1' in cols:
                        f.write(f" {'D1':>8}")
                    if 'd2' in cols:
                        f.write(f" {'D2':>8}")
                    if 'check_item' in cols:
                        f.write(f" {'전략':>10}")
                    f.write("\n")
                    f.write("  " + "-" * 95 + "\n")

                    for idx, row in df_buy_list.iterrows():
                        line = f"  {idx+1:<6} {row.get('code', 'N/A'):<10} {row.get('code_name', 'N/A'):<20}"

                        if 'close' in cols:
                            line += f" {int(row['close']):>12,}원" if pd.notna(row.get('close')) else f" {'N/A':>12}"
                        if 'd1' in cols:
                            line += f" {row['d1']:>8.2f}" if pd.notna(row.get('d1')) else f" {'N/A':>8}"
                        if 'd2' in cols:
                            line += f" {row['d2']:>8.2f}" if pd.notna(row.get('d2')) else f" {'N/A':>8}"
                        if 'check_item' in cols:
                            strategy = str(row['check_item'])[:10] if pd.notna(row.get('check_item')) else 'N/A'
                            line += f" {strategy:>10}"

                        f.write(line + "\n")
                else:
                    f.write("  매수 후보 종목이 없습니다.\n")
                f.write("\n")
            except Exception as e:
                f.write(f"  매수 후보 분석 실패: {e}\n\n")

            # 푸터
            f.write("=" * 100 + "\n")
            f.write("✅ 리포트 생성 완료\n")
            f.write(f"📁 파일 위치: {report_path}\n")
            f.write("=" * 100 + "\n")

        con_daily_buy.close()
        con_daily_craw.close()
        con_jackbot.close()
        return str(report_path)

    except Exception as e:
        print(f"리포트 생성 오류: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_trader_report(trader, trade_history=None):
    """
    Trader 실행 결과 요약 리포트 생성

    Args:
        trader: TraderAdvanced 인스턴스
        trade_history: 오늘 거래 내역 리스트 (옵션)

    Returns:
        str: 생성된 리포트 파일 경로
    """
    try:
        today = datetime.now().strftime('%Y%m%d')
        report_dir = pathlib.Path(__file__).parent.parent.absolute() / 'log' / 'reports'
        os.makedirs(report_dir, exist_ok=True)

        report_path = report_dir / f'trader_report_{today}.txt'

        with open(report_path, 'w', encoding='utf-8') as f:
            # 헤더
            f.write("=" * 100 + "\n")
            f.write("💼 트레이딩 결과 리포트\n")
            f.write("=" * 100 + "\n")
            f.write(f"거래 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 100 + "\n\n")

            # 1. 계좌 정보
            f.write("💰 계좌 정보\n")
            f.write("-" * 100 + "\n")

            try:
                deposit = int(trader.open_api.deposit) if hasattr(trader.open_api, 'deposit') else 0
                d2_deposit = int(trader.open_api.d2_deposit_before_format) if hasattr(trader.open_api, 'd2_deposit_before_format') else 0
                total_purchase = int(trader.open_api.total_purchase_price) if hasattr(trader.open_api, 'total_purchase_price') else 0
                total_eval = int(trader.open_api.total_evaluation_price) if hasattr(trader.open_api, 'total_evaluation_price') else 0
                total_profit = int(trader.open_api.total_evaluation_profit_loss_price) if hasattr(trader.open_api, 'total_evaluation_profit_loss_price') else 0
                profit_rate = float(trader.open_api.total_earning_rate) if hasattr(trader.open_api, 'total_earning_rate') else 0.0

                f.write(f"  예수금: {deposit:,}원\n")
                f.write(f"  D+2 예수금: {d2_deposit:,}원\n")
                f.write(f"  총 매입금액: {total_purchase:,}원\n")
                f.write(f"  총 평가금액: {total_eval:,}원\n")
                f.write(f"  총 평가손익: {total_profit:,}원 ({profit_rate:.2f}%)\n")
                f.write(f"  총 자산: {deposit + total_eval:,}원\n\n")
            except Exception as e:
                f.write(f"  계좌 정보 로드 실패: {e}\n\n")

            # 2. 현재 포트폴리오
            f.write("📊 현재 포트폴리오\n")
            f.write("-" * 100 + "\n")

            try:
                if hasattr(trader.open_api, 'opw00018_output') and 'multi' in trader.open_api.opw00018_output:
                    positions = trader.open_api.opw00018_output['multi']

                    if positions:
                        f.write(f"  보유 종목 수: {len(positions)}개\n\n")
                        f.write(f"  {'종목코드':<10} {'종목명':<20} {'보유수량':>10} {'매입가':>12} {'현재가':>12} {'수익률':>10} {'평가손익':>15}\n")
                        f.write("  " + "-" * 95 + "\n")

                        for item in positions:
                            code = item[6] if len(item) > 6 else ''
                            name = item[0] if len(item) > 0 else ''
                            quantity = int(item[1]) if len(item) > 1 else 0
                            buy_price = int(item[2]) if len(item) > 2 else 0
                            current_price = int(item[3]) if len(item) > 3 else 0
                            profit = int(item[4]) if len(item) > 4 else 0
                            profit_rate = float(item[5]) if len(item) > 5 else 0.0

                            f.write(f"  {code:<10} {name:<20} {quantity:>10,}주 {buy_price:>12,}원 "
                                   f"{current_price:>12,}원 {profit_rate:>9.2f}% {profit:>15,}원\n")
                    else:
                        f.write("  보유 종목이 없습니다.\n")
                else:
                    f.write("  포트폴리오 정보를 불러올 수 없습니다.\n")
                f.write("\n")
            except Exception as e:
                f.write(f"  포트폴리오 로드 실패: {e}\n\n")

            # 3. 오늘의 거래 내역 (전달받은 trade_history 사용)
            f.write("📝 오늘의 거래 내역\n")
            f.write("-" * 100 + "\n")

            if trade_history and len(trade_history) > 0:
                f.write(f"  총 {len(trade_history)}건의 거래\n\n")
                f.write(f"  {'시간':<12} {'구분':<6} {'종목코드':<10} {'종목명':<20} {'가격':>12} {'수량':>10} {'전략':>15}\n")
                f.write("  " + "-" * 95 + "\n")

                for trade in trade_history:
                    f.write(f"  {trade.get('time', ''):<12} {trade.get('type', ''):<6} "
                           f"{trade.get('code', ''):<10} {trade.get('name', ''):<20} "
                           f"{trade.get('price', 0):>12,}원 {trade.get('quantity', 0):>10,}주 "
                           f"{trade.get('strategy', 'N/A')[:15]:>15}\n")
            else:
                f.write("  오늘 거래 내역이 없습니다.\n")
            f.write("\n")

            # 4. 전략 설정
            f.write("⚙️ 전략 설정\n")
            f.write("-" * 100 + "\n")
            f.write(f"  고급 매수 전략: {'사용' if trader.use_advanced_buy else '미사용'}\n")
            f.write(f"  고급 매도 전략: {'사용' if trader.use_advanced_sell else '미사용'}\n")
            f.write(f"  리스크 프로필: {trader.risk_profile}\n")
            f.write(f"  최소 팩터 스코어: {trader.min_factor_score}\n")
            f.write(f"  최대 보유 종목: {trader.max_positions}개\n\n")

            # 푸터
            f.write("=" * 100 + "\n")
            f.write("✅ 리포트 생성 완료\n")
            f.write(f"📁 파일 위치: {report_path}\n")
            f.write("=" * 100 + "\n")

        return str(report_path)

    except Exception as e:
        print(f"트레이더 리포트 생성 오류: {e}")
        import traceback
        traceback.print_exc()
        return None
