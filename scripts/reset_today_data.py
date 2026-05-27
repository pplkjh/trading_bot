# -*- coding: utf-8 -*-
"""
오늘 날짜 수집 데이터 강제 리셋 유틸리티

사용 목적:
- 장중에 수집한 데이터를 삭제하고 종가로 재수집하고 싶을 때
- 데이터 수집 중 오류가 발생하여 처음부터 다시 수집하고 싶을 때

실행 방법:
    python reset_today_data.py

주의사항:
- 이 프로그램은 오늘 날짜의 모든 수집 데이터를 삭제합니다
- 실행 후 collector_v3.py를 다시 실행하면 처음부터 재수집됩니다
"""

import sys
import datetime
import pymysql
from sqlalchemy import create_engine
from library import cf
from library.utils import get_latest_complete_date

# Windows 콘솔 UTF-8 인코딩 설정
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


class TodayDataResetter:
    def __init__(self):
        """데이터베이스 연결 초기화"""
        self.today = datetime.datetime.today().strftime("%Y%m%d")
        self.target_date = get_latest_complete_date()  # daily_buy_list 테이블 기준 날짜

        # 데이터베이스 연결 (pymysql 사용)
        db_url_base = f"mysql+pymysql://{cf.db_id}:{cf.db_passwd}@{cf.db_ip}:{cf.db_port}"

        self.engine_JB = create_engine(
            f"{db_url_base}/jackbot1_imi1",
            encoding='utf-8'
        )
        self.engine_daily_craw = create_engine(
            f"{db_url_base}/daily_craw",
            encoding='utf-8'
        )
        self.engine_daily_buy_list = create_engine(
            f"{db_url_base}/daily_buy_list",
            encoding='utf-8'
        )

    def check_today_data(self):
        """오늘 날짜 수집 데이터 확인"""
        print(f"\n{'='*70}")
        print(f"📊 오늘({self.today}) 수집 데이터 확인")
        print(f"{'='*70}\n")

        # 1. setting_data 확인
        sql = "SELECT daily_crawler, daily_buy_list FROM setting_data LIMIT 1"
        result = self.engine_JB.execute(sql).fetchone()

        print("1️⃣  Setting 상태:")
        if result:
            daily_crawler = result[0] or 'None'
            daily_buy_list = result[1] or 'None'
            print(f"   - daily_crawler: {daily_crawler}")
            print(f"   - daily_buy_list: {daily_buy_list}")
        else:
            print("   - 데이터 없음")

        # 2. daily_buy_list 테이블 확인
        sql = f"""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'daily_buy_list' AND table_name = '{self.target_date}'
        """
        result = self.engine_daily_buy_list.execute(sql).fetchone()

        print(f"\n2️⃣  daily_buy_list.{self.target_date} 테이블 (기준날짜):")
        if result:
            sql_count = f"SELECT COUNT(*) FROM `{self.target_date}`"
            count = self.engine_daily_buy_list.execute(sql_count).fetchone()[0]
            print(f"   - 존재함 ({count}개 종목)")
        else:
            print(f"   - 존재하지 않음")

        # 3. daily_craw 오늘 날짜 데이터 확인
        sql = """
            SELECT code_name FROM stock_item_all
            WHERE check_daily_crawler IN (1, 3)
            LIMIT 10
        """
        results = self.engine_daily_buy_list.execute(sql).fetchall()

        print(f"\n3️⃣  daily_craw 종목별 테이블 (샘플 10개):")
        if results:
            print(f"   - 수집 완료된 종목 수: {len(results)}개")
            for row in results[:5]:
                # 각 종목 테이블에서 오늘 날짜 데이터 확인
                try:
                    sql_check = f"SELECT 1 FROM `{row[0]}` WHERE date = '{self.today}' LIMIT 1"
                    has_today = self.engine_daily_craw.execute(sql_check).fetchone()
                    if has_today:
                        print(f"     ✓ {row[0]}: 오늘 데이터 있음")
                except:
                    pass
        else:
            print(f"   - 수집된 데이터 없음")

        print(f"\n{'='*70}\n")

    def reset_today_data(self):
        """오늘 날짜 데이터 강제 리셋"""
        print(f"🔄 오늘({self.today}) 데이터 리셋 시작...\n")

        # 1. daily_buy_list 테이블 삭제
        print(f"1️⃣  daily_buy_list.{self.target_date} 테이블 삭제 중...")
        try:
            sql = f"DROP TABLE IF EXISTS `{self.target_date}`"
            self.engine_daily_buy_list.execute(sql)
            print("   ✅ 완료")
        except Exception as e:
            print(f"   ⚠️  오류: {e}")

        # 2. daily_craw 종목별 오늘 날짜 데이터 삭제
        print("\n2️⃣  daily_craw 오늘 날짜 데이터 삭제 중...")

        # 모든 종목 리스트 가져오기
        sql = "SELECT code_name FROM stock_item_all"
        stock_list = self.engine_daily_buy_list.execute(sql).fetchall()

        deleted_count = 0
        error_count = 0

        for i, row in enumerate(stock_list):
            code_name = row[0]

            # 진행률 표시
            if (i + 1) % 100 == 0:
                print(f"   진행 중: {i+1}/{len(stock_list)}개", end='\r')

            try:
                # 테이블이 존재하는지 확인
                sql_check = f"""
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'daily_craw' AND table_name = '{code_name}'
                """
                if self.engine_daily_craw.execute(sql_check).fetchone():
                    # 오늘 날짜 row 삭제
                    sql_delete = f"DELETE FROM `{code_name}` WHERE date = '{self.today}'"
                    result = self.engine_daily_craw.execute(sql_delete)
                    if result.rowcount > 0:
                        deleted_count += 1
            except Exception as e:
                error_count += 1
                if error_count <= 5:  # 처음 5개 오류만 출력
                    print(f"\n   ⚠️  {code_name} 오류: {e}")

        print(f"\n   ✅ 완료 ({deleted_count}개 종목에서 데이터 삭제, {error_count}개 오류)")

        # 3. check_daily_crawler 리셋
        print("\n3️⃣  check_daily_crawler 리셋 중...")
        try:
            sql = "UPDATE stock_item_all SET check_daily_crawler = 0 WHERE check_daily_crawler = 1"
            result = self.engine_daily_buy_list.execute(sql)
            print(f"   ✅ 완료 ({result.rowcount}개 종목)")
        except Exception as e:
            print(f"   ⚠️  오류: {e}")

        # 4. realtime_daily_buy_list 테이블 삭제 (jackbot1_imi1)
        print("\n4️⃣  realtime_daily_buy_list 테이블 삭제 중...")
        try:
            sql = "DROP TABLE IF EXISTS realtime_daily_buy_list"
            self.engine_JB.execute(sql)
            print("   ✅ 완료")
        except Exception as e:
            print(f"   ⚠️  오류: {e}")

        # 5. setting_data 리셋
        print("\n5️⃣  setting_data 플래그 리셋 중...")
        try:
            sql = """
                UPDATE setting_data
                SET daily_crawler = '0', daily_buy_list = '0', today_buy_list = '0'
                WHERE 1=1
            """
            self.engine_JB.execute(sql)
            print("   ✅ 완료")
        except Exception as e:
            print(f"   ⚠️  오류: {e}")

        print(f"\n{'='*70}")
        print("✅ 오늘 데이터 리셋 완료!")
        print(f"{'='*70}")
        print("\n💡 이제 collector_v3.py를 실행하면 처음부터 재수집됩니다.\n")


def main():
    print("\n" + "="*70)
    print("🔄 오늘 날짜 수집 데이터 강제 리셋 유틸리티")
    print("="*70)

    try:
        resetter = TodayDataResetter()

        # 현재 상태 확인
        resetter.check_today_data()

        # 사용자 확인
        print("⚠️  경고: 오늘 날짜의 모든 수집 데이터가 삭제됩니다!")
        print("   이 작업은 되돌릴 수 없습니다.\n")

        response = input("계속 진행하시겠습니까? (y/n): ").lower().strip()

        if response == 'y':
            print()
            resetter.reset_today_data()
        else:
            print("\n❌ 작업이 취소되었습니다.\n")
            return

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return

    # 종료 대기
    print("\n종료하려면 아무 키나 누르세요...")
    input()


if __name__ == "__main__":
    main()
