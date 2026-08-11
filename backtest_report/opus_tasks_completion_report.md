# Opus 지시 이행 완료 보고서

> 작성일: 2026-08-11  
> 브랜치: `claude/optimize-trading-system-01QGef7W2a7VPiNKLNBvgfE3`  
> 이전 보고서: `backtest_report/step1_3_result_report.md`

---

## 1. 판단 1 — B차 무효 확정 처리 ✅

### 수행 내용

`backtest_report/data_integrity_audit_report.md` Section 2 (Task A - valid_from 해석) 에 주석 추가.

### 결론 요약

| 항목 | 내용 |
|---|---|
| valid_from 재해석 | "처음 생겼다" → "~100% 완성됐다" (완성일) |
| 이전 구간 실태 | ADX/DMI: 63% 유효, 37% 제로 (LIMIT 120 아티팩트) |
| B차 무효 사유 | 정체불명의 63% 부분집합에서 측정, 선택 편향 불명, 재현 불가 |
| 조치 | 구 성과표 → `backtest_report/invalidated_baselines.md` 격리 (무효 헤더 포함) |
| 비고 | 63/37 분할 규칙 조사 안 함 (Opus 지시: "조사하지 마라") |

---

## 2. 판단 2 — baseline_v1 신규 수립 ✅

### 수행 내용

1. `library/value_strategy_e.py` 전면 교체 (4차 조건 → baseline_v1)
2. `docs/baseline_v1_spec.md` 신규 생성 (완전 명세서)
3. `docs/prompts/strategy_e_diagnosis_prompt.md` 구 성과표 섹션 제거 + 무효화 헤더
4. git 커밋 완료

### baseline_v1 매수 조건

```sql
WHERE (vol20 + 0.0) * close >= 10_000_000_000   -- 거래대금 100억
  AND close > clo20 AND clo20 > clo60 AND clo60 > clo120   -- 3단정배열
  AND plus_di > minus_di                          -- DMI 방향성
  AND NOT EXISTS (stock_invest_caution ... 날짜 필터)
  AND NOT EXISTS (stock_invest_warning ... 날짜 필터)
  AND NOT EXISTS (stock_invest_danger  ... 날짜 필터)
  AND NOT EXISTS (stock_managing ...)
  AND NOT EXISTS (stock_konex ...)
ORDER BY (clo120 / yes_clo120) DESC   -- 120일MA 모멘텀
LIMIT 3
```

### 기존과의 차이

| 항목 | 4차 (이전) | baseline_v1 |
|---|---|---|
| 정배열 단계 | 6단 (clo5>clo20>clo40>clo60>clo80>clo120) | 3단 (close>clo20>clo60>clo120) |
| MA 상승 조건 | AND clo20>yes_clo20 AND clo60>yes_clo60 AND clo120>yes_clo120 | 제거 |
| ATR 필터 | atr14/close <= 0.030 | 제거 |
| BB 필터 | bb_bandwidth <= 0.13 | 제거 |
| ADX 범위 | 18~35 | 제거 |
| 거래량비율 | vol20/vol120 BETWEEN 0.7 AND 1.8 | 제거 |
| 눌림목 범위 | close BETWEEN clo40*0.97 AND clo20*1.03 | 제거 |
| RSI 범위 | rsi14 BETWEEN 40 AND 58 | 제거 |
| 거래량 조건 | vol5 < vol20 * 1.1 AND macd > 0 | 제거 |
| 정렬 기준 | close/clo120 DESC | clo120/yes_clo120 DESC |
| 위험종목 필터 | 날짜 필터 없음 (역사적 전체 배제) | 날짜 필터 적용 |

---

## 3. 판단 3 — 위험종목 날짜 필터 ✅

### 사전 확인 결과 (이전 세션에서 DB 쿼리 완료)

| 테이블 | 확인 내용 | 결론 |
|---|---|---|
| `stock_invest_caution` | DATEDIFF(fix_date, post_date) avg=1.5일, max=8일 | fix_date = 해제일 (투자주의는 1~8일 단기 지정) |
| `stock_invest_warning` | post_date → fix_date(고시) → cleared_date(해제) 순서 확인 | cleared_date = 실제 해제일 |
| `stock_invest_danger` | warning과 동일 스키마 (post_date, fix_date, cleared_date) | 동일 패턴 |
| `stock_managing` | 날짜 컬럼 없음 | 현재 등록 전체 제외 (낙관 편향 명시) |
| `stock_konex` | 날짜 컬럼 없음 | 현재 등록 전체 제외 |

### 적용된 필터 (value_strategy_e.py 반영)

```sql
-- caution: fix_date = 해제일
AND NOT EXISTS (SELECT 1 FROM stock_invest_caution c
  WHERE c.code = a.code
    AND c.post_date <= '{date_fmt}'
    AND c.fix_date  >= '{date_fmt}')

-- warning: cleared_date = 실제 해제일 (NULL = 현재 지정 중)
AND NOT EXISTS (SELECT 1 FROM stock_invest_warning w
  WHERE w.code = a.code
    AND w.post_date <= '{date_fmt}'
    AND (w.cleared_date IS NULL OR w.cleared_date >= '{date_fmt}'))

-- danger: 동일 구조
AND NOT EXISTS (SELECT 1 FROM stock_invest_danger d
  WHERE d.code = a.code
    AND d.post_date <= '{date_fmt}'
    AND (d.cleared_date IS NULL OR d.cleared_date >= '{date_fmt}'))
```

---

## 4. P-1 — 재계산 구간 20260810 연장 ✅

### 실행 결과

| 항목 | 값 |
|---|---|
| 연장 날짜 | 9개 (20260729~20260810) |
| 처리 종목 | 2,757개 |
| UPDATE 성공 | ~24,813건 (9날짜 × 2757종목 × 1행) |
| skip | 0 |
| 방법 | `recalc_extend_810.py` (original compute_all_indicators 로직 import) |

### 검증

| 날짜 | avg_atr | zero_atr | null_atr |
|---|---|---|---|
| 20260729 | 2,014.97 | 102개 | 14개 |
| 20260807 | 1,941.78 | 105개 | 4개 |
| 20260810 | 1,929.36 | 107개 | 2개 |

삼성전자 20260810: atr14=23,092.86, adx=26.30, rsi14=42.16 (정상값, 非고정값)

zero_atr 102~107개는 Issue-001 (코드명 매핑 실패) 로 별도 등록. baseline_v1에 실질적 영향 없음.

### 수집기 결함 이슈 등록

`backtest_report/issues/issue_002_collector_defect.md` 참조.  
별도 지시 전 수정 금지.

---

## 5. P-2 — D-2~D-6 게이트 상대 기준 재설계 ✅

### 이전 문제

절대 밴드 (adx: 15~30, rsi: 45~60 등)가 시장 국면 변화를 데이터 손상으로 오탐.
FAIL이 발생해도 "현재 시장 수준"일 수 있어 실용적이지 않음.

### 신규 설계 (sql/daily_etl_validator.py)

```python
# 상대 기준 (±30% 이탈 = 데이터 손상 가능성)
|당일값 / 직전60일 평균 - 1| < 0.30

# 절대 안전망 (항상 검사)
adx:     5 ~ 80
rsi14:   5 ~ 95
mfi14:   5 ~ 95
atr_pct: 0.5% ~ 20%
bb_bw:   3% ~ 75%
```

새 함수 `get_60d_baseline(conn, date_str)`:
- 직전 60 거래일 테이블에서 각 지표 평균 조회
- 60일 미만이면 None → 절대 안전망 fallback

로그에 `b60_*` 컬럼 추가 (60일 기준선 추적).

### 설계 원칙

> 게이트의 목적은 데이터 손상 탐지이지 시장 국면 탐지가 아니다.
> 시장이 아무리 변동해도 ±30% 이상 이탈하지 않으면 PASS.
> 데이터가 손상되면 급격히 이탈하므로 탐지 가능.

---

## 6. P-3 — KONEX 필터 유지 ✅

### 매칭 건수

| 날짜 | daily_buy_list × stock_konex 매칭 |
|---|---|
| 20260807 | 109건 |
| 20250602 | 103건 |
| 20230601 | 92건 |

→ 0건이 아님. 필터가 실제로 작동하며 92~109종목을 매일 제외함.  
→ 제거 제안 안 함. 현행 유지.

---

## 7. Step 4-A — 36% 손상 수치 재조정 ✅

감사 보고서 Section 11 (`backtest_report/data_integrity_audit_report.md`) 참조.

**요약**: "36%"와 "valid_from 재해석 (37% 제로)"은 완전히 정합. 수치 재조정 불요.  
두 해석의 차이는 측정 방법의 차이(샘플 5날짜 vs 전체 평균)였으며, 같은 현상을 가리킨다.

---

## 8. Step 4-B — daily_craw 미수록 종목 분류 수정 ✅

### 감사 보고서 기존 수치: "20개 미수록"

### 실제 조사 결과

| 분류 | 건수 |
|---|---|
| 활성 (코드명 매핑 실패) | 103개 |
| 상폐 (더테크놀로지 043090) | 1개 |
| **합계** | **104개** |

- 원인: "daily_craw 미수록" ❌ → "코드명 매핑 실패" ✅  
  (`information_schema`로 조회 시 in_craw=True이나 recalculate가 매핑하지 못함)
- 영향: baseline_v1에서 ATR 미사용 → 실질적 영향 없음
- Issue-001 (`backtest_report/issues/issue_001_codename_mapping.md`) 등록

---

## 9. 변경 파일 목록

| 파일 | 변경 내용 |
|---|---|
| `library/value_strategy_e.py` | baseline_v1 매수 조건 + 날짜 필터 |
| `docs/baseline_v1_spec.md` | 신규 — baseline_v1 전체 명세 |
| `docs/prompts/strategy_e_diagnosis_prompt.md` | 구 성과표 제거 + 무효화 헤더 |
| `backtest_report/invalidated_baselines.md` | 신규 — 무효화된 A/B/C/D차, 1~4차 |
| `backtest_report/data_integrity_audit_report.md` | Section 11/12 추가 + valid_from 주석 |
| `sql/daily_etl_validator.py` | D-2~D-6 상대 기준 재설계 + 60일 baseline |
| `backtest_report/issues/issue_001_codename_mapping.md` | 신규 |
| `backtest_report/issues/issue_002_collector_defect.md` | 신규 |

git 커밋: `c2b407a` (2026-08-11, baseline_v1 수립 + P-2 + 판단 1/2/3)

---

## 10. 미완료 / 별도 지시 필요

| 항목 | 이유 |
|---|---|
| Phase 0-B/0-D 재측정 | 별도 지시 대기 |
| baseline_v1 백테스트 실행 | 별도 지시 대기 (`docs/baseline_v1_spec.md` 명세 완료) |
| Issue-001 코드명 매핑 수정 | 별도 지시 대기 |
| Issue-002 수집기 결함 수정 | 별도 지시 대기 |
| D-8 외부 대조 수동 검증 | 사용자 직접 수행 필요 (인터넷 접근 불가) |
| daily_etl_validator.py → collector 연결 | 권장 작업 — 별도 지시 후 |
