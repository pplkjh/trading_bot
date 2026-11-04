# -*- coding: utf-8 -*-
"""
feature_discovery/main.py

필터 이전 후보 종목 전체를 대상으로 "어떤 피처가 실제 주가 상승을 예측하는가" 분석.
ml_analysis와 다른 점: 스코어 필터 없음, 라벨 = 실제 N일 후 수익률.

실행 위치: trading_bot/ 루트에서
  python -m feature_discovery.main [옵션]

예시:
  # 빠른 테스트 (5일마다 샘플링, CatBoost + LightGBM + LASSO)
  python -m feature_discovery.main --sample_every 5 --mode boost

  # 전체 기간 전체 분석
  python -m feature_discovery.main --start 20230101 --mode boost

  # 수급 피처만 집중 분석
  python -m feature_discovery.main --groups supply momentum --horizon 10
"""
import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import pandas as pd

# ml_analysis 모델 학습/분석 로직 재사용
from ml_analysis.train import (
    train_catboost, train_lightgbm, train_lasso,
    train_random_forest, compute_permutation_importance, print_cv_summary,
)
from ml_analysis.analyze import (
    compute_pearson_correlation, print_correlation_report,
    plot_correlation_bar, plot_feature_importance, plot_importance_comparison_bar,
    compute_shap_values, plot_shap_summary, plot_shap_bar,
    save_results_csv,
)

from .data_builder import build_dataset, prepare_dataset
from .config import CATBOOST_PARAMS_CLF, CATBOOST_PARAMS_REG
from .config import LGBM_PARAMS_CLF, LGBM_PARAMS_REG, LASSO_C, OUTPUT_DIR


def parse_args():
    p = argparse.ArgumentParser(description='feature_discovery — 필터 이전 피처 예측력 분석')
    p.add_argument('--start',        default='20230101',
                   help='데이터 시작일 YYYYMMDD (기본: 20230101)')
    p.add_argument('--end',          default=None,
                   help='데이터 종료일 YYYYMMDD (기본: 오늘)')
    p.add_argument('--horizon',      type=int, default=10,
                   help='예측 호라이즌 거래일 수 (기본: 10)')
    p.add_argument('--label',        default='win',
                   choices=['win', 'big_win', 'return', 'max'],
                   help='라벨 유형 (기본: win = N일 후 양수 수익률)')
    p.add_argument('--mode',         default='boost',
                   choices=['corr_only', 'quick', 'boost', 'full'],
                   help='실행 모드 (기본: boost)')
    p.add_argument('--groups',       nargs='+', default=None,
                   help='사용할 피처 그룹 (기본: 전체). 예: --groups supply momentum')
    p.add_argument('--sample_every', type=int, default=1,
                   help='N일마다 1개 샘플링 (빠른 테스트: 5~10, 기본: 1=전체)')
    p.add_argument('--n_splits',     type=int, default=5,
                   help='Walk-Forward CV fold 수 (기본: 5)')
    p.add_argument('--top_n',        type=int, default=20,
                   help='중요도 표시 상위 N개 (기본: 20)')
    p.add_argument('--output',       default=OUTPUT_DIR,
                   help='결과 저장 디렉토리')
    p.add_argument('--cache',        default=None,
                   help='캐시 파일 경로 (.parquet). 지정 시 저장/재사용.')
    return p.parse_args()


def _tag(args) -> str:
    grp = '_'.join(args.groups) if args.groups else 'all'
    return f"h{args.horizon}_{args.label}_{grp}"


def main():
    args = parse_args()
    os.makedirs(args.output, exist_ok=True)
    tag = _tag(args)

    print(f"\n{'='*70}")
    print(f"  feature_discovery  (필터 이전 원시 피처 예측력 분석)")
    print(f"  기간: {args.start} ~ {args.end or '오늘'}")
    print(f"  호라이즌: {args.horizon}일  라벨: {args.label}  모드: {args.mode}")
    if args.sample_every > 1:
        print(f"  샘플링: {args.sample_every}일마다 1개 (약 {100//args.sample_every}% 데이터)")
    print(f"{'='*70}")

    # ── 데이터 로드 ──────────────────────────────────────────────────────────
    if args.cache and os.path.exists(args.cache):
        print(f"\n  캐시 로드: {args.cache}")
        df_raw = pd.read_parquet(args.cache)
        print(f"  {len(df_raw):,}행 캐시에서 복원")
    else:
        from .config import DEFAULT_HORIZONS
        df_raw = build_dataset(
            start_date=args.start,
            end_date=args.end,
            horizons=DEFAULT_HORIZONS,  # 캐시 재사용을 위해 항상 전체 호라이즌 계산
            sample_every=args.sample_every,
        )
        if args.cache:
            df_raw.to_parquet(args.cache, index=False)
            print(f"  캐시 저장: {args.cache}")

    X, y, _, dates, _ = prepare_dataset(
        df_raw,
        horizon=args.horizon,
        label_type=args.label,
        feature_groups=args.groups,
    )

    if len(X) < 100:
        print(f"  ⚠ 샘플 수 부족 ({len(X)}건). 기간 또는 sample_every 조정 필요.")
        return

    # ── Pearson 상관분석 ─────────────────────────────────────────────────────
    print(f"\n{'─'*50}")
    print("  [상관분석] Pearson r")
    print(f"{'─'*50}")
    corr_df = compute_pearson_correlation(X, y)
    print_correlation_report(corr_df, f'fwd_return_{args.horizon}d_{args.label}', args.top_n)
    plot_correlation_bar(
        corr_df,
        target_name=f'fwd_{args.horizon}d_{args.label}',
        top_n=args.top_n,
        output_path=os.path.join(args.output, f'corr_{tag}.png'),
    )

    if args.mode == 'corr_only':
        save_results_csv(corr_df, [], args.output, tag)
        print("\n  corr_only 모드 완료.")
        return

    # ── CatBoost ─────────────────────────────────────────────────────────────
    print(f"\n{'─'*50}")
    print("  [CatBoost] Walk-Forward CV")
    print(f"{'─'*50}")
    task_type = 'binary' if args.label in ('win', 'big_win') else 'regression'
    cb_params = CATBOOST_PARAMS_CLF if task_type == 'binary' else CATBOOST_PARAMS_REG
    cb_result = train_catboost(X, y, dates, task_type, cb_params, args.n_splits)
    print_cv_summary(cb_result)
    results_list = [cb_result]

    if args.mode == 'quick':
        _finalize(results_list, None, corr_df, X, args, tag)
        return

    # ── LightGBM + LASSO ─────────────────────────────────────────────────────
    print(f"\n{'─'*50}")
    print("  [LightGBM]")
    print(f"{'─'*50}")
    lgbm_params = LGBM_PARAMS_CLF if task_type == 'binary' else LGBM_PARAMS_REG
    lgbm_result = train_lightgbm(X, y, dates, task_type, lgbm_params, args.n_splits)
    print_cv_summary(lgbm_result)
    results_list.append(lgbm_result)

    print(f"\n{'─'*50}")
    print("  [LASSO Logistic / Linear]")
    print(f"{'─'*50}")
    lasso_result = train_lasso(X, y, dates, task_type, LASSO_C, args.n_splits)
    print_cv_summary(lasso_result)
    results_list.append(lasso_result)

    # Permutation Importance — pd.Series 반환, results_list와 별도 관리
    perm_result = compute_permutation_importance(cb_result, X, y)

    if args.mode == 'full':
        print(f"\n{'─'*50}")
        print("  [RandomForest]")
        print(f"{'─'*50}")
        from ml_analysis.config import RF_PARAMS
        rf_result = train_random_forest(X, y, dates, task_type, RF_PARAMS, args.n_splits)
        print_cv_summary(rf_result)
        results_list.append(rf_result)

    _finalize(results_list, perm_result, corr_df, X, args, tag)


def _finalize(results_list, perm_result, corr_df, X, args, tag):
    """SHAP + 차트 + CSV 저장."""
    cb_result = next((r for r in results_list if r.get('model_type') == 'catboost'), None)

    # 피처 중요도 차트
    plot_feature_importance(
        results_list,
        top_n=args.top_n,
        output_path=os.path.join(args.output, f'importance_{tag}.png'),
    )
    if len(results_list) >= 2:
        plot_importance_comparison_bar(
            results_list,
            top_n=args.top_n,
            output_path=os.path.join(args.output, f'importance_cmp_{tag}.png'),
        )

    # SHAP
    if cb_result and cb_result.get('model') and args.mode not in ('corr_only', 'quick'):
        print(f"\n{'─'*50}")
        print("  [SHAP] TreeExplainer")
        print(f"{'─'*50}")
        try:
            shap_vals = compute_shap_values(cb_result['model'], X)
            plot_shap_summary(
                shap_vals, X,
                title=f'SHAP — fwd_{args.horizon}d_{args.label}',
                output_path=os.path.join(args.output, f'shap_bee_{tag}.png'),
            )
            plot_shap_bar(
                shap_vals, X,
                title=f'SHAP bar — fwd_{args.horizon}d_{args.label}',
                output_path=os.path.join(args.output, f'shap_bar_{tag}.png'),
            )
        except Exception as e:
            print(f"  SHAP 실패: {e}")

    # CSV 저장 (모델별 feature_importance + cv_scores)
    save_results_csv(corr_df, results_list, args.output, tag)

    # Permutation Importance 별도 CSV
    if perm_result is not None:
        perm_path = os.path.join(args.output, f'perm_importance_{tag}.csv')
        perm_result.to_csv(perm_path, header=True, encoding='utf-8-sig')
        print(f"  저장: {perm_path}")

    print(f"\n  결과 저장 완료 → {args.output}/")
    print(f"  파일 접두사: {tag}")
    print(f"\n{'='*70}\n")


if __name__ == '__main__':
    main()
