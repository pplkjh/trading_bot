# -*- coding: utf-8 -*-
"""
ml_analysis/train.py
CatBoost / RandomForest 학습 + Walk-Forward 시계열 교차검증

시계열 데이터는 미래 데이터로 과거를 학습하면 look-ahead bias가 발생하므로,
날짜 기준 Walk-Forward CV 를 사용해야 합니다.
"""
import numpy as np
import pandas as pd
from typing import Optional, List


# ── Walk-Forward CV ──────────────────────────────────────────────────────────

class WalkForwardCV:
    """
    날짜 기준 Walk-Forward 교차검증.

    전체 기간을 n_splits+1 구간으로 나눠:
      - Fold i:  [시작 ~ i번째 경계] 학습 / [i번째 ~ i+1번째 경계] 검증
    """

    def __init__(self, n_splits: int = 5, min_train_size: int = 100):
        self.n_splits = n_splits
        self.min_train_size = min_train_size

    def split(self, X, dates: pd.Series):
        """
        Yields (train_indices, val_indices).
        dates : buy_date → pd.Timestamp Series (X 와 동일 index)
        """
        dates = pd.Series(dates.values)  # re-index 0..n
        sorted_dates = sorted(dates.dropna().unique())
        n_dates = len(sorted_dates)

        if n_dates < self.n_splits + 1:
            # 날짜가 적으면 단순 비율 split
            cut = int(len(dates) * 0.8)
            yield np.arange(cut), np.arange(cut, len(dates))
            return

        fold_size = max(1, n_dates // (self.n_splits + 1))

        for i in range(1, self.n_splits + 1):
            train_end = sorted_dates[min(i * fold_size - 1, n_dates - 2)]
            val_end   = sorted_dates[min((i + 1) * fold_size - 1, n_dates - 1)]

            train_idx = np.where(dates <= train_end)[0]
            val_idx   = np.where((dates > train_end) & (dates <= val_end))[0]

            if len(train_idx) < self.min_train_size or len(val_idx) == 0:
                continue

            yield train_idx, val_idx


# ── CatBoost ─────────────────────────────────────────────────────────────────

def train_catboost(
    X: pd.DataFrame,
    y: pd.Series,
    dates: pd.Series,
    task_type: str = 'binary',
    params: Optional[dict] = None,
    n_splits: int = 5,
) -> dict:
    """
    CatBoost 학습 + Walk-Forward CV.

    Returns
    -------
    dict {model, cv_scores, feature_importance, model_type}
    """
    try:
        from catboost import CatBoostClassifier, CatBoostRegressor
    except ImportError:
        raise ImportError("CatBoost 미설치: pip install catboost")

    from .config import CATBOOST_PARAMS_CLF, CATBOOST_PARAMS_REG

    if params is None:
        params = CATBOOST_PARAMS_REG.copy() if task_type == 'regression' else CATBOOST_PARAMS_CLF.copy()

    ModelClass = CatBoostRegressor if task_type == 'regression' else CatBoostClassifier

    cv = WalkForwardCV(n_splits=n_splits)
    cv_scores = []

    for i, (tr_idx, val_idx) in enumerate(cv.split(X, dates)):
        X_tr, X_val = X.iloc[tr_idx], X.iloc[val_idx]
        y_tr, y_val = y.iloc[tr_idx], y.iloc[val_idx]

        m = ModelClass(**params)
        m.fit(X_tr, y_tr, eval_set=(X_val, y_val),
              early_stopping_rounds=50, verbose=False)

        score = _score(m, X_val, y_val, task_type)
        score['fold'] = i
        score['n_train'] = len(tr_idx)
        score['n_val']   = len(val_idx)
        cv_scores.append(score)
        _print_fold(i, score, task_type)

    # 전체 데이터로 최종 모델
    final = ModelClass(**params)
    final.fit(X, y, verbose=False)

    feat_imp = pd.Series(
        final.get_feature_importance(),
        index=X.columns,
        name='importance'
    ).sort_values(ascending=False)

    return {
        'model':              final,
        'cv_scores':          cv_scores,
        'feature_importance': feat_imp,
        'model_type':         f'CatBoost-{task_type}',
        'task_type':          task_type,
    }


# ── RandomForest ─────────────────────────────────────────────────────────────

def train_random_forest(
    X: pd.DataFrame,
    y: pd.Series,
    dates: pd.Series,
    task_type: str = 'binary',
    params: Optional[dict] = None,
    n_splits: int = 5,
) -> dict:
    """RandomForest 학습 + Walk-Forward CV."""
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.impute import SimpleImputer
    from .config import RF_PARAMS

    if params is None:
        params = RF_PARAMS.copy()

    ModelClass = RandomForestRegressor if task_type == 'regression' else RandomForestClassifier

    # RF는 NaN을 처리 못하므로 median imputation
    imp = SimpleImputer(strategy='median')
    X_imp = pd.DataFrame(imp.fit_transform(X), columns=X.columns, index=X.index)

    cv = WalkForwardCV(n_splits=n_splits)
    cv_scores = []

    for i, (tr_idx, val_idx) in enumerate(cv.split(X_imp, dates)):
        X_tr, X_val = X_imp.iloc[tr_idx], X_imp.iloc[val_idx]
        y_tr, y_val = y.iloc[tr_idx], y.iloc[val_idx]

        m = ModelClass(**params)
        m.fit(X_tr, y_tr)

        score = _score(m, X_val, y_val, task_type)
        score['fold'] = i
        score['n_train'] = len(tr_idx)
        score['n_val']   = len(val_idx)
        cv_scores.append(score)
        _print_fold(i, score, task_type)

    final = ModelClass(**params)
    final.fit(X_imp, y)

    feat_imp = pd.Series(
        final.feature_importances_,
        index=X.columns,
        name='importance'
    ).sort_values(ascending=False)

    return {
        'model':              final,
        'cv_scores':          cv_scores,
        'feature_importance': feat_imp,
        'model_type':         f'RandomForest-{task_type}',
        'task_type':          task_type,
        '_imputer':           imp,
    }


# ── 헬퍼 ────────────────────────────────────────────────────────────────────

def _score(model, X_val, y_val, task_type: str) -> dict:
    if task_type == 'binary':
        from sklearn.metrics import roc_auc_score, accuracy_score
        try:
            prob = model.predict_proba(X_val)[:, 1]
            auc  = roc_auc_score(y_val, prob)
        except Exception:
            auc = float('nan')
        pred = model.predict(X_val)
        return {'auc': auc, 'accuracy': accuracy_score(y_val, pred)}
    else:
        from sklearn.metrics import r2_score, mean_squared_error
        pred = model.predict(X_val)
        r2   = r2_score(y_val, pred)
        rmse = np.sqrt(mean_squared_error(y_val, pred))
        return {'r2': r2, 'rmse': rmse}


def _print_fold(i: int, score: dict, task_type: str):
    if task_type == 'binary':
        print(f"    Fold {i}  AUC={score.get('auc', 0):.4f}  "
              f"Acc={score.get('accuracy', 0):.4f}  "
              f"(train={score['n_train']}, val={score['n_val']})")
    else:
        print(f"    Fold {i}  R²={score.get('r2', 0):.4f}  "
              f"RMSE={score.get('rmse', 0):.4f}  "
              f"(train={score['n_train']}, val={score['n_val']})")


# ── LightGBM ─────────────────────────────────────────────────────────────────

def train_lightgbm(
    X: pd.DataFrame,
    y: pd.Series,
    dates: pd.Series,
    task_type: str = 'binary',
    params: Optional[dict] = None,
    n_splits: int = 5,
) -> dict:
    """LightGBM 학습 + Walk-Forward CV. CatBoost 대비 5~10배 빠름."""
    try:
        import lightgbm as lgb
    except ImportError:
        raise ImportError("LightGBM 미설치: pip install lightgbm")

    from .config import LGBM_PARAMS_CLF, LGBM_PARAMS_REG

    if params is None:
        params = LGBM_PARAMS_REG.copy() if task_type == 'regression' else LGBM_PARAMS_CLF.copy()

    ModelClass = lgb.LGBMRegressor if task_type == 'regression' else lgb.LGBMClassifier

    cv = WalkForwardCV(n_splits=n_splits)
    cv_scores = []

    for i, (tr_idx, val_idx) in enumerate(cv.split(X, dates)):
        X_tr, X_val = X.iloc[tr_idx], X.iloc[val_idx]
        y_tr, y_val = y.iloc[tr_idx], y.iloc[val_idx]

        m = ModelClass(**params)
        m.fit(
            X_tr, y_tr,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(-1)],
        )

        score = _score(m, X_val, y_val, task_type)
        score['fold'] = i
        score['n_train'] = len(tr_idx)
        score['n_val']   = len(val_idx)
        cv_scores.append(score)
        _print_fold(i, score, task_type)

    final = ModelClass(**params)
    final.fit(X, y, callbacks=[lgb.log_evaluation(-1)])

    feat_imp = pd.Series(
        final.feature_importances_,
        index=X.columns,
        name='importance'
    ).sort_values(ascending=False)

    return {
        'model':              final,
        'cv_scores':          cv_scores,
        'feature_importance': feat_imp,
        'model_type':         f'LightGBM-{task_type}',
        'task_type':          task_type,
    }


# ── LASSO Logistic Regression ─────────────────────────────────────────────────

def train_lasso(
    X: pd.DataFrame,
    y: pd.Series,
    dates: pd.Series,
    task_type: str = 'binary',
    C: Optional[float] = None,
    n_splits: int = 5,
) -> dict:
    """
    LASSO (L1 정규화) 선형 모델.

    계수(coeff)가 0인 피처 = 통계적으로 불필요.
    비선형 모델(CatBoost 등)과 비교해 "선형 효과만으로 얼마나 설명되는가" 파악용.
    StandardScaler 전처리 필수 (정규화되지 않으면 L1 계수 비교 불가).
    """
    from sklearn.linear_model import LogisticRegression, Lasso
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline
    from .config import LASSO_C

    c_val = C if C is not None else LASSO_C

    if task_type == 'binary':
        model_inner = LogisticRegression(
            penalty='l1', solver='liblinear', C=c_val,
            max_iter=1000, random_state=42,
        )
    else:
        # sklearn Lasso loss는 이미 1/N으로 정규화됨 → alpha는 N과 무관하게 고정
        model_inner = Lasso(alpha=1.0 / (2 * c_val), max_iter=20000, random_state=42)

    cv = WalkForwardCV(n_splits=n_splits)
    cv_scores = []

    for i, (tr_idx, val_idx) in enumerate(cv.split(X, dates)):
        X_tr_raw, X_val_raw = X.iloc[tr_idx], X.iloc[val_idx]
        y_tr, y_val = y.iloc[tr_idx], y.iloc[val_idx]

        scaler = StandardScaler()
        X_tr_s = scaler.fit_transform(X_tr_raw.fillna(0))
        X_val_s = scaler.transform(X_val_raw.fillna(0))

        m = (LogisticRegression(penalty='l1', solver='liblinear', C=c_val,
                                max_iter=1000, random_state=42)
             if task_type == 'binary'
             else Lasso(alpha=1.0 / (2 * c_val), max_iter=20000))
        m.fit(X_tr_s, y_tr)

        score = _score_sklearn(m, X_val_s, y_val, task_type)
        score['fold'] = i
        score['n_train'] = len(tr_idx)
        score['n_val']   = len(val_idx)
        cv_scores.append(score)
        _print_fold(i, score, task_type)

    # 전체 데이터 최종 모델
    scaler_final = StandardScaler()
    X_scaled = scaler_final.fit_transform(X.fillna(0))

    final = (LogisticRegression(penalty='l1', solver='liblinear', C=c_val,
                                max_iter=1000, random_state=42)
             if task_type == 'binary'
             else Lasso(alpha=1.0 / (2 * c_val), max_iter=20000, random_state=42))
    final.fit(X_scaled, y)

    # LASSO 계수 = 피처 중요도
    coef = final.coef_.flatten() if task_type == 'binary' else final.coef_
    feat_imp = pd.Series(
        np.abs(coef), index=X.columns, name='importance'
    ).sort_values(ascending=False)

    # 0이 된 피처 수 (L1 sparsity)
    n_zero = int((np.abs(coef) < 1e-10).sum())
    print(f"  LASSO sparsity: {n_zero}/{len(coef)} 피처가 0 (제거됨)")

    return {
        'model':              final,
        'cv_scores':          cv_scores,
        'feature_importance': feat_imp,
        'coef':               pd.Series(coef, index=X.columns).sort_values(),
        'model_type':         f'LASSO-{task_type}',
        'task_type':          task_type,
        '_scaler':            scaler_final,
        'n_zero_features':    n_zero,
    }


# ── Permutation Importance ────────────────────────────────────────────────────

def compute_permutation_importance(
    result: dict,
    X: pd.DataFrame,
    y: pd.Series,
    n_repeats: int = 10,
    sample_n: int = 3000,
) -> pd.Series:
    """
    모델-agnostic Permutation Importance.

    피처 하나를 무작위 셔플 → 성능 하락폭 = 그 피처의 실제 기여도.
    CatBoost 내장 importance 와 비교해 "진짜로 중요한가" 이중 검증용.
    """
    from sklearn.inspection import permutation_importance

    model = result['model']
    task_type = result['task_type']

    # 표본 추출 (전체 데이터가 크면 느림)
    idx = np.random.choice(len(X), min(sample_n, len(X)), replace=False)
    X_s = X.iloc[idx]
    y_s = y.iloc[idx]

    # LASSO는 스케일러 전처리 필요
    if '_scaler' in result:
        X_s = pd.DataFrame(
            result['_scaler'].transform(X_s.fillna(0)),
            columns=X_s.columns
        )

    scoring = 'roc_auc' if task_type == 'binary' else 'r2'

    print(f"  Permutation Importance 계산 중 (n_repeats={n_repeats}, n={len(X_s)})...")
    perm = permutation_importance(model, X_s, y_s,
                                  n_repeats=n_repeats,
                                  scoring=scoring,
                                  random_state=42,
                                  n_jobs=-1)

    perm_imp = pd.Series(
        perm.importances_mean,
        index=X.columns,
        name='perm_importance'
    ).sort_values(ascending=False)

    print(f"\n  Permutation Importance Top 15")
    print(f"  {'피처':<35} {'mean':>8}  {'std':>7}")
    print(f"  {'-'*55}")
    top15_idx = perm_imp.head(15).index
    for feat in top15_idx:
        fidx = list(X.columns).index(feat)
        mean = perm.importances_mean[fidx]
        std  = perm.importances_std[fidx]
        bar  = '█' * max(1, int(mean / max(perm_imp.max(), 1e-9) * 20))
        print(f"  {feat:<35} {mean:8.4f}  {std:7.4f}  {bar}")

    return perm_imp


# ── TabNet ────────────────────────────────────────────────────────────────────

def train_tabnet(
    X: pd.DataFrame,
    y: pd.Series,
    dates: pd.Series,
    task_type: str = 'binary',
    params: Optional[dict] = None,
    fit_params: Optional[dict] = None,
    n_splits: int = 5,
) -> dict:
    """
    TabNet (Google Research) — Attention 기반 tabular 딥러닝.

    feature_importances_ : 전역 피처 중요도
    explain()            : 거래별 attention mask (어느 피처를 집중했는지)

    pytorch-tabnet 필요: pip install pytorch-tabnet
    """
    try:
        from pytorch_tabnet.tab_model import TabNetClassifier, TabNetRegressor
    except ImportError:
        raise ImportError("TabNet 미설치: pip install pytorch-tabnet")

    from sklearn.preprocessing import StandardScaler
    from .config import TABNET_PARAMS, TABNET_FIT_PARAMS

    if params is None:
        params = TABNET_PARAMS.copy()
    if fit_params is None:
        fit_params = TABNET_FIT_PARAMS.copy()

    ModelClass = TabNetRegressor if task_type == 'regression' else TabNetClassifier

    # TabNet: numpy array 필요, NaN → 0 처리
    scaler = StandardScaler()
    X_arr = scaler.fit_transform(X.fillna(0)).astype(np.float32)
    y_arr = y.values.astype(np.float32 if task_type == 'regression' else np.int64)

    cv = WalkForwardCV(n_splits=n_splits)
    cv_scores = []

    for i, (tr_idx, val_idx) in enumerate(cv.split(X, dates)):
        X_tr, X_val = X_arr[tr_idx], X_arr[val_idx]
        y_tr, y_val_arr = y_arr[tr_idx], y_arr[val_idx]

        m = ModelClass(**params)
        m.fit(
            X_tr, y_tr,
            eval_set=[(X_val, y_val_arr)],
            eval_name=['val'],
            **fit_params,
        )

        score = _score_tabnet(m, X_val, y.iloc[val_idx], task_type)
        score['fold'] = i
        score['n_train'] = len(tr_idx)
        score['n_val']   = len(val_idx)
        cv_scores.append(score)
        _print_fold(i, score, task_type)

    # 전체 데이터 최종 모델
    final = ModelClass(**params)
    final.fit(X_arr, y_arr, **{**fit_params, 'eval_set': None})

    feat_imp = pd.Series(
        final.feature_importances_,
        index=X.columns,
        name='importance'
    ).sort_values(ascending=False)

    return {
        'model':              final,
        'cv_scores':          cv_scores,
        'feature_importance': feat_imp,
        'model_type':         f'TabNet-{task_type}',
        'task_type':          task_type,
        '_scaler':            scaler,
        '_X_arr':             X_arr,   # explain() 용
    }


def _score_sklearn(model, X_val, y_val, task_type: str) -> dict:
    """StandardScaler 전처리된 sklearn 모델 평가"""
    if task_type == 'binary':
        from sklearn.metrics import roc_auc_score, accuracy_score
        try:
            prob = model.predict_proba(X_val)[:, 1]
            auc  = roc_auc_score(y_val, prob)
        except Exception:
            auc = float('nan')
        return {'auc': auc, 'accuracy': accuracy_score(y_val, model.predict(X_val))}
    else:
        from sklearn.metrics import r2_score, mean_squared_error
        pred = model.predict(X_val)
        return {'r2': r2_score(y_val, pred),
                'rmse': np.sqrt(mean_squared_error(y_val, pred))}


def _score_tabnet(model, X_val_arr, y_val: pd.Series, task_type: str) -> dict:
    """TabNet 전용 평가 (numpy array 입력)"""
    if task_type == 'binary':
        from sklearn.metrics import roc_auc_score, accuracy_score
        prob = model.predict_proba(X_val_arr)[:, 1]
        pred = (prob >= 0.5).astype(int)
        return {'auc': roc_auc_score(y_val, prob),
                'accuracy': accuracy_score(y_val, pred)}
    else:
        from sklearn.metrics import r2_score, mean_squared_error
        pred = model.predict(X_val_arr)
        return {'r2': r2_score(y_val, pred),
                'rmse': np.sqrt(mean_squared_error(y_val, pred))}


def print_cv_summary(result: dict):
    """교차검증 요약 + 피처 중요도 Top-15 출력"""
    model_type = result['model_type']
    task_type  = result['task_type']
    cv_df = pd.DataFrame(result['cv_scores'])

    print(f"\n{'='*65}")
    print(f"  {model_type}  교차검증 요약")
    print(f"{'='*65}")

    if task_type == 'binary':
        print(f"  AUC      : {cv_df['auc'].mean():.4f}  ±{cv_df['auc'].std():.4f}")
        print(f"  Accuracy : {cv_df['accuracy'].mean():.4f}  ±{cv_df['accuracy'].std():.4f}")
    else:
        print(f"  R²   : {cv_df['r2'].mean():.4f}  ±{cv_df['r2'].std():.4f}")
        print(f"  RMSE : {cv_df['rmse'].mean():.4f}  ±{cv_df['rmse'].std():.4f}")

    print(f"\n  피처 중요도 Top 15")
    print(f"  {'피처':<35} {'점수':>8}")
    print(f"  {'-'*45}")
    top15 = result['feature_importance'].head(15)
    max_imp = top15.max()
    for feat, imp in top15.items():
        bar = '█' * max(1, int(imp / max(max_imp, 1e-9) * 25))
        print(f"  {feat:<35} {imp:8.2f}  {bar}")
