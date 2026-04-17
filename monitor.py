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

import re
import os
import pymysql
import pandas as pd
from datetime import datetime
import argparse
from library.cf import *
from library.utils import get_latest_complete_date


def parse_today_sell_reasons(log_path: str = 'log/jackbot.log') -> dict:
    """
    오늘 jackbot.log에서 매도 사유를 파싱해 {code: reason_str} 반환.
    로그 포맷: '손절 매도: 종목명(코드) -4.23% [사유] - N주'
               '익절 매도: 종목명(코드) 8.11% [사유] - N주'
    """
    reasons = {}
    today_prefix = datetime.today().strftime('%Y-%m-%d')
    pattern = re.compile(
        r'(?:손절|익절) 매도: .+?\((\d{6})\) [+-]?\d+\.\d+% \[(.+?)\]'
    )
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f:
                if today_prefix not in line:
                    continue
                m = pattern.search(line)
                if m:
                    reasons[m.group(1)] = m.group(2)
    except Exception:
        pass
    return reasons


def get_trailing_info(con_jb) -> dict:
    """
    realtime_position_monitor에서 highest_price 조회 → {code: highest_price}
    """
    try:
        df = pd.read_sql("SELECT code, highest_price FROM realtime_position_monitor", con_jb)
        return dict(zip(df['code'].astype(str), df['highest_price']))
    except Exception:
        return {}


def get_latest_indicators(codes: list) -> dict:
    """
    daily_buy_list 최신 날짜 테이블에서 ADX/ATR/BB 조회 → {code: {adx, atr14, bb_position}}
    """
    try:
        con = pymysql.connect(
            user=db_id, passwd=db_passwd, host=db_ip,
            db='daily_buy_list', charset='utf8', port=int(db_port)
        )
        cursor = con.cursor()
        cursor.execute(
            "SELECT TABLE_NAME FROM information_schema.tables "
            "WHERE table_schema='daily_buy_list' AND table_name REGEXP '^[0-9]{8}$' "
            "ORDER BY TABLE_NAME DESC LIMIT 1"
        )
        row = cursor.fetchone()
        if not row:
            con.close()
            return {}

        latest_table = row[0]
        placeholders = ','.join(['%s'] * len(codes))
        cursor.execute(
            f"SELECT code, adx, atr14, bb_upper, bb_lower, close "
            f"FROM `{latest_table}` WHERE code IN ({placeholders})",
            codes
        )
        result = {}
        for r in cursor.fetchall():
            code, adx, atr14, bb_upper, bb_lower, close = r
            bb_range = float(bb_upper or 0) - float(bb_lower or 0)
            bb_pos = (float(close or 0) - float(bb_lower or 0)) / bb_range if bb_range > 0 else 0.5
            result[str(code).zfill(6)] = {
                'adx':        float(adx or 0),
                'atr14':      float(atr14 or 0),
                'bb_position': bb_pos,
            }
        con.close()
        return result
    except Exception:
        return {}


def parse_today_skips(log_path: str = 'log/jackbot.log') -> dict:
    """
    오늘 날짜 jackbot.log에서 매수 스킵 로그를 파싱해 {code: reason_str} 반환
    """
    skips = {}
    today_prefix = datetime.today().strftime('%Y-%m-%d')
    # 가격 범위 초과 패턴: 에스씨디(042110) 목표가=1430 현재가=1451 허용범위=[...]
    pattern_price = re.compile(
        r'매수 스킵 \(가격 범위 초과\): .+?\((\d+)\) 목표가=(\S+) 현재가=(\S+) 허용범위=(\S+)'
    )
    # 이미 처리됨 패턴
    pattern_done = re.compile(r'매수 스킵 \(이미 처리됨\): .+?\((\d+)\)')
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f:
                if today_prefix not in line or '매수 스킵' not in line:
                    continue
                m = pattern_price.search(line)
                if m:
                    code, target, cur, rng = m.group(1), m.group(2), m.group(3), m.group(4)
                    skips[code] = f"⛔ 가격 범위 초과  목표가={target}  현재가={cur}  허용={rng}"
                    continue
                m = pattern_done.search(line)
                if m:
                    skips[m.group(1)] = "⛔ 이미 처리됨"
    except Exception:
        pass
    return skips


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
            p.code,
            COALESCE(a.code_name, p.code) as code_name,
            p.date,
            p.puchase_price,
            p.holding_amount,
            p.present_price,
            p.valuation_profit,
            p.rate
        FROM possessed_item p
        LEFT JOIN (
            SELECT code, code_name
            FROM all_item_db
            WHERE sell_date = '0'
            GROUP BY code
        ) a ON p.code = a.code
        WHERE p.holding_amount > 0
        ORDER BY p.date DESC
        """

        df_positions = pd.read_sql(query_positions, con)

        if not df_positions.empty:
            print(f"\n📈 보유 종목 ({len(df_positions)}개)")
            print("-"*100)

            # highest_price / ADX 지표 일괄 조회
            codes = df_positions['code'].astype(str).tolist()
            trailing_map  = get_trailing_info(con)
            indicator_map = get_latest_indicators(codes)

            total_buy = 0
            total_value = 0
            total_profit = 0

            for idx, row in df_positions.iterrows():
                code  = str(row['code'])
                value = row['present_price'] * row['holding_amount']
                total_buy    += row['puchase_price'] * row['holding_amount']
                total_value  += value
                total_profit += row['valuation_profit']

                print(f"\n[{idx+1}] {code} - {row['code_name']}")
                print(f"  매수일:     {row['date']}")
                print(f"  매수가:     {row['puchase_price']:>10,}원")
                print(f"  현재가:     {row['present_price']:>10,}원")
                print(f"  수량:       {row['holding_amount']:>10}주")
                print(f"  평가금액:   {value:>10,}원")
                print(f"  수익률:     {row['rate']:>10.2f}%")
                print(f"  평가손익:   {row['valuation_profit']:>10,}원")

                # trailing stop 정보
                ind          = indicator_map.get(code, {})
                highest      = trailing_map.get(code)
                adx          = ind.get('adx', 0)
                atr14        = ind.get('atr14', 0)
                bb_pos       = ind.get('bb_position', None)

                if adx >= 25:
                    trail_mult = 2.5
                    trail_act  = 3.0
                    max_days   = 10
                elif adx >= 20:
                    trail_mult = 2.0
                    trail_act  = 4.0
                    max_days   = 8
                else:
                    trail_mult = 1.5
                    trail_act  = 5.0
                    max_days   = 6

                if highest and atr14 > 0:
                    trail_stop = highest - atr14 * trail_mult
                    trail_stop_str = f"{int(trail_stop):,}원"
                    trail_gain = (row['present_price'] / row['puchase_price'] - 1) * 100
                    trail_active = trail_gain >= trail_act
                    trail_status = "🟢 활성" if trail_active else f"⚪ {trail_act:.0f}% 도달 시 활성"
                    print(f"  최고가:     {int(highest):>10,}원  (트레일링 스톱: {trail_stop_str}  {trail_status})")
                elif highest:
                    print(f"  최고가:     {int(highest):>10,}원")

                if adx > 0:
                    adx_label = "추세장" if adx >= 25 else ("중립" if adx >= 20 else "횡보장")
                    atr_str   = f"ATR={atr14:.0f}" if atr14 > 0 else ""
                    bb_str    = f"  BB위치={bb_pos:.2f}" if bb_pos is not None else ""
                    print(f"  매도전략:   ADX={adx:.1f}({adx_label})  손절×{trail_mult}  최대{max_days}일  {atr_str}{bb_str}")

            print("\n" + "-"*100)
            print(f"총 매수금액:  {total_buy:>15,.0f}원")
            print(f"총 평가금액:  {total_value:>15,.0f}원")
            print(f"총 평가손익:  {total_profit:>15,.0f}원")
            print(f"총 수익률:    {(total_profit/total_buy*100) if total_buy > 0 else 0:>15.2f}%")

        else:
            print("\n✅ 보유 종목이 없습니다.")

        # 2. 오늘 매매 이력
        today = datetime.today().strftime("%Y%m%d")

        query_today_trades = """
        SELECT
            code,
            code_name,
            buy_date as trade_date,
            purchase_price,
            holding_amount,
            0 as sell_price,
            0.0 as sell_rate,
            0 as realized_profit,
            'BUY' as type
        FROM all_item_db
        WHERE LEFT(buy_date, 8) = %s

        UNION ALL

        SELECT
            code,
            code_name,
            sell_date as trade_date,
            purchase_price,
            holding_amount,
            sell_price,
            sell_rate,
            realized_profit,
            'SELL' as type
        FROM all_item_db
        WHERE LEFT(sell_date, 8) = %s AND sell_date != '0'

        ORDER BY trade_date DESC
        """

        df_today = pd.read_sql(query_today_trades, con, params=(today, today))

        if not df_today.empty:
            buy_rows   = df_today[df_today['type'] == 'BUY']
            sell_rows  = df_today[df_today['type'] == 'SELL']
            sell_reason_map = parse_today_sell_reasons()
            print(f"\n📝 오늘 매매 이력 ({len(df_today)}건: 매수 {len(buy_rows)}건 / 매도 {len(sell_rows)}건)")
            print("-"*100)

            for idx, row in df_today.iterrows():
                if row['type'] == 'BUY':
                    amount = int(row['holding_amount']) if row['holding_amount'] else 0
                    total = int(row['purchase_price']) * amount
                    print(f"  🟢 매수  {row['code']} ({row['code_name']:<12})  "
                          f"{int(row['purchase_price']):>8,}원 × {amount:>4}주 = {total:>12,}원  "
                          f"({row['trade_date'][8:10]}:{row['trade_date'][10:12]})")
                else:
                    buy_p  = int(row['purchase_price'])
                    sell_p = int(row['sell_price'])
                    # sell_rate는 당일 등락률 — 실제 매수 대비 수익률로 직접 계산
                    rate   = (sell_p / buy_p - 1) * 100 if buy_p > 0 else 0.0
                    profit = int((sell_p - buy_p) * row['holding_amount'])
                    sign   = '+' if rate >= 0 else ''
                    emoji  = '🔴' if rate >= 0 else '🔵'
                    reason = sell_reason_map.get(str(row['code']), '')
                    reason_str = f"  [{reason}]" if reason else ''
                    print(f"  {emoji} 매도  {row['code']} ({row['code_name']:<12})  "
                          f"{sell_p:>8,}원  "
                          f"수익률 {sign}{rate:.2f}%  실현손익 {sign}{profit:,}원  "
                          f"({row['trade_date'][8:10]}:{row['trade_date'][10:12]}){reason_str}")

            if not sell_rows.empty:
                total_realized = int(((sell_rows['sell_price'] - sell_rows['purchase_price']) * sell_rows['holding_amount']).sum())
                sign = '+' if total_realized >= 0 else ''
                print(f"  {'─'*90}")
                print(f"  오늘 실현손익 합계: {sign}{total_realized:,}원")

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
                cols = df_candidates.columns.tolist()

                # composite_score 기준 정렬
                if 'composite_score' in cols:
                    df_candidates = df_candidates.sort_values('composite_score', ascending=False)
                elif 'd1' in cols:
                    df_candidates = df_candidates.sort_values('d1', ascending=False)

                # 오늘 실제 매수된 코드 목록
                today_str = datetime.today().strftime("%Y%m%d")
                bought_today = set()
                try:
                    df_bought = pd.read_sql(
                        f"SELECT code FROM all_item_db WHERE LEFT(buy_date, 8) = '{today_str}'",
                        con
                    )
                    bought_today = set(df_bought['code'].astype(str).tolist())
                except Exception:
                    pass

                # 오늘 스킵된 종목 (로그 파싱)
                skip_reasons = parse_today_skips()

                def _v(row, col, default=None):
                    return row[col] if col in cols and pd.notna(row.get(col)) else default

                for rank, (_, row) in enumerate(df_candidates.iterrows(), 1):
                    code = str(_v(row, 'code', 'N/A'))
                    code_name = str(_v(row, 'code_name', 'N/A'))
                    if code in bought_today:
                        status = '✅ 매수완료'
                    elif code in skip_reasons:
                        status = skip_reasons[code]
                    else:
                        status = '⏳ 미매수'
                    print(f"\n[{rank}] {code} - {code_name}  {status}")

                    close = _v(row, 'close')
                    if close is not None:
                        print(f"  현재가:       {int(close):>10,}원")

                    score = _v(row, 'composite_score')
                    if score is not None:
                        print(f"  종합 스코어:  {score:>10.1f}/200")

                    # 추세 지표
                    rsi  = _v(row, 'rsi14')
                    adx  = _v(row, 'adx')
                    pdi  = _v(row, 'plus_di')
                    mdi  = _v(row, 'minus_di')
                    if any(x is not None for x in [rsi, adx, pdi, mdi]):
                        parts = []
                        if rsi  is not None: parts.append(f"RSI={rsi:.1f}")
                        if adx  is not None: parts.append(f"ADX={adx:.1f}")
                        if pdi  is not None: parts.append(f"+DI={pdi:.1f}")
                        if mdi  is not None: parts.append(f"-DI={mdi:.1f}")
                        print(f"  추세:         {'  '.join(parts)}")

                    # 모멘텀/거래량
                    cmf  = _v(row, 'cmf20')
                    mfi  = _v(row, 'mfi14')
                    macd = _v(row, 'macd')
                    msig = _v(row, 'macd_signal')
                    if any(x is not None for x in [cmf, mfi, macd]):
                        parts = []
                        if cmf  is not None: parts.append(f"CMF={cmf:.3f}")
                        if mfi  is not None: parts.append(f"MFI={mfi:.1f}")
                        if macd is not None and msig is not None:
                            parts.append(f"MACD={'↑' if macd > msig else '↓'}({macd:.1f}/{msig:.1f})")
                        print(f"  모멘텀:       {'  '.join(parts)}")

                    # 변동성
                    atr  = _v(row, 'atr14')
                    bbw  = _v(row, 'bb_bandwidth')
                    if any(x is not None for x in [atr, bbw]):
                        parts = []
                        if atr is not None and close:
                            parts.append(f"ATR%={atr/close*100:.1f}%")
                        if bbw is not None:
                            parts.append(f"BB폭={bbw:.3f}")
                        print(f"  변동성:       {'  '.join(parts)}")
            else:
                # collector 실행 여부는 daily_buy_list의 오늘 날짜 테이블로 확인
                con_daily = pymysql.connect(
                    user=db_id,
                    passwd=db_passwd,
                    host=db_ip,
                    db='daily_buy_list',
                    charset='utf8',
                    port=int(db_port)
                )
                cursor_daily = con_daily.cursor()

                # daily_buy_list 데이터베이스에 기준 날짜 테이블이 있는지 확인
                target_date = get_latest_complete_date()
                cursor_daily.execute(f"""
                    SELECT COUNT(*)
                    FROM information_schema.TABLES
                    WHERE TABLE_SCHEMA = 'daily_buy_list'
                    AND TABLE_NAME = '{target_date}'
                """)
                target_table_exists = cursor_daily.fetchone()[0]

                if target_table_exists > 0:
                    # collector는 돌았지만 min_score 이상이 없는 경우
                    print(f"  ✅ collector_v3.py 실행 완료 (기준: {target_date})")
                    print(f"  ❌ {v2_min_score}점 이상 종목이 없습니다.")
                    print("  💡 시장 상황이 좋지 않아 매수 조건을 만족하는 종목이 없습니다.")
                else:
                    # collector가 안 돌아간 경우 - 최신 데이터 날짜 확인
                    cursor_daily.execute("""
                        SELECT TABLE_NAME
                        FROM information_schema.TABLES
                        WHERE TABLE_SCHEMA = 'daily_buy_list'
                        AND TABLE_NAME REGEXP '^[0-9]{8}$'
                        ORDER BY TABLE_NAME DESC
                        LIMIT 1
                    """)
                    latest_table = cursor_daily.fetchone()

                    print(f"  ❌ collector_v3.py가 실행되지 않았습니다. (기준: {target_date})")
                    if latest_table and latest_table[0]:
                        print(f"  📅 가장 최근 데이터: {latest_table[0]}")
                    else:
                        print("  📅 데이터베이스가 비어있습니다.")
                    print("  💡 collector_v3.py를 먼저 실행하여 매수 후보를 생성하세요.")

                con_daily.close()
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
    트레이더 실행 상태 확인 (realtime_position_monitor last_update 기준)
    """
    try:
        import pymysql
        pymysql.install_as_MySQLdb()
        from sqlalchemy import create_engine, text
        from library.cf import db_id, db_passwd, db_ip, db_port, imi1_db_name
        from datetime import datetime, timedelta

        url = f'mysql+mysqldb://{db_id}:{db_passwd}@{db_ip}:{db_port}/{imi1_db_name}'
        engine = create_engine(url, encoding='utf-8')

        row = engine.execute(text('SELECT MAX(last_update) FROM realtime_position_monitor')).fetchone()
        last_update = row[0]

        if last_update and datetime.now() - last_update < timedelta(minutes=2):
            print(f"\n✅ 트레이더가 실행 중입니다. (최근 업데이트: {last_update.strftime('%H:%M:%S')})")
        else:
            if last_update:
                print(f"\n⚠️  트레이더가 실행되지 않았습니다. (마지막 업데이트: {last_update.strftime('%H:%M:%S')})")
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
    parser.add_argument('--db', type=str, default=imi1_db_name,
                        help=f'데이터베이스 이름 (기본: {imi1_db_name})')
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
