# -*- coding: utf-8 -*-
"""
OPT10045 기관/외국인 순매수 역사 데이터 backfill
daily_craw 각 종목 테이블에 inst_net_buy, foreign_net_buy 컬럼을 추가하고
가능한 최대 기간(~600거래일)으로 수집합니다.

사용법:
    python backfill_inst_data.py
    python backfill_inst_data.py --start 20240101   # 시작일 지정
    python backfill_inst_data.py --resume           # 이미 수집된 종목 스킵

진행상황:
    - 수집 완료 종목은 daily_buy_list.stock_item_all.inst_backfill_done = 1 로 표시
    - 중단 후 --resume 으로 이어서 실행 가능

예상 소요시간:
    - 2300종목 × 0.5초 ≈ 20~30분 (페이지네이션 없을 경우)
    - 페이지네이션 발생 시 추가 시간 필요
"""
import sys
import os
import datetime
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from PyQt5.QtWidgets import QApplication
from library.open_api import open_api
from library import cf

# ── 기본 시작일: 오늘 기준 약 600거래일(≈2.4년) 전 ────────────────────────────
DEFAULT_START = (datetime.datetime.now() - datetime.timedelta(days=870)).strftime('%Y%m%d')
TODAY = datetime.datetime.now().strftime('%Y%m%d')


def parse_args():
    parser = argparse.ArgumentParser(description='OPT10045 기관/외국인 backfill')
    parser.add_argument('--start', default=DEFAULT_START,
                        help=f'시작일 YYYYMMDD (기본: {DEFAULT_START})')
    parser.add_argument('--resume', action='store_true',
                        help='이미 수집한 종목 스킵 (중단 후 이어서 실행)')
    return parser.parse_args()


def ensure_inst_columns(engine, code_name):
    """daily_craw 테이블에 inst_net_buy, foreign_net_buy 컬럼 추가 (이미 있으면 무시)."""
    for col in ('inst_net_buy', 'foreign_net_buy'):
        try:
            engine.execute(f"ALTER TABLE `{code_name}` ADD COLUMN {col} INT DEFAULT NULL")
        except Exception:
            pass  # 이미 존재


def batch_update_inst(engine, code_name, history):
    """history dict → daily_craw UPDATE (날짜 매칭, 없는 날짜는 무시).
    history: {date_str: {'inst_net_buy': int|None, 'foreign_net_buy': int|None}}
    """
    if not history:
        return 0

    updated = 0
    for date_str, vals in history.items():
        inst = vals.get('inst_net_buy')
        foreign = vals.get('foreign_net_buy')
        if inst is None and foreign is None:
            continue
        set_parts = []
        if inst is not None:
            set_parts.append(f"inst_net_buy = {inst}")
        if foreign is not None:
            set_parts.append(f"foreign_net_buy = {foreign}")
        try:
            result = engine.execute(
                f"UPDATE `{code_name}` SET {', '.join(set_parts)} WHERE date = '{date_str}'"
            )
            updated += result.rowcount
        except Exception:
            pass
    return updated


def mark_done(engine_buy, code):
    """stock_item_all에 inst_backfill_done 플래그 기록."""
    try:
        # 컬럼이 없으면 생성
        try:
            engine_buy.execute(
                "ALTER TABLE stock_item_all ADD COLUMN inst_backfill_done TINYINT DEFAULT 0"
            )
        except Exception:
            pass
        engine_buy.execute(
            f"UPDATE stock_item_all SET inst_backfill_done = 1 WHERE code = '{code}'"
        )
    except Exception:
        pass


def is_done(engine_buy, code):
    """이미 수집된 종목인지 확인."""
    try:
        row = engine_buy.execute(
            f"SELECT inst_backfill_done FROM stock_item_all WHERE code = '{code}'"
        ).fetchone()
        return row and int(row[0] or 0) == 1
    except Exception:
        return False


def main():
    args = parse_args()
    start_date = args.start
    resume = args.resume

    print(f"\n{'='*60}")
    print(f"OPT10045 기관/외국인 순매수 Backfill")
    print(f"  수집 기간: {start_date} ~ {TODAY}")
    print(f"  resume 모드: {resume}")
    print(f"{'='*60}\n")

    app = QApplication(sys.argv)
    api = open_api()

    engine_craw = api.engine_daily_craw
    engine_buy  = api.engine_daily_buy_list

    # ── 전체 종목 목록 ──────────────────────────────────────────────
    stocks = engine_buy.execute(
        "SELECT code, code_name FROM stock_item_all ORDER BY code"
    ).fetchall()
    total = len(stocks)
    print(f"대상 종목 수: {total}개\n")

    done_count  = 0
    skip_count  = 0
    error_count = 0
    start_time  = time.time()

    for idx, row in enumerate(stocks, 1):
        code      = str(row[0]).strip()
        code_name = str(row[1]).strip()

        # daily_craw 테이블이 없는 종목 스킵
        if not engine_craw.dialect.has_table(engine_craw, code_name):
            skip_count += 1
            continue

        # resume 모드: 이미 수집한 종목 스킵
        if resume and is_done(engine_buy, code):
            skip_count += 1
            continue

        # 진행률
        elapsed = time.time() - start_time
        rate    = done_count / elapsed if elapsed > 0 and done_count > 0 else 0
        remain  = (total - idx) / rate if rate > 0 else 0
        eta_str = f"ETA {int(remain//60)}분 {int(remain%60)}초" if rate > 0 else "계산중"
        print(f"[{idx:4d}/{total}] {code_name:<12} ({code})  {eta_str}", end='  ', flush=True)

        try:
            history = api.get_inst_history(code, start_date, TODAY)

            if not history:
                print("데이터 없음")
                skip_count += 1
                continue

            ensure_inst_columns(engine_craw, code_name)
            updated = batch_update_inst(engine_craw, code_name, history)
            mark_done(engine_buy, code)

            done_count += 1
            print(f"✓ {len(history)}일 수집, {updated}행 업데이트")

        except Exception as e:
            error_count += 1
            print(f"✗ 오류: {e}")

    elapsed_total = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"Backfill 완료")
    print(f"  수집 성공: {done_count}개")
    print(f"  스킵:      {skip_count}개")
    print(f"  오류:      {error_count}개")
    print(f"  소요시간:  {int(elapsed_total//60)}분 {int(elapsed_total%60)}초")
    print(f"{'='*60}\n")

    sys.exit(0)


if __name__ == '__main__':
    main()
