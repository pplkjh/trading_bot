"""
d1_diff_rate 0값 수정 스크립트

문제: collector가 장전 실행 시 daily_buy_list 테이블의 d1_diff_rate가 0으로 저장됨
원인: 장전에는 당일 daily_craw 데이터가 미완성 상태라 변동률 계산 불가
해결: 연속된 두 테이블의 close 값으로 직접 계산
      d1_diff_rate = (curr.close - prev.close) / prev.close * 100

- Kiwoom API 연결 불필요 (daily_buy_list DB만 사용)
- d1_diff_rate = 0 인 행만 업데이트 (이미 올바른 값은 건드리지 않음)
- 중단 후 재실행 안전
- 실행 방법: python sql/fix_d1_diff_rate.py
            python sql/fix_d1_diff_rate.py --dry-run   (실제 변경 없이 결과만 출력)
"""

import sys
import os
import argparse
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from library import cf

# ─── DB 연결 ───────────────────────────────────────────────────────────────────
engine = create_engine(
    f"mysql+pymysql://{cf.db_id}:{cf.db_passwd}@{cf.db_ip}:{cf.db_port}/daily_buy_list",
    encoding='utf-8',
    connect_args={"autocommit": True}
)


def get_date_tables():
    """daily_buy_list DB의 날짜 테이블 목록 (오름차순)"""
    rows = engine.execute("""
        SELECT TABLE_NAME
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = 'daily_buy_list'
          AND TABLE_NAME REGEXP '^[0-9]{8}$'
        ORDER BY TABLE_NAME ASC
    """).fetchall()
    return [r[0] for r in rows]


def count_zero_d1(table):
    """d1_diff_rate = 0 인 행 수"""
    try:
        row = engine.execute(
            f"SELECT COUNT(*) FROM `{table}` WHERE d1_diff_rate = 0 OR d1_diff_rate IS NULL"
        ).fetchone()
        return row[0] if row else 0
    except Exception:
        return 0


def fix_table(curr_table, prev_table, dry_run=False):
    """
    curr_table의 d1_diff_rate를 prev_table의 close 기준으로 계산해서 UPDATE

    Returns: (업데이트 행 수, 스킵 행 수)
    """
    zero_count = count_zero_d1(curr_table)
    if zero_count == 0:
        return 0, 0

    sql_update = f"""
        UPDATE `{curr_table}` a
        JOIN `{prev_table}` b ON a.code = b.code
        SET a.d1_diff_rate = ROUND((a.close - b.close) / b.close * 100, 4)
        WHERE (a.d1_diff_rate = 0 OR a.d1_diff_rate IS NULL)
          AND b.close > 0
          AND a.close > 0
    """

    if dry_run:
        # 업데이트될 행 수만 계산
        sql_count = f"""
            SELECT COUNT(*) FROM `{curr_table}` a
            JOIN `{prev_table}` b ON a.code = b.code
            WHERE (a.d1_diff_rate = 0 OR a.d1_diff_rate IS NULL)
              AND b.close > 0 AND a.close > 0
        """
        matched = engine.execute(sql_count).fetchone()[0]
        skipped = zero_count - matched
        return matched, skipped

    result = engine.execute(sql_update)
    updated = result.rowcount

    # prev_table에 없어서 못 고친 행 (종목 상장폐지 등)
    skipped = zero_count - updated
    return updated, skipped


def main():
    parser = argparse.ArgumentParser(description='d1_diff_rate 0값 수정')
    parser.add_argument('--dry-run', action='store_true',
                        help='실제 변경 없이 결과만 출력')
    args = parser.parse_args()

    dry_run = args.dry_run

    print("=" * 80)
    print("d1_diff_rate 수정 스크립트")
    if dry_run:
        print("  *** DRY RUN 모드 -- 실제 변경 없음 ***")
    print("=" * 80)

    tables = get_date_tables()
    if len(tables) < 2:
        print("날짜 테이블이 2개 미만입니다. 종료.")
        return

    print(f"\n총 {len(tables)}개 날짜 테이블 발견 ({tables[0]} ~ {tables[-1]})\n")

    total_updated = 0
    total_skipped = 0
    fixed_tables = 0
    start = time.time()

    for i in range(1, len(tables)):
        curr = tables[i]
        prev = tables[i - 1]

        zero = count_zero_d1(curr)
        if zero == 0:
            continue  # 이미 정상 — 출력도 스킵

        updated, skipped = fix_table(curr, prev, dry_run=dry_run)

        action = "[DRY]" if dry_run else "[FIX]"
        print(f"{action} {curr} (기준: {prev})  "
              f"수정: {updated:4d}개  미매칭: {skipped:3d}개")

        total_updated += updated
        total_skipped += skipped
        if updated > 0:
            fixed_tables += 1

    elapsed = time.time() - start
    print("\n" + "=" * 80)
    if dry_run:
        print(f"[DRY RUN 결과]")
        print(f"  수정 예정 테이블: {fixed_tables}개")
        print(f"  수정 예정 행:     {total_updated:,}개")
        print(f"  미매칭 행:        {total_skipped:,}개 (상장폐지 등)")
        print(f"  --dry-run 제거 후 다시 실행하면 실제 반영됩니다.")
    else:
        print(f"완료 ({elapsed:.1f}초)")
        print(f"  수정된 테이블: {fixed_tables}개")
        print(f"  수정된 행:     {total_updated:,}개")
        print(f"  미매칭 행:     {total_skipped:,}개 (상장폐지 등 — 정상)")
    print("=" * 80)


if __name__ == "__main__":
    main()
