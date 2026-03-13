"""
collector_v3.py 스코어링 완료 여부 확인 스크립트
배치파일에서 호출: python batch/check_collector_done.py
exit code: 0 = 완료, 1 = 미완료
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from library.cf import db_id, db_passwd, db_ip, db_port, imi1_db_name
import pymysql
from datetime import datetime

today = datetime.now().strftime("%Y%m%d")

try:
    con = pymysql.connect(
        user=db_id,
        passwd=db_passwd,
        host=db_ip,
        port=int(db_port),
        db=imi1_db_name,
        charset='utf8'
    )
    cursor = con.cursor()
    cursor.execute("SELECT today_buy_list FROM setting_data LIMIT 1")
    row = cursor.fetchone()
    con.close()

    if row and row[0] and str(row[0])[:8] == today:
        print(f"[OK] 오늘({today}) collector 스코어링 완료 (today_buy_list={row[0]})")
        sys.exit(0)
    else:
        val = row[0] if row else 'None'
        print(f"[FAIL] 오늘({today}) collector 스코어링 미완료 (today_buy_list={val})")
        sys.exit(1)

except Exception as e:
    print(f"[ERROR] DB 연결 실패: {e}")
    sys.exit(1)
