"""
Phase 1 완료 후 Phase 3 재실행 강제용 스크립트.
today_buy_list 를 NULL 로 초기화 → check_collector_done.py --phase 3 이 FAIL 반환
→ collector_auto_restart.bat 이 Phase 3 을 반드시 재실행함.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from library.cf import db_id, db_passwd, db_ip, db_port, imi1_db_name
import pymysql

con = pymysql.connect(
    user=db_id, passwd=db_passwd, host=db_ip,
    port=int(db_port), db=imi1_db_name, charset='utf8'
)
cur = con.cursor()
cur.execute("UPDATE setting_data SET today_buy_list = NULL")
con.commit()
con.close()
print("[reset_flag] today_buy_list 초기화 완료 - Phase 3 재스코어링 대기")
