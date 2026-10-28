# ml_analysis — 사용 설명서

---

## 1. 환경 요구사항

- Python 3.7+
- MySQL 실행 중 (`daily_craw`, `daily_buy_list`, `simulator4/5/6` DB 존재)
- `library/cf.py`의 DB 접속 정보 정상 설정
- OPT10045 backfill 완료 (`backfill_inst_data.py` 실행 후) — `supply` 피처 사용 시

---

## 2. 의존성 설치

```bash
# Step 1: PyTorch (TabNet 전제조건, CPU 버전)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Step 2: ML 패키지
pip install catboost lightgbm scikit-learn shap pytorch-tabnet
```

> TabNet 없이 쓸 경우 torch / pytorch-tabnet 생략 가능.  
> `--tabnet` 플래그 없이 실행하면 나머지 모델은 정상 동작.

---

## 3. 실행 위치

반드시 프로젝트 루트에서 실행.

```bash
cd "C:\Users\USER\Desktop\Personal project\trading_bot"
python -m ml_analysis.main [옵션]
```

---

## 4. 빠른 시작

```bash
# 가장 빠른 확인 (상관분석만, 모델 학습 없음, ~30초)
python -m ml_analysis.main --simul 4 --strategy A --target win --mode corr_only

# 추천 첫 실행 (CatBoost + LightGBM + LASSO + SHAP, ~5분)
python -m ml_analysis.main --simul 4 --strategy A --target win --mode boost

# Strategy A 전체 분석 + RandomForest (~8분)
python -m ml_analysis.main --simul 4 --strategy A --target win --mode full

# Strategy B (샘플 적으므로 quick 권장)
python -m ml_analysis.main --simul 5 --strategy B --target win --mode quick

# A+B 혼합 분석 (sim=6 백테스트)
python -m ml_analysis.main --simul 6 --strategy all --target win --mode boost

# 실전 데이터 분석 (jackbot4_imi1)
python -m ml_analysis.main --simul 6 --live --target win --mode boost

# inst_flow(score_g) 효과 집중 확인 — supply 그룹 포함해서 top_n 늘리기
python -m ml_analysis.main --simul 6 --strategy A --target win --mode boost --top_n 30

# max_high_pct 기준 분석 (매도전략 왜곡 없는 순수 상한 수익)
python -m ml_analysis.main --simul 4 --strategy A --target max_pct --mode boost

# daily_buy_list 확장 지표 없이 빠르게
python -m ml_analysis.main --simul 4 --strategy A --no_enrich --mode quick

# TabNet 포함 (딥러닝, ~20분)
python -m ml_analysis.main --simul 4 --strategy A --mode full --tabnet
```

---

## 5. 전체 옵션 표

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--simul` | `4 5 6` | 백테스트 DB 번호. 복수 가능 (`--simul 4 5`) |
| `--strategy` | `all` | `A` / `B` / `all` — 전략 필터 |
| `--target` | `win` | 예측 대상 (아래 표 참조) |
| `--mode` | `full` | 실행 모드 (아래 표 참조) |
| `--live` | off | 백테스트 대신 실전 DB (`jackbot4_imi1`) 사용 |
| `--no_enrich` | off | daily_buy_list 확장 지표 병합 생략 |
| `--tabnet` | off | TabNet (딥러닝) 추가 실행 |
| `--n_splits` | `5` | Walk-Forward CV fold 수 |
| `--top_n` | `20` | 피처 중요도/상관계수 표시 상위 N개 |
| `--output` | `ml_analysis/output/` | 결과 저장 디렉토리 |

### `--target` 옵션

| 값 | 타입 | 설명 |
|---|---|---|
| `win` | 이진 분류 | sell_rate > 0 → 1 (기본) |
| `big_win` | 이진 분류 | sell_rate ≥ 5% → 1 |
| `sell_rate` | 회귀 | 실현 수익률 값 그대로 |
| `max_pct` | 회귀 | 보유 중 최대 수익률 (매도전략 왜곡 없음, 가장 순수한 타겟) |

### `--mode` 옵션

| 모드 | 실행 모델 | 소요 시간 |
|---|---|---|
| `corr_only` | Pearson 상관분석 + 차트만 | ~30초 |
| `quick` | 상관분석 + CatBoost | ~2분 |
| `boost` | 상관분석 + CatBoost + LightGBM + LASSO + Permutation + SHAP | ~5분 |
| `full` | `boost` + RandomForest | ~8분 |
| `full --tabnet` | `full` + TabNet | ~20분 (GPU 없는 경우) |
| `shap_only` | CatBoost 학습 후 SHAP만 | ~3분 |

---

## 6. 피처 그룹

`FEATURE_GROUPS`에 정의된 피처. `--no_enrich` 없이 실행하면 자동으로 `daily_buy_list`에서 확장 지표를 JOIN한다.

| 그룹 | 피처 | 출처 |
|---|---|---|
| `score` | composite_score, score_a~g, score_penalty | all_item_db (전략 점수) |
| `momentum` | d1_diff_rate, rsi14, macd, macd_histogram, adx, plus_di, minus_di, di_diff | daily_buy_list + 파생 |
| `volatility` | atr_rate, bb_bandwidth, bb_position | daily_buy_list + 파생 |
| `volume` | volume_ratio, obv, mfi14, cmf20 | daily_buy_list |
| `ma_ratio` | close_vs_ma5/20/60/120 | 파생 (close/MA - 1) |
| `pattern` | candle_pattern_score | daily_buy_list |
| `ichimoku` | ichimoku_tenkan_vs_close, ichimoku_kijun_vs_close | daily_buy_list + 파생 |
| `supply` | inst_buy_ratio, foreign_buy_ratio | daily_buy_list + 파생 (OPT10045 backfill 필요) |

> `supply` 그룹은 `backfill_inst_data.py` + `migration_inst_to_daily_buy_list.py` 실행 후 유효.  
> 미실행 시 `inst_buy_ratio = NaN` → `-1`로 채워져 분석에 포함되지만 의미 없음.

---

## 7. 출력 파일

결과는 `ml_analysis/output/`에 저장. 파일명에 실행 파라미터 포함.

예) `--simul 6 --strategy A --target win` → 접두사 `sim6_A_win`

| 파일 | 내용 |
|---|---|
| `corr_sim6_A_win.png` | Pearson r 수평 막대그래프 |
| `correlation_sim6_A_win.csv` | Pearson r 수치 전체 |
| `score_dist_sim6_A_win.png` | composite_score 구간별 승률/평균수익 |
| `heatmap_sim6_A_win.png` | 스코어 컴포넌트 간 상관 히트맵 |
| `importance_sim6_A_win.png` | 모델별 피처 중요도 차트 |
| `importance_cmp_sim6_A_win.png` | 모델 간 피처 중요도 비교 |
| `importance_catboost_*.csv` | CatBoost 피처 중요도 수치 |
| `importance_lightgbm_*.csv` | LightGBM 피처 중요도 수치 |
| `importance_lasso_*.csv` | LASSO 계수 절댓값 (0 = 불필요 피처) |
| `perm_importance_*.csv` | Permutation Importance 수치 |
| `cv_scores_catboost_*.csv` | Fold별 AUC/Accuracy 수치 |
| `shap_bee_sim6_A_win.png` | SHAP Beeswarm plot |
| `shap_bar_sim6_A_win.png` | SHAP 전역 중요도 bar plot |

---

## 8. 파라미터 조정

`ml_analysis/config.py`에서 모델별 하이퍼파라미터 수정 가능.

```python
# CatBoost 반복 횟수 줄이기 (빠른 실험)
CATBOOST_PARAMS_CLF['iterations'] = 200

# LASSO 정규화 강도 조정
LASSO_C = 0.1   # 완화: 더 많은 피처 살아남음
LASSO_C = 0.01  # 강화: 핵심 2~5개만 남음

# TabNet 빠르게
TABNET_PARAMS['n_steps'] = 3
TABNET_FIT_PARAMS['max_epochs'] = 100
```

---

## 9. 자주 쓰는 분석 조합

### score_g(inst_flow) 효과 검증

```bash
# 1. score_component_analysis로 Pearson r 먼저 확인
python score_component_analysis.py 6

# 2. ml_analysis로 비선형 상호작용 + SHAP 확인
python -m ml_analysis.main --simul 6 --strategy A --target win --mode boost --top_n 30
```

결과에서 `inst_buy_ratio` (score_g 원천)를 찾아 SHAP 값과 Permutation Importance 확인.

### 역상관 피처 탐색

```bash
python -m ml_analysis.main --simul 4 --strategy A --target win --mode corr_only
```

`correlation_*.csv`에서 `pearson_r` < 0인 피처 확인.  
현재 양수 점수로 보상 중이라면 패널티로 전환 검토.

### 선형 vs 비선형 효과 비교

```bash
python -m ml_analysis.main --simul 4 --strategy A --mode boost
```

콘솔 출력에서:
- LASSO AUC ≈ CatBoost AUC → 신호가 대부분 선형 (현재 스코어 구조 이미 양호)
- LASSO AUC << CatBoost AUC → 비선형 상호작용이 중요 (스코어 구조 개선 여지)
