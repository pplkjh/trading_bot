# Issue-001: daily_craw 코드명 매핑 실패 (104종목 atr14=0 잔류)

> 등록일: 2026-08-11  
> 우선순위: LOW  
> 상태: OPEN  
> 관련 Task: Step 4-B (데이터 무결성 감사 후속)

---

## 현상

`daily_buy_list` 날짜 테이블에 `atr14=0.0` 또는 `atr14 IS NULL`로 남아 있는 종목이
`20260728` 기준 104개 존재한다. `recalculate_indicators.py` 전면 재계산 후에도 해소되지 않음.
P-1 연장(20260729~20260810) 후에도 동일 종목들이 102~107개/날짜로 유지됨.

예시 종목 (일부):
- DGI (099520), DH오토넥스 (000300), EDGC (245620)
- SPAC 계열: IBKS제24호스팩, 교보15호스팩, 미래에셋비전스팩7호, 유진스팩10호
- 소형 바이오: 나노솔루션, 레메디, 에이치엘지노믹스 등

## 원인 가설

`recalculate_indicators.py`는 `daily_buy_list` 테이블의 `code_name` 컬럼을 `daily_craw` 테이블명으로 직접 조회한다. 다음 중 하나의 이유로 매핑이 실패한다:

1. **회사명 변경**: 과거에는 A명칭이었으나 현재 B명칭으로 변경. `daily_buy_list`는 현재 명칭, `daily_craw`는 구 명칭(또는 반대).
2. **특수문자·공백 차이**: 중간점(·), 괄호, 숫자 표기 방식이 두 DB 간 다름.
3. **인코딩 차이**: UTF-8 vs EUC-KR 처리 방식 차이로 같은 글자가 다른 바이트열.
4. **SPAC 명칭 규칙**: SPAC은 설립 후 합병 시 사명이 변경되며, 두 DB의 갱신 시점이 다를 수 있음.

## 영향 평가

| 항목 | 평가 |
|---|---|
| baseline_v1 매수 필터 | **영향 없음** — ATR 미사용 (3단정배열+DMI+거래대금만 사용) |
| D-7 frozen ATR 탐지 | **영향 없음** — atr14=0은 volume=0 기간과 구분 가능 |
| 향후 ATR 기반 필터 추가 시 | **주의 필요** — 104종목 제외 또는 별도 처리 필요 |
| 비중 | 전체 2,757종목 중 104개 = **3.8%** (이전 추정 "0.7%" 수정) |

## 해결 방안 (미실행)

1. **진단**: `daily_buy_list` code_name과 `daily_craw` table_name의 전수 비교 → 불일치 목록 추출
2. **매핑 테이블**: code → correct_craw_table_name 매핑 테이블 생성
3. **재계산**: 104종목에 대해 correct_craw_table_name으로 재처리

## 구현 예시 (미실행, 참고용)

```sql
-- 불일치 후보 찾기: code_name이 daily_craw에 없는 종목
SELECT DISTINCT t.code, t.code_name
FROM `20260728` t
WHERE t.atr14 = 0 OR t.atr14 IS NULL
  AND NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='daily_craw' AND table_name = t.code_name
  )
```

---

> **지시 전까지 수정하지 않는다.** 별도 작업 지시 후 처리.
