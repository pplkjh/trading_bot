from sqlalchemy import create_engine, text
import pymysql
import datetime
from library.cf import db_id, db_passwd, db_ip, db_port, imi1_db_name
pymysql.install_as_MySQLdb()

_url = f'mysql+mysqldb://{db_id}:{db_passwd}@{db_ip}:{db_port}'
engine = create_engine(f'{_url}/{imi1_db_name}', encoding='utf-8')
engine_daily = create_engine(f'{_url}/daily_buy_list', encoding='utf-8')

print("=" * 100)
print("매수 후보 리스트 (realtime_daily_buy_list)")
print("=" * 100)

# 1. 전체 매수 후보 확인 (점수순 정렬)
sql = """
SELECT code, code_name, composite_score, check_item, close
FROM realtime_daily_buy_list
ORDER BY composite_score DESC, code
"""

result = engine.execute(sql).fetchall()

print(f"\n총 {len(result)}개 종목")
print("-" * 100)
print(f"{'순위':<5} {'종목코드':<10} {'종목명':<20} {'점수':<10} {'매수상태':<10} {'종가':<10}")
print("-" * 100)

for idx, row in enumerate(result, 1):
    code, code_name, score, check_item, close = row
    status = "완료" if check_item == 1 else "대기"
    print(f"{idx:<5} {code:<10} {code_name:<20} {score:<10.2f} {status:<10} {close:<10}")

# 2. 매수 대기 중인 종목만 표시
print("\n" + "=" * 100)
print("매수 대기 중인 종목 (check_item = 0)")
print("=" * 100)

sql_pending = """
SELECT code, code_name, composite_score, close
FROM realtime_daily_buy_list
WHERE check_item = 0
ORDER BY composite_score DESC, code
"""

pending = engine.execute(sql_pending).fetchall()

if len(pending) > 0:
    print(f"\n총 {len(pending)}개 종목 매수 대기 중")
    print("-" * 100)
    print(f"{'순위':<5} {'종목코드':<10} {'종목명':<20} {'점수':<10} {'종가':<10}")
    print("-" * 100)

    for idx, row in enumerate(pending, 1):
        code, code_name, score, close = row
        print(f"{idx:<5} {code:<10} {code_name:<20} {score:<10.2f} {close:<10}")
else:
    print("\n매수 대기 중인 종목이 없습니다.")

# 3. 매수 완료된 종목
print("\n" + "=" * 100)
print("매수 시도 완료 종목 (check_item = 1)")
print("=" * 100)

sql_done = """
SELECT code, code_name, composite_score, close
FROM realtime_daily_buy_list
WHERE check_item = 1
ORDER BY composite_score DESC, code
"""

done = engine.execute(sql_done).fetchall()

if len(done) > 0:
    print(f"\n총 {len(done)}개 종목 매수 시도 완료")
    print("-" * 100)
    print(f"{'순위':<5} {'종목코드':<10} {'종목명':<20} {'점수':<10} {'종가':<10}")
    print("-" * 100)

    for idx, row in enumerate(done, 1):
        code, code_name, score, close = row
        print(f"{idx:<5} {code:<10} {code_name:<20} {score:<10.2f} {close:<10}")
else:
    print("\n매수 시도 완료된 종목이 없습니다.")

# 4. 점수 분포 통계
print("\n" + "=" * 100)
print("점수 분포 통계")
print("=" * 100)

sql_stats = """
SELECT
    MIN(composite_score) as min_score,
    MAX(composite_score) as max_score,
    AVG(composite_score) as avg_score,
    COUNT(*) as total_count
FROM realtime_daily_buy_list
"""

stats = engine.execute(sql_stats).fetchone()

# 데이터가 없을 때 처리
if stats and stats[3] and stats[3] > 0:
    print(f"\n최저 점수: {stats[0]:.2f}")
    print(f"최고 점수: {stats[1]:.2f}")
    print(f"평균 점수: {stats[2]:.2f}")
    print(f"전체 종목: {stats[3]}개")
else:
    # collector 실행 여부는 daily_buy_list의 오늘 날짜 테이블로 확인
    today = datetime.datetime.now().strftime("%Y%m%d")

    # daily_buy_list 데이터베이스에 오늘 날짜 테이블이 있는지 확인
    sql_check_daily_table = f"""
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = 'daily_buy_list'
    AND TABLE_NAME = '{today}'
    """
    today_table_exists = engine_daily.execute(sql_check_daily_table).fetchone()[0]

    if today_table_exists > 0:
        # collector는 돌았지만 90점 이상이 없는 경우
        print("\n✅ collector_v3.py 실행 완료")
        print(f"❌ 오늘({today}) 90점 이상 종목이 없습니다.")
        print("💡 시장 상황이 좋지 않아 매수 조건을 만족하는 종목이 없습니다.")
        print("   아래 '전체 시장 상위 20개' 섹션에서 90점 미만 종목을 확인하세요.")
    else:
        # collector가 안 돌아간 경우 - 최신 데이터 날짜 확인 (daily_buy_list에서)
        sql_latest_table = """
        SELECT TABLE_NAME
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = 'daily_buy_list'
        AND TABLE_NAME REGEXP '^[0-9]{8}$'
        ORDER BY TABLE_NAME DESC
        LIMIT 1
        """
        latest_table = engine_daily.execute(sql_latest_table).fetchone()

        print(f"\n❌ collector_v3.py가 실행되지 않았습니다. (오늘 날짜: {today})")
        if latest_table and latest_table[0]:
            print(f"📅 가장 최근 데이터: {latest_table[0]}")
        else:
            print("📅 데이터베이스가 비어있습니다.")
        print("💡 collector_v3.py를 먼저 실행하여 매수 후보를 생성하세요.")

# 5. 전체 시장에서 종합 스코어 상위 20개 종목 (90점 미만 포함)
print("\n" + "=" * 100)
print("전체 시장 종합 스코어 상위 20개 종목 (매수 커트라인 무시)")
print("=" * 100)

# 오늘 날짜 테이블명 구하기
today_table = datetime.datetime.now().strftime("%Y%m%d")

# 테이블이 존재하는지 확인
check_table_sql = f"""
SELECT COUNT(*)
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'daily_buy_list'
AND TABLE_NAME = '{today_table}'
"""

table_exists = engine_daily.execute(check_table_sql).fetchone()[0]

if table_exists > 0:
    # Hybrid 전략 점수 계산 (collector_v3.py와 동일)
    sql_top20_all = f"""
    SELECT
        code,
        code_name,
        close,
        d1_diff_rate,
        volume,
        vol5,
        vol20,
        clo5,
        clo10,
        clo20,
        clo60,
        rsi14,

        (
            -- 모멘텀 (60점 만점)
            CASE
                WHEN volume > vol20 * 2.0 THEN 20
                WHEN volume > vol20 * 1.5 THEN 15
                WHEN volume > vol20 * 1.2 THEN 10
                ELSE 5
            END +
            CASE
                WHEN clo5 > clo20 AND clo20 > clo60 THEN 20
                WHEN clo5 > clo20 THEN 15
                ELSE 5
            END +
            CASE
                WHEN atr14 > 0 AND (high - low) > atr14 * 1.5 THEN 20
                WHEN atr14 > 0 AND (high - low) > atr14 THEN 15
                ELSE 10
            END +
            -- 평균회귀 (40점 만점)
            CASE
                WHEN rsi14 <= 30 THEN 15
                WHEN rsi14 <= 40 THEN 10
                WHEN rsi14 <= 50 THEN 5
                ELSE 0
            END +
            CASE
                WHEN bb_lower > 0 AND close <= bb_lower THEN 15
                WHEN bb_lower > 0 AND close <= bb_lower * 1.02 THEN 10
                WHEN bb_middle > 0 AND close < bb_middle THEN 5
                ELSE 0
            END +
            CASE
                WHEN close > clo20 * 0.95 AND close < clo20 * 1.0 THEN 10
                WHEN close > clo60 * 0.95 AND close < clo60 * 1.0 THEN 8
                ELSE 3
            END
        ) as composite_score,

        CASE
            WHEN rsi14 <= 30 AND bb_lower > 0 AND close <= bb_lower * 1.02 THEN 'mean_reversion'
            WHEN volume > vol20 * 1.5 AND clo5 > clo20 THEN 'momentum_breakout'
            ELSE 'hybrid'
        END as strategy_type

    FROM `{today_table}`
    WHERE close > 0
        AND volume > 0
        AND rsi14 > 0
        AND bb_lower > 0
        AND close BETWEEN 1000 AND 500000
    ORDER BY composite_score DESC
    LIMIT 20
    """

    top20_all = engine_daily.execute(text(sql_top20_all)).fetchall()

    if len(top20_all) > 0:
        print(f"\n상위 {len(top20_all)}개 종목 (날짜: {today_table}):")
        print("-" * 100)

        for idx, row in enumerate(top20_all, 1):
            code, code_name, close, d1_diff, vol, vol5, vol20, clo5, clo10, clo20, clo60, rsi, score, strategy = row

            # 매수 리스트 포함 여부 확인
            in_buy_list = "✅" if score >= 90.0 else "  "

            # 첫 번째 줄: 기본 정보
            print(f"\n[{idx:2d}] {in_buy_list} {code} {code_name:<20} | Score: {score:>5.1f} | RSI: {rsi:>5.1f} | Strategy: {strategy}")

            # 두 번째 줄: 가격 및 거래량 정보
            vol_ratio_5 = (vol / vol5 * 100) if vol5 > 0 else 0
            vol_ratio_20 = (vol / vol20 * 100) if vol20 > 0 else 0
            print(f"     종가: {close:>8,.0f}원 | 전일비: {d1_diff:>+6.2f}% | 거래량: {vol:>12,} (5일평균 대비 {vol_ratio_5:>5.1f}%, 20일평균 대비 {vol_ratio_20:>5.1f}%)")

            # 세 번째 줄: 이동평균선 정보
            print(f"     이평선: 5일 {clo5:>8,.0f} | 10일 {clo10:>8,.0f} | 20일 {clo20:>8,.0f} | 60일 {clo60:>8,.0f}")

        print("\n" + "=" * 100)
        print(f"평균 점수: {sum([r[12] for r in top20_all]) / len(top20_all):.2f}")
        print(f"점수 범위: {top20_all[-1][12]:.2f} ~ {top20_all[0][12]:.2f}")
        print(f"매수 커트라인(90점) 이상: {sum([1 for r in top20_all if r[12] >= 90.0])}개 / {len(top20_all)}개")
        print("=" * 100)
    else:
        print(f"\n❌ {today_table} 테이블에 데이터가 없습니다.")
else:
    print(f"\n❌ {today_table} 테이블이 존재하지 않습니다.")
    print("💡 collector_v3.py를 먼저 실행하세요.")

print("\n" + "=" * 100)

engine.dispose()
engine_daily.dispose()
