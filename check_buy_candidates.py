from sqlalchemy import create_engine, text
import pymysql
import datetime
from library.cf import db_id, db_passwd, db_ip, db_port, imi1_db_name, v2_min_score
pymysql.install_as_MySQLdb()

_url = f'mysql+mysqldb://{db_id}:{db_passwd}@{db_ip}:{db_port}'
engine = create_engine(f'{_url}/{imi1_db_name}', encoding='utf-8')
engine_daily = create_engine(f'{_url}/daily_buy_list', encoding='utf-8')

today = datetime.datetime.now().strftime("%Y%m%d")

# 1. 매수 후보 리스트 (커트라인 이상, 점수순)
print("=" * 100)
print(f"매수 후보 리스트 (realtime_daily_buy_list, 커트라인 {v2_min_score}점 이상)")
print("=" * 100)

sql = """
SELECT code, code_name, composite_score, check_item, close
FROM realtime_daily_buy_list
ORDER BY composite_score DESC, code
"""

result = engine.execute(sql).fetchall()

if result:
    print(f"\n총 {len(result)}개 종목")
    print("-" * 100)
    print(f"{'순위':<5} {'종목코드':<10} {'종목명':<20} {'점수/200':<12} {'매수상태':<10} {'종가':<10}")
    print("-" * 100)

    for idx, row in enumerate(result, 1):
        code, code_name, score, check_item, close = row
        status = "완료" if check_item == 1 else "대기"
        print(f"{idx:<5} {code:<10} {code_name:<20} {float(score):>6.2f}/200    {status:<10} {close:<10}")
else:
    print(f"\n❌ 매수 후보 없음 (오늘 {today} collector 미실행이거나 {v2_min_score}점 이상 종목 없음)")

# 2. 점수 분포 통계
print("\n" + "=" * 100)
print("점수 분포 통계")
print("=" * 100)

stats = engine.execute("""
    SELECT MIN(composite_score), MAX(composite_score), AVG(composite_score), COUNT(*)
    FROM realtime_daily_buy_list
""").fetchone()

if stats and stats[3] and stats[3] > 0:
    print(f"\n최저: {stats[0]:.2f} | 최고: {stats[1]:.2f} | 평균: {stats[2]:.2f} | 전체: {stats[3]}개")
else:
    today_exists = engine_daily.execute(f"""
        SELECT COUNT(*) FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = 'daily_buy_list' AND TABLE_NAME = '{today}'
    """).fetchone()[0]

    if today_exists:
        print(f"\n✅ collector_v3.py 실행 완료")
        print(f"❌ 오늘({today}) {v2_min_score}점 이상 종목이 없습니다.")
    else:
        latest = engine_daily.execute("""
            SELECT TABLE_NAME FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = 'daily_buy_list' AND TABLE_NAME REGEXP '^[0-9]{8}$'
            ORDER BY TABLE_NAME DESC LIMIT 1
        """).fetchone()
        print(f"\n❌ collector_v3.py가 실행되지 않았습니다. (오늘: {today})")
        if latest:
            print(f"📅 가장 최근 데이터: {latest[0]}")
        print("💡 collector_v3.py를 먼저 실행하세요.")

# 3. 전체 시장 상위 20개 (HybridStrategyV2 간이 점수 — df_120 제외, 최대 ~142pt)
print("\n" + "=" * 100)
print(f"전체 시장 상위 20개 (HybridStrategyV2 간이점수, df_120 미사용 최대 ~142pt)")
print("=" * 100)

table_exists = engine_daily.execute(f"""
    SELECT COUNT(*) FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = 'daily_buy_list' AND TABLE_NAME = '{today}'
""").fetchone()[0]

if table_exists:
    # 어제 날짜 테이블 찾기 (전일비 계산용)
    prev_table_row = engine_daily.execute(f"""
        SELECT TABLE_NAME FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = 'daily_buy_list' AND TABLE_NAME REGEXP '^[0-9]{{8}}$'
        AND TABLE_NAME < '{today}'
        ORDER BY TABLE_NAME DESC LIMIT 1
    """).fetchone()
    prev_table = prev_table_row[0] if prev_table_row else None

    # SQL 사전 필터: 모멘텀/추세/수급 신호 기준 상위 200개 후보
    if prev_table:
        candidates_sql = text(f"""
            SELECT a.*,
                ROUND((a.close - b.close) / b.close * 100, 2) as d1_change
            FROM `{today}` a
            LEFT JOIN `{prev_table}` b ON a.code = b.code
            WHERE a.close > 0 AND a.volume > 0 AND a.vol20 > 0
              AND a.adx > 0 AND a.rsi14 > 0 AND a.bb_lower > 0
              AND a.close BETWEEN 1000 AND 500000
            ORDER BY (
                (CASE WHEN a.adx > 20 THEN 1 ELSE 0 END) +
                (CASE WHEN a.clo5 > a.clo20 THEN 1 ELSE 0 END) +
                (CASE WHEN a.rsi14 BETWEEN 30 AND 55 THEN 1 ELSE 0 END) +
                (CASE WHEN a.macd > a.macd_signal THEN 1 ELSE 0 END) +
                (CASE WHEN a.cmf20 > 0 THEN 1 ELSE 0 END)
            ) DESC
            LIMIT 200
        """)
    else:
        candidates_sql = text(f"""
            SELECT a.*, 0 as d1_change
            FROM `{today}` a
            WHERE a.close > 0 AND a.volume > 0 AND a.vol20 > 0
              AND a.adx > 0 AND a.rsi14 > 0 AND a.bb_lower > 0
              AND a.close BETWEEN 1000 AND 500000
            ORDER BY (
                (CASE WHEN a.adx > 20 THEN 1 ELSE 0 END) +
                (CASE WHEN a.clo5 > a.clo20 THEN 1 ELSE 0 END) +
                (CASE WHEN a.rsi14 BETWEEN 30 AND 55 THEN 1 ELSE 0 END) +
                (CASE WHEN a.macd > a.macd_signal THEN 1 ELSE 0 END) +
                (CASE WHEN a.cmf20 > 0 THEN 1 ELSE 0 END)
            ) DESC
            LIMIT 200
        """)

    candidates = engine_daily.execute(candidates_sql).fetchall()

    if candidates:
        from library.hybrid_strategy_v2 import HybridStrategyV2
        strategy_v2 = HybridStrategyV2()

        scored = []
        for row in candidates:
            row_dict = dict(row)
            # df_120=None → A4/D1/D3/E1/E2/F1 스킵, 나머지 row dict만으로 계산
            score = strategy_v2.calculate_total_score(row_dict, None, None, None)
            scored.append((row_dict, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        top20 = scored[:20]

        print(f"\n상위 {len(top20)}개 종목 (날짜: {today}, 간이점수 최대 ~142pt — df_120 없이 A+B+C+D2+E3 계산)")
        print("-" * 100)
        for idx, (row_dict, score) in enumerate(top20, 1):
            code = row_dict.get('code', '')
            code_name = row_dict.get('code_name', '')
            close = row_dict.get('close', 0) or 0
            vol = row_dict.get('volume', 0) or 0
            vol20 = row_dict.get('vol20', 0) or 0
            clo5 = row_dict.get('clo5', 0) or 0
            clo20 = row_dict.get('clo20', 0) or 0
            clo60 = row_dict.get('clo60', 0) or 0
            rsi = row_dict.get('rsi14', 0) or 0
            adx = row_dict.get('adx', 0) or 0
            cmf = row_dict.get('cmf20', 0) or 0
            d1_change = row_dict.get('d1_change', 0) or 0

            flag = "✅" if score >= v2_min_score else "  "
            vol_ratio = (vol / vol20 * 100) if vol20 > 0 else 0
            d1_str = f"{float(d1_change):>+6.2f}%"

            print(f"\n[{idx:2d}] {flag} {code} {code_name:<20} | 간이점수: {score:>6.1f} | RSI: {rsi:>5.1f} | ADX: {adx:>5.1f} | CMF: {float(cmf):>+5.2f}")
            print(f"     종가: {close:>8,.0f}원 | 전일비: {d1_str} | 거래량비율: {vol_ratio:>5.1f}%")
            print(f"     이평: 5일 {clo5:>8,.0f} | 20일 {clo20:>8,.0f} | 60일 {clo60:>8,.0f}")

        print("\n" + "=" * 100)
        scores = [s for _, s in top20]
        print(f"범위: {min(scores):.1f} ~ {max(scores):.1f} | 평균: {sum(scores)/len(scores):.1f}")
        print(f"커트라인({v2_min_score}점) 이상: {sum(1 for s in scores if s >= v2_min_score)}개 / {len(scores)}개")
        print("=" * 100)
    else:
        print(f"\n❌ {today} 테이블에 데이터가 없습니다.")
else:
    print(f"\n❌ {today} 테이블이 없습니다. collector_v3.py를 먼저 실행하세요.")

engine.dispose()
engine_daily.dispose()
