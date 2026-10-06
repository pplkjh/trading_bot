# ml_analysis — 프로젝트 개요 및 개발 히스토리

---

## 1. JackBot 트레이딩 봇 배경

JackBot은 **Kiwoom OpenAPI** 기반 한국 주식 자동매매 시스템이다.  
Python 3.7 + SQLAlchemy 1.3.x + MySQL 구성으로, 매일 장 마감 후 종목을 스크리닝해  
다음날 아침 자동 매수/매도한다.

### 전략 발전 히스토리

```
simul_num=1  (초기)
  └── 기본 전략: 이동평균 골든크로스 + 단순 RSI 필터

simul_num=3  HybridStrategyV2 (200pt 만점)
  ├── 5가지 팩터: 모멘텀(50) + 평균회귀(20) + 추세강도(50) + 거래량(40) + 상대강도(30) + 다중프레임(10)
  ├── ADX 기반 동적 가중치
  ├── 백테스트(2023–2026): 총수익률 +5,547%, MDD 55%, 승률 60%
  └── 문제점: EOD 종가 기준 "급등+MA정배열" → 다음날 이미 고점에서 매수

simul_num=4/5/6  (현재 실전 운영 중, 2026-05-26~)
  ├── Strategy A — BreakoutStrategyV3 (돌파 초입)
  │     횡보/압축 후 오늘 막 돌파한 종목. MA정배열 완성 전, ADX 낮다가 올라오는 중
  │     백테스트: +8,354%, 승률 70.0%, MDD 6.54%, 평균보유 4.6일
  │
  └── Strategy B — ReversalStrategyV3 (저점 반등)
        RSI 과매도 바닥 패턴 → 중장기 사이클 상승 구간
        백테스트: +65.97%, 승률 64.4%, MDD 3.23%, 평균보유 10.2일
```

### 스코어링 구조 (hybrid_strategy_v3.py — v3.4+inst_flow, 2026-06-08)

```
Strategy A 220pt 만점:
  score_a  셋업품질       50pt  — Pocket Pivot + VCP압축도 + 베이스타이트니스
  score_b  BB+단기MA      60pt  — BB 돌파 위치 + 단기 MA 배열
  score_c  ADX방향성      10pt  — ADX 상승 추세
  score_d  MACD전환       30pt  — MACD 골든크로스
  score_e  RSI50돌파      30pt  — RSI 50선 돌파
  score_f  BB활성도       20pt  — bb_bandwidth 기반 실거래 품질
  score_g  기관수급       20pt  — inst_net_buy/vol + foreign_net_buy/vol  ← 2026-06-08 추가
  penalty  리스크패널티   차감

Strategy B 220pt 만점 (실전) / 180pt (백테스트, 펀더멘털 제외):
  score_a  RSI신호        65pt
  score_b  펀더멘털       40pt  ← 백테스트 비활성 (Look-ahead bias)
  score_c  장기추세       55pt
  score_d  BB사이클       10pt
  score_e  거래량MACD     15pt
  score_f  회복모멘텀     15pt
  score_g  기관수급       20pt  ← 2026-06-08 추가
```

---

## 2. ml_analysis를 만든 이유

### 문제 의식

스코어링 시스템은 수백 시간의 백테스트와 Pearson 상관분석을 기반으로 설계됐지만,  
**여전히 사람이 정한 가중치**다.

```
score_a: 셋업품질 50pt  →  "이 50pt가 정말 수익과 상관있나?"
score_b: BB돌파위치 60pt →  "60pt 기준이 최적인가?"
score_g: 기관수급 20pt   →  "inst_flow가 독립적 신호인가? 아니면 다른 피처가 이미 반영하는가?"
```

기존 상관분석(`score_component_analysis.py`)은 단일 Pearson r 계산이다.  
여러 피처 간의 **비선형 상호작용**, **feature interaction**, **redundancy**를 파악하지 못한다.

### 보완 관계: score_component_analysis.py vs ml_analysis

| 도구 | 방법 | 알려주는 것 |
|---|---|---|
| `score_component_analysis.py` | Pearson r | 각 컴포넌트가 sell_rate와 선형 상관 여부 |
| `ml_analysis` | CatBoost + LASSO + SHAP | 비선형 상호작용, 피처 간 redundancy, 중요도 순위 |

### ml_analysis의 4가지 목표

1. **어떤 피처/컴포넌트가 수익에 실제로 기여하는가?**  
   score_a~g 뿐 아니라 원시 지표(RSI, ADX, inst_buy_ratio 등) 전체 비교

2. **비선형 효과가 얼마나 중요한가?**  
   LASSO(선형) vs CatBoost(비선형) AUC 비교

3. **Strategy A와 B는 다른 피처를 보는가?**  
   TabNet attention map으로 거래별 집중 피처 시각화

4. **inst_flow(score_g)가 독립적 신호인가?**  
   기존 score_a~f와 독립적으로 예측력이 있는지 SHAP으로 분리 검증

---

## 3. 개발 히스토리

### Phase 1 — 기초 구조 (2026-06 초)

- `data_loader.py`: all_item_db 로드 + daily_buy_list 확장 지표 JOIN
- `train.py`: WalkForwardCV + CatBoost
- `analyze.py`: Pearson 상관 + SHAP
- `main.py`: CLI 파이프라인

### Phase 2 — 모델 확장

- LightGBM 추가 (CatBoost 결과 교차검증용, 5~10배 빠름)
- LASSO L1 추가 (불필요 피처 자동 탈락, 선형 효과 분리)
- Permutation Importance 추가 (모델 독립적 검증)
- TabNet 추가 (거래별 attention — Strategy A/B 피처 패턴 차이 시각화)

### Phase 3 — inst_flow 추가 (2026-06-08)

- `backfill_inst_data.py`: OPT10045로 전 종목 과거 수급 데이터 수집
- `migration_inst_to_daily_buy_list.py`: daily_craw → daily_buy_list 이관
- `hybrid_strategy_v3.py`: `score_g = _score_inst_flow()` 추가 (A/B 공통)
- `ml_analysis/config.py`: `'supply'` 피처 그룹 추가
- `ml_analysis/data_loader.py`: `inst_buy_ratio`, `foreign_buy_ratio` 파생 피처 추가

---

## 4. 데이터 흐름

```
[MySQL DB]
  daily_craw          일봉 OHLCV + inst_net_buy/foreign_net_buy (OPT10045 backfill)
  daily_buy_list      날짜별 후보 종목 테이블 (YYYYMMDD, 기술적 지표 + 수급)
  simulator4/5/6      백테스트 매매 결과 (all_item_db)
  jackbot4_imi1       실전 매매 결과 (all_item_db)

       ↓ data_loader.py
[DataFrame — 완료 거래]
  N건 (buy_date, sell_date, sell_rate, score_a~g, ...)
  + daily_buy_list에서 확장 지표 JOIN (macd, adx, obv, inst_net_buy, ...)
  + 파생 피처 계산 (close/ma비율, bb_position, inst_buy_ratio, ...)

       ↓ train.py
[ML 모델 — Walk-Forward CV]
  CatBoost / LightGBM / LASSO / RF / TabNet

       ↓ analyze.py
[결과]
  Pearson 상관계수 CSV + 차트
  피처 중요도 CSV + 차트
  SHAP beeswarm / bar plot
  Permutation Importance CSV
```

---

## 5. 구조적 한계 (반드시 인지)

| 한계 | 설명 |
|---|---|
| **선택 편향** | score ≥ 100/90pt 통과한 종목만 분석. 전체 주식 우주 대비 편향 존재 |
| **매도 의존성** | sell_rate는 -5%/trailing 매도에 의해 잘린 값. 순수 주가 상승과 다름 |
| **Strategy B 샘플 부족** | ~200건은 ML에 통계적으로 불충분. 참고 수준 |
| **look-ahead 방지** | daily_buy_list 지표 자체는 해당 날짜 종가 기준 (정상). 펀더멘털은 비활성화 |

> 선택 편향 문제를 해결하는 도구 = `feature_discovery/`  
> (필터 이전 전체 후보 + 실제 미래 가격 라벨 사용)

---

## 6. feature_discovery와의 관계

```
ml_analysis      : "필터 통과한 거래 중 어느 피처가 더 나은 결과를 냈는가?"
feature_discovery: "필터 이전 전체 후보 중 어느 피처가 주가 상승을 예측하는가?"

두 도구의 결과를 교차 검증:
  inst_buy_ratio가 양쪽에서 모두 높음 → 진짜 독립 신호 (score_g 비중 올릴 근거)
  feature_discovery에서만 높음 → 기존 필터가 이미 흡수 중
  양쪽 다 낮음 → inst_flow 효과 없음 (score_g 제거 검토)
```
