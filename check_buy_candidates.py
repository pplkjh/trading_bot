from sqlalchemy import create_engine, text
import pymysql
import datetime
from library.cf import db_id, db_passwd, db_ip, db_port, imi1_db_name, v2_min_score
from library.utils import get_latest_complete_date
pymysql.install_as_MySQLdb()

_url = f'mysql+mysqldb://{db_id}:{db_passwd}@{db_ip}:{db_port}'
engine = create_engine(f'{_url}/{imi1_db_name}', encoding='utf-8')
engine_daily = create_engine(f'{_url}/daily_buy_list', encoding='utf-8')

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

# 3. 전체 시장 상위 20개 (collector가 저장한 200pt 실제 점수)
print("\n" + "=" * 100)
print(f"전체 시장 상위 20개 (collector 200pt 실제 점수, realtime_daily_buy_list 기준)")
print("=" * 100)

latest_table_row = engine_daily.execute("""
    SELECT TABLE_NAME FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = 'daily_buy_list' AND TABLE_NAME REGEXP '^[0-9]{8}$'
    ORDER BY TABLE_NAME DESC LIMIT 1
""").fetchone()
latest_table = latest_table_row[0] if latest_table_row else None

top20_rows = engine.execute(f"""
    SELECT r.code, r.code_name, r.composite_score, r.check_item,
           d.close, d.volume, d.vol20, d.clo5, d.clo20, d.clo60,
           d.rsi14, d.adx, d.cmf20, d.d1_diff_rate
    FROM realtime_daily_buy_list r
    LEFT JOIN daily_buy_list.`{latest_table}` d ON r.code = d.code
    ORDER BY r.composite_score DESC
    LIMIT 20
""").fetchall() if latest_table else []

if top20_rows:
    print(f"\n상위 {len(top20_rows)}개 종목 (날짜: {latest_table}, 200pt 만점)")
    print("-" * 100)
    for idx, row in enumerate(top20_rows, 1):
        code, code_name, score, check_item = row[0], row[1], row[2], row[3]
        close   = row[4] or 0
        vol     = row[5] or 0
        vol20   = row[6] or 0
        clo5    = row[7] or 0
        clo20   = row[8] or 0
        clo60   = row[9] or 0
        rsi     = row[10] or 0
        adx     = row[11] or 0
        cmf     = row[12] or 0
        d1_diff = row[13] or 0

        flag      = "✅" if float(score) >= v2_min_score else "  "
        status    = "완료" if check_item == 1 else "대기"
        vol_ratio = (vol / vol20 * 100) if vol20 > 0 else 0

        print(f"\n[{idx:2d}] {flag} {code} {code_name:<20} | 점수: {float(score):>6.1f}/200 ({status}) | RSI: {float(rsi):>5.1f} | ADX: {float(adx):>5.1f} | CMF: {float(cmf):>+5.2f}")
        print(f"     종가: {close:>8,.0f}원 | 전일비: {float(d1_diff):>+6.2f}% | 거래량비율: {vol_ratio:>5.1f}%")
        print(f"     이평: 5일 {clo5:>8,.0f} | 20일 {clo20:>8,.0f} | 60일 {clo60:>8,.0f}")

    print("\n" + "=" * 100)
    scores = [float(r[2]) for r in top20_rows]
    print(f"범위: {min(scores):.1f} ~ {max(scores):.1f} | 평균: {sum(scores)/len(scores):.1f}")
    print(f"커트라인({v2_min_score}점) 이상: {sum(1 for s in scores if s >= v2_min_score)}개 / {len(scores)}개")
    print("=" * 100)
else:
    print(f"\n❌ realtime_daily_buy_list가 비어있습니다. collector_v3.py를 먼저 실행하세요.")

engine.dispose()
engine_daily.dispose()
