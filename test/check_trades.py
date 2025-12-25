"""
거래 내역 확인 스크립트
all_item_db 테이블의 데이터를 확인
"""
import pymysql
import pandas as pd
from library.cf import *

try:
    con = pymysql.connect(
        user=db_id,
        passwd=db_passwd,
        host=db_ip,
        db=imi1_db_name,
        charset='utf8',
        port=int(db_port)
    )

    print("\n" + "="*80)
    print("📊 거래 데이터 확인")
    print("="*80)

    # 1. 전체 거래 수 확인
    query_total = "SELECT COUNT(*) as total FROM all_item_db"
    df_total = pd.read_sql(query_total, con)
    print(f"\n총 거래 데이터: {df_total.iloc[0]['total']}개")

    # 2. 매수 데이터 확인
    query_buy = """
    SELECT COUNT(*) as total
    FROM all_item_db
    WHERE buy_date IS NOT NULL AND buy_date != ''
    """
    df_buy = pd.read_sql(query_buy, con)
    print(f"매수 데이터: {df_buy.iloc[0]['total']}개")

    # 3. 매도 데이터 확인
    query_sell = """
    SELECT COUNT(*) as total
    FROM all_item_db
    WHERE sell_date IS NOT NULL AND sell_date != ''
    """
    df_sell = pd.read_sql(query_sell, con)
    print(f"매도 데이터: {df_sell.iloc[0]['total']}개")

    # 4. 최근 매도 데이터 샘플 (최대 10개)
    query_recent_sell = """
    SELECT code, code_name, buy_date, sell_date, purchase_price, sell_price, sell_rate
    FROM all_item_db
    WHERE sell_date IS NOT NULL AND sell_date != ''
    ORDER BY sell_date DESC
    LIMIT 10
    """
    df_recent = pd.read_sql(query_recent_sell, con)

    if not df_recent.empty:
        print(f"\n최근 매도 내역 (최대 10개):")
        print("-"*80)
        for idx, row in df_recent.iterrows():
            print(f"\n[{idx+1}] {row['code']} - {row['code_name']}")
            print(f"  매수일: {row['buy_date']}")
            print(f"  매도일: {row['sell_date']}")
            print(f"  매수가: {row['purchase_price']:,}원")
            print(f"  매도가: {row['sell_price']:,}원")
            print(f"  수익률: {row['sell_rate']:.2f}%")
    else:
        print("\n매도 완료된 거래가 없습니다.")

    # 5. 최근 7일 매도 데이터 확인
    query_7days = """
    SELECT COUNT(*) as total
    FROM all_item_db
    WHERE sell_date IS NOT NULL
      AND sell_date != ''
      AND sell_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
    """
    df_7days = pd.read_sql(query_7days, con)
    print(f"\n최근 7일 매도 데이터: {df_7days.iloc[0]['total']}개")

    # 6. 날짜 형식 확인
    query_dates = """
    SELECT DISTINCT sell_date
    FROM all_item_db
    WHERE sell_date IS NOT NULL AND sell_date != ''
    ORDER BY sell_date DESC
    LIMIT 5
    """
    df_dates = pd.read_sql(query_dates, con)
    if not df_dates.empty:
        print(f"\n최근 매도 날짜 형식:")
        for date in df_dates['sell_date']:
            print(f"  {date}")

    # 7. CURDATE() 확인
    query_curdate = "SELECT CURDATE() as today"
    df_curdate = pd.read_sql(query_curdate, con)
    print(f"\nMySQL CURDATE(): {df_curdate.iloc[0]['today']}")

    con.close()
    print("\n" + "="*80)

except Exception as e:
    print(f"\n❌ 오류 발생: {e}")
    import traceback
    traceback.print_exc()
