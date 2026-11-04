# -*- coding: utf-8 -*-
"""
daily_craw의 inst_net_buy / foreign_net_buy 를
daily_buy_list YYYYMMDD 날짜 테이블에 복사하는 마이그레이션

동작 순서:
  1. daily_craw 전 종목 inst 데이터를 메모리에 pre-load
     {(code, date): (inst_net_buy, foreign_net_buy)}
  2. inst 데이터가 있는 날짜 범위의 daily_buy_list 테이블들에
     inst_net_buy / foreign_net_buy 컬럼 추가 후 값 복사

실행: python migration_inst_to_daily_buy_list.py
     (Kiwoom 로그인 불필요 — 순수 DB 작업)
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import pymysql
pymysql.install_as_MySQLdb()

from sqlalchemy import create_engine
from library import cf


def make_engine(db_name):
    return create_engine(
        f"mysql+mysqldb://{cf.db_id}:{cf.db_passwd}"
        f"@{cf.db_ip}:{cf.db_port}/{db_name}?charset=utf8",
        pool_pre_ping=True
    )


CHUNK = 400   # CASE 구문 한 번에 처리할 종목 수


def batch_update(engine, date_str, updates):
    """updates: list of (inst_net_buy, foreign_net_buy, code)
    CASE 구문으로 한 번의 UPDATE로 처리."""
    if not updates:
        return 0

    total_updated = 0
    for i in range(0, len(updates), CHUNK):
        chunk = updates[i:i + CHUNK]
        case_inst    = ' '.join(f"WHEN '{c}' THEN {iv if iv is not None else 'NULL'}"
                                for iv, fv, c in chunk)
        case_foreign = ' '.join(f"WHEN '{c}' THEN {fv if fv is not None else 'NULL'}"
                                for iv, fv, c in chunk)
        codes_in     = ','.join(f"'{c}'" for _, _, c in chunk)
        sql = (
            f"UPDATE `{date_str}` SET "
            f"inst_net_buy = CASE code {case_inst} ELSE inst_net_buy END, "
            f"foreign_net_buy = CASE code {case_foreign} ELSE foreign_net_buy END "
            f"WHERE code IN ({codes_in})"
        )
        try:
            res = engine.execute(sql)
            total_updated += res.rowcount
        except Exception as e:
            print(f"\n  UPDATE 오류 ({date_str} chunk {i//CHUNK}): {e}")
    return total_updated


def main():
    engine_craw = make_engine('daily_craw')
    engine_buy  = make_engine('daily_buy_list')

    # ── Step 1: code → code_name 맵 ─────────────────────────────────
    print("Step 1. 종목 코드 맵 구축 중...")
    code_map = {}
    for r in engine_buy.execute("SELECT code, code_name FROM stock_item_all").fetchall():
        code_map[str(r[0]).strip()] = str(r[1]).strip()
    print(f"  {len(code_map)}개 종목\n")

    # ── Step 2: inst 데이터 범위 확인 ────────────────────────────────
    print("Step 2. inst_net_buy 데이터 범위 확인 중...")
    ref = engine_craw.execute(
        "SELECT MIN(date), MAX(date) FROM `삼성전자` WHERE inst_net_buy IS NOT NULL"
    ).fetchone()
    inst_start, inst_end = str(ref[0]), str(ref[1])
    print(f"  inst 데이터 범위: {inst_start} ~ {inst_end}\n")

    # ── Step 3: daily_craw 전 종목 inst 데이터 pre-load ─────────────
    print("Step 3. daily_craw inst 데이터 메모리에 로드 중 (약 2~3분 소요)...")
    inst_dict = {}   # {(code, date): (inst_net_buy, foreign_net_buy)}
    loaded_stocks = 0
    load_start = time.time()

    for code, code_name in code_map.items():
        try:
            rows = engine_craw.execute(
                f"SELECT date, inst_net_buy, foreign_net_buy FROM `{code_name}` "
                f"WHERE inst_net_buy IS NOT NULL "
                f"AND date >= '{inst_start}' AND date <= '{inst_end}'"
            ).fetchall()
            for r in rows:
                inst_dict[(code, str(r[0]))] = (r[1], r[2])
            loaded_stocks += 1
        except Exception:
            pass   # 테이블 없는 종목 무시

        if loaded_stocks % 200 == 0:
            elapsed = time.time() - load_start
            print(f"  {loaded_stocks}/{len(code_map)} 종목 로드  "
                  f"({len(inst_dict):,}건)  {elapsed:.0f}초 경과")

    print(f"  완료: {len(inst_dict):,}건 로드 ({time.time() - load_start:.0f}초)\n")

    # ── Step 4: 날짜 테이블 목록 (inst 범위 내) ──────────────────────
    print("Step 4. 대상 날짜 테이블 조회 중...")
    date_rows = engine_buy.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'daily_buy_list' "
        "  AND table_name REGEXP '^[0-9]{8}$' "
        f" AND table_name >= '{inst_start}' "
        f" AND table_name <= '{inst_end}' "
        "ORDER BY table_name"
    ).fetchall()
    date_tables = [str(r[0]) for r in date_rows]
    total = len(date_tables)
    print(f"  {total}개 날짜 테이블 처리 예정\n")

    # ── Step 5: 날짜 테이블별 UPDATE ─────────────────────────────────
    print("Step 5. daily_buy_list 날짜 테이블 업데이트 중...")
    mig_start = time.time()
    total_rows = 0

    for idx, date_str in enumerate(date_tables, 1):
        # 컬럼 추가 (이미 있으면 무시)
        for col in ('inst_net_buy', 'foreign_net_buy'):
            try:
                engine_buy.execute(
                    f"ALTER TABLE `{date_str}` ADD COLUMN {col} INT DEFAULT NULL"
                )
            except Exception:
                pass

        # 이 날짜 테이블의 종목 코드 조회
        codes = [str(r[0]).strip() for r in
                 engine_buy.execute(f"SELECT code FROM `{date_str}`").fetchall()]

        # inst 데이터 수집
        updates = []
        for code in codes:
            key = (code, date_str)
            if key in inst_dict:
                iv, fv = inst_dict[key]
                if iv is not None or fv is not None:
                    updates.append((iv, fv, code))

        updated = batch_update(engine_buy, date_str, updates)
        total_rows += updated

        # 진행률
        elapsed = time.time() - mig_start
        rate = idx / elapsed if elapsed > 0 else 0
        eta = (total - idx) / rate if rate > 0 else 0
        print(f"  [{idx:3d}/{total}] {date_str}  {updated:4d}건 업데이트  "
              f"ETA {int(eta//60)}분 {int(eta%60)}초", flush=True)

    elapsed_total = time.time() - mig_start
    print(f"\n{'='*60}")
    print(f"마이그레이션 완료")
    print(f"  처리 날짜 테이블: {total}개")
    print(f"  총 업데이트 행:   {total_rows:,}건")
    print(f"  소요시간:         {int(elapsed_total//60)}분 {int(elapsed_total%60)}초")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
