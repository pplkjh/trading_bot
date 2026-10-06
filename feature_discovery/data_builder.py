# -*- coding: utf-8 -*-
"""
feature_discovery/data_builder.py

ml_analysis와의 근본적 차이:
  ml_analysis  : simulator all_item_db → 필터 통과한 거래 결과만 분석 (selection bias)
  feature_discovery: daily_buy_list 후보 전체 → N일 후 실제 가격으로 라벨링 (편향 없음)

흐름:
  1. daily_buy_list YYYYMMDD 테이블 → 후보 종목 + 원시 지표 로드
  2. daily_craw → N일 후 종가/고가 조회 → forward return 계산
  3. 파생 피처 계산 (MA비율, inst_buy_ratio, bb_position 등)
"""
import pandas as pd
import numpy as np
import time
from typing import List, Optional, Dict, Tuple


# ── 1. 후보 종목 로드 ─────────────────────────────────────────────────────────

# daily_buy_list 날짜 테이블에서 로드할 컬럼
# (score_a~f 없음 — 필터 이전 원시 지표)
_CANDIDATE_COLS = [
    'code', 'code_name',
    'close', 'volume',            # open/high/low 제거 — compute_features에서 미사용
    'd1_diff_rate',
    'clo5', 'clo10', 'clo20', 'clo40', 'clo60', 'clo120',
    'clo5_diff_rate', 'clo20_diff_rate',
    'vol5', 'vol20',
    'rsi14',
    'bb_upper', 'bb_lower',       # bb_middle 제거 — 미사용
    'atr14',
    'macd', 'macd_signal', 'macd_histogram',
    'adx', 'plus_di', 'minus_di',
    'obv', 'mfi14', 'cmf20',
    'ichimoku_tenkan', 'ichimoku_kijun',
    'candle_pattern_score',
    'bb_bandwidth',
    'volume_ratio',
    'inst_net_buy', 'foreign_net_buy',
]


def _get_date_tables(engine_buy, start_date: str, end_date: str) -> List[str]:
    """daily_buy_list DB에서 날짜 범위 내 YYYYMMDD 테이블 목록 반환."""
    sql = (
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'daily_buy_list' "
        "AND table_name REGEXP '^[0-9]{8}$' "
        "ORDER BY table_name"
    )
    rows = engine_buy.execute(sql).fetchall()
    all_dates = [r[0] for r in rows]
    return [d for d in all_dates if start_date <= d <= end_date]


def _load_candidates_from_table(engine_buy, date_str: str) -> Optional[pd.DataFrame]:
    """단일 YYYYMMDD 테이블에서 후보 종목 로드."""
    try:
        # 실제 존재하는 컬럼만 선택
        col_sql = (
            "SELECT column_name FROM information_schema.columns "
            f"WHERE table_schema='daily_buy_list' AND table_name='{date_str}'"
        )
        cols_in_tbl = {r[0] for r in engine_buy.execute(col_sql).fetchall()}
        sel = ['code', 'code_name'] + [c for c in _CANDIDATE_COLS[2:] if c in cols_in_tbl]
        sel_str = ', '.join(f'`{c}`' for c in sel)
        df = pd.read_sql(f"SELECT {sel_str} FROM `{date_str}`", engine_buy)
        df['date'] = date_str
        for col in ('code', 'code_name', 'date'):
            if col in df.columns:
                df[col] = df[col].astype(str)
        return df
    except Exception:
        return None


def load_all_candidates(
    start_date: str = '20230101',
    end_date: Optional[str] = None,
    sample_every: int = 1,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    daily_buy_list 전체 후보 종목 로드.

    Parameters
    ----------
    start_date   : YYYYMMDD 시작일
    end_date     : YYYYMMDD 종료일 (None = 오늘)
    sample_every : N일 간격 샘플링 (1=전체, 5=주 1회 수준 — 속도 우선시 시 사용)
    verbose      : 진행상황 출력

    Returns
    -------
    DataFrame with date + all _CANDIDATE_COLS
    """
    from .config import make_engine
    import datetime

    if end_date is None:
        end_date = datetime.datetime.now().strftime('%Y%m%d')

    engine_buy = make_engine('daily_buy_list')
    date_tables = _get_date_tables(engine_buy, start_date, end_date)
    if sample_every > 1:
        date_tables = date_tables[::sample_every]

    if verbose:
        print(f"  날짜 테이블 {len(date_tables)}개 로드 시작 ({start_date} ~ {end_date})")

    # 청크 단위 병합으로 peak 메모리 절감 (전체 리스트 보유 후 concat 대신)
    MERGE_EVERY = 100
    chunks = []
    pieces = []
    t0 = time.time()
    for i, date_str in enumerate(date_tables):
        df = _load_candidates_from_table(engine_buy, date_str)
        if df is not None and len(df) > 0:
            pieces.append(df)
        if len(pieces) >= MERGE_EVERY:
            chunks.append(pd.concat(pieces, ignore_index=True))
            pieces = []
        if verbose and (i + 1) % 50 == 0:
            elapsed = time.time() - t0
            eta = elapsed / (i + 1) * (len(date_tables) - i - 1)
            print(f"    {i+1}/{len(date_tables)} 테이블 완료  "
                  f"({elapsed:.0f}s 경과, ETA {eta:.0f}s)")

    if pieces:
        chunks.append(pd.concat(pieces, ignore_index=True))

    if not chunks:
        raise ValueError("로드된 후보 종목 데이터가 없습니다.")

    combined = pd.concat(chunks, ignore_index=True)
    del chunks  # 즉시 해제
    # 문자열 컬럼 category 변환 — 2.1M × 2 object 컬럼 ~250MB → ~8MB
    for col in ('code', 'code_name', 'date'):
        if col in combined.columns:
            combined[col] = combined[col].astype('category')
    if verbose:
        uniq_stocks = combined['code'].nunique()
        print(f"  후보 종목 로드 완료: {len(combined):,}행 / "
              f"{uniq_stocks:,} 종목 / {len(date_tables)} 날짜")
    return combined


# ── 2. daily_craw 가격 이력 로드 ────────────────────────────────────────────

def _load_price_history(
    code_names: List[str],
    engine_craw,
    verbose: bool = True,
) -> Dict[str, pd.DataFrame]:
    """
    daily_craw에서 종목별 (date, close, high) 이력 로드.
    daily_craw 테이블명 = 한국어 회사명 (code_name)

    Returns: {code_name: DataFrame(index=date_str, columns=['close','high'])}
    """
    price_dict = {}
    t0 = time.time()

    for i, cname in enumerate(code_names):
        try:
            df = pd.read_sql(
                f"SELECT date, close, high FROM `{cname}` ORDER BY date",
                engine_craw
            )
            if len(df) == 0:
                continue
            df['date'] = df['date'].astype(str)
            df = df.drop_duplicates('date').set_index('date')
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
            df['high']  = pd.to_numeric(df['high'],  errors='coerce')
            # 날짜→위치 매핑 (O(1) 조회용)
            df['_pos'] = range(len(df))
            price_dict[cname] = df
        except Exception:
            pass  # 삭제된 종목 등 무시

        if verbose and (i + 1) % 200 == 0:
            elapsed = time.time() - t0
            print(f"    가격 이력 로드: {i+1}/{len(code_names)} 종목 ({elapsed:.0f}s)")

    if verbose:
        print(f"  가격 이력 로드 완료: {len(price_dict):,} 종목 ({time.time()-t0:.0f}s)")
    return price_dict


# ── 3. N일 후 수익률 계산 ────────────────────────────────────────────────────

def _compute_fwd_returns_for_stock(
    grp: pd.DataFrame,
    price_df: pd.DataFrame,
    horizons: List[int],
) -> pd.DataFrame:
    """
    단일 종목 그룹에 대해 N일 후 수익률 컬럼 추가.
    price_df: index=date_str, columns=['close','high','_pos']
    """
    grp = grp.copy()
    date_to_pos = price_df['_pos'].to_dict()
    closes = price_df['close'].values
    highs  = price_df['high'].values
    n_prices = len(closes)

    for h in horizons:
        fwd_returns = []
        fwd_maxes   = []
        for d in grp['date']:
            pos = date_to_pos.get(str(d))
            if pos is None or pos + h >= n_prices:
                fwd_returns.append(np.nan)
                fwd_maxes.append(np.nan)
                continue
            cur = closes[pos]
            if cur <= 0:
                fwd_returns.append(np.nan)
                fwd_maxes.append(np.nan)
                continue
            fwd_close = closes[pos + h]
            fwd_max   = float(np.nanmax(highs[pos + 1:pos + h + 1]))
            fwd_returns.append(fwd_close / cur - 1.0)
            fwd_maxes.append(fwd_max / cur - 1.0)
        grp[f'fwd_return_{h}d'] = fwd_returns
        grp[f'fwd_max_{h}d']    = fwd_maxes

    return grp


def attach_forward_returns(
    df: pd.DataFrame,
    price_dict: Dict[str, pd.DataFrame],
    horizons: List[int],
    verbose: bool = True,
) -> pd.DataFrame:
    """
    후보 종목 DataFrame에 N일 후 수익률 컬럼 추가.
    code_name 기준으로 daily_craw 가격 이력과 조인.
    """
    df = df.copy()
    df['date'] = df['date'].astype(str)

    pieces = []
    missing = 0
    t0 = time.time()

    for i, (cname, grp) in enumerate(df.groupby('code_name', sort=False, observed=True)):
        if cname not in price_dict:
            missing += 1
            # 라벨 컬럼은 NaN으로 채워서 포함
            for h in horizons:
                grp = grp.copy()
                grp[f'fwd_return_{h}d'] = np.nan
                grp[f'fwd_max_{h}d']    = np.nan
            pieces.append(grp)
            continue
        pieces.append(_compute_fwd_returns_for_stock(grp, price_dict[cname], horizons))

        if verbose and (i + 1) % 300 == 0:
            print(f"    forward return 계산: {i+1} 종목 ({time.time()-t0:.0f}s)")

    result = pd.concat(pieces, ignore_index=True)
    if verbose and missing > 0:
        print(f"  가격 이력 없는 종목: {missing:,}개 (라벨=NaN)")
    return result


# ── 3.5 NASDAQ/SOX 지수 join ─────────────────────────────────────────────────

def _load_nasdaq_data(engine_craw) -> Optional[pd.DataFrame]:
    """
    daily_craw DB에서 nasdaq_index, sox_index 로드 후 피처 계산.

    반환: DataFrame(index=date_str YYYYMMDD, columns=[nasdaq_1d_ret, nasdaq_5d_ret, sox_1d_ret])
    None if 테이블 없음.
    """
    try:
        nq = pd.read_sql("SELECT date, close FROM nasdaq_index ORDER BY date", engine_craw)
        nq['date'] = nq['date'].astype(str)
        nq = nq.drop_duplicates('date').sort_values('date').reset_index(drop=True)
        nq['close'] = pd.to_numeric(nq['close'], errors='coerce')
        nq['nasdaq_1d_ret'] = nq['close'].pct_change(1)
        nq['nasdaq_5d_ret'] = nq['close'].pct_change(5)
        nq['date_dt'] = pd.to_datetime(nq['date'], format='%Y%m%d')
    except Exception:
        return None

    try:
        sx = pd.read_sql("SELECT date, close FROM sox_index ORDER BY date", engine_craw)
        sx['date'] = sx['date'].astype(str)
        sx = sx.drop_duplicates('date').sort_values('date').reset_index(drop=True)
        sx['close'] = pd.to_numeric(sx['close'], errors='coerce')
        sx['sox_1d_ret'] = sx['close'].pct_change(1)
        sx['date_dt'] = pd.to_datetime(sx['date'], format='%Y%m%d')
        nq = nq.merge(sx[['date_dt', 'sox_1d_ret']], on='date_dt', how='left')
    except Exception:
        nq['sox_1d_ret'] = np.nan

    return nq[['date_dt', 'nasdaq_1d_ret', 'nasdaq_5d_ret', 'sox_1d_ret']]


def attach_nasdaq_features(df: pd.DataFrame, engine_craw, verbose: bool = True) -> pd.DataFrame:
    """
    한국 날짜 T에 NASDAQ T-1 데이터를 join.

    미국 장은 한국 T일 새벽에 마감 → T-1 NASDAQ 종가는 한국 T일 장 시작 전 알 수 있음.
    pd.merge_asof로 한국 T-1일 이전 가장 최근 미국 거래일을 backward 매칭.
    """
    nasdaq_df = _load_nasdaq_data(engine_craw)
    if nasdaq_df is None or nasdaq_df.empty:
        if verbose:
            print("  [nasdaq] 데이터 없음 — backfill_nasdaq_data.py 먼저 실행 필요")
        return df

    df = df.copy()
    # 한국 T일 → T-1일로 이동 후 backward merge (주말/공휴일 자동 처리)
    kor_dates = pd.to_datetime(df['date'].astype(str), format='%Y%m%d')
    df['_kor_date_m1'] = kor_dates - pd.Timedelta(days=1)

    nasdaq_sorted = nasdaq_df.sort_values('date_dt')
    df_sorted = df.sort_values('_kor_date_m1')

    merged = pd.merge_asof(
        df_sorted,
        nasdaq_sorted,
        left_on='_kor_date_m1',
        right_on='date_dt',
        direction='backward',
    )
    merged = merged.drop(columns=['_kor_date_m1', 'date_dt'], errors='ignore')

    if verbose:
        valid = merged['nasdaq_1d_ret'].notna().sum()
        print(f"  [nasdaq] join 완료: {valid:,}행에 nasdaq 피처 부착")

    return merged


# ── 4. 파생 피처 계산 ────────────────────────────────────────────────────────

def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """raw daily_buy_list 컬럼 → ML 피처 계산."""
    df = df.copy()

    close = pd.to_numeric(df.get('close', pd.Series(dtype=float)), errors='coerce')
    vol   = pd.to_numeric(df.get('volume', pd.Series(dtype=float)), errors='coerce')

    # MA 비율 (close/MAn - 1)
    for n in [5, 20, 60, 120]:
        clo_col = f'clo{n}'
        if clo_col in df.columns:
            ma = pd.to_numeric(df[clo_col], errors='coerce')
            df[f'close_vs_clo{n}'] = np.where(ma > 0, close / ma - 1.0, np.nan)

    # 거래량 가속 비율
    if {'vol5', 'vol20'}.issubset(df.columns):
        v5  = pd.to_numeric(df['vol5'],  errors='coerce')
        v20 = pd.to_numeric(df['vol20'], errors='coerce')
        df['vol_ratio_5_20'] = np.where(v20 > 0, v5 / v20, np.nan)

    # BB position
    if {'bb_upper', 'bb_lower'}.issubset(df.columns):
        bb_u = pd.to_numeric(df['bb_upper'], errors='coerce')
        bb_l = pd.to_numeric(df['bb_lower'], errors='coerce')
        rng  = bb_u - bb_l
        df['bb_position'] = np.where(rng > 0, (close - bb_l) / rng, np.nan)

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

    # 수급 비율
    if 'inst_net_buy' in df.columns:
        inst = pd.to_numeric(df['inst_net_buy'], errors='coerce')
        df['inst_buy_ratio'] = np.where(vol > 0, inst / vol, np.nan)
    if 'foreign_net_buy' in df.columns:
        foreign = pd.to_numeric(df['foreign_net_buy'], errors='coerce')
        df['foreign_buy_ratio'] = np.where(vol > 0, foreign / vol, np.nan)

    return df


# ── 5. ML용 데이터셋 준비 ────────────────────────────────────────────────────

def prepare_dataset(
    df: pd.DataFrame,
    horizon: int = 10,
    label_type: str = 'win',
    feature_groups: Optional[List[str]] = None,
) -> Tuple[pd.DataFrame, pd.Series, List[str], pd.Series, pd.DataFrame]:
    """
    X, y, feature_names, dates, meta 반환.

    Parameters
    ----------
    df          : build_dataset() 결과
    horizon     : 예측 호라이즌 (거래일)
    label_type  : 'win'     — fwd_return > 0 (이진)
                  'big_win' — fwd_return > 3% (이진)
                  'return'  — 연속 수익률
                  'max'     — N일 내 최대 상승률
    feature_groups : 사용할 그룹 리스트 (None = 전체)
    """
    from .config import FEATURE_GROUPS, ALL_FEATURES

    df = df.copy()

    label_col = f'fwd_return_{horizon}d' if label_type in ('win', 'big_win', 'return') \
                else f'fwd_max_{horizon}d'

    if label_col not in df.columns:
        raise ValueError(f"라벨 컬럼 '{label_col}' 없음. attach_forward_returns() 먼저 실행 필요.")

    # 라벨이 있는 행만
    df = df[df[label_col].notna()].copy()

    # supply 그룹 포함 시 — inst/foreign 데이터가 없는 기간 행 제거
    # backfill 미수집 기간(pre-2024)의 NaN→-1 채움이 모델에게 기간 효과를 학습시키는 것을 방지
    if feature_groups and 'supply' in feature_groups:
        supply_cols = [c for c in ['inst_buy_ratio', 'foreign_buy_ratio'] if c in df.columns]
        if supply_cols:
            before = len(df)
            df = df[df[supply_cols].notna().any(axis=1)].copy()
            dropped = before - len(df)
            if dropped > 0:
                print(f"  [supply NaN 제거] {dropped:,}행 제거 ({before:,} → {len(df):,})")
                print(f"  → 유효 기간: {df['date'].min()} ~ {df['date'].max()}")

    # nasdaq 그룹 포함 시 — backfill 이전 기간 NaN 행 제거
    if feature_groups and 'nasdaq' in feature_groups:
        nq_cols = [c for c in ['nasdaq_1d_ret', 'nasdaq_5d_ret', 'sox_1d_ret'] if c in df.columns]
        if nq_cols:
            before = len(df)
            df = df[df[nq_cols].notna().any(axis=1)].copy()
            dropped = before - len(df)
            if dropped > 0:
                print(f"  [nasdaq NaN 제거] {dropped:,}행 제거 ({before:,} → {len(df):,})")
                print(f"  → 유효 기간: {df['date'].min()} ~ {df['date'].max()}")

    if label_type == 'win':
        y = (df[label_col] > 0).astype(int)
        task_type = 'binary'
    elif label_type == 'big_win':
        y = (df[label_col] > 0.03).astype(int)
        task_type = 'binary'
    elif label_type == 'return':
        y = df[label_col].astype(float)
        task_type = 'regression'
    else:  # max
        y = df[label_col].astype(float)
        task_type = 'regression'

    # 피처 선택
    if feature_groups:
        feat_cols = [f for g in feature_groups for f in FEATURE_GROUPS.get(g, [])]
    else:
        feat_cols = ALL_FEATURES

    available = [f for f in feat_cols if f in df.columns]
    missing   = [f for f in feat_cols if f not in df.columns]
    if missing:
        print(f"  누락 피처 {len(missing)}개: {missing[:8]}{'...' if len(missing)>8 else ''}")

    X = df[available].copy()
    for col in X.columns:
        X[col] = pd.to_numeric(X[col], errors='coerce').fillna(-1)

    dates = pd.to_datetime(df['date'].astype(str), format='%Y%m%d', errors='coerce')

    meta = df[['code', 'code_name', 'date', label_col]].copy()
    meta.columns = ['code', 'code_name', 'date', 'label']

    print(f"  데이터셋: {len(X):,} 샘플 / {len(available)} 피처 / "
          f"target=fwd_return_{horizon}d({task_type})")
    if task_type == 'binary':
        pos_rate = y.mean()
        print(f"  양성 비율: {pos_rate:.1%}  ({y.sum():,}/{len(y):,})")

    return X, y, available, dates, meta


# ── 6. 통합 빌더 ─────────────────────────────────────────────────────────────

def build_dataset(
    start_date: str = '20230101',
    end_date: Optional[str] = None,
    horizons: List[int] = None,
    sample_every: int = 1,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    daily_buy_list 후보 → forward return 라벨 → 파생 피처 계산 → 반환.

    Parameters
    ----------
    start_date   : YYYYMMDD
    end_date     : YYYYMMDD (None = 오늘)
    horizons     : forward return 계산할 거래일 수 리스트 (기본 [5, 10, 15])
    sample_every : N일마다 1개 샘플링 (빠른 테스트 시 5~10 권장)
    verbose      : 진행상황 출력

    Returns
    -------
    DataFrame:
      - 원시 지표 컬럼 (daily_buy_list)
      - 파생 피처 컬럼 (close_vs_clo5, bb_position, inst_buy_ratio 등)
      - fwd_return_Nd, fwd_max_Nd (N ∈ horizons)
    """
    from .config import make_engine, DEFAULT_HORIZONS
    import datetime

    if horizons is None:
        horizons = DEFAULT_HORIZONS
    if end_date is None:
        end_date = datetime.datetime.now().strftime('%Y%m%d')

    engine_craw = make_engine('daily_craw')

    # Step 1: 후보 종목 로드
    if verbose:
        print(f"\n[Step 1] 후보 종목 로드  ({start_date} ~ {end_date})")
    df = load_all_candidates(start_date, end_date, sample_every, verbose)

    # Step 2: 가격 이력 로드
    if verbose:
        print(f"\n[Step 2] daily_craw 가격 이력 로드 ({df['code_name'].nunique():,} 종목)")
    code_names = df['code_name'].dropna().unique().tolist()
    price_dict = _load_price_history(code_names, engine_craw, verbose)

    # Step 3: forward return 계산
    if verbose:
        print(f"\n[Step 3] {horizons}일 forward return 계산")
    df = attach_forward_returns(df, price_dict, horizons, verbose)

    # Step 3.5: NASDAQ/SOX 지수 join (테이블 없으면 자동 스킵)
    if verbose:
        print(f"\n[Step 3.5] NASDAQ/SOX join")
    df = attach_nasdaq_features(df, engine_craw, verbose)

    # Step 4: 파생 피처 계산
    if verbose:
        print(f"\n[Step 4] 파생 피처 계산")
    df = compute_features(df)

    # 불필요한 중간 컬럼 제거
    drop_cols = ['open', 'high', 'low',
                 'clo10', 'clo40', 'clo80',
                 'yes_clo5', 'yes_clo10', 'yes_clo20',
                 'bb_upper', 'bb_middle', 'bb_lower',
                 'ichimoku_tenkan', 'ichimoku_kijun',
                 'inst_net_buy', 'foreign_net_buy',
                 'vol5', 'vol20', 'atr14']
    df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors='ignore')

    if verbose:
        fwd_col = f'fwd_return_{horizons[0]}d'
        valid = df[fwd_col].notna().sum()
        print(f"\n  최종 데이터셋: {len(df):,}행 / 라벨 유효: {valid:,}행 / {len(df.columns)} 컬럼")

    return df
