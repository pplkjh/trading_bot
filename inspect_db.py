"""
데이터베이스 구조 및 데이터 현황 조회 스크립트
전체 DB, 테이블, 컬럼, 데이터 개수를 한눈에 확인
실행 시 db_schema.json 파일 자동 생성
"""
import pymysql
import json
from library.cf import *
from datetime import datetime

def get_connection(db_name=None):
    """DB 연결"""
    return pymysql.connect(
        user=db_id,
        passwd=db_passwd,
        host=db_ip,
        db=db_name if db_name else None,
        charset='utf8',
        port=int(db_port)
    )

def get_all_databases():
    """모든 데이터베이스 목록 조회"""
    con = get_connection()
    cursor = con.cursor()
    cursor.execute("SHOW DATABASES")
    databases = [row[0] for row in cursor.fetchall()]
    con.close()

    # 시스템 DB 제외
    exclude = ['information_schema', 'mysql', 'performance_schema', 'sys']
    return [db for db in databases if db not in exclude]

def get_tables_in_database(db_name):
    """특정 DB의 모든 테이블 목록"""
    con = get_connection(db_name)
    cursor = con.cursor()
    cursor.execute("SHOW TABLES")
    tables = [row[0] for row in cursor.fetchall()]
    con.close()
    return tables

def get_table_info(db_name, table_name):
    """테이블 정보 (컬럼, 데이터 개수)"""
    con = get_connection(db_name)
    cursor = con.cursor()

    # 컬럼 정보
    cursor.execute(f"DESCRIBE `{table_name}`")
    columns = cursor.fetchall()

    # 데이터 개수
    try:
        cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
        count = cursor.fetchone()[0]
    except:
        count = 0

    con.close()
    return columns, count

def print_separator(char='=', length=100):
    """구분선"""
    print(char * length)

def collect_db_schema():
    """전체 DB 스키마 정보를 수집하여 딕셔너리로 반환"""
    schema = {
        "last_updated": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "main_trading_db": "jackbot1_imi1",  # 실제 운영 DB
        "databases": {}
    }

    databases = get_all_databases()

    for db_name in databases:
        tables = get_tables_in_database(db_name)

        # 날짜 테이블과 일반 테이블 구분
        date_tables = [t for t in tables if t.isdigit() and len(t) == 8]
        normal_tables = [t for t in tables if t not in date_tables]

        db_info = {
            "table_count": len(tables),
            "normal_tables": {},
            "date_tables": {
                "count": len(date_tables),
                "latest": max(date_tables) if date_tables else None,
                "oldest": min(date_tables) if date_tables else None
            }
        }

        # DB 용도 설명
        if db_name == "jackbot1_imi1":
            db_info["description"] = "실전 트레이딩 봇 메인 DB"
        elif db_name == "daily_buy_list":
            db_info["description"] = "날짜별 매수 후보 집계 테이블"
        elif db_name == "daily_craw":
            db_info["description"] = "종목별 일봉 데이터"
        elif db_name == "min_craw":
            db_info["description"] = "분봉 데이터 (주요 종목)"
        elif "simulator" in db_name:
            db_info["description"] = f"시뮬레이터 DB ({db_name})"
        else:
            db_info["description"] = "용도 미분류"

        # 일반 테이블 상세 정보
        for table_name in normal_tables:
            columns, count = get_table_info(db_name, table_name)
            col_names = [col[0] for col in columns]

            table_info = {
                "row_count": count,
                "column_count": len(columns),
                "columns": col_names
            }

            # 주요 테이블 설명 및 중요 컬럼 표시
            if table_name == "realtime_daily_buy_list":
                table_info["description"] = "내일 매수 후보 리스트"
                table_info["has_strategy_columns"] = all(c in col_names for c in ['strategy_type', 'composite_score', 'volume_ratio'])
                table_info["important_columns"] = ['code', 'code_name', 'strategy_type', 'composite_score', 'volume_ratio']
            elif table_name == "possessed_item":
                table_info["description"] = "현재 보유 종목"
                table_info["important_columns"] = ['code', 'code_name', 'stock_quantity']
            elif table_name == "setting_data":
                table_info["description"] = "시스템 설정 및 상태"
                table_info["important_columns"] = ['today_buy_list', 'daily_buy_list', 'daily_crawler']
            elif table_name == "all_item_db":
                table_info["description"] = "전체 종목 DB"
            elif table_name == "jango_data":
                table_info["description"] = "잔고 데이터"
            elif table_name == "stock_item_all":
                table_info["description"] = "전체 종목 정보"

            db_info["normal_tables"][table_name] = table_info

        schema["databases"][db_name] = db_info

    return schema

def main():
    print("\n" + "="*100)
    print("📊 데이터베이스 전체 구조 분석")
    print("="*100)
    print(f"조회 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*100 + "\n")

    # 모든 DB 조회
    databases = get_all_databases()

    print(f"🗄️  총 데이터베이스 개수: {len(databases)}개\n")

    # DB별로 상세 정보 출력
    for db_idx, db_name in enumerate(databases, 1):
        print(f"\n{'='*100}")
        print(f"[{db_idx}/{len(databases)}] 📁 데이터베이스: {db_name}")
        print(f"{'='*100}")

        # 테이블 목록
        tables = get_tables_in_database(db_name)
        print(f"\n  📊 총 테이블 개수: {len(tables)}개")

        if not tables:
            print("  ⚠️  테이블이 없습니다.\n")
            continue

        # 날짜 테이블과 일반 테이블 구분
        date_tables = [t for t in tables if t.isdigit() and len(t) == 8]
        normal_tables = [t for t in tables if t not in date_tables]

        # 일반 테이블 상세 정보
        if normal_tables:
            print(f"\n  📋 일반 테이블 ({len(normal_tables)}개):")
            print(f"  {'-'*96}")
            print(f"  {'번호':<6} {'테이블명':<35} {'데이터 수':>15} {'주요 컬럼'}")
            print(f"  {'-'*96}")

            for idx, table_name in enumerate(sorted(normal_tables), 1):
                columns, count = get_table_info(db_name, table_name)

                # 주요 컬럼 (최대 5개)
                col_names = [col[0] for col in columns[:5]]
                col_str = ', '.join(col_names)
                if len(columns) > 5:
                    col_str += f", ... (+{len(columns)-5}개)"

                print(f"  {idx:<6} {table_name:<35} {count:>15,}행  {col_str}")

        # 날짜 테이블 요약
        if date_tables:
            print(f"\n  📅 날짜별 테이블 ({len(date_tables)}개):")
            date_tables_sorted = sorted(date_tables, reverse=True)

            # 최근 5개만 상세 표시
            print(f"  {'-'*96}")
            print(f"  {'날짜':<15} {'데이터 수':>15} {'비고'}")
            print(f"  {'-'*96}")

            for i, table_name in enumerate(date_tables_sorted[:5]):
                _, count = get_table_info(db_name, table_name)

                # 날짜 포맷팅 (YYYYMMDD -> YYYY-MM-DD)
                formatted_date = f"{table_name[:4]}-{table_name[4:6]}-{table_name[6:]}"
                note = "최신" if i == 0 else ""

                print(f"  {formatted_date:<15} {count:>15,}행  {note}")

            if len(date_tables) > 5:
                print(f"  {'...':<15} {'':>15}   외 {len(date_tables)-5}개 테이블")

            print(f"\n  📆 날짜 범위: {date_tables_sorted[-1]} ~ {date_tables_sorted[0]}")

    # 주요 테이블 상세 정보
    print(f"\n\n{'='*100}")
    print("🔍 주요 테이블 상세 정보")
    print(f"{'='*100}\n")

    important_tables = [
        ('jackbot1_imi1', 'realtime_daily_buy_list', '내일 매수 후보 리스트'),
        ('jackbot1_imi1', 'possessed_item', '현재 보유 종목'),
        ('jackbot1_imi1', 'setting_data', '시스템 설정'),
        ('jackbot1_imi1', 'all_item_db', '전체 종목 DB'),
    ]

    for db_name, table_name, description in important_tables:
        try:
            con = get_connection(db_name)
            cursor = con.cursor()

            # 테이블 존재 여부 확인
            cursor.execute(f"""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = '{db_name}'
                AND table_name = '{table_name}'
            """)

            if cursor.fetchone()[0] == 0:
                print(f"  ⚠️  {db_name}.{table_name} ({description}) - 테이블 없음")
                con.close()
                continue

            # 컬럼 정보
            cursor.execute(f"DESCRIBE `{table_name}`")
            columns = cursor.fetchall()

            # 데이터 개수
            cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
            count = cursor.fetchone()[0]

            print(f"  📊 {db_name}.{table_name} ({description})")
            print(f"     - 데이터: {count:,}행")
            print(f"     - 컬럼: {len(columns)}개")

            # 주요 컬럼만 표시
            if table_name == 'realtime_daily_buy_list':
                # 전략 컬럼 확인
                col_names = [col[0] for col in columns]
                has_strategy = 'strategy_type' in col_names
                has_score = 'composite_score' in col_names
                has_volume = 'volume_ratio' in col_names

                if has_strategy and has_score and has_volume:
                    print(f"     - ✅ 고급 전략 컬럼 존재 (strategy_type, composite_score, volume_ratio)")
                else:
                    print(f"     - ❌ 고급 전략 컬럼 누락")

                # 샘플 데이터 (최대 3개)
                if count > 0:
                    cursor.execute(f"""
                        SELECT code, code_name,
                               strategy_type, composite_score, volume_ratio
                        FROM `{table_name}`
                        LIMIT 3
                    """)
                    samples = cursor.fetchall()
                    print(f"     - 샘플 데이터:")
                    for sample in samples:
                        if has_strategy:
                            print(f"       • {sample[0]} {sample[1]}: {sample[2]} ({sample[3]:.1f}점, {sample[4]:.2f}x)")
                        else:
                            print(f"       • {sample[0]} {sample[1]}")

            elif table_name == 'possessed_item':
                if count > 0:
                    cursor.execute(f"SELECT code, code_name, stock_quantity FROM `{table_name}` LIMIT 5")
                    samples = cursor.fetchall()
                    print(f"     - 보유 종목:")
                    for sample in samples:
                        print(f"       • {sample[0]} {sample[1]}: {sample[2]:,}주")

            elif table_name == 'setting_data':
                cursor.execute(f"""
                    SELECT today_buy_list, daily_buy_list, daily_crawler
                    FROM `{table_name}`
                    LIMIT 1
                """)
                setting = cursor.fetchone()
                if setting:
                    print(f"     - 마지막 매수리스트 생성: {setting[0]}")
                    print(f"     - 마지막 daily_buy_list: {setting[1]}")
                    print(f"     - 마지막 일봉 수집: {setting[2]}")

            con.close()
            print()

        except Exception as e:
            print(f"  ❌ {db_name}.{table_name} 조회 오류: {e}\n")

    # JSON 스키마 파일 생성
    print(f"\n{'='*100}")
    print("📝 DB 구조 문서화 파일 생성 중...")
    print(f"{'='*100}\n")

    try:
        schema = collect_db_schema()
        schema_file = "db_schema.json"

        with open(schema_file, 'w', encoding='utf-8') as f:
            json.dump(schema, f, ensure_ascii=False, indent=2)

        print(f"  ✅ DB 구조 파일 생성 완료!")
        print(f"  📁 파일 위치: {schema_file}")
        print(f"  💡 다음 작업 시 이 파일을 Claude에게 제공하면 DB 구조를 즉시 파악할 수 있습니다.\n")

    except Exception as e:
        print(f"  ❌ JSON 파일 생성 실패: {e}\n")

    print(f"{'='*100}")
    print("✅ 데이터베이스 분석 완료!")
    print(f"{'='*100}\n")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
