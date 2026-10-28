# -*- coding: utf-8 -*-
"""
ml_analysis/analyze.py
SHAP 분석, Pearson 상관계수, 피처 중요도 시각화, 스코어-수익 분포

모든 시각화 함수는 output_path 를 받아 PNG 파일로 저장하고 plt.close()를 호출하므로
GUI 없는 환경(서버/배치)에서도 실행 가능.
"""
import os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from typing import Optional, List

# 한글 폰트 설정 (Windows)
matplotlib.rcParams['font.family'] = ['Malgun Gothic', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False


# ── Pearson 상관계수 분석 ───────────────────────────────────────────────────

def compute_pearson_correlation(
    X: pd.DataFrame,
    y: pd.Series,
) -> pd.DataFrame:
    """
    각 피처와 타겟(y)의 Pearson 상관계수 계산.
    NaN·-1 (missing fill) 값은 제외하고 계산.

    Returns
    -------
    DataFrame: columns=['pearson_r', 'abs_r'], index=feature_name, 내림차순 정렬
    """
    corrs = {}
    for col in X.columns:
        try:
            xv = pd.to_numeric(X[col], errors='coerce')
            valid = (xv != -1) & (~xv.isna()) & (~y.isna())
            if valid.sum() < 20:
                continue
            r = float(np.corrcoef(xv[valid], y[valid])[0, 1])
            if not np.isnan(r):
                corrs[col] = r
        except Exception:
            pass

    result = pd.DataFrame.from_dict(corrs, orient='index', columns=['pearson_r'])
    result['abs_r'] = result['pearson_r'].abs()
    return result.sort_values('abs_r', ascending=False)


def print_correlation_report(corr_df: pd.DataFrame, target_name: str = 'win', top_n: int = 25):
    """Pearson 상관계수 텍스트 리포트 출력"""
    def _judge(r):
        a = abs(r)
        if a >= 0.15: return '★★★ 유의미'
        if a >= 0.08: return '★★  중간'
        if a >= 0.04: return '★   약함'
        return '    미미'

    print(f"\n{'='*65}")
    print(f"  타겟 [{target_name}] 과의 Pearson 상관계수  (Top {top_n})")
    print(f"{'='*65}")
    print(f"  {'피처':<32} {'r':>8}  해석")
    print(f"  {'-'*55}")
    for feat, row in corr_df.head(top_n).iterrows():
        r = row['pearson_r']
        direction = '↑수익' if r > 0 else '↓수익'
        print(f"  {feat:<32} {r:>+8.4f}  {_judge(r)} {direction}")


# ── 피처 중요도 시각화 ────────────────────────────────────────────────────────

def plot_feature_importance(
    results_list: List[dict],
    top_n: int = 20,
    output_path: Optional[str] = None,
):
    """
    results_list 에 있는 모델별 피처 중요도를 나란히 bar chart 로 출력.
    results_list 각 원소 = train_catboost / train_random_forest 반환값.
    """
    n = len(results_list)
    if n == 0:
        return

    fig, axes = plt.subplots(1, n, figsize=(11 * n, 10), squeeze=False)

    for ax, result in zip(axes[0], results_list):
        fi = result['feature_importance'].head(top_n)
        colors = plt.cm.RdYlGn(np.linspace(0.3, 0.9, len(fi)))[::-1]
        bars = ax.barh(range(len(fi)), fi.values, color=colors, edgecolor='white', linewidth=0.5)
        ax.set_yticks(range(len(fi)))
        ax.set_yticklabels(fi.index, fontsize=9)
        ax.invert_yaxis()
        ax.set_xlabel('Importance', fontsize=10)
        ax.set_title(f"{result['model_type']}\n피처 중요도 Top {top_n}", fontsize=12, pad=10)
        ax.grid(axis='x', alpha=0.3, linestyle='--')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

    plt.tight_layout()
    _save_and_close(output_path, '피처 중요도')


def plot_importance_comparison_bar(
    results_list: List[dict],
    top_n: int = 20,
    output_path: Optional[str] = None,
):
    """여러 모델의 피처 중요도를 한 차트에 grouped bar chart 로 비교"""
    if not results_list:
        return

    all_feat = []
    for r in results_list:
        all_feat.extend(r['feature_importance'].head(top_n).index.tolist())
    features = list(dict.fromkeys(all_feat))[:top_n]

    x = np.arange(len(features))
    width = 0.8 / len(results_list)
    fig, ax = plt.subplots(figsize=(16, 7))

    for i, result in enumerate(results_list):
        fi = result['feature_importance']
        vals = [fi.get(f, 0) for f in features]
        offset = (i - len(results_list) / 2 + 0.5) * width
        ax.bar(x + offset, vals, width, label=result['model_type'], alpha=0.8)

    ax.set_xticks(x)
    ax.set_xticklabels(features, rotation=45, ha='right', fontsize=8)
    ax.set_ylabel('Importance', fontsize=10)
    ax.set_title('모델 간 피처 중요도 비교', fontsize=13)
    ax.legend(fontsize=9)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    _save_and_close(output_path, '피처 중요도 비교')


# ── 상관계수 시각화 ───────────────────────────────────────────────────────────

def plot_correlation_bar(
    corr_df: pd.DataFrame,
    target_name: str = 'win',
    top_n: int = 25,
    output_path: Optional[str] = None,
):
    """Pearson r 수평 막대그래프"""
    top = corr_df.head(top_n)
    colors = ['#2ecc71' if r > 0 else '#e74c3c' for r in top['pearson_r']]
    alpha  = [min(1.0, abs(r) * 5 + 0.3) for r in top['pearson_r']]

    fig, ax = plt.subplots(figsize=(11, 8))
    for idx, (feat, row) in enumerate(top.iterrows()):
        ax.barh(idx, row['pearson_r'], color=colors[idx], alpha=alpha[idx], edgecolor='white')

    ax.set_yticks(range(len(top)))
    ax.set_yticklabels(top.index, fontsize=9)
    ax.axvline(0, color='#333', linewidth=0.8)
    ax.axvline( 0.08, color='orange', linewidth=0.8, linestyle='--', alpha=0.6, label='r=±0.08')
    ax.axvline(-0.08, color='orange', linewidth=0.8, linestyle='--', alpha=0.6)
    ax.axvline( 0.15, color='red',    linewidth=0.8, linestyle='--', alpha=0.6, label='r=±0.15')
    ax.axvline(-0.15, color='red',    linewidth=0.8, linestyle='--', alpha=0.6)
    ax.invert_yaxis()
    ax.set_xlabel('Pearson r', fontsize=11)
    ax.set_title(f"피처 ↔ [{target_name}] Pearson 상관계수  (|r| 내림차순)", fontsize=13)
    ax.legend(fontsize=8, loc='lower right')
    ax.grid(axis='x', alpha=0.2, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    _save_and_close(output_path, '상관계수 차트')


# ── 스코어 구간별 승률 / 평균수익 ────────────────────────────────────────────

def plot_win_rate_by_score(
    df: pd.DataFrame,
    score_col: str = 'composite_score',
    strategy: str = 'all',
    output_path: Optional[str] = None,
):
    """
    score_col 구간별 승률 + 평균수익률 이중 차트.
    strategy : 'A' | 'B' | 'all'
    """
    df = df.copy()
    if strategy in ('A', 'B') and 'strategy_type' in df.columns:
        df = df[df['strategy_type'] == strategy]

    if score_col not in df.columns or 'sell_rate' not in df.columns:
        return
    if len(df) < 20:
        return

    # 구간 설정
    s_min = int(df[score_col].dropna().min())
    s_max = int(df[score_col].dropna().max())
    step  = max(5, (s_max - s_min) // 20)
    bins  = range(s_min - step, s_max + step * 2, step)

    df['_bin'] = pd.cut(df[score_col], bins=list(bins))
    grouped = (
        df.groupby('_bin', observed=False)
        .agg(
            count=('sell_rate', 'count'),
            win_rate=('sell_rate', lambda x: (x > 0).mean()),
            avg_ret=('sell_rate', 'mean'),
        )
        .reset_index()
    )
    grouped = grouped[grouped['count'] >= 5]

    if grouped.empty:
        return

    x = range(len(grouped))
    labels = [str(b).replace('(', '').replace(']', '').replace(', ', '~')
              for b in grouped['_bin']]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10), sharex=True)
    fig.suptitle(
        f"{score_col} 구간별 분석  (strategy={strategy}, n={len(df):,})",
        fontsize=14
    )

    # 승률
    c1 = ['#2196F3' if w >= 0.5 else '#FF5722' for w in grouped['win_rate']]
    bars = ax1.bar(x, grouped['win_rate'] * 100, color=c1, alpha=0.75, edgecolor='white')
    ax1.axhline(50, color='grey', linestyle='--', linewidth=1, alpha=0.7)
    ax1.set_ylabel('승률 (%)', fontsize=11)
    ax1.set_ylim(0, 105)
    ax1.grid(axis='y', alpha=0.3, linestyle='--')
    for bar, cnt, wr in zip(bars, grouped['count'], grouped['win_rate']):
        ax1.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + 1,
                 f'{wr*100:.0f}%\nn={cnt}', ha='center', fontsize=7)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)

    # 평균수익
    c2 = ['#27ae60' if v >= 0 else '#c0392b' for v in grouped['avg_ret']]
    ax2.bar(x, grouped['avg_ret'], color=c2, alpha=0.75, edgecolor='white')
    ax2.axhline(0, color='black', linewidth=0.8)
    ax2.set_ylabel('평균 수익률 (%)', fontsize=11)
    ax2.set_xticks(list(x))
    ax2.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
    ax2.grid(axis='y', alpha=0.3, linestyle='--')
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)

    plt.tight_layout()
    _save_and_close(output_path, f'{score_col} 구간 분포')


def plot_score_component_heatmap(
    df: pd.DataFrame,
    score_cols: Optional[List[str]] = None,
    output_path: Optional[str] = None,
):
    """score_a ~ score_f 상호 상관 히트맵 (다중공선성 확인)"""
    if score_cols is None:
        score_cols = [c for c in
                      ['composite_score', 'score_a', 'score_b', 'score_c',
                       'score_d', 'score_e', 'score_f', 'score_penalty', 'sell_rate']
                      if c in df.columns]
    if len(score_cols) < 2:
        return

    corr_mat = df[score_cols].corr()

    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(corr_mat, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
    plt.colorbar(im, ax=ax, shrink=0.8)

    ax.set_xticks(range(len(score_cols)))
    ax.set_yticks(range(len(score_cols)))
    ax.set_xticklabels(score_cols, rotation=45, ha='right', fontsize=9)
    ax.set_yticklabels(score_cols, fontsize=9)
    ax.set_title('스코어 컴포넌트 상관 히트맵', fontsize=13)

    for i in range(len(score_cols)):
        for j in range(len(score_cols)):
            val = corr_mat.iloc[i, j]
            ax.text(j, i, f'{val:.2f}', ha='center', va='center',
                    fontsize=7, color='black' if abs(val) < 0.7 else 'white')

    plt.tight_layout()
    _save_and_close(output_path, '스코어 히트맵')


# ── SHAP ─────────────────────────────────────────────────────────────────────

def compute_shap_values(model, X: pd.DataFrame, sample_n: int = 2000):
    """
    CatBoost / RandomForest 에 대해 SHAP 값 계산.

    Returns (shap_values, X_sample)
    shap_values : shap.Explanation 객체
    """
    try:
        import shap
    except ImportError:
        raise ImportError("shap 미설치: pip install shap")

    X_sample = X.sample(min(sample_n, len(X)), random_state=42)
    explainer = shap.TreeExplainer(model)
    shap_values = explainer(X_sample)
    return shap_values, X_sample


def plot_shap_summary(
    shap_values,
    X_sample: pd.DataFrame,
    title: str = 'SHAP Summary',
    output_path: Optional[str] = None,
):
    """SHAP beeswarm(dot) summary plot"""
    try:
        import shap
        fig, ax = plt.subplots(figsize=(12, 9))
        shap.summary_plot(shap_values, X_sample, show=False, plot_type='dot')
        if title:
            plt.title(title, fontsize=13, pad=12)
        plt.tight_layout()
        _save_and_close(output_path, 'SHAP Summary')
    except Exception as e:
        print(f"  SHAP summary plot 실패: {e}")


def plot_shap_bar(
    shap_values,
    X_sample: pd.DataFrame,
    title: str = 'SHAP 평균 절댓값',
    output_path: Optional[str] = None,
):
    """SHAP bar plot (전역 중요도)"""
    try:
        import shap
        fig, ax = plt.subplots(figsize=(11, 8))
        shap.summary_plot(shap_values, X_sample, show=False, plot_type='bar')
        if title:
            plt.title(title, fontsize=13, pad=12)
        plt.tight_layout()
        _save_and_close(output_path, 'SHAP Bar')
    except Exception as e:
        print(f"  SHAP bar plot 실패: {e}")


# ── 공통 유틸 ────────────────────────────────────────────────────────────────

def _save_and_close(path: Optional[str], label: str = ''):
    if path:
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        plt.savefig(path, dpi=150, bbox_inches='tight')
        print(f"  저장: {path}")
    plt.close('all')


def save_results_csv(
    corr_df: pd.DataFrame,
    results_list: List[dict],
    output_dir: str,
    tag: str,
):
    """상관계수 + 피처 중요도를 CSV로 저장"""
    os.makedirs(output_dir, exist_ok=True)

    corr_path = os.path.join(output_dir, f'correlation_{tag}.csv')
    corr_df.to_csv(corr_path, encoding='utf-8-sig')
    print(f"  저장: {corr_path}")

    for result in results_list:
        fi = result['feature_importance']
        model_name = result['model_type'].replace('-', '_').lower()
        fi_path = os.path.join(output_dir, f'importance_{model_name}_{tag}.csv')
        fi.to_csv(fi_path, header=True, encoding='utf-8-sig')
        print(f"  저장: {fi_path}")

        cv_path = os.path.join(output_dir, f'cv_scores_{model_name}_{tag}.csv')
        pd.DataFrame(result['cv_scores']).to_csv(cv_path, index=False, encoding='utf-8-sig')
        print(f"  저장: {cv_path}")
