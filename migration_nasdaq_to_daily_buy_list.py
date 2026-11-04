# -*- coding: utf-8 -*-
"""
daily_craw의 nasdaq_index / sox_index 수익률을
daily_buy_list YYYYMMDD 날짜 테이블에 backfill하는 마이그레이션

동작 순서:
  1. daily_craw.nasdaq_index / sox_index 전체 로드
  2. 날짜별 1d/5d 수익률 계산 (pct_change)
  3. daily_buy_list의 각 날짜 테이블에
     nasdaq_1d_ret / nasdaq_5d_ret / sox_1d_ret 컬럼 ADD IF NOT EXISTS
  4. 각 날짜 테이블 전 행을 해당 날짜 T 기준 T-1 NASDAQ 값으로 일괄 UPDATE

실행: python migration_nasdaq_to_daily_buy_list.py
     (Kiwoom 로그인 불필요 — 순수 DB 작업)

참고:
  - T-1 기준: bisect_left(nq_dates, T) - 1
    한국 거래일 T 이전의 마지막 NASDAQ 거래일 값 사용
  - nasdaq_index/sox_index 테이블이 없으면 스크립트가 안내 후 종료
"""
import sys
import os
import bisect
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import pymysql
pymysql.install_as_MySQLdb()

from sqlalchemy import create_engine, text
from library import cf


def make_engine(db_name):
    return create_engine(
        f"mysql+mysqldb://{cf.db_id}:{cf.db_passwd}"
        f"@{cf.db_ip}:{cf.db_port}/{db_name}?charset=utf8",
        pool_pre_ping=True
    )


def load_nasdaq_lookup(engine_craw):
    """nasdaq_index, sox_index 로드 → bisect 조회용 dict 반환"""
    try:
        nq = engine_craw.execute(
            "SELECT date, close FROM nasdaq_index ORDER BY date ASC"
        ).fetchall()
    except Exception as e:
        print(f"❌ nasdaq_index 테이블 조회 실패: {e}")
        print("   daily_craw DB에 nasdaq_index 테이블이 있는지 확인하세요.")
        sys.exit(1)

    try:
        sx = engine_craw.execute(
            "SELECT date, close FROM sox_index ORDER BY date ASC"
        ).fetchall()
    except Exception as e:
        print(f"❌ sox_index 테이블 조회 실패: {e}")
        print("   daily_craw DB에 sox_index 테이블이 있는지 확인하세요.")
        sys.exit(1)

    nq_dates  = [str(r[0]) for r in nq]
    nq_closes = [float(r[1]) for r in nq]
    sx_dates  = [str(r[0]) for r in sx]
    sx_closes = [float(r[1]) for r in sx]

    # 1d / 5d pct_change
    def pct(closes, i, n):
        if i < n or closes[i - n] == 0:
            return 0.0
        return (closes[i] - closes[i - n]) / closes[i - n]

    nq_n1 = [pct(nq_closes, i, 1) for i in range(len(nq_closes))]
    nq_n5 = [pct(nq_closes, i, 5) for i in range(len(nq_closes))]
    sx_s1 = [pct(sx_closes, i, 1) for i in range(len(sx_closes))]

    print(f"  nasdaq_index: {len(nq_dates)}행  sox_index: {len(sx_dates)}행")
    return {
        'nq_dates': nq_dates, 'nq_n1': nq_n1, 'nq_n5': nq_n5,
        'sx_dates': sx_dates, 'sx_s1': sx_s1,
    }


def get_nasdaq_vals(lookup, date_str):
    """date_str(YYYYMMDD) T → T-1 NASDAQ 값. 없으면 (None, None, None)"""
    nq_dates = lookup['nq_dates']
    idx = bisect.bisect_left(nq_dates, str(date_str)) - 1
    if idx < 0:
        return None, None, None
    n1 = lookup['nq_n1'][idx]
    n5 = lookup['nq_n5'][idx]
    sx_idx = bisect.bisect_left(lookup['sx_dates'], str(date_str)) - 1
    s1 = lookup['sx_s1'][sx_idx] if sx_idx >= 0 else None
    return n1, n5, s1


def add_columns_if_missing(engine_buy, date_str):
    """테이블에 nasdaq_1d_ret/nasdaq_5d_ret/sox_1d_ret 컬럼이 없으면 추가"""
    for col, comment in [
        ('nasdaq_1d_ret', 'NASDAQ 전일대비 수익률 (T-1)'),
        ('nasdaq_5d_ret', 'NASDAQ 5일 수익률 (T-1)'),
        ('sox_1d_ret',    'SOX 전일대비 수익률 (T-1)'),
    ]:
        try:
            engine_buy.execute(
                f"ALTER TABLE `{date_str}` "
                f"ADD COLUMN `{col}` DECIMAL(10,6) DEFAULT NULL COMMENT '{comment}'"
            )
        except Exception as e:
            err = str(e).lower()
            if 'duplicate column' in err or 'already exists' in err:
                pass  # 이미 있음 — 정상
            else:
                raise


def update_table(engine_buy, date_str, n1, n5, s1):
    """date_str 테이블의 모든 행을 n1/n5/s1로 UPDATE (전 종목 동일값)"""
    if n1 is None and n5 is None and s1 is None:
        return 0
    parts = []
    if n1 is not None: parts.append(f"nasdaq_1d_ret = {n1:.8f}")
    if n5 is not None: parts.append(f"nasdaq_5d_ret = {n5:.8f}")
    if s1 is not None: parts.append(f"sox_1d_ret = {s1:.8f}")
    sql = f"UPDATE `{date_str}` SET {', '.join(parts)}"
    try:
        res = engine_buy.execute(sql)
        return res.rowcount
    except Exception as e:
        print(f"\n  UPDATE 오류 ({date_str}): {e}")
        return 0


def main():
    engine_craw = make_engine('daily_craw')
    engine_buy  = make_engine('daily_buy_list')

    # ── Step 1: NASDAQ/SOX lookup 구축 ──────────────────────────────
    print("Step 1. NASDAQ/SOX lookup 구축 중...")
    lookup = load_nasdaq_lookup(engine_craw)
    print()

    # ── Step 2: daily_buy_list 날짜 테이블 목록 조회 ─────────────────
    print("Step 2. daily_buy_list 날짜 테이블 목록 조회 중...")
    tables = engine_buy.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'daily_buy_list' "
        "  AND table_name REGEXP '^[0-9]{8}$' "
        "ORDER BY table_name ASC"
    ).fetchall()
    date_tables = [str(r[0]) for r in tables]
    print(f"  {len(date_tables)}개 날짜 테이블 발견 "
          f"({date_tables[0] if date_tables else '?'} ~ "
          f"{date_tables[-1] if date_tables else '?'})\n")

    if not date_tables:
        print("날짜 테이블 없음. 종료.")
        return

    # ── Step 3: 각 테이블 컬럼 추가 + 값 업데이트 ────────────────────
    print("Step 3. 컬럼 추가 + NASDAQ 값 backfill 중...")
    total_rows = 0
    skipped    = 0
    t0 = time.time()

    for i, date_str in enumerate(date_tables):
        n1, n5, s1 = get_nasdaq_vals(lookup, date_str)

        if n1 is None and n5 is None and s1 is None:
            skipped += 1
            if (i + 1) % 50 == 0 or i == len(date_tables) - 1:
                elapsed = time.time() - t0
                print(f"  [{i+1}/{len(date_tables)}] {date_str} SKIP (NASDAQ 데이터 없음)"
                      f"  ({elapsed:.1f}s)", flush=True)
            continue

        try:
            add_columns_if_missing(engine_buy, date_str)
            updated = update_table(engine_buy, date_str, n1, n5, s1)
            total_rows += updated
        except Exception as e:
            print(f"\n  ❌ {date_str} 오류: {e}")
            continue

        if (i + 1) % 50 == 0 or i == len(date_tables) - 1:
            elapsed = time.time() - t0
            print(f"  [{i+1}/{len(date_tables)}] {date_str}  "
                  f"n1={n1:+.4f} n5={n5:+.4f} s1={s1:+.4f}  "
                  f"+{updated}행  (총 {total_rows:,}행, {elapsed:.1f}s)", flush=True)

    elapsed = time.time() - t0
    print(f"\n✅ 완료: {len(date_tables) - skipped}개 테이블 처리, "
          f"{skipped}개 스킵, 총 {total_rows:,}행 업데이트  ({elapsed:.1f}s)")


if __name__ == '__main__':
    main()
