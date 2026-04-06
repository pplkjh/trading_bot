"""
collector_v3.py 완료 여부 확인 스크립트
배치파일에서 호출: python batch/check_collector_done.py
exit code: 0 = 완료, 1 = 미완료
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from library.cf import db_id, db_passwd, db_ip, db_port, imi1_db_name, v2_fundamental_collect_interval
import pymysql
from datetime import datetime, timedelta

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

    # 1. 스코어링 완료 여부 확인
    cursor.execute("SELECT today_buy_list FROM setting_data LIMIT 1")
    row = cursor.fetchone()
    con.close()

    if not (row and row[0] and str(row[0])[:8] == today):
        val = row[0] if row else 'None'
        print(f"[FAIL] 오늘({today}) 스코어링 미완료 (today_buy_list={val})")
        sys.exit(1)

    print(f"[OK] 스코어링 완료 (today_buy_list={row[0]})")

    # 2. 펀더멘탈 수집 완료 여부 확인
    # v2_fundamental_collect_interval일 주기인데 마지막 수집이 오래됐으면 오늘 완료했는지 체크
    try:
        import pymysql as _pm
        con2 = _pm.connect(
            user=db_id, passwd=db_passwd, host=db_ip,
            port=int(db_port), db='daily_buy_list', charset='utf8'
        )
        cursor2 = con2.cursor()
        cursor2.execute(
            "SELECT updated_date FROM stock_fundamental ORDER BY updated_date DESC LIMIT 1"
        )
        fund_row = cursor2.fetchone()

        if fund_row:
            last_date_str = str(fund_row[0])[:8]
            last_dt = datetime.strptime(last_date_str, "%Y%m%d")
            today_dt = datetime.strptime(today, "%Y%m%d")
            days_since = (today_dt - last_dt).days

            if days_since >= v2_fundamental_collect_interval:
                # 펀더멘탈 수집이 필요한 주기인데 오늘 완료 안 됨
                con2.close()
                print(f"[FAIL] 펀더멘탈 수집 필요 (마지막 수집: {last_date_str}, {days_since}일 경과)")
                sys.exit(1)
            elif last_date_str == today:
                # 오늘 데이터가 있지만 체크포인트(부분 저장)일 수 있으므로 건수 검증
                cursor2.execute("SELECT COUNT(*) FROM stock_fundamental WHERE updated_date = %s", (today,))
                today_count = cursor2.fetchone()[0]
                cursor2.execute("SELECT COUNT(*) FROM stock_item_all")
                total_count = cursor2.fetchone()[0]
                con2.close()
                if total_count > 0 and today_count < total_count * 0.95:
                    print(f"[FAIL] 펀더멘탈 수집 미완료 (오늘 저장: {today_count}/{total_count}, 체크포인트 상태)")
                    sys.exit(1)
                print(f"[OK] 펀더멘탈 수집 완료 ({today_count}/{total_count})")
            else:
                con2.close()
                print(f"[OK] 펀더멘탈 수집 불필요 (마지막 수집: {last_date_str}, {days_since}일 경과 < {v2_fundamental_collect_interval}일)")
        else:
            con2.close()
            # stock_fundamental 테이블이 비어있음 → 수집 필요
            print(f"[FAIL] 펀더멘탈 데이터 없음 (stock_fundamental 비어있음)")
            sys.exit(1)

    except Exception as e:
        # 펀더멘탈 체크 실패 시 스코어링 완료만으로 진행 허용
        print(f"[WARN] 펀더멘탈 체크 실패 (무시하고 진행): {e}")

    print(f"[OK] 모든 수집 완료 확인")
    sys.exit(0)

except Exception as e:
    print(f"[ERROR] DB 연결 실패: {e}")
    sys.exit(1)
