#!/usr/bin/env python3
"""stock_item_all 테이블 생성 스크립트"""

import pymysql

# DB 연결 설정
db_config = {
    'host': 'localhost',
    'user': 'bot',
    'password': 'bot1234',
    'db': 'daily_buy_list',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

# 테이블 생성 SQL
create_table_sql = """
CREATE TABLE IF NOT EXISTS stock_item_all (
    code VARCHAR(10) PRIMARY KEY COMMENT '종목코드 (6자리)',
    code_name VARCHAR(100) NOT NULL COMMENT '종목명',
    check_item TINYINT DEFAULT 0 COMMENT '활성 종목 여부 (0:비활성, 1:활성)',
    check_daily_crawler TINYINT DEFAULT 0 COMMENT '일봉 수집 상태 (0:미수집, 1:완료, 3:과거완료, 4:업데이트필요)',
    check_min_crawler TINYINT DEFAULT 0 COMMENT '분봉 수집 상태 (0:미수집, 1:완료)',

    market VARCHAR(10) COMMENT '시장 구분 (KOSPI, KOSDAQ, KONEX, ETF)',
    sector VARCHAR(50) COMMENT '업종',

    is_managing TINYINT DEFAULT 0 COMMENT '관리종목 여부',
    is_insincerity TINYINT DEFAULT 0 COMMENT '불성실법인종목 여부',
    is_suspended TINYINT DEFAULT 0 COMMENT '거래정지 여부',

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '생성일시',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정일시',

    INDEX idx_check_item (check_item),
    INDEX idx_market (market),
    INDEX idx_check_daily (check_daily_crawler),
    INDEX idx_check_min (check_min_crawler)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='전체 종목 리스트 및 수집 상태 관리'
"""

try:
    # DB 연결
    print("📡 데이터베이스 연결 중...")
    connection = pymysql.connect(**db_config)

    with connection.cursor() as cursor:
        # 테이블 생성
        print("📝 stock_item_all 테이블 생성 중...")
        cursor.execute(create_table_sql)
        connection.commit()
        print("✅ stock_item_all 테이블 생성 완료!")

        # 테이블 확인
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print("\n📋 현재 테이블 목록:")
        for table in tables:
            print(f"  - {list(table.values())[0]}")

        # 테이블 구조 확인
        cursor.execute("DESC stock_item_all")
        columns = cursor.fetchall()
        print("\n🔍 stock_item_all 테이블 구조:")
        for col in columns:
            print(f"  {col['Field']:20s} {col['Type']:20s} {col['Null']:5s} {col['Key']:3s}")

    print("\n" + "="*80)
    print("참고: collector_v3.py 실행 시 종목 데이터가 자동으로 입력됩니다.")
    print("현재는 빈 테이블이므로 매수 후보가 없습니다.")
    print("="*80)

except Exception as e:
    print(f"❌ 에러 발생: {e}")
    import traceback
    traceback.print_exc()
finally:
    if 'connection' in locals():
        connection.close()
        print("\n✅ 연결 종료")
