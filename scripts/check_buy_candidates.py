import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from sqlalchemy import create_engine, text
import pymysql
import pandas as pd
import datetime
from library.cf import db_id, db_passwd, db_ip, db_port, imi1_db_name, v2_min_score, invest_unit
from library.utils import get_latest_complete_date
from library.hybrid_strategy_v2 import HybridStrategyV2
pymysql.install_as_MySQLdb()

_url = f'mysql+mysqldb://{db_id}:{db_passwd}@{db_ip}:{db_port}'
engine = create_engine(f'{_url}/{imi1_db_name}', encoding='utf-8')
engine_daily = create_engine(f'{_url}/daily_buy_list', encoding='utf-8')
engine_craw  = create_engine(f'{_url}/daily_craw',     encoding='utf-8')

today = datetime.datetime.now().strftime("%Y%m%d")
target_date = get_latest_complete_date()  # 장마감 여부에 따라 오늘 or 전 영업일

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
    target_exists = engine_daily.execute(f"""
        SELECT COUNT(*) FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = 'daily_buy_list' AND TABLE_NAME = '{target_date}'
    """).fetchone()[0]

    if target_exists:
        print(f"\n✅ collector_v3.py 실행 완료 (기준: {target_date})")
        print(f"❌ {v2_min_score}점 이상 종목이 없습니다.")
    else:
        latest = engine_daily.execute("""
            SELECT TABLE_NAME FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = 'daily_buy_list' AND TABLE_NAME REGEXP '^[0-9]{8}$'
            ORDER BY TABLE_NAME DESC LIMIT 1
        """).fetchone()
        print(f"\n❌ collector_v3.py가 실행되지 않았습니다. (기준: {target_date})")
        if latest:
            print(f"📅 가장 최근 데이터: {latest[0]}")
        print("💡 collector_v3.py를 먼저 실행하세요.")

# 3. 전체 시장 상위 20개 — collector와 동일한 pre-filter + Python 풀스코어링
print("\n" + "=" * 100)
print(f"전체 시장 상위 20개 (collector 동일 로직 재계산, 200pt 만점)")
print("=" * 100)

latest_table_row = engine_daily.execute("""
    SELECT TABLE_NAME FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = 'daily_buy_list' AND TABLE_NAME REGEXP '^[0-9]{8}$'
    ORDER BY TABLE_NAME DESC LIMIT 1
""").fetchone()
latest_table = latest_table_row[0] if latest_table_row else None

if latest_table:
    # collector num=21과 완전히 동일한 SQL pre-filter
    candidates_sql = f"""
        SELECT a.* FROM `{latest_table}` a
        WHERE NOT EXISTS (SELECT null FROM stock_konex b WHERE a.code=b.code)
        AND a.close > 0 AND a.close < {invest_unit}
        AND a.volume > 0 AND a.vol20 > 0
        ORDER BY (
            (CASE WHEN a.adx > 20 THEN 1 ELSE 0 END) +
            (CASE WHEN a.clo5 > a.clo20 THEN 1 ELSE 0 END) +
            (CASE WHEN a.rsi14 BETWEEN 30 AND 55 THEN 1 ELSE 0 END) +
            (CASE WHEN a.macd > a.macd_signal THEN 1 ELSE 0 END) +
            (CASE WHEN a.cmf20 > 0 THEN 1 ELSE 0 END)
        ) DESC
        LIMIT 200
    """
    candidates = engine_daily.execute(candidates_sql).fetchall()
    print(f"\nSQL 사전필터 완료 — {len(candidates)}개 후보 스코어링 중...")

    # kospi 시장 데이터 로드
    market_data = None
    try:
        mdf = pd.read_sql("SELECT close FROM kospi_index ORDER BY date DESC LIMIT 20", engine_craw)
        if not mdf.empty:
            market_data = mdf['close'].iloc[::-1].reset_index(drop=True)
    except Exception:
        pass

    strategy_v2 = HybridStrategyV2()
    scored = []
    for row in candidates:
        try:
            code      = str(row[2]).zfill(6)
            code_name = row[3]
            row_dict  = dict(row)
            df_120 = pd.read_sql(
                f"SELECT * FROM `{code_name}` ORDER BY date DESC LIMIT 120",
                engine_craw
            ).sort_values('date').reset_index(drop=True)
            score_result = strategy_v2.calculate_total_score(row_dict, df_120, None, market_data)
            score_result['code']      = code
            score_result['code_name'] = code_name
            score_result['close']     = row_dict.get('close', 0)
            score_result['d1_diff']   = row_dict.get('d1_diff_rate', 0)
            score_result['rsi14']     = row_dict.get('rsi14', 0)
            score_result['adx']       = row_dict.get('adx', 0)
            scored.append(score_result)
        except Exception:
            continue

    scored.sort(key=lambda x: x['total'], reverse=True)
    top20 = scored[:20]

    if top20:
        print(f"\n{'순위':<4} {'종목코드':<10} {'종목명':<20} {'총점':>6}  {'A모멘':>6} {'B평균':>6} {'C추세':>6} {'D거래':>6} {'E시장':>6} {'F시간':>6} {'패널티':>7}  {'RSI':>5} {'ADX':>5} {'종가'}")
        print("-" * 130)
        for idx, s in enumerate(top20, 1):
            flag = "✅" if s['total'] >= v2_min_score else "  "
            print(f"[{idx:2d}]{flag} {s['code']:<10} {s['code_name']:<20} {s['total']:>6.1f}"
                  f"  {s['score_a']:>6.1f} {s['score_b']:>6.1f} {s['score_c']:>6.1f}"
                  f" {s['score_d']:>6.1f} {s['score_e']:>6.1f} {s['score_f']:>6.1f}"
                  f" {s['score_penalty']:>7.1f}"
                  f"  {float(s['rsi14'] or 0):>5.1f} {float(s['adx'] or 0):>5.1f}"
                  f"  {s['close']:>8,}")
        print("\n" + "=" * 100)
        all_scores = [s['total'] for s in top20]
        print(f"범위: {min(all_scores):.1f} ~ {max(all_scores):.1f} | 평균: {sum(all_scores)/len(all_scores):.1f}")
        print(f"커트라인({v2_min_score}점) 이상: {sum(1 for s in all_scores if s >= v2_min_score)}개 / {len(top20)}개")
        print("=" * 100)
    else:
        print("❌ 스코어링 결과 없음")
else:
    print("❌ daily_buy_list 테이블 없음. collector_v3.py를 먼저 실행하세요.")

engine.dispose()
engine_daily.dispose()
engine_craw.dispose()

