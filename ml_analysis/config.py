# -*- coding: utf-8 -*-
"""
ml_analysis/config.py
DB 연결 팩토리, 피처 그룹 정의, 모델 기본 파라미터
"""
import sys
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from library import cf

# ── 출력 디렉토리 ────────────────────────────────────────────────────────────
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')

# ── 백테스트 DB 매핑 ─────────────────────────────────────────────────────────
SIMULATOR_DBS = {
    3: 'simulator3',
    4: 'simulator4',
    5: 'simulator5',
    6: 'simulator6',
}

# 실전/모의 운영 DB (--live 플래그 시 사용)
LIVE_DBS = {
    3: 'jackbot3_imi1',
    6: 'jackbot4_imi1',
}

# ── 피처 그룹 정의 ───────────────────────────────────────────────────────────
FEATURE_GROUPS = {
    # ① 전략 스코어 컴포넌트 (매수 당시 기록)
    'score': [
        'composite_score',
        'score_a', 'score_b', 'score_c',
        'score_d', 'score_e', 'score_f',
        'score_penalty',
    ],
    # ② MA 비율 (close / MAn - 1, 파생 피처)
    'ma_ratio': [
        'close_vs_ma5',
        'close_vs_ma20',
        'close_vs_ma60',
        'close_vs_ma120',
    ],
    # ③ 모멘텀
    'momentum': [
        'd1_diff_rate',
        'rsi14',
        'macd',
        'macd_signal',
        'macd_histogram',
        'adx',
        'plus_di',
        'minus_di',
        'di_diff',          # +DI - -DI (파생)
    ],
    # ④ 변동성
    'volatility': [
        'atr_rate',         # ATR14 / close (파생)
        'bb_bandwidth',
        'bb_position',      # (close - bb_lower) / (bb_upper - bb_lower) (파생)
    ],
    # ⑤ 거래량 / 자금흐름
    'volume': [
        'volume_ratio',
        'obv',
        'mfi14',
        'cmf20',
    ],
    # ⑥ 캔들 패턴
    'pattern': [
        'candle_pattern_score',
    ],
    # ⑦ 일목균형표
    'ichimoku': [
        'ichimoku_tenkan_vs_close',
        'ichimoku_kijun_vs_close',
    ],
    # ⑧ 기관/외국인 수급 (score_g 원천 데이터)
    'supply': [
        'inst_buy_ratio',     # inst_net_buy / volume
        'foreign_buy_ratio',  # foreign_net_buy / volume
    ],
}

ALL_FEATURES = [f for grp in FEATURE_GROUPS.values() for f in grp]

# ── 타겟 정의 ────────────────────────────────────────────────────────────────
TARGETS = {
    'win':       ('binary',     lambda df: (df['sell_rate'] > 0).astype(int)),
    'big_win':   ('binary',     lambda df: (df['sell_rate'] >= 5).astype(int)),
    'sell_rate': ('regression', lambda df: df['sell_rate']),
    'max_pct':   ('regression', lambda df: df['max_high_pct']),
}

# ── CatBoost 파라미터 ─────────────────────────────────────────────────────────
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

CATBOOST_PARAMS_REG = {
    **CATBOOST_PARAMS_CLF,
    'loss_function': 'RMSE',
    'eval_metric':   'RMSE',
}

# ── RandomForest 파라미터 ─────────────────────────────────────────────────────
RF_PARAMS = {
    'n_estimators':     300,
    'max_depth':        8,
    'min_samples_leaf': 10,
    'random_state':     42,
    'n_jobs':           -1,
}

# ── LightGBM 파라미터 ─────────────────────────────────────────────────────────
LGBM_PARAMS_CLF = {
    'n_estimators':      500,
    'learning_rate':     0.05,
    'num_leaves':        31,
    'max_depth':         -1,
    'min_child_samples': 20,
    'reg_alpha':         0.1,
    'reg_lambda':        0.1,
    'random_state':      42,
    'n_jobs':            -1,
    'verbosity':         -1,
}

LGBM_PARAMS_REG = {**LGBM_PARAMS_CLF}

# ── LASSO 파라미터 ────────────────────────────────────────────────────────────
# C = 1/lambda. 작을수록 강한 L1 정규화 → 더 많은 피처가 0이 됨
LASSO_C = 0.05

# ── TabNet 파라미터 ───────────────────────────────────────────────────────────
TABNET_PARAMS = {
    'n_d':          32,
    'n_a':          32,
    'n_steps':       5,
    'gamma':        1.3,
    'momentum':     0.02,
    'optimizer_params': {'lr': 1e-3},
    'mask_type':   'sparsemax',
    'verbose':       0,
}

TABNET_FIT_PARAMS = {
    'max_epochs':        200,
    'patience':           20,
    'batch_size':        256,
    'virtual_batch_size': 128,
}


def make_engine(db_name: str):
    """SQLAlchemy 엔진 생성"""
    from sqlalchemy import create_engine
    url = (
        f"mysql+pymysql://{cf.db_id}:{cf.db_passwd}"
        f"@{cf.db_ip}:{cf.db_port}/{db_name}?charset=utf8mb4"
    )
    return create_engine(url)
