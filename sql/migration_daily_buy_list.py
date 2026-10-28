"""
daily_buy_list DB 마이그레이션 스크립트 (v2 확장 지표 컬럼 추가)

기존 날짜 테이블에 20개 v2 지표 컬럼을 추가하고
daily_craw DB에서 과거 데이터를 읽어 값을 계산해서 채웁니다.

- Kiwoom API 연결 불필요 (daily_craw DB만 사용)
- 중단 후 재실행해도 안전 (macd 컬럼 존재 여부로 스킵 처리)
- 실행 방법: python sql/migration_daily_buy_list.py

추가되는 20개 컬럼:
  macd, macd_signal, macd_histogram,
  adx, plus_di, minus_di,
  obv, mfi14, cmf20,
  ichimoku_tenkan, ichimoku_kijun, ichimoku_senkou_a, ichimoku_senkou_b,
  pivot, pivot_s1, pivot_s2, pivot_r1, pivot_r2,
  candle_pattern_score, bb_bandwidth
"""

import sys
import os

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
import pandas as pd
from library import cf
from library.technical_indicators import (
    calculate_macd, calculate_adx, calculate_obv, calculate_mfi, calculate_cmf,
    calculate_ichimoku, calculate_pivot_points, detect_candle_pattern,
    calculate_bollinger_bandwidth
)

# ── DB 엔진 ──────────────────────────────────────────────────────────────────
engine_daily_craw = create_engine(
    "mysql+pymysql://" + cf.db_id + ":" + cf.db_passwd + "@"
    + cf.db_ip + ":" + cf.db_port + "/daily_craw?charset=utf8mb4"
)
engine_daily_buy_list = create_engine(
    "mysql+pymysql://" + cf.db_id + ":" + cf.db_passwd + "@"
    + cf.db_ip + ":" + cf.db_port + "/daily_buy_list?charset=utf8mb4"
)

NEW_COLUMNS = [
    ('macd',               'FLOAT'),
    ('macd_signal',        'FLOAT'),
    ('macd_histogram',     'FLOAT'),
    ('adx',                'FLOAT'),
    ('plus_di',            'FLOAT'),
    ('minus_di',           'FLOAT'),
    ('obv',                'FLOAT'),
    ('mfi14',              'FLOAT'),
    ('cmf20',              'FLOAT'),
    ('ichimoku_tenkan',    'FLOAT'),
    ('ichimoku_kijun',     'FLOAT'),
    ('ichimoku_senkou_a',  'FLOAT'),
    ('ichimoku_senkou_b',  'FLOAT'),
    ('pivot',              'FLOAT'),
    ('pivot_s1',           'FLOAT'),
    ('pivot_s2',           'FLOAT'),
    ('pivot_r1',           'FLOAT'),
    ('pivot_r2',           'FLOAT'),
    ('candle_pattern_score', 'FLOAT'),
    ('bb_bandwidth',       'FLOAT'),
]


def get_date_tables():
    """daily_buy_list DB에서 8자리 숫자 날짜 테이블 목록 조회 (오름차순)"""
    sql = ("SELECT table_name FROM information_schema.tables "
           "WHERE table_schema = 'daily_buy_list' "
           "AND table_name REGEXP '^[0-9]{8}$' "
           "ORDER BY table_name")
    rows = engine_daily_buy_list.execute(sql).fetchall()
    return [row[0] for row in rows]


def has_new_columns(date_table: str) -> bool:
    """macd 컬럼 존재 여부로 이미 마이그레이션된 테이블인지 확인"""
    sql = ("SELECT 1 FROM information_schema.columns "
           "WHERE table_schema = 'daily_buy_list' "
           f"AND table_name = '{date_table}' "
           "AND column_name = 'macd'")
    rows = engine_daily_buy_list.execute(sql).fetchall()
    return len(rows) > 0


def alter_table(date_table: str):
    """날짜 테이블에 20개 컬럼 ALTER TABLE로 추가"""
    add_parts = ", ".join(
        f"ADD COLUMN `{col}` {dtype} DEFAULT 0"
        for col, dtype in NEW_COLUMNS
    )
    sql = f"ALTER TABLE `{date_table}` {add_parts}"
    engine_daily_buy_list.execute(sql)


def calc_indicators(code_name: str, date_str: str):
    """daily_craw에서 date 이전 120일 데이터 조회 후 20개 지표 계산"""
    try:
        sql = (f"SELECT * FROM `{code_name}` "
               f"WHERE date <= '{date_str}' "
               "ORDER BY date DESC LIMIT 120")
        df = pd.read_sql(sql, engine_daily_craw)

        if len(df) < 2:
            return _defaults()

        df = df.sort_values('date').reset_index(drop=True)

        macd, macd_signal, macd_histogram = calculate_macd(df['close'])
        adx, plus_di, minus_di = calculate_adx(df['high'], df['low'], df['close'])
        obv = calculate_obv(df['close'], df['volume'])
        mfi14 = calculate_mfi(df['high'], df['low'], df['close'], df['volume'], 14)
        cmf20 = calculate_cmf(df['high'], df['low'], df['close'], df['volume'], 20)
        ichimoku_tenkan, ichimoku_kijun, ichimoku_senkou_a, ichimoku_senkou_b = \
            calculate_ichimoku(df['high'], df['low'], df['close'])

        pivot, pivot_s1, pivot_s2, pivot_r1, pivot_r2 = calculate_pivot_points(
            float(df['high'].iloc[-2]),
            float(df['low'].iloc[-2]),
            float(df['close'].iloc[-2])
        )
        candle_pattern_score = detect_candle_pattern(
            float(df['open'].iloc[-1]), float(df['high'].iloc[-1]),
            float(df['low'].iloc[-1]),  float(df['close'].iloc[-1]),
            float(df['open'].iloc[-2]), float(df['high'].iloc[-2]),
            float(df['low'].iloc[-2]),  float(df['close'].iloc[-2])
        )

        # bb_bandwidth: daily_buy_list 테이블의 기존 bb_upper/middle/lower 사용
        # (여기서는 별도 계산 — 동일 df에서)
        from library.technical_indicators import calculate_bollinger_bands
        bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(df['close'], 20)
        bb_bandwidth = calculate_bollinger_bandwidth(bb_upper, bb_middle, bb_lower)

        return (macd, macd_signal, macd_histogram,
                adx, plus_di, minus_di,
                obv, mfi14, cmf20,
                ichimoku_tenkan, ichimoku_kijun, ichimoku_senkou_a, ichimoku_senkou_b,
                pivot, pivot_s1, pivot_s2, pivot_r1, pivot_r2,
                candle_pattern_score, bb_bandwidth)
    except Exception as e:
        return _defaults()


def _defaults():
    return (0.0, 0.0, 0.0,   # macd, macd_signal, macd_histogram
            0.0, 0.0, 0.0,   # adx, plus_di, minus_di
            0.0, 50.0, 0.0,  # obv, mfi14, cmf20
            0.0, 0.0, 0.0, 0.0,  # ichimoku 4개
            0.0, 0.0, 0.0, 0.0, 0.0,  # pivot 5개
            0.0, 0.0)         # candle_pattern_score, bb_bandwidth


def migrate_table(date_table: str):
    """단일 날짜 테이블 마이그레이션: ALTER + UPDATE 각 종목"""
    # 1. 컬럼 추가
    alter_table(date_table)

    # 2. 해당 날짜 테이블의 모든 종목 조회
    rows = engine_daily_buy_list.execute(
        f"SELECT code, code_name FROM `{date_table}`"
    ).fetchall()

    updated = 0
    skipped = 0
    for row in rows:
        code = row[0]
        code_name = row[1]
        try:
            vals = calc_indicators(code_name, date_table)
            (macd, macd_signal, macd_histogram,
             adx, plus_di, minus_di,
             obv, mfi14, cmf20,
             ichimoku_tenkan, ichimoku_kijun, ichimoku_senkou_a, ichimoku_senkou_b,
             pivot, pivot_s1, pivot_s2, pivot_r1, pivot_r2,
             candle_pattern_score, bb_bandwidth) = vals

            sql = f"""
                UPDATE `{date_table}` SET
                  macd={macd}, macd_signal={macd_signal}, macd_histogram={macd_histogram},
                  adx={adx}, plus_di={plus_di}, minus_di={minus_di},
                  obv={obv}, mfi14={mfi14}, cmf20={cmf20},
                  ichimoku_tenkan={ichimoku_tenkan}, ichimoku_kijun={ichimoku_kijun},
                  ichimoku_senkou_a={ichimoku_senkou_a}, ichimoku_senkou_b={ichimoku_senkou_b},
                  pivot={pivot}, pivot_s1={pivot_s1}, pivot_s2={pivot_s2},
                  pivot_r1={pivot_r1}, pivot_r2={pivot_r2},
                  candle_pattern_score={candle_pattern_score},
                  bb_bandwidth={bb_bandwidth}
                WHERE code='{code}'
            """
            engine_daily_buy_list.execute(sql)
            updated += 1
        except Exception as e:
            skipped += 1

    return updated, skipped


def main():
    print("=" * 70)
    print("daily_buy_list v2 마이그레이션 시작")
    print("  20개 기술적 지표 컬럼 추가 (Kiwoom API 불필요)")
    print("=" * 70)

    date_tables = get_date_tables()
    total = len(date_tables)
    print(f"대상 날짜 테이블: {total}개\n")

    already_done = 0
    for idx, dt in enumerate(date_tables):
        if has_new_columns(dt):
            already_done += 1
            continue

        updated, skipped = migrate_table(dt)
        print(f"[{idx + 1:4d}/{total}] {dt}  완료={updated} 스킵={skipped}")

    if already_done > 0:
        print(f"\n이미 완료된 테이블: {already_done}개 스킵")

    print("\n✅ 마이그레이션 완료!")
    print("이제 collector_v3.py를 실행하면 새 날짜 테이블은 자동으로 20개 컬럼이 포함됩니다.")


if __name__ == "__main__":
    main()
