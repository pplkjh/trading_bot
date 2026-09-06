# -*- coding: utf-8 -*-
"""
ml_analysis/data_loader.py
simulator{N} / jackbot all_item_db → 피처 풍부화 → 파생 피처 계산

흐름:
  1. load_trade_data()        — all_item_db (완료 거래) 로드
  2. enrich_with_daily_buy_list() — daily_buy_list 날짜테이블에서 확장 지표 병합
  3. compute_derived_features()   — 비율·파생 피처 계산
  4. prepare_dataset()            — X, y, feature_names, dates 반환
"""
import pandas as pd
import numpy as np
from typing import List, Optional, Tuple


# ── 1. 거래 데이터 로드 ──────────────────────────────────────────────────────

def load_trade_data(
    simul_nums: List[int] = None,
    use_live: bool = False,
) -> pd.DataFrame:
    """
    simulator{N} 또는 jackbot{N}_imi1 의 all_item_db에서
    매도 완료된 거래를 모두 로드해 하나의 DataFrame으로 반환.

    Parameters
    ----------
    simul_nums : 조회할 simul_num 리스트 (기본: [4, 5, 6])
    use_live   : True → 실전 DB, False → 백테스트 simulator DB
    """
    if simul_nums is None:
        simul_nums = [4, 5, 6]

    from .config import make_engine, SIMULATOR_DBS, LIVE_DBS
    db_map = LIVE_DBS if use_live else SIMULATOR_DBS

    dfs = []
    for sn in simul_nums:
        db_name = db_map.get(sn)
        if not db_name:
            print(f"  [skip] simul_num={sn} — DB 매핑 없음")
            continue
        try:
            engine = make_engine(db_name)
            sql = """
                SELECT * FROM all_item_db
                WHERE sell_date IS NOT NULL
                  AND sell_date != '0'
                  AND sell_rate IS NOT NULL
            """
            df = pd.read_sql(sql, engine)
            df['_source_simul'] = sn
            dfs.append(df)
            print(f"  [{db_name}] {len(df):,} 거래 로드 완료")
        except Exception as e:
            print(f"  [{db_name or f'sim={sn}'}] 로드 실패: {e}")

    if not dfs:
        raise ValueError("로드된 거래 데이터가 없습니다. DB 연결·DB명을 확인하세요.")

    combined = pd.concat(dfs, ignore_index=True)
    before = len(combined)
    combined = combined.drop_duplicates(subset=['code', 'buy_date', 'strategy_type'])
    print(f"  중복 제거: {before:,} → {len(combined):,}")
    return combined


# ── 2. daily_buy_list 확장 지표 병합 ──────────────────────────────────────────

# daily_buy_list 날짜 테이블에서 가져올 확장 지표 컬럼
_EXTENDED_COLS = [
    'macd', 'macd_signal', 'macd_histogram',
    'adx', 'plus_di', 'minus_di',
    'obv', 'mfi14', 'cmf20',
    'ichimoku_tenkan', 'ichimoku_kijun',
    'ichimoku_senkou_a', 'ichimoku_senkou_b',
    'bb_bandwidth',
    'candle_pattern_score',
    # 아래는 all_item_db에 없지만 daily_buy_list에 있는 기본 지표
    'bb_upper', 'bb_middle', 'bb_lower',
    'atr14',
    'volume_ratio',
    # 수급 원본 (inst_buy_ratio 파생에 필요)
    'inst_net_buy', 'foreign_net_buy', 'volume',
]


def enrich_with_daily_buy_list(df: pd.DataFrame) -> pd.DataFrame:
    """
    daily_buy_list DB의 YYYYMMDD 날짜 테이블에서 확장 지표를 읽어
    df 에 LEFT JOIN 으로 병합.

    날짜 테이블이 없거나 migration이 안 된 날짜는 NaN으로 처리.
    """
    from .config import make_engine

    engine_dbl = make_engine('daily_buy_list')

    # 존재하는 날짜 테이블 목록 (8자리 숫자)
    try:
        tbl_sql = (
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'daily_buy_list' "
            "AND table_name REGEXP '^[0-9]{8}$' "
            "ORDER BY table_name"
        )
        existing_tables = {
            row[0] for row in engine_dbl.execute(tbl_sql).fetchall()
        }
    except Exception as e:
        print(f"  daily_buy_list 테이블 목록 조회 실패: {e}")
        return df

    df = df.copy()
    df['buy_date'] = df['buy_date'].astype(str)

    buy_dates = df['buy_date'].unique()
    available = sorted(d for d in buy_dates if d in existing_tables)
    print(f"  날짜 테이블 보유: {len(available)}/{len(buy_dates)} 날짜")

    if not available:
        print("  확장 지표 병합 생략: 해당 날짜 테이블 없음")
        return df

    pieces = []
    for date_str in available:
        try:
            # 해당 테이블에 실제로 있는 컬럼만 선택
            col_sql = (
                "SELECT column_name FROM information_schema.columns "
                f"WHERE table_schema='daily_buy_list' AND table_name='{date_str}'"
            )
            cols_in_tbl = {
                row[0] for row in engine_dbl.execute(col_sql).fetchall()
            }
            sel = ['code'] + [c for c in _EXTENDED_COLS if c in cols_in_tbl]

            if len(sel) <= 1:
                continue  # 확장 컬럼 없는 테이블

            # 이 날짜에 매수된 코드만 WHERE IN으로 필터링
            codes_today = df.loc[df['buy_date'] == date_str, 'code'].tolist()
            if not codes_today:
                continue

            codes_str = ','.join(f"'{c}'" for c in codes_today)
            sel_str = ', '.join(f'`{c}`' for c in sel)
            sub = pd.read_sql(
                f"SELECT {sel_str} FROM `{date_str}` WHERE code IN ({codes_str})",
                engine_dbl
            )
            sub['buy_date'] = date_str
            pieces.append(sub)
        except Exception:
            pass  # 개별 날짜 오류는 무시

    if not pieces:
        print("  확장 지표 로드된 날짜 없음 — 병합 생략")
        return df

    extra = pd.concat(pieces, ignore_index=True)
    extra['buy_date'] = extra['buy_date'].astype(str)

    df = df.merge(extra, on=['code', 'buy_date'], how='left', suffixes=('', '_dbl'))
    # merge 후 중복 컬럼 제거
    df = df.drop(columns=[c for c in df.columns if c.endswith('_dbl')], errors='ignore')

    n_enriched = extra['code'].nunique()
    print(f"  확장 지표 병합 완료 — {n_enriched:,} 코드 / {len(df.columns)} 컬럼")
    return df


# ── 3. 파생 피처 계산 ────────────────────────────────────────────────────────

def compute_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    비율·상대 피처 계산:
      - close_vs_maX : close/MAx - 1
      - bb_position  : BB 내 상대 위치 [0, 1]
      - atr_rate     : ATR14 / close
      - di_diff      : +DI - -DI
      - ichimoku_*_vs_close : 일목 기준선 / close - 1
    """
    df = df.copy()

    close = pd.to_numeric(df.get('close', pd.Series(dtype=float)), errors='coerce')

    # MA 비율
    for n in [5, 20, 60, 120]:
        ma_col = f'ma{n}'
        if ma_col in df.columns:
            ma = pd.to_numeric(df[ma_col], errors='coerce')
            df[f'close_vs_ma{n}'] = np.where(ma > 0, close / ma - 1.0, np.nan)

    # BB position
    if {'bb_upper', 'bb_lower'}.issubset(df.columns):
        bb_u = pd.to_numeric(df['bb_upper'], errors='coerce')
        bb_l = pd.to_numeric(df['bb_lower'], errors='coerce')
        bb_range = bb_u - bb_l
        df['bb_position'] = np.where(
            bb_range > 0,
            (close - bb_l) / bb_range,
            np.nan
        )

    # ATR rate
    if 'atr14' in df.columns:
        atr = pd.to_numeric(df['atr14'], errors='coerce')
        df['atr_rate'] = np.where(close > 0, atr / close, np.nan)

    # DI difference
    if {'plus_di', 'minus_di'}.issubset(df.columns):
        pdi = pd.to_numeric(df['plus_di'], errors='coerce')
        mdi = pd.to_numeric(df['minus_di'], errors='coerce')
        df['di_diff'] = pdi - mdi

    # 일목 vs close
    for col in ('ichimoku_tenkan', 'ichimoku_kijun'):
        if col in df.columns:
            val = pd.to_numeric(df[col], errors='coerce')
            df[f'{col}_vs_close'] = np.where(close > 0, val / close - 1.0, np.nan)

    # 수급 비율 (score_g 원천: inst_net_buy / volume)
    vol = pd.to_numeric(df.get('volume', pd.Series(dtype=float)), errors='coerce')
    if 'inst_net_buy' in df.columns:
        inst = pd.to_numeric(df['inst_net_buy'], errors='coerce')
        df['inst_buy_ratio'] = np.where(vol > 0, inst / vol, np.nan)
    if 'foreign_net_buy' in df.columns:
        foreign = pd.to_numeric(df['foreign_net_buy'], errors='coerce')
        df['foreign_buy_ratio'] = np.where(vol > 0, foreign / vol, np.nan)

    return df


# ── 4. 학습용 데이터셋 준비 ───────────────────────────────────────────────────

def prepare_dataset(
    df: pd.DataFrame,
    target: str = 'win',
    strategy_filter: Optional[str] = None,
    feature_groups: Optional[List[str]] = None,
) -> Tuple[pd.DataFrame, pd.Series, List[str], pd.Series, pd.DataFrame]:
    """
    X, y, feature_names, dates, meta_df 반환.

    Parameters
    ----------
    df              : load → enrich → derive 처리된 DataFrame
    target          : 'win' | 'big_win' | 'sell_rate' | 'max_pct'
    strategy_filter : 'A' | 'B' | None(전체)
    feature_groups  : 사용할 그룹 리스트 (None = 전체)

    Returns
    -------
    X            : 피처 DataFrame (NaN → -1 fill)
    y            : 타겟 Series
    feature_names: 사용된 컬럼 리스트
    dates        : buy_date → datetime Series (Walk-Forward CV용)
    meta         : 원본 메타정보 (code, sell_rate 등 포함)
    """
    from .config import TARGETS, FEATURE_GROUPS, ALL_FEATURES

    df = df.copy()

    # 전략 필터
    if strategy_filter in ('A', 'B') and 'strategy_type' in df.columns:
        df = df[df['strategy_type'] == strategy_filter].copy()

    if len(df) == 0:
        raise ValueError(f"strategy_filter='{strategy_filter}' 후 데이터가 없습니다.")

    # 타겟 생성
    if target not in TARGETS:
        raise ValueError(f"Unknown target '{target}'. 선택: {list(TARGETS.keys())}")
    task_type, target_fn = TARGETS[target]
    y = target_fn(df)

    # 피처 컬럼 결정
    if feature_groups:
        feat_cols = [f for g in feature_groups for f in FEATURE_GROUPS.get(g, [])]
    else:
        feat_cols = ALL_FEATURES

    available = [f for f in feat_cols if f in df.columns]
    missing   = [f for f in feat_cols if f not in df.columns]
    if missing:
        print(f"  누락 피처 {len(missing)}개: {missing[:8]}{'...' if len(missing) > 8 else ''}")

    X = df[available].copy()

    # NaN → -1 (CatBoost는 NaN을 인식하지만, RF를 위해 -1 채움)
    for col in X.columns:
        X[col] = pd.to_numeric(X[col], errors='coerce').fillna(-1)

    # 날짜 (Walk-Forward CV)
    dates = pd.to_datetime(df['buy_date'].astype(str), format='%Y%m%d', errors='coerce')

    # 메타 (분석·시각화용)
    meta_cols = ['code', 'code_name', 'buy_date', 'sell_date',
                 'sell_rate', 'strategy_type', 'max_high_pct', 'min_low_pct',
                 '_source_simul']
    meta = df[[c for c in meta_cols if c in df.columns]].copy()

    valid = ~y.isna()
    print(
        f"  데이터셋 확정: {valid.sum():,} 샘플 / {len(available)} 피처 / "
        f"target='{target}'({task_type})"
    )

    return X[valid], y[valid], available, dates[valid], meta[valid]
