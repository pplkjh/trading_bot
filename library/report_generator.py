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
    Trader 일일 결산 리포트 생성 (DB 기반 — 재시작 후에도 당일 전체 내역 포함)

    Args:
        trader: TraderAdvanced 인스턴스
        trade_history: 현재 세션 거래 내역 리스트 (매도사유 보완용)

    Returns:
        str: 생성된 리포트 파일 경로
    """
    try:
        today = datetime.now().strftime('%Y%m%d')
        report_dir = pathlib.Path(__file__).parent.parent.absolute() / 'log' / 'reports'
        os.makedirs(report_dir, exist_ok=True)
        report_path = report_dir / f'trader_report_{today}.txt'

        # DB 연결 (jackbot3_imi1)
        con = pymysql.connect(
            user=db_id,
            passwd=db_passwd,
            host=db_ip,
            db=imi1_db_name,
            charset='utf8',
            port=int(db_port)
        )

        # trade_history에서 종목코드 → 매도사유 매핑 (현재 세션 보완용)
        exit_reason_map = {}
        if trade_history:
            for t in trade_history:
                if t.get('type') == '매도' and t.get('code'):
                    exit_reason_map[t['code']] = t.get('strategy', '')

        with con.cursor() as cur:
            # 오늘 매도 완료된 종목
            cur.execute("""
                SELECT code, code_name, buy_date, sell_date,
                       purchase_price, holding_amount, sell_price, sell_rate,
                       composite_score, score_a, score_b, score_c,
                       score_d, score_e, score_f, score_penalty, exit_reason
                FROM all_item_db
                WHERE sell_date LIKE %s AND simul_num = 3
                ORDER BY sell_date ASC
            """, (today + '%',))
            sold_cols = [d[0] for d in cur.description]
            sold_records = [dict(zip(sold_cols, r)) for r in cur.fetchall()]

            # 오늘 매수 체결된 종목 (당일 buy_date, chegyul_check='0' = 체결완료)
            cur.execute("""
                SELECT code, code_name, buy_date,
                       purchase_price, holding_amount,
                       composite_score, score_a, score_b, score_c,
                       score_d, score_e, score_f, score_penalty
                FROM all_item_db
                WHERE buy_date LIKE %s AND chegyul_check = '0' AND simul_num = 3
                ORDER BY buy_date ASC
            """, (today + '%',))
            bought_cols = [d[0] for d in cur.description]
            bought_records = [dict(zip(bought_cols, r)) for r in cur.fetchall()]

            # 현재 보유 중인 종목 (sell_date='0' = 미매도)
            cur.execute("""
                SELECT code, code_name, buy_date,
                       purchase_price, holding_amount, present_price, rate,
                       composite_score, score_a, score_b, score_c,
                       score_d, score_e, score_f, score_penalty
                FROM all_item_db
                WHERE sell_date = '0'
                  AND chegyul_check = '0'
                  AND simul_num = 3
                ORDER BY buy_date ASC
            """)
            held_cols = [d[0] for d in cur.description]
            held_records = [dict(zip(held_cols, r)) for r in cur.fetchall()]

            # 전체 기간 누적 실현손익 (봇 시작 이후 모든 매도 합산)
            cur.execute("""
                SELECT purchase_price, sell_price, holding_amount
                FROM all_item_db
                WHERE sell_date != '0' AND simul_num = 3 AND chegyul_check = '0'
            """)
            _all_sold = cur.fetchall()
            all_time_realized = sum(
                (int(r[1]) - int(r[0])) * int(r[2])
                for r in _all_sold
                if int(r[0]) > 0
            )

        con.close()

        # ─── 헬퍼 ───────────────────────────────────────────
        def parse_dt(s):
            """'202604140912' → datetime, 실패 시 None"""
            if not s:
                return None
            try:
                if len(s) >= 12:
                    return datetime.strptime(s[:12], '%Y%m%d%H%M')
                return datetime.strptime(s[:8], '%Y%m%d')
            except Exception:
                return None

        def holding_days(buy_str, sell_str=None):
            bd = parse_dt(buy_str)
            sd = parse_dt(sell_str) if sell_str else datetime.now()
            if bd and sd:
                return max(0, (sd.date() - bd.date()).days)
            return 0

        def fmt_score(r):
            return (
                f"종합 {int(r['composite_score']):>3}/200 | "
                f"A(모멘텀) {float(r['score_a']):>5.1f} | "
                f"B(평균회귀) {float(r['score_b']):>5.1f} | "
                f"C(추세강도) {float(r['score_c']):>5.1f} | "
                f"D(거래량/수급) {float(r['score_d']):>5.1f} | "
                f"E(상대강도) {float(r['score_e']):>5.1f} | "
                f"F(멀티TF) {float(r['score_f']):>5.1f} | "
                f"패널티 {float(r['score_penalty']):>+6.1f}"
            )

        def calc_realized(r):
            return (int(r['sell_price']) - int(r['purchase_price'])) * int(r['holding_amount'])

        def infer_reason(record):
            """DB exit_reason → trade_history → 수익률 추정 순으로 사용"""
            # 1순위: DB에 저장된 실제 매도사유
            db_reason = (record.get('exit_reason') or '').strip()
            if db_reason:
                return db_reason
            # 2순위: 현재 세션 trade_history
            th_reason = exit_reason_map.get(record['code'], '').strip()
            if th_reason:
                return th_reason
            # 3순위: 수익률로 추정 (sell_rate는 당일 등락률 — 실제 매수 대비 수익률로 계산)
            buy_p = int(record.get('purchase_price') or 0)
            sell_p = int(record.get('sell_price') or 0)
            rate = (sell_p / buy_p - 1) * 100 if buy_p > 0 else 0.0
            if rate <= -4.5:
                return '손절 (고정 -5%)'
            if rate <= -2.5:
                return '손절 (-3%)'
            if rate >= 5.5:
                return '익절 (+6%)'
            if rate > 0:
                return '익절'
            return '손절'

        # 실시간 현재가 맵: opw00018_output 우선
        live_price_map = {}
        try:
            positions = trader.open_api.opw00018_output.get('multi', [])
            for item in positions:
                code = item[7].strip() if len(item) > 7 else ''
                if code:
                    live_price_map[code] = int(item[3])
        except Exception:
            pass

        # 보유 종목 평가 사전 계산 (API가 0 반환할 때 보정용)
        portfolio_eval_price = 0
        portfolio_unrealized = 0
        for r in held_records:
            buy_p = int(r['purchase_price'])
            shares = int(r['holding_amount'])
            curr = live_price_map.get(r['code'], int(r.get('present_price') or buy_p))
            portfolio_eval_price += curr * shares
            portfolio_unrealized += (curr - buy_p) * shares

        # ─── 매도 성과 집계 ──────────────────────────────────
        def actual_rate(r):
            """sell_rate(당일 등락률) 대신 매수가 대비 실제 수익률 계산"""
            buy_p = int(r['purchase_price'])
            return (int(r['sell_price']) / buy_p - 1) * 100 if buy_p > 0 else 0.0

        total_sold = len(sold_records)
        wins = sum(1 for r in sold_records if actual_rate(r) > 0)
        losses = total_sold - wins
        win_rate = wins / total_sold * 100 if total_sold > 0 else 0.0
        avg_profit = (
            sum(actual_rate(r) for r in sold_records if actual_rate(r) > 0) / wins
            if wins > 0 else 0.0
        )
        avg_loss = (
            sum(actual_rate(r) for r in sold_records if actual_rate(r) <= 0) / losses
            if losses > 0 else 0.0
        )
        total_realized = sum(calc_realized(r) for r in sold_records)

        SEP = "=" * 110
        SUB = "-" * 110

        with open(report_path, 'w', encoding='utf-8') as f:

            # ════ 헤더 ════
            f.write(SEP + "\n")
            _dt = datetime.now()
            _dt_str = f"{_dt.year}년 {_dt.month:02d}월 {_dt.day:02d}일 {_dt.strftime('%H:%M')}"
            f.write(f"  트레이딩 일일 결산 리포트  —  {_dt_str}\n")
            f.write(SEP + "\n\n")

            # ════ 오늘 성과 요약 ════
            f.write("[ 오늘 성과 요약 ]\n")
            f.write(SUB + "\n")
            f.write(f"  매수: {len(bought_records)}건  |  매도: {total_sold}건  |  보유 중: {len(held_records)}개\n")
            if total_sold > 0:
                f.write(
                    f"  매도 성과: 승 {wins}건 / 패 {losses}건  |  "
                    f"승률 {win_rate:.1f}%  |  "
                    f"평균 익절 {avg_profit:+.2f}%  |  "
                    f"평균 손절 {avg_loss:+.2f}%\n"
                )
                f.write(f"  총 실현손익: {total_realized:>+,}원\n")
            f.write("\n")

            # ════ 1. 계좌 정보 ════
            f.write("[ 1. 계좌 정보 ]\n")
            f.write(SUB + "\n")
            try:
                deposit = int(trader.open_api.deposit) if hasattr(trader.open_api, 'deposit') else 0
                d2 = int(trader.open_api.d2_deposit_before_format) if hasattr(trader.open_api, 'd2_deposit_before_format') else 0
                t_buy = int(trader.open_api.total_purchase_price) if hasattr(trader.open_api, 'total_purchase_price') else 0
                t_eval = int(trader.open_api.total_evaluation_price) if hasattr(trader.open_api, 'total_evaluation_price') else 0
                t_pnl = int(trader.open_api.total_evaluation_profit_loss_price) if hasattr(trader.open_api, 'total_evaluation_profit_loss_price') else 0
                t_rate = float(trader.open_api.total_earning_rate) if hasattr(trader.open_api, 'total_earning_rate') else 0.0

                # API가 0을 반환할 때 포트폴리오 직접 계산값으로 보정
                # (장 종료 후 실시간 가격 업데이트 중단으로 Kiwoom API 값이 0이 되는 경우 발생)
                if t_eval == 0 and portfolio_eval_price > 0:
                    t_eval = portfolio_eval_price
                if t_pnl == 0 and portfolio_unrealized != 0:
                    t_pnl = portfolio_unrealized
                if t_rate == 0.0 and t_buy > 0 and t_pnl != 0:
                    t_rate = t_pnl / t_buy * 100

                # 예수금이 0이면 D+2 예수금을 현금으로 사용 (T+2 정산 전 상태)
                cash = deposit if deposit > 0 else d2
                total_assets = cash + t_eval

                f.write(f"  예수금:                   {deposit:>15,}원")
                if deposit == 0 and d2 > 0:
                    f.write("  (D+2 미정산 — 아래 D+2 기준 사용)")
                f.write("\n")
                f.write(f"  D+2 예수금 (결제 기준):   {d2:>15,}원\n")
                f.write(f"  총 매입금액 (현 보유):     {t_buy:>15,}원\n")
                f.write(f"  총 평가금액:              {t_eval:>15,}원\n")
                f.write(f"  미실현 손익:              {t_pnl:>+15,}원  ({t_rate:+.2f}%)\n")
                f.write(f"  총 자산 (현금+평가):      {total_assets:>15,}원\n")
                f.write("\n")

                # ─ 손익 요약 ─
                f.write(f"  [ 손익 요약 ]\n")
                f.write(f"  오늘 실현손익:            {total_realized:>+15,}원\n")
                f.write(f"  현재 미실현손익:          {t_pnl:>+15,}원\n")
                f.write(f"  오늘 예상 손익 합계:      {total_realized + t_pnl:>+15,}원\n")
                f.write(f"  봇 전체 누적 실현손익:    {all_time_realized:>+15,}원\n")
            except Exception as e:
                f.write(f"  계좌 정보 로드 실패: {e}\n")
            f.write("\n")

            # ════ 2. 오늘 매도 내역 ════
            f.write("[ 2. 오늘 매도 내역 ]\n")
            f.write(SUB + "\n")
            if sold_records:
                for r in sold_records:
                    bd = parse_dt(r['buy_date'])
                    sd = parse_dt(r['sell_date'])
                    buy_str = bd.strftime('%Y-%m-%d %H:%M') if bd else r['buy_date']
                    sell_str = sd.strftime('%Y-%m-%d %H:%M') if sd else r['sell_date']
                    days = holding_days(r['buy_date'], r['sell_date'])
                    realized = calc_realized(r)
                    # sell_rate는 당일 등락률 — 실제 매수 대비 수익률로 직접 계산
                    rate = (int(r['sell_price']) / int(r['purchase_price']) - 1) * 100 if int(r['purchase_price']) > 0 else 0.0
                    reason = infer_reason(r)

                    f.write(f"  [{r['code']}] {r['code_name']}\n")
                    f.write(f"    매수: {buy_str}  →  매도: {sell_str}  ({days}일 보유)\n")
                    f.write(
                        f"    매수가: {int(r['purchase_price']):>10,}원 × {int(r['holding_amount']):,}주  |  "
                        f"매도가: {int(r['sell_price']):>10,}원\n"
                    )
                    f.write(
                        f"    수익률: {rate:>+7.2f}%  |  실현손익: {realized:>+12,}원  |  매도사유: {reason}\n"
                    )
                    f.write(f"    스코어: {fmt_score(r)}\n\n")
            else:
                f.write("  오늘 매도한 종목이 없습니다.\n\n")

            # ════ 3. 오늘 매수 내역 ════
            f.write("[ 3. 오늘 매수 내역 ]\n")
            f.write(SUB + "\n")
            if bought_records:
                for r in bought_records:
                    bd = parse_dt(r['buy_date'])
                    buy_str = bd.strftime('%Y-%m-%d %H:%M') if bd else r['buy_date']
                    total_invest = int(r['purchase_price']) * int(r['holding_amount'])

                    f.write(f"  [{r['code']}] {r['code_name']}\n")
                    f.write(
                        f"    매수: {buy_str}  |  "
                        f"매수가: {int(r['purchase_price']):>10,}원 × {int(r['holding_amount']):,}주  |  "
                        f"투자금: {total_invest:,}원\n"
                    )
                    f.write(f"    스코어: {fmt_score(r)}\n\n")
            else:
                f.write("  오늘 매수한 종목이 없습니다.\n\n")

            # ════ 4. 현재 포트폴리오 ════
            f.write("[ 4. 현재 포트폴리오 ]\n")
            f.write(SUB + "\n")
            if held_records:
                f.write(f"  보유 종목 수: {len(held_records)}개\n\n")
                total_unrealized = 0

                for r in held_records:
                    bd = parse_dt(r['buy_date'])
                    buy_str = bd.strftime('%Y-%m-%d %H:%M') if bd else r['buy_date']
                    days = holding_days(r['buy_date'])
                    buy_price = int(r['purchase_price'])
                    shares = int(r['holding_amount'])
                    curr = live_price_map.get(r['code'], int(r.get('present_price') or buy_price))
                    unrealized = (curr - buy_price) * shares
                    unreal_rate = (curr / buy_price - 1) * 100 if buy_price > 0 else 0.0
                    total_unrealized += unrealized

                    f.write(f"  [{r['code']}] {r['code_name']}\n")
                    f.write(f"    매수: {buy_str}  ({days}일 보유)\n")
                    f.write(
                        f"    매수가: {buy_price:>10,}원 × {shares:,}주  |  "
                        f"현재가: {curr:>10,}원\n"
                    )
                    f.write(
                        f"    평가손익: {unrealized:>+12,}원  ({unreal_rate:>+7.2f}%)\n"
                    )
                    f.write(f"    매수 스코어: {fmt_score(r)}\n\n")

                f.write(f"  합계 평가손익: {total_unrealized:>+,}원\n")
            else:
                f.write("  현재 보유 중인 종목이 없습니다.\n")
            f.write("\n")

            # ════ 5. 전략 설정 ════
            f.write("[ 5. 전략 설정 ]\n")
            f.write(SUB + "\n")
            try:
                f.write(f"  고급 매수 전략: {'사용' if trader.use_advanced_buy else '미사용'}\n")
                f.write(f"  고급 매도 전략: {'사용' if trader.use_advanced_sell else '미사용'}\n")
                f.write(f"  리스크 프로필: {trader.risk_profile}\n")
                f.write(f"  최소 팩터 스코어: {trader.min_factor_score}\n")
                f.write(f"  최대 보유 종목: {trader.max_positions}개\n")
            except Exception as e:
                f.write(f"  전략 정보 로드 실패: {e}\n")
            f.write("\n")

            # ════ 푸터 ════
            f.write(SEP + "\n")
            f.write(f"  리포트 생성 완료  |  파일: {report_path}\n")
            f.write(SEP + "\n")

        return str(report_path)

    except Exception as e:
        print(f"트레이더 리포트 생성 오류: {e}")
        import traceback
        traceback.print_exc()
        return None
