from library import cf
import pymysql

conn = pymysql.connect(host=cf.db_ip, port=int(cf.db_port), user=cf.db_id, password=cf.db_passwd, db='daily_craw', charset='utf8')
cur = conn.cursor()

# 선광 2023-04-17 ~ 2023-04-25 가격 확인
print("=== 선광 2023-04-17 ~ 2023-04-25 ===")
cur.execute("SELECT date, open, close, low, high FROM `선광` WHERE date BETWEEN 20230417 AND 20230425 ORDER BY date")
rows = cur.fetchall()
for r in rows:
    print(r)

# 매수가 추정: 2023-04-17 open
# rate 계산: (open_today / open_20230417 - 1) * 100
if rows:
    buy_open = rows[0][1]
    print(f"\n매수 추정가 (2023-04-17 open): {buy_open}")
    print("\n날짜별 누적 수익률 (매수가 기준):")
    for r in rows:
        date, open_, close, low, high = r
        rate = (open_ / buy_open - 1) * 100
        rate_close = (close / buy_open - 1) * 100
        print(f"  {date}: open={open_:,} ({rate:+.2f}%) | close={close:,} ({rate_close:+.2f}%)")

conn.close()

# daily_buy_list에도 있는지 확인
conn2 = pymysql.connect(host=cf.db_ip, port=int(cf.db_port), user=cf.db_id, password=cf.db_passwd, db='daily_buy_list', charset='utf8')
cur2 = conn2.cursor()
print("\n=== daily_buy_list 날짜 테이블에 선광 존재 여부 ===")
for date in ['20230417', '20230418', '20230419', '20230420', '20230421', '20230424', '20230425']:
    try:
        cur2.execute(f"SELECT code_name, close, open FROM `{date}` WHERE code_name = '선광'")
        r = cur2.fetchall()
        print(f"  {date}: {'있음 ' + str(r) if r else '없음'}")
    except Exception as e:
        print(f"  {date}: 테이블 없음 ({e})")
conn2.close()
