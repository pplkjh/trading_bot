# ml_analysis — 모델 특징 및 비교

이 분석 도구는 5개 모델 + 1개 진단 도구를 사용한다.  
각 모델이 서로 다른 관점에서 "어떤 피처가 수익에 기여하는가"를 바라보기 때문에,  
**여러 모델에서 공통으로 중요한 피처**가 가장 신뢰도 높은 후보다.

---

## CatBoost

```
용도: 주력 예측 모델
속도: 중간 (~2분 / fold)
```

### 특징

- Gradient Boosting 중 **범주형 데이터와 NaN에 가장 강함**
- 트리 기반 → 피처 간 비선형 상호작용 자동 포착
- `feature_importances_` = split gain 기반 (피처를 분기점으로 얼마나 자주/효과적으로 사용했는가)
- SHAP과 완벽하게 호환 (TreeExplainer)

### 이 프로젝트에서의 역할

다른 모델들의 기준점(baseline). "전체 피처를 종합해서 가장 잘 예측하는 베이스 모델"

### 주의사항

- `composite_score`와 `score_a~g`를 동시에 넣으면 다중공선성 발생 가능
  → `heatmap_*.png`에서 상관 0.9 이상인 피처 쌍 확인
- Strategy B ~200건은 과적합 위험 → `quick` 모드 권장

---

## LightGBM

```
용도: 빠른 검증 / CatBoost 교차확인
속도: 빠름 (CatBoost 대비 5~10배)
```

### 특징

- Leaf-wise tree growth → 대용량 데이터에 강함 (Strategy A ~17,000건에 적합)
- 피처 중요도: `split` 방식 (분기 횟수) 사용

### CatBoost vs LightGBM 비교

| 상황 | 의미 |
|---|---|
| 두 모델 AUC 비슷 | 신호 안정적으로 존재 |
| 중요 피처 일치 | 그 피처는 강한 신호 |
| LightGBM AUC 낮음 | CatBoost의 범주 처리 능력이 차이를 만듦 |
| 둘 다 AUC ≈ 0.5~0.55 | 신호 약하거나 노이즈 많음 |

---

## LASSO Logistic Regression

```
용도: 선형 효과 분리 / 불필요 피처 자동 탈락
속도: 매우 빠름
```

### 특징

- L1 정규화 → 계수가 정확히 0이 되는 피처 발생 (Sparse solution)
- 계수 0 = 이 피처는 불필요 (다른 피처로 설명 가능하거나 노이즈)
- StandardScaler 전처리 필수

### 핵심 해석

```
LASSO sparsity: 12/27 피처가 0 (제거됨)
```
→ 27개 피처 중 12개는 예측에 기여하지 않음.  
→ `importance_lasso_*.csv`에서 0.0000인 피처 = "제거 후보"

### CatBoost와 AUC 비교

| 상황 | 해석 |
|---|---|
| LASSO AUC ≈ CatBoost AUC | 신호가 선형 → 현재 스코어 구조 이미 최적에 가까움 |
| LASSO AUC << CatBoost AUC | 비선형 상호작용 중요 → 스코어 개선 여지 있음 |

### `LASSO_C` 파라미터 (config.py)

```
C = 0.01  → 강한 정규화: 핵심 2~5개만 남음
C = 0.05  → 기본: 중요 피처 ~10개 선별 (권장)
C = 0.1   → 약한 정규화: 20개 이상 살아남음
```

---

## RandomForest

```
용도: Bagging 기반 앙상블 기준선
속도: 느림
```

### 특징

- 수백 개 독립 결정 트리의 평균 → 과적합에 강함
- CatBoost/LightGBM과 달리 트리들이 서로 **독립적** (부스팅 아님)
- 피처 중요도: MDI (Mean Decrease Impurity) 기반

### 이 프로젝트에서의 역할

부스팅 계열의 공통 편향을 다른 관점에서 검증.  
RF에서도 중요도 높은 피처 → 방법론 독립적으로 강한 신호.

---

## Permutation Importance

```
용도: 모델 독립적 이중 검증
속도: 중간
```

### 원리

```
1. 모델 학습 완료
2. 피처 X_i 를 무작위로 셔플
3. AUC 변화 측정: 셔플 전 AUC - 셔플 후 AUC
4. 차이가 클수록 X_i 가 중요한 피처
```

### 해석

```
perm_importance > 0    → 이 피처 제거 시 성능 하락 (실제로 중요)
perm_importance ≈ 0    → 성능에 거의 영향 없음 (제거 가능)
perm_importance < 0    → 노이즈 피처 (제거하면 오히려 나아짐)
```

---

## TabNet (선택적)

```
용도: 거래별 attention 분석
속도: 느림 (~20분, CPU)
필요: pytorch-tabnet, torch
실행: --tabnet 플래그 추가
```

### 특징

각 예측마다 **어느 피처에 집중할지 동적으로 결정**.  
같은 모델이라도 거래마다 다른 피처 조합 사용 가능.

### 이 프로젝트에서 기대하는 발견

```
Strategy A 거래: ADX↑, bb_position↑, d1_diff_rate↑ 집중
Strategy B 거래: rsi14↑, ichimoku_kijun↑, di_diff↑ 집중
```

A/B 거래가 정말 다른 피처 패턴을 보인다면  
→ 두 전략을 별도 모델로 운영하는 것이 더 정확하다는 근거.

---

## 모델 선택 가이드

| 질문 | 사용할 모델 |
|---|---|
| 어떤 피처가 가장 중요한가? | CatBoost + SHAP |
| 불필요한 피처를 제거하고 싶다 | LASSO (C=0.05) |
| 선형 vs 비선형 효과 비교 | LASSO AUC vs CatBoost AUC |
| 피처 중요도를 신뢰도 있게 검증 | Permutation Importance |
| 거래별로 어떤 피처가 작동했는지 | TabNet explain() |
| 여러 모델이 일치하는 핵심 피처 | `boost` 모드 전체 실행 → 중첩 확인 |
