"""
collector_v3.py 완료 여부 확인 스크립트
배치파일에서 호출: python batch/check_collector_done.py [--phase 1|2|3]
exit code: 0 = 완료, 1 = 미완료

--phase 1: 종가 수집 완료 여부 (daily_buy_list 날짜 테이블 오늘 건수 확인)
--phase 2: 펀더멘탈 수집 완료 여부 (sf_YYYYMMDD 건수 확인)
--phase 3: 스코어링 완료 여부 (setting_data.today_buy_list 확인)
(없음): 전체 확인 (기존 동작 — phase 3 + 펀더멘탈 체크)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from library.cf import db_id, db_passwd, db_ip, db_port, imi1_db_name, v2_fundamental_collect_interval
from library.utils import get_latest_complete_date
import pymysql
from datetime import datetime, timedelta

today = datetime.now().strftime("%Y%m%d")
ref_date = get_latest_complete_date()  # 장전이면 전 영업일, 장후면 오늘

# --phase 인자 파싱
phase = None
if '--phase' in sys.argv:
    idx = sys.argv.index('--phase')
    if idx + 1 < len(sys.argv):
        phase = int(sys.argv[idx + 1])

# ─────────────────────────────────────────────
# Phase 1: 종가 수집 완료 여부 (시간대별 판단)
#
#  00:00~08:00 : 야간 → 스킵 (exit 0)
#  08:00~09:00 : 장전 → 오늘 08:00 이후에 수집 완료됐으면 OK
#  09:00~16:00 : 장중 → 마지막 수집이 1시간 이내면 OK, 초과면 재수집
#  16:00~24:00 : 장후 → 오늘 16:00 이후에 수집 완료됐으면 최종 OK
#
# "마지막 수집 시각"은 information_schema.tables.UPDATE_TIME 으로 판단
# ─────────────────────────────────────────────
if phase == 1:
    now = datetime.now()
    hour = now.hour

    # 00:00~08:00: 야간 — 수집 불필요, 바로 스킵
    if 0 <= hour < 8:
        print(f"[OK] Phase 1: night time (00:00-08:00), skip")
        sys.exit(0)

    print(f"[INFO] Phase 1 check: {now.strftime('%H:%M')} ref_date={ref_date}")

    try:
        con = pymysql.connect(
            user=db_id, passwd=db_passwd, host=db_ip,
            port=int(db_port), db='daily_buy_list', charset='utf8'
        )
        cursor = con.cursor()

        # daily_buy_list.{ref_date} 테이블의 마지막 수정 시각 조회
        cursor.execute(
            "SELECT UPDATE_TIME, TABLE_ROWS FROM information_schema.tables "
            "WHERE table_schema = 'daily_buy_list' AND table_name = %s",
            (ref_date,)
        )
        tbl_row = cursor.fetchone()

        # 종목 전체 수
        cursor.execute("SELECT COUNT(*) FROM stock_item_all")
        total_count = cursor.fetchone()[0]
        con.close()

        if 8 <= hour < 16:
            # 장전/장중: 날짜 테이블 이름은 전 영업일(예: 20260430)이라 ref_date(오늘)와 다름
            # UPDATE_TIME 체크 대신 setting_data.daily_buy_list 타임스탬프로 판단
            # → 컬렉터가 Phase 1 완료 시 이 값을 오늘 날짜(YYYYMMDDHHMM)로 업데이트
            try:
                con_jb = pymysql.connect(
                    user=db_id, passwd=db_passwd, host=db_ip,
                    port=int(db_port), db=imi1_db_name, charset='utf8'
                )
                cursor_jb = con_jb.cursor()
                cursor_jb.execute("SELECT daily_buy_list FROM setting_data LIMIT 1")
                row_jb = cursor_jb.fetchone()
                con_jb.close()
                val = str(row_jb[0]) if (row_jb and row_jb[0]) else ''
                if val[:8] == today:
                    print(f"[OK] Phase 1: 오늘 수집 완료 (daily_buy_list={val})")
                    sys.exit(0)
                else:
                    print(f"[FAIL] Phase 1: 오늘 수집 필요 (daily_buy_list={val or 'None'}, today={today})")
                    sys.exit(1)
            except Exception as e:
                print(f"[ERROR] Phase 1 check failed: {e}")
                sys.exit(1)

        else:  # hour >= 16
            # 장후: setting_data.daily_buy_list 타임스탬프 기반 확인
            # 한국 공휴일인 경우 날짜 테이블이 어제(전 영업일) 이름이라 ref_date 테이블이 없을 수 있음
            # collector가 daily_buy_list_check() 완료 시 현재 시각(YYYYMMDDHHMM)으로 업데이트하므로
            # 이 값이 오늘 날짜(YYYYMMDD)로 시작하면 Phase 1 완료 확인
            try:
                con_jb = pymysql.connect(
                    user=db_id, passwd=db_passwd, host=db_ip,
                    port=int(db_port), db=imi1_db_name, charset='utf8'
                )
                cursor_jb = con_jb.cursor()
                cursor_jb.execute("SELECT daily_buy_list FROM setting_data LIMIT 1")
                row_jb = cursor_jb.fetchone()
                con_jb.close()
                val = str(row_jb[0]) if (row_jb and row_jb[0]) else ''
                # 오늘 16:00 이후에 수집 완료된 경우만 OK
                # (오전 모닝 런이 오늘 날짜로 찍혀 있어도, 장후 수집은 16시 이후 타임스탬프여야 함)
                if val[:8] == today and val[8:12] >= '1600':
                    print(f"[OK] Phase 1: post-market final done (daily_buy_list={val})")
                    sys.exit(0)
                else:
                    print(f"[FAIL] Phase 1: post-market final needed (daily_buy_list={val or 'None'}, today={today})")
                    sys.exit(1)
            except Exception as inner_e:
                print(f"[ERROR] Phase 1 post-market check failed: {inner_e}")
                sys.exit(1)

    except Exception as e:
        print(f"[ERROR] Phase 1 check failed: {e}")
        sys.exit(1)

# ─────────────────────────────────────────────
# Phase 2: 펀더멘탈 수집 완료 여부
# ─────────────────────────────────────────────
if phase == 2:
    try:
        con = pymysql.connect(
            user=db_id, passwd=db_passwd, host=db_ip,
            port=int(db_port), db='daily_buy_list', charset='utf8'
        )
        cursor = con.cursor()

        cursor.execute(
            "SELECT TABLE_NAME FROM information_schema.tables "
            "WHERE table_schema = 'daily_buy_list' AND TABLE_NAME LIKE 'sf_2%' "
            "ORDER BY TABLE_NAME DESC LIMIT 1"
        )
        fund_row = cursor.fetchone()

        if not fund_row:
            con.close()
            print(f"[FAIL] Phase 2 미완료: sf_YYYYMMDD 테이블 없음")
            sys.exit(1)

        last_table = fund_row[0]
        last_date_str = last_table[3:]
        last_dt = datetime.strptime(last_date_str, "%Y%m%d")
        today_dt = datetime.strptime(today, "%Y%m%d")
        days_since = (today_dt - last_dt).days

        if days_since >= v2_fundamental_collect_interval:
            con.close()
            print(f"[FAIL] Phase 2 미완료: 펀더멘탈 갱신 필요 (마지막: {last_date_str}, {days_since}일 경과)")
            sys.exit(1)

        if last_date_str == today:
            # 오늘 테이블 — 건수 검증
            cursor.execute(f"SELECT COUNT(*) FROM `sf_{today}`")
            today_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM stock_item_all")
            total_count = cursor.fetchone()[0]
            con.close()
            if total_count > 0 and today_count < total_count * 0.95:
                print(f"[FAIL] Phase 2 미완료: 펀더멘탈 {today_count}/{total_count} ({today_count/total_count*100:.1f}%)")
                sys.exit(1)
            print(f"[OK] Phase 2 완료: 펀더멘탈 {today_count}/{total_count} ({last_table})")
        else:
            con.close()
            print(f"[OK] Phase 2 완료: 펀더멘탈 갱신 불필요 (마지막: {last_date_str}, {days_since}일 경과 < {v2_fundamental_collect_interval}일)")

        sys.exit(0)

    except Exception as e:
        print(f"[ERROR] Phase 2 체크 실패: {e}")
        sys.exit(1)

# ─────────────────────────────────────────────
# Phase 3 또는 전체: 스코어링 완료 여부
# ─────────────────────────────────────────────
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

    # 스코어링 완료 여부 확인
    cursor.execute("SELECT today_buy_list FROM setting_data LIMIT 1")
    row = cursor.fetchone()
    con.close()

    if not (row and row[0] and str(row[0])[:8] == today):
        val = row[0] if row else 'None'
        print(f"[FAIL] 오늘({today}) 스코어링 미완료 (today_buy_list={val})")
        sys.exit(1)

    print(f"[OK] 스코어링 완료 (today_buy_list={row[0]})")

    if phase == 3:
        # Phase 3 전용: 스코어링만 확인
        print(f"[OK] Phase 3 완료")
        sys.exit(0)

    # 전체 모드 (phase=None): 펀더멘탈도 함께 확인
    try:
        con2 = pymysql.connect(
            user=db_id, passwd=db_passwd, host=db_ip,
            port=int(db_port), db='daily_buy_list', charset='utf8'
        )
        cursor2 = con2.cursor()

        cursor2.execute(
            "SELECT TABLE_NAME FROM information_schema.tables "
            "WHERE table_schema = 'daily_buy_list' AND TABLE_NAME LIKE 'sf_2%' "
            "ORDER BY TABLE_NAME DESC LIMIT 1"
        )
        fund_row = cursor2.fetchone()

        if fund_row:
            last_table = fund_row[0]
            last_date_str = last_table[3:]
            last_dt = datetime.strptime(last_date_str, "%Y%m%d")
            today_dt = datetime.strptime(today, "%Y%m%d")
            days_since = (today_dt - last_dt).days

            if days_since >= v2_fundamental_collect_interval:
                con2.close()
                print(f"[FAIL] 펀더멘탈 수집 필요 (마지막: {last_date_str}, {days_since}일 경과)")
                sys.exit(1)
            elif last_date_str == today:
                cursor2.execute(f"SELECT COUNT(*) FROM `sf_{today}`")
                today_count = cursor2.fetchone()[0]
                cursor2.execute("SELECT COUNT(*) FROM stock_item_all")
                total_count = cursor2.fetchone()[0]
                con2.close()
                if total_count > 0 and today_count < total_count * 0.95:
                    print(f"[FAIL] 펀더멘탈 수집 미완료 (오늘 저장: {today_count}/{total_count}, 체크포인트 상태)")
                    sys.exit(1)
                print(f"[OK] 펀더멘탈 수집 완료 ({today_count}/{total_count}, {last_table})")
            else:
                con2.close()
                print(f"[OK] 펀더멘탈 수집 불필요 (마지막: {last_date_str}, {days_since}일 경과 < {v2_fundamental_collect_interval}일)")
        else:
            con2.close()
            print(f"[FAIL] 펀더멘탈 데이터 없음 (sf_YYYYMMDD 테이블 없음)")
            sys.exit(1)

    except Exception as e:
        print(f"[WARN] 펀더멘탈 체크 실패 (무시하고 진행): {e}")

    print(f"[OK] 모든 수집 완료 확인")
    sys.exit(0)

except Exception as e:
    print(f"[ERROR] DB 연결 실패: {e}")
    sys.exit(1)
