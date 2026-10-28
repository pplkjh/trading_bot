#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JackBot ML Analysis — 주가 상승 원인 분석 도구

사용법:
  python -m ml_analysis.main [옵션]
  또는
  python ml_analysis/main.py [옵션]

예시:
  # Strategy A 백테스트 데이터로 승률 예측 (전체 모드)
  python -m ml_analysis.main --simul 4 --strategy A --target win --mode full

  # sim=6 (A+B 혼합) 수익률 상관분석만 빠르게
  python -m ml_analysis.main --simul 6 --target sell_rate --mode corr_only

  # Strategy B — 확장 지표 없이 빠른 CatBoost 학습
  python -m ml_analysis.main --simul 5 --strategy B --target win --mode quick --no_enrich

  # 실전 DB 데이터 분석
  python -m ml_analysis.main --simul 6 --live --target sell_rate --mode full

모드:
  full       : 상관분석 + CatBoost + RandomForest + SHAP
  quick      : 상관분석 + CatBoost 만
  corr_only  : 상관분석 + 스코어 분포 차트만 (모델 학습 없음, 빠름)
  shap_only  : 이미 학습된 모델 없이 SHAP 재실행 (full 실행 후 사용)
"""
import argparse
import sys
import os

# 프로젝트 루트
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def parse_args():
    p = argparse.ArgumentParser(
        description='JackBot ML 피처 분석',
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        '--simul', nargs='+', type=int, default=[4, 5, 6],
        metavar='N',
        help='백테스트 simulator 번호 (기본: 4 5 6)',
    )
    p.add_argument(
        '--strategy', choices=['A', 'B', 'all'], default='all',
        help='전략 필터: A=돌파초입 / B=저점반등 / all=전체 (기본: all)',
    )
    p.add_argument(
        '--target',
        choices=['win', 'big_win', 'sell_rate', 'max_pct'],
        default='win',
        help=(
            'win       : sell_rate > 0  (이진 분류, 기본)\n'
            'big_win   : sell_rate >= 5  (이진 분류)\n'
            'sell_rate : 실현 수익률  (회귀)\n'
            'max_pct   : 보유 중 최대 수익률  (회귀)'
        ),
    )
    p.add_argument(
        '--mode',
        choices=['full', 'boost', 'quick', 'corr_only', 'shap_only'],
        default='full',
        help=(
            'full      : 상관분석 + CatBoost + LightGBM + RF + LASSO + Perm + SHAP\n'
            'boost     : 상관분석 + CatBoost + LightGBM + LASSO + SHAP  (RF 생략)\n'
            'quick     : 상관분석 + CatBoost 만\n'
            'corr_only : 상관분석 + 차트만 (모델 없음)\n'
            'shap_only : CatBoost 학습 후 SHAP 만'
        ),
    )
    p.add_argument(
        '--tabnet', action='store_true',
        help='TabNet (딥러닝) 추가 실행 (pytorch-tabnet 필요)',
    )
    p.add_argument(
        '--live', action='store_true',
        help='백테스트 DB 대신 실전(jackbot4_imi1) DB 사용',
    )
    p.add_argument(
        '--no_enrich', action='store_true',
        help='daily_buy_list 확장 지표 병합 생략 (빠른 실행)',
    )
    p.add_argument(
        '--output', type=str, default=None,
        metavar='DIR',
        help='결과 저장 디렉토리 (기본: ml_analysis/output/)',
    )
    p.add_argument(
        '--n_splits', type=int, default=5,
        help='Walk-Forward CV fold 수 (기본: 5)',
    )
    p.add_argument(
        '--top_n', type=int, default=20,
        help='피처 중요도 / 상관계수 표시 상위 N개 (기본: 20)',
    )
    return p.parse_args()


def run(args):
    from ml_analysis.config import OUTPUT_DIR, TARGETS
    from ml_analysis.data_loader import (
        load_trade_data,
        enrich_with_daily_buy_list,
        compute_derived_features,
        prepare_dataset,
    )
    from ml_analysis.analyze import (
        compute_pearson_correlation,
        print_correlation_report,
        plot_correlation_bar,
        plot_win_rate_by_score,
        plot_score_component_heatmap,
        save_results_csv,
    )

    # ── 출력 디렉토리 / 파일 접두사 ────────────────────────────────────────
    out_dir = args.output or OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    simul_tag    = '_'.join(map(str, args.simul))
    strategy_tag = args.strategy
    tag = f"sim{simul_tag}_{strategy_tag}_{args.target}"

    _header(args)

    # ── Step 1: 데이터 로드 ─────────────────────────────────────────────────
    print("\n[ 1 ] 거래 데이터 로드")
    df = load_trade_data(simul_nums=args.simul, use_live=args.live)

    # ── Step 2: 확장 지표 병합 ──────────────────────────────────────────────
    if args.no_enrich:
        print("\n[ 2 ] 확장 지표 병합 생략 (--no_enrich)")
    else:
        print("\n[ 2 ] daily_buy_list 확장 지표 병합")
        df = enrich_with_daily_buy_list(df)

    # ── Step 3: 파생 피처 ───────────────────────────────────────────────────
    print("\n[ 3 ] 파생 피처 계산")
    df = compute_derived_features(df)

    # ── Step 4: 데이터셋 준비 ───────────────────────────────────────────────
    strategy_filter = args.strategy if args.strategy != 'all' else None
    task_type, _ = TARGETS[args.target]

    X, y, feature_names, dates, meta = prepare_dataset(
        df,
        target=args.target,
        strategy_filter=strategy_filter,
    )

    if len(X) < 30:
        print(f"\n⚠ 샘플 수 {len(X)}개로 분석에 충분하지 않습니다.")
        return

    # 타겟 분포 요약
    print(f"\n  타겟 분포:")
    if task_type == 'binary':
        pos = int(y.sum())
        print(f"    win={pos:,} ({pos/len(y)*100:.1f}%)  "
              f"loss={len(y)-pos:,} ({(len(y)-pos)/len(y)*100:.1f}%)")
    else:
        print(f"    mean={y.mean():.2f}  std={y.std():.2f}  "
              f"min={y.min():.2f}  max={y.max():.2f}")

    # ── Step 5: 상관분석 ────────────────────────────────────────────────────
    print("\n[ 4 ] Pearson 상관분석")
    corr_df = compute_pearson_correlation(X, y)
    print_correlation_report(corr_df, target_name=args.target, top_n=args.top_n)

    plot_correlation_bar(
        corr_df, target_name=args.target, top_n=args.top_n,
        output_path=os.path.join(out_dir, f'corr_{tag}.png'),
    )
    plot_win_rate_by_score(
        df,
        score_col='composite_score',
        strategy=args.strategy,
        output_path=os.path.join(out_dir, f'score_dist_{tag}.png'),
    )
    plot_score_component_heatmap(
        df,
        output_path=os.path.join(out_dir, f'heatmap_{tag}.png'),
    )

    if args.mode == 'corr_only':
        save_results_csv(corr_df, [], out_dir, tag)
        _footer(out_dir, tag)
        return

    # ── 모델 학습 파이프라인 ─────────────────────────────────────────────────
    from ml_analysis.train import (
        train_catboost, train_lightgbm, train_lasso,
        train_random_forest, train_tabnet,
        compute_permutation_importance, print_cv_summary,
    )
    from ml_analysis.analyze import (
        plot_feature_importance,
        plot_importance_comparison_bar,
        compute_shap_values,
        plot_shap_summary,
        plot_shap_bar,
    )

    results_list = []
    step = 5

    # ── CatBoost (전 모드 공통) ──────────────────────────────────────────────
    print(f"\n[ {step} ] CatBoost 학습 (task={task_type})")
    step += 1
    try:
        cb = train_catboost(X, y, dates, task_type=task_type, n_splits=args.n_splits)
        print_cv_summary(cb)
        results_list.append(cb)
    except ImportError as e:
        print(f"  CatBoost 건너뜀: {e}")

    # ── LightGBM (boost / full 모드) ─────────────────────────────────────────
    if args.mode in ('full', 'boost'):
        print(f"\n[ {step} ] LightGBM 학습")
        step += 1
        try:
            lgb_r = train_lightgbm(X, y, dates, task_type=task_type, n_splits=args.n_splits)
            print_cv_summary(lgb_r)
            results_list.append(lgb_r)
        except ImportError as e:
            print(f"  LightGBM 건너뜀: {e}")

    # ── LASSO (boost / full 모드) ────────────────────────────────────────────
    if args.mode in ('full', 'boost'):
        print(f"\n[ {step} ] LASSO Logistic Regression 학습")
        step += 1
        try:
            lasso_r = train_lasso(X, y, dates, task_type=task_type, n_splits=args.n_splits)
            print_cv_summary(lasso_r)
            results_list.append(lasso_r)
        except Exception as e:
            print(f"  LASSO 건너뜀: {e}")

    # ── RandomForest (full 모드만) ───────────────────────────────────────────
    if args.mode == 'full':
        print(f"\n[ {step} ] RandomForest 학습")
        step += 1
        try:
            rf_r = train_random_forest(X, y, dates, task_type=task_type, n_splits=args.n_splits)
            print_cv_summary(rf_r)
            results_list.append(rf_r)
        except Exception as e:
            print(f"  RandomForest 건너뜀: {e}")

    # ── TabNet (--tabnet 플래그 시) ──────────────────────────────────────────
    if getattr(args, 'tabnet', False):
        print(f"\n[ {step} ] TabNet 학습 (딥러닝)")
        step += 1
        try:
            tab_r = train_tabnet(X, y, dates, task_type=task_type, n_splits=args.n_splits)
            print_cv_summary(tab_r)
            results_list.append(tab_r)
        except ImportError as e:
            print(f"  TabNet 건너뜀: {e}")
        except Exception as e:
            print(f"  TabNet 오류: {e}")

    # ── 피처 중요도 차트 ─────────────────────────────────────────────────────
    if results_list:
        plot_feature_importance(
            results_list, top_n=args.top_n,
            output_path=os.path.join(out_dir, f'importance_{tag}.png'),
        )
        if len(results_list) > 1:
            plot_importance_comparison_bar(
                results_list, top_n=args.top_n,
                output_path=os.path.join(out_dir, f'importance_cmp_{tag}.png'),
            )

    # ── Permutation Importance (boost / full 모드) ───────────────────────────
    if args.mode in ('full', 'boost') and results_list:
        print(f"\n[ {step} ] Permutation Importance (CatBoost 기준)")
        step += 1
        try:
            perm_imp = compute_permutation_importance(results_list[0], X, y)
            # Permutation 결과를 CSV로 저장
            import os as _os
            perm_path = _os.path.join(out_dir, f'perm_importance_{tag}.csv')
            perm_imp.to_csv(perm_path, header=True, encoding='utf-8-sig')
            print(f"  저장: {perm_path}")
        except Exception as e:
            print(f"  Permutation Importance 건너뜀: {e}")

    # ── SHAP (full / boost / shap_only 모드) ────────────────────────────────
    if args.mode in ('full', 'boost', 'shap_only') and results_list:
        # CatBoost 또는 LightGBM 모델로 SHAP (tree-based라 빠름)
        shap_model = next(
            (r for r in results_list if 'CatBoost' in r['model_type'] or 'LightGBM' in r['model_type']),
            results_list[0]
        )
        print(f"\n[ {step} ] SHAP 분석 ({shap_model['model_type']})")
        try:
            shap_vals, X_sample = compute_shap_values(shap_model['model'], X)
            plot_shap_summary(
                shap_vals, X_sample,
                title=f"SHAP Beeswarm — {shap_model['model_type']} / {tag}",
                output_path=os.path.join(out_dir, f'shap_bee_{tag}.png'),
            )
            plot_shap_bar(
                shap_vals, X_sample,
                title=f"SHAP Bar — {shap_model['model_type']} / {tag}",
                output_path=os.path.join(out_dir, f'shap_bar_{tag}.png'),
            )
        except ImportError:
            print("  shap 미설치: pip install shap")
        except Exception as e:
            print(f"  SHAP 건너뜀: {e}")

    # ── CSV 저장 ────────────────────────────────────────────────────────────
    save_results_csv(corr_df, results_list, out_dir, tag)

    _footer(out_dir, tag)


# ── 출력 헬퍼 ────────────────────────────────────────────────────────────────

def _header(args):
    print(f"\n{'#'*65}")
    print(f"  JackBot ML Analysis")
    print(f"  simul    : {args.simul}")
    print(f"  strategy : {args.strategy}")
    print(f"  target   : {args.target}")
    print(f"  mode     : {args.mode}")
    print(f"  enrich   : {'아니오' if args.no_enrich else '예 (daily_buy_list)'}")
    print(f"  tabnet   : {'예' if getattr(args, 'tabnet', False) else '아니오'}")
    print(f"  source   : {'실전 DB' if args.live else '백테스트 DB'}")
    print(f"{'#'*65}")


def _footer(out_dir: str, tag: str):
    print(f"\n{'='*65}")
    print(f"  분석 완료!")
    print(f"  결과 위치: {out_dir}")
    generated = [f for f in os.listdir(out_dir) if tag in f]
    for f in sorted(generated):
        print(f"    {f}")
    print(f"{'='*65}\n")


# ── 진입점 ───────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    args = parse_args()
    run(args)
