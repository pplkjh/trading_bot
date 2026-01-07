from sqlalchemy import create_engine
import pymysql
pymysql.install_as_MySQLdb()

engine = create_engine('mysql+mysqldb://bot:qwer1232@localhost:3306/jackbot1_imi1', encoding='utf-8')

print("=" * 100)
print("매수 후보 리스트 (realtime_daily_buy_list)")
print("=" * 100)

# 1. 전체 매수 후보 확인 (점수순 정렬)
sql = """
SELECT code, code_name, composite_score, check_item, close, strategy_type
FROM realtime_daily_buy_list
ORDER BY composite_score DESC, code
"""

result = engine.execute(sql).fetchall()

print(f"\n총 {len(result)}개 종목")
print("-" * 100)
print(f"{'순위':<5} {'종목코드':<10} {'종목명':<20} {'점수':<10} {'매수상태':<10} {'종가':<10} {'전략':<15}")
print("-" * 100)

for idx, row in enumerate(result, 1):
    code, code_name, score, check_item, close, strategy = row
    status = "완료" if check_item == 1 else "대기"
    print(f"{idx:<5} {code:<10} {code_name:<20} {score:<10.2f} {status:<10} {close:<10} {strategy:<15}")

# 2. 매수 대기 중인 종목만 표시
print("\n" + "=" * 100)
print("매수 대기 중인 종목 (check_item = 0)")
print("=" * 100)

sql_pending = """
SELECT code, code_name, composite_score, close, strategy_type
FROM realtime_daily_buy_list
WHERE check_item = 0
ORDER BY composite_score DESC, code
"""

pending = engine.execute(sql_pending).fetchall()

if len(pending) > 0:
    print(f"\n총 {len(pending)}개 종목 매수 대기 중")
    print("-" * 100)
    print(f"{'순위':<5} {'종목코드':<10} {'종목명':<20} {'점수':<10} {'종가':<10} {'전략':<15}")
    print("-" * 100)

    for idx, row in enumerate(pending, 1):
        code, code_name, score, close, strategy = row
        print(f"{idx:<5} {code:<10} {code_name:<20} {score:<10.2f} {close:<10} {strategy:<15}")
else:
    print("\n매수 대기 중인 종목이 없습니다.")

# 3. 매수 완료된 종목
print("\n" + "=" * 100)
print("매수 시도 완료 종목 (check_item = 1)")
print("=" * 100)

sql_done = """
SELECT code, code_name, composite_score, close, strategy_type
FROM realtime_daily_buy_list
WHERE check_item = 1
ORDER BY composite_score DESC, code
"""

done = engine.execute(sql_done).fetchall()

if len(done) > 0:
    print(f"\n총 {len(done)}개 종목 매수 시도 완료")
    print("-" * 100)
    print(f"{'순위':<5} {'종목코드':<10} {'종목명':<20} {'점수':<10} {'종가':<10} {'전략':<15}")
    print("-" * 100)

    for idx, row in enumerate(done, 1):
        code, code_name, score, close, strategy = row
        print(f"{idx:<5} {code:<10} {code_name:<20} {score:<10.2f} {close:<10} {strategy:<15}")
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
    print("\n매수 후보가 없습니다.")
    print("💡 collector_v3.py를 실행하여 매수 후보를 생성하거나,")
    print("   오늘 시장에서 90점 이상의 종목이 없을 수 있습니다.")

print("\n" + "=" * 100)

engine.dispose()
