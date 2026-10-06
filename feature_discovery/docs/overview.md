# feature_discovery — 프로젝트 개요 및 제작 배경

---

## 1. 왜 만들었는가

### ml_analysis의 구조적 한계

`ml_analysis`는 simulator4/5/6의 `all_item_db`를 분석한다.  
이 DB에는 **스코어 필터(score ≥ 100/90pt)를 이미 통과한 거래만** 기록되어 있다.

```
[전체 한국 주식 2,300종목]
        ↓ daily_buy_list 후보 필터
[매일 후보 종목 200~2,000개]
        ↓ BreakoutStrategyV3 스코어링 (≥ 100pt)
[매수 대상 5~20개]  ← ml_analysis는 여기서만 분석
        ↓ 매도 후
[all_item_db 거래 결과]
```

이 구조에서 ml_analysis는 다음 질문에만 답할 수 있다:

> "**이미 좋은 종목으로 분류된 것들 중에서** 어느 피처가 더 나은 결과를 냈는가?"

반면 우리가 정말 알고 싶은 것은:

> "**전체 후보 종목 중에서** 어떤 피처를 가진 종목이 실제로 올랐는가?"

이 두 질문은 **선택 편향(selection bias)** 때문에 다른 답을 낼 수 있다.

### 선택 편향의 구체적 예

inst_buy_ratio(기관 순매수 비율)를 예로 들면:

```
ml_analysis 관점:
  "score ≥ 100pt인 종목 중 inst_buy_ratio 높은 것이 더 수익이 났는가?"
  → 이미 다른 지표로 좋은 종목을 골랐는데, 그 안에서 inst 효과 측정
  → inst와 상관있는 피처(거래량, BB, ADX)가 이미 필터에 들어가 있다면 inst 효과가 희석됨

feature_discovery 관점:
  "일봉 후보 2,000종목 중 inst_buy_ratio 높은 날 이후 10일 수익률이 실제로 높은가?"
  → 선택 편향 없이 raw 예측력 측정
  → inst_flow가 정말 독립적 신호인지 직접 검증
```

### 또 다른 라벨 문제

ml_analysis의 `sell_rate`는 매도 전략(-5% SL, trailing)에 의해 **잘린 수익률**이다.

```
실제 주가가 +15% 올랐지만 trailing에서 +6%에 팔린 경우 → sell_rate = 6%
```

feature_discovery의 라벨 = **N일 후 실제 주가** → 매도 전략 왜곡 없음.

---

## 2. feature_discovery가 답하는 질문

1. **어떤 원시 지표가 주가 상승을 예측하는가?**  
   (필터 없이 전체 후보 대상)

2. **inst_flow(기관/외국인 수급)는 진짜 독립적 신호인가?**  
   (기존 필터와 독립적으로 예측력이 있는지 검증)

3. **예측 효과가 몇 일 후 가장 강한가?**  
   (5일 / 10일 / 15일 호라이즌 비교)

4. **sim=7 새 전략 설계를 위한 피처 후보 발굴**  
   (현재 스코어에 없는 새로운 예측 신호 탐색)

---

## 3. 개발 배경 및 히스토리

### 계기

2026-06-10, `docs/KIWOOM_API_REFERENCE.md` 작성 과정에서  
현재 수집 중인 데이터 외에도 활용 가능한 TR이 훨씬 많다는 것을 발견.

주요 미수집 TR:
- OPT10045: 기관/외국인 순매수 (→ 이미 backfill 완료)
- OPT10034/35: 외인 연속 순매매 상위
- OPT10082/83: 주봉/월봉
- OPT90004: 프로그램 매매
- OPT10042: 순매수 거래원 순위

### 구현 결정

추가 TR 데이터를 ML로 분석해 어떤 것이 유의미한지 먼저 검증하고,  
그 결과를 sim=7 설계에 반영하는 전략을 수립.

**feature_discovery = "실험실"**, **sim=7 = "양산"** 의 관계.

---

## 4. ml_analysis와의 관계 및 차이

| | ml_analysis | feature_discovery |
|---|---|---|
| **데이터 입력** | all_item_db (필터 통과한 거래) | daily_buy_list 전체 후보 |
| **라벨** | sell_rate (매도전략에 의해 잘린 값) | N일 후 실제 주가 상승률 |
| **샘플 수** | ~17,000건 (sim=4, 3년) | ~300,000~500,000건 |
| **목적** | 현재 스코어 구조 개선 검증 | 새로운 예측 신호 발굴 |
| **선택 편향** | 있음 (필터 통과 종목만) | 없음 (전체 후보) |
| **score_a~f** | 있음 (분석 대상) | 없음 (필터 이전이라 미계산) |
| **적합한 질문** | "현재 스코어 개선 방향?" | "어떤 피처가 주가 상승 예측?" |

### 두 도구를 함께 쓰는 법

```
1. feature_discovery로 원시 피처 예측력 확인
   → "inst_buy_ratio가 전체 후보에서 통계적으로 유의미한 신호인가?"

2. ml_analysis로 스코어에 반영 효과 검증
   → "score_g(inst_flow)를 추가했을 때 filtered 거래 결과가 개선됐는가?"

3. score_component_analysis.py로 최종 확인
   → "score_g Pearson r이 양수이고 유의미한가?"

4. 백테스트로 채택 결정
   → "composite_score 개선 + 승률/수익률 변화 확인"
```

---

## 5. 데이터 흐름

```
[MySQL DB]
  daily_buy_list   날짜별 후보 종목 (YYYYMMDD 테이블)
    → code, code_name, close, volume
    → clo5~clo120 (MA), rsi14, bb_*, atr14
    → macd, adx, plus_di, minus_di
    → obv, mfi14, cmf20
    → ichimoku_tenkan, ichimoku_kijun
    → inst_net_buy, foreign_net_buy  ← OPT10045 backfill
    → candle_pattern_score, bb_bandwidth

  daily_craw       종목별 일봉 OHLCV (회사명 테이블)
    → date, close, high  ← N일 후 가격 조회용

         ↓ data_builder.py
[DataFrame]
  후보 종목 300K~500K행
  + 파생 피처 (close_vs_clo20, bb_position, inst_buy_ratio 등)
  + 라벨 (fwd_return_5d, fwd_return_10d, fwd_return_15d)
  + fwd_max_5d, fwd_max_10d (N일 내 최대 상승률)

         ↓ main.py → ml_analysis.train
[ML 모델 — Walk-Forward CV]
  CatBoost / LightGBM / LASSO / RandomForest

         ↓ ml_analysis.analyze
[결과]
  Pearson r CSV + 차트
  피처 중요도 CSV + 차트
  SHAP beeswarm / bar plot
  Permutation Importance CSV
```

---

## 6. 한계 및 주의사항

| 한계 | 설명 |
|---|---|
| **후보 풀 편향** | daily_buy_list도 기본 필터(거래량 등) 적용된 후보임. 상장 전 종목 포함 불가 |
| **라벨 미래 유출 없음** | fwd_return = N 거래일 후 실제 가격 (look-ahead bias 없음) |
| **수급 데이터 공백** | backfill 이전 기간은 inst_buy_ratio = NaN. 분석 시 기간 조정 필요 |
| **로드 시간** | 전체 기간 3년 × 2,000종목 = 10~20분. `--cache` 옵션으로 재사용 권장 |
| **시장 국면 변화** | Walk-Forward CV가 완전한 해결책은 아님. bull/bear 국면별 재분석 권장 |
