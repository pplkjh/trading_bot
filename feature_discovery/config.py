# -*- coding: utf-8 -*-
"""
feature_discovery/config.py

ml_analysis와 차이점:
  - 입력: daily_buy_list 후보 종목 전체 (필터 이전)
  - 라벨: N일 후 실제 가격 상승률 (daily_craw 직접 계산)
  - 목적: 어떤 원시 피처가 실제 주가 상승을 예측하는가 (sim=7 설계 기반)
"""
import sys, os
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from library import cf

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')

# ── 예측 호라이즌 (거래일 기준) ─────────────────────────────────────────────
DEFAULT_HORIZONS = [5, 10, 15]

# ── 피처 그룹 (daily_buy_list 원본 컬럼 + 파생) ──────────────────────────────
# 중요: score_a~f 없음 — 필터 이전 원시 지표만 사용
FEATURE_GROUPS = {
    # 단기 가격 모멘텀
    'price': [
        'd1_diff_rate',         # 전일 대비 등락률
        'close_vs_clo5',        # close/MA5 - 1
        'close_vs_clo20',       # close/MA20 - 1
        'close_vs_clo60',       # close/MA60 - 1
        'close_vs_clo120',      # close/MA120 - 1
        'clo5_diff_rate',       # MA5 기울기
        'clo20_diff_rate',      # MA20 기울기
    ],
    # 거래량 / 수급강도
    'volume': [
        'vol_ratio_5_20',       # vol5/vol20 — 단기 거래량 가속
        'volume_ratio',         # vol5/vol20 (migration 컬럼, 위와 동일 개념)
        'obv',
        'mfi14',
        'cmf20',
    ],
    # 모멘텀 오실레이터
    'momentum': [
        'rsi14',
        'macd',
        'macd_signal',
        'macd_histogram',
        'adx',
        'plus_di',
        'minus_di',
        'di_diff',              # +DI - -DI
    ],
    # 변동성 / BB 구조
    'volatility': [
        'bb_position',          # (close - bb_lower) / (bb_upper - bb_lower)
        'bb_bandwidth',
        'atr_rate',             # atr14 / close
    ],
    # 캔들 패턴
    'pattern': [
        'candle_pattern_score',
    ],
    # 일목균형표
    'ichimoku': [
        'ichimoku_tenkan_vs_close',
        'ichimoku_kijun_vs_close',
    ],
    # 기관/외국인 수급 (backfill 후 유효)
    'supply': [
        'inst_buy_ratio',       # inst_net_buy / volume
        'foreign_buy_ratio',    # foreign_net_buy / volume
    ],
    # 미국 시장 지수 (전날 나스닥/SOX — 한국 T일 매수 시 알 수 있는 정보)
    'nasdaq': [
        'nasdaq_1d_ret',        # 전날 NASDAQ Composite 수익률
        'nasdaq_5d_ret',        # 5거래일 NASDAQ 추세
        'sox_1d_ret',           # 전날 SOX (필라델피아 반도체) 수익률
    ],
}

ALL_FEATURES = [f for grp in FEATURE_GROUPS.values() for f in grp]

# ── CatBoost 파라미터 ──────────────────────────────────────────────────────
CATBOOST_PARAMS_CLF = {
    'iterations':          500,
    'learning_rate':       0.05,
    'depth':               6,
    'l2_leaf_reg':         3,
    'loss_function':       'Logloss',
    'eval_metric':         'AUC',
    'random_seed':         42,
    'verbose':             False,
    'allow_writing_files': False,
}
CATBOOST_PARAMS_REG = {**CATBOOST_PARAMS_CLF, 'loss_function': 'RMSE', 'eval_metric': 'RMSE'}

LGBM_PARAMS_CLF = {
    'n_estimators':      500,
    'learning_rate':     0.05,
    'num_leaves':        63,    # 더 큰 데이터셋 → leaf 수 증가
    'max_depth':         -1,
    'min_child_samples': 50,    # 대용량이므로 더 보수적으로
    'reg_alpha':         0.1,
    'reg_lambda':        0.1,
    'random_state':      42,
    'n_jobs':            -1,
    'verbosity':         -1,
}
LGBM_PARAMS_REG = {**LGBM_PARAMS_CLF}
LASSO_C = 0.05


def make_engine(db_name: str):
    from sqlalchemy import create_engine
    url = (f"mysql+pymysql://{cf.db_id}:{cf.db_passwd}"
           f"@{cf.db_ip}:{cf.db_port}/{db_name}?charset=utf8mb4")
    return create_engine(url)
