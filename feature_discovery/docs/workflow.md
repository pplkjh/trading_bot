# feature_discovery — 전체 워크플로우

두 분석 도구를 어떤 순서로, 어떤 목적으로 사용하는지 단계별로 정리한다.

---

## 워크플로우 1 — inst_flow(score_g) 효과 검증

새로 추가한 `score_g`가 실제로 유효한 신호인지 검증하는 절차.

```
[Step 1] score_component_analysis.py로 빠른 선형 확인
  python score_component_analysis.py 6

  확인 포인트:
  - score_g Pearson r > 0 → 양의 상관 확인
  - r ≥ 0.04 → 적어도 약한 신호 존재

[Step 2] ml_analysis로 비선형 + 상호작용 확인
  python -m ml_analysis.main --simul 6 --strategy A --mode boost --top_n 30

  확인 포인트:
  - inst_buy_ratio (score_g 원천) 피처 중요도 순위
  - Permutation Importance > 0 여부
  - LASSO에서 살아남는지 여부 (0이 아닌지)

[Step 3] feature_discovery로 선택 편향 없는 독립 검증
  python -m feature_discovery.main --cache fd.parquet \
      --groups supply momentum --mode boost

  확인 포인트:
  - inst_buy_ratio Pearson r ≥ 0.05 → 전체 후보에서 유의미
  - 모든 호라이즌(5/10/15일)에서 양수인지

[판단]
  Step 1 + Step 2 + Step 3 모두 양성 → score_g 비중 유지/강화
  Step 1/2는 양성이지만 Step 3 음성 → 기존 필터가 흡수 중, score_g 효과 과대평가
  모두 음성 → score_g 효과 없음 → 제거 검토
```

---

## 워크플로우 2 — 새로운 스코어 컴포넌트 발굴

현재 score_a~g에 없는 새로운 신호를 찾는 절차.

```
[Step 1] feature_discovery 전체 피처 분석
  python -m feature_discovery.main --cache fd.parquet --mode boost

  목표: 현재 score_a~g와 겹치지 않으면서 예측력 있는 피처 발견

[Step 2] 발견된 후보 피처의 특성 파악
  - Pearson r 부호: 선형적으로 높을수록/낮을수록 상승?
  - SHAP bee plot: 비선형 패턴이 있는가?
  - 호라이즌별 차이: 단기/중기 중 어디서 강한가?

[Step 3] 스코어 공식 설계
  선형 패턴 → 구간별 점수 부여
    예: inst_buy_ratio ≥ 0.05 → 12pt, ≥ 0.02 → 5pt
  비선형 패턴 → 임계값 기반 이진 조건
    예: rsi14 < 40 AND rsi14 > rsi14(3일 전) → 5pt

[Step 4] score_analyze.py 백테스트로 검증
  실제 스코어링에 반영 후 방향성 승률 변화 확인
```

---

## 워크플로우 3 — sim=7 전략 설계 준비

feature_discovery 결과를 sim=7 전략 설계에 반영하는 절차.

```
[Phase 1] 기존 피처 한계 파악 (현재 단계)
  python -m feature_discovery.main --cache fd.parquet --mode full
  → 현재 수집된 피처만으로 달성 가능한 AUC 상한 측정

[Phase 2] 새 TR 데이터 수집 결정
  현재 미수집 TR 중 기대 효과가 높은 것 선정:
    OPT10082/83: 주봉/월봉 (다중 시간프레임)
    OPT90004: 프로그램 매매 방향
    OPT10035: 외인 연속 순매매 일수

  수집 우선순위 기준:
    1. feature_discovery에서 이미 있는 비슷한 피처의 예측력
    2. 수집 난이도 (TR 제한, 페이지네이션)
    3. 데이터 가용 기간

[Phase 3] 새 TR 수집 후 재분석
  새 컬럼 daily_buy_list에 추가 후 캐시 재생성
  python -m feature_discovery.main --cache fd_new.parquet --mode full

  AUC 상승 여부 확인 → 새 TR의 실제 예측력 검증

[Phase 4] sim=7 구조 설계
  feature_discovery에서 검증된 피처 조합 →
  hybrid_strategy_v4.py 설계 →
  score_analyze.py 백테스트 →
  실전 배포
```

---

## 두 도구 빠른 참조표

| 궁금한 것 | 사용할 도구 | 명령어 |
|---|---|---|
| score_g가 수익과 선형 상관 있나? | score_component_analysis.py | `python score_component_analysis.py 6` |
| 스코어 컴포넌트 간 비선형 상호작용 | ml_analysis | `--simul 6 --mode boost` |
| 전체 주식 우주에서 inst_flow 효과 | feature_discovery | `--groups supply --mode boost` |
| 10일 후 수익 예측하는 피처 순위 | feature_discovery | `--horizon 10 --mode full` |
| Strategy A vs B 피처 패턴 차이 | ml_analysis TabNet | `--simul 6 --mode full --tabnet` |
| 역상관 피처 발굴 | 양쪽 모두 | `corr_*.csv`에서 r < 0 확인 |
| sim=7 새 피처 후보 | feature_discovery | `--mode full --top_n 30` |
