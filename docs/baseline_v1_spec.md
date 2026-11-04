# Strategy E — baseline_v1 명세서

> 수립일: 2026-08-11  
> 수립 배경: 데이터 무결성 감사 후 손상 전 기간에서 측정된 모든 기준선을 무효화하고
> 손상 수정 완료(870개 날짜 재계산) 후 신규 수립.  
> 이전 기록: `backtest_report/invalidated_baselines.md`

---

## 1. 매수 조건

### 1-1. 기술 필터 (`value_strategy_e.py` screen())

| 조건 | SQL | 비고 |
|---|---|---|
| 거래대금 | `vol20 * close >= 10_000_000_000` | 일평균 100억, 소형주·조작주 차단 |
| 3단 정배열 | `close > clo20 AND clo20 > clo60 AND clo60 > clo120` | 중기 추세 확인 |
| DMI 방향성 | `plus_di > minus_di` | 상승 추세 우위 |
| 위험종목 제외 | NOT EXISTS (아래 참조) | 날짜 필터 적용 |
| 정렬 | `ORDER BY (clo120 / yes_clo120) DESC` | 120일MA 모멘텀 상위 |
| 최대 신호 | `LIMIT 3` | 일별 최대 3종목 |

### 1-2. 위험종목 날짜 필터

| 테이블 | 활성 조건 | 근거 |
|---|---|---|
| `stock_invest_caution` | `post_date <= date AND fix_date >= date` | fix_date = 해제일 (avg 1.5일, max 8일) |
| `stock_invest_warning` | `post_date <= date AND (cleared_date IS NULL OR cleared_date >= date)` | cleared_date = 실제 해제일 |
| `stock_invest_danger` | 위와 동일 | 동일 스키마 구조 |
| `stock_managing` | 날짜 필터 없음 — 현재 등록 전체 제외 | 날짜 컬럼 미존재 (낙관 편향 명시) |
| `stock_konex` | 날짜 필터 없음 — 현재 등록 전체 제외 | 날짜 컬럼 미존재, 실제 매칭 92~109건/일 |

### 1-3. 데이터 유효성

- 백테스트 구간: **2023-01-02 ~ 2026-08-10** (손상 수정 완료 구간)
- 지표 재계산: `sql/recalculate_indicators.py` (20230102~20260728) +
  `scripts/recalc_extend_810.py` (20260729~20260810)
- 손상 이전 기준선 결과가 이 스펙과 다를 수 있음 (정상)

---

## 2. 매도 조건 (시뮬레이터 구현)

우선순위 순:

| 우선순위 | 조건 | 비고 |
|---|---|---|
| 1 | `rate <= -15%` | 손절선 |
| 2 | `present_price < ma60` | MA60 이탈 청산 |
| 3 | `rsi14 >= 80` | 과매수 청산 |

> 매도 로직 구현 위치: `library/simulator_func_mysql.py` (simul_num=10 분기)

---

## 3. 시뮬레이션 파라미터

| 항목 | 값 |
|---|---|
| 포트폴리오 슬롯 | 5 |
| 종목당 투자금 | 200만원 |
| 체결 방식 | 신호 다음날 종가 체결 |
| 왕복 비용 | 0.23% |
| 최대 동시 신호 | 3 (빈 슬롯이 부족하면 선착순) |

---

## 4. baseline_v1 결과 (기록 예정)

> 백테스트 실행 후 여기에 기재. 현재 미실행.

| 항목 | 값 |
|---|---|
| 측정 기간 | — |
| 거래 수 | — |
| 승률 | — |
| 수익률 | — |
| MDD | — |
| 샤프 | — |

---

## 5. 비고

- B차(112거래/42.9%/+119%)와 수치가 다른 것은 **정상**:
  B차는 37% 손상 풀에서 측정됐고, 선택 편향이 존재함.
- `ORDER BY close/clo120 DESC` (4차)에서 `ORDER BY clo120/yes_clo120 DESC` (baseline_v1)으로 변경:
  종가 과열 기준 → 120일MA 상승 모멘텀 기준.
- 6단→3단 완화: 6단은 역선택 문제(추세 꺾이는 종목 선택) 확인됨.
