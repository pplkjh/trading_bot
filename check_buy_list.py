"""
realtime_daily_buy_list 확인 스크립트
매수 후보가 있는지 빠르게 확인
"""
import pymysql
import pandas as pd
from library.cf import *

try:
    # JackBot DB 연결
    con = pymysql.connect(
        user=db_id,
        passwd=db_passwd,
        host=db_ip,
        db=imi1_db_name,
        charset='utf8',
        port=int(db_port)
    )

    print("\n" + "="*80)
    print(f"🔍 매수 후보 리스트 확인 (DB: {imi1_db_name})")
    print("="*80)

    # 데이터 개수 확인
    query_count = "SELECT COUNT(*) as total FROM realtime_daily_buy_list"
    df_count = pd.read_sql(query_count, con)
    total = df_count.iloc[0]['total']

    print(f"\n📊 총 매수 후보 수: {total}개\n")

    if total > 0:
        # 실제 데이터 조회
        query_data = "SELECT * FROM realtime_daily_buy_list LIMIT 20"
        df_data = pd.read_sql(query_data, con)

        print("📋 매수 후보 목록 (최대 20개):")
        print("-"*80)

        # 컬럼 확인
        cols = df_data.columns.tolist()
        print(f"컬럼: {', '.join(cols)}\n")

        # D1 기준 정렬 (있는 경우)
        if 'd1' in cols:
            df_data = df_data.sort_values('d1', ascending=False)

        # 데이터 출력
        for idx, row in df_data.iterrows():
            print(f"[{idx+1}] 종목코드: {row.get('code', 'N/A'):<10} "
                  f"종목명: {row.get('code_name', 'N/A'):<20} ", end='')

            if 'close' in cols and pd.notna(row.get('close')):
                print(f"현재가: {int(row['close']):>10,}원 ", end='')
            if 'd1' in cols and pd.notna(row.get('d1')):
                print(f"D1: {row['d1']:>6.2f} ", end='')
            if 'd2' in cols and pd.notna(row.get('d2')):
                print(f"D2: {row['d2']:>6.2f} ", end='')
            if 'check_item' in cols and pd.notna(row.get('check_item')):
                print(f"전략: {str(row['check_item'])[:15]}", end='')

            print()
    else:
        print("❌ 매수 후보가 없습니다!")
        print("\n💡 해결 방법:")
        print("  1. collector_v3.py를 실행하여 데이터를 수집하세요")
        print("  2. Collector가 매수 조건을 만족하는 종목을 찾아야 합니다")

    con.close()
    print("\n" + "="*80)

except Exception as e:
    print(f"\n❌ 오류 발생: {e}")
    import traceback
    traceback.print_exc()
