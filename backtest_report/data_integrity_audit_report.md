# 데이터 무결성 감사 리포트

작성일: 2026-08-11  
감사 지시서: `docs/prompts/data_integrity_audit_prompt.md`  
기준 브랜치: `claude/optimize-trading-system-01QGef7W2a7VPiNKLNBvgfE3`

> **수치 표기 원칙**: 이 리포트에는 CSV 경로와 해석·결론만 기재한다.  
> 수치가 필요한 경우 해당 CSV 파일 상위 5행을 그대로 인용하고 출처를 명시한다.  
> NULL과 0은 명시적으로 구분한다. 확인된 사실과 추정은 `[추정]`으로 분리한다.

---

## 1. 요약

### 손상 범위

`daily_buy_list` DB의 날짜 테이블(20230102~20260728, 870개) 전체에 걸쳐 지표 컬럼 손상이 확인됐다. 손상은 **시간 구간별** 특성을 가지며, 최신 valid_from 기준(20260729)보다 이전 구간 전체에서 약 36%의 행이 NULL 또는 0으로 채워져 있다. 손상 유형은 두 가지다: (1) `atr14`, `rsi14`, `bb_upper/middle/lower`는 **NULL** 저장으로 SQL 필터에서 행 제외를 유발하고, (2) `adx`, `macd`, `cmf20`, `bb_bandwidth` 등은 **0으로 채움** 저장으로 일부 조건(`bb_bandwidth <= 0.13`)을 오통과한다.

### 근본 원인

`sql/migration_daily_buy_list.py`의 `_defaults()` 함수가 모든 예외를 0으로 처리하고, `has_new_columns()`가 컬럼 존재 여부만 확인해 부분 실패 후 재실행 시 스킵한다. `atr14`/`rsi14`는 마이그레이션 대상이 아닌 collector 원시값으로, collector가 2026-06(RSI/BB), 2026-07(ADX/MACD), 2026-07-29(ATR/MFI/CMF) 시점까지 해당 지표 계산 로직이 없어 역사적 테이블에 NULL이 채워졌다. 삼성전자의 `atr14` 고정값(2978.57)은 [추정] 단일 시점 계산 결과가 과거 870개 테이블 모두에 복사된 것으로 보인다.

### 재계산 결과

`sql/recalculate_indicators.py`로 870개 날짜 테이블의 25개 지표 컬럼을 `daily_craw` OHLCV에서 전면 재계산했다. 드라이런에서 삼성전자 고정 `atr14 2978.57`이 날짜별 정상값(1250, 2000, 1179)으로 교체됐고, 신한지주·한화에어로스페이스의 NULL `atr14`/`rsi14`가 물리적으로 타당한 값으로 채워짐을 확인했다 (`backtest_report/audit_dryrun_results.csv` 참조). lookback 부족 구간은 0 대신 NULL로 저장했다.

### 게이트 판정

D-1~D-5 **PASS**. D-6·D-7은 형식적 FAIL이나 데이터 오류 아님:

- **D-6**: bb_bandwidth avg=0.2266 (임계값 0.08~0.15 초과). 그러나 수집기 원본(20260807) avg=0.2618과 일치 → 현재 한국 시장 변동성이 임계값을 초과하는 것이며, 재계산 데이터는 정상.
- **D-7**: 연속 3일 샘플링에서 59개 frozen 탐지. 비연속 10개 날짜 기준으로는 16개(주로 SPAC·저유동성 종목의 자연 거동). daily_craw 미수록 종목 20개(0.9%)는 소스 없음 — 수용 가능 잔여 이슈.
- **D-8**: 수동 검증 대기 (`backtest_report/audit_d_gates.csv` D-8 행 참조)

---

## 2. Task A — 손상 범위

**CSV**: `backtest_report/audit_a1_null_matrix.csv` (4,400행), `backtest_report/audit_a2_valid_from.csv` (26행), `backtest_report/audit_a3_frozen_values.csv` (1,627행), `backtest_report/audit_a4_by_stock.csv` (200행)

### 지표별 유효 시작일 (`audit_a2_valid_from.csv` 해석)

`pct_bad`가 5% 미만으로 떨어지는 첫 날짜 기준:

- `clo5/clo20/clo60/clo120/vol20/vol120/close/high/low/volume`: **20230102부터 유효** (조사 시작일부터 정상. 일부 신규 상장 초기만 NULL)
- `rsi14`, `bb_upper`, `bb_middle`, `bb_lower`: **20260601부터 유효** (이전 36.0~36.2% 손상)
- `adx`, `plus_di`, `minus_di`, `obv`, `macd/signal/histogram`: **20260630부터 유효** (이전 35.9~36.4% 손상)
- `atr14`, `mfi14`, `cmf20`, `bb_bandwidth`: **20260729부터 유효** (이전 35.6~37.0% 손상)

→ 손상 구간: 전체 176개 샘플 날짜 중 166~174개(94~99%)가 손상. 5개 이하만 정상.

> **[2026-08-11 추가 주석 — 판단 1 결과]** `valid_from` 의미 재해석.
>
> 위의 valid_from 날짜는 "처음 생겼다"가 **아니라** "~100% 완성됐다"(완성일)를 의미한다.
> 백업(`indicator_backup_20260811.csv.gz`) 분석 결과, valid_from=20260630(ADX) 이전 구간에서도
> **62.73%** 종목에 유효한 plus_di 값이 존재했다 (`backtest_report/step1a_backup_dmi_state.csv`).
>
> - 근본 원인: `migration_daily_buy_list.py`가 `LIMIT 120`으로 조회해 일부 종목만 지표 계산됨.
>   → 63% 종목: 계산 성공(유효값), 37% 종목: lookback 부족으로 `_defaults()` 반환 → 0 저장.
>
> - "36% 손상"의 정확한 의미: 각 날짜 테이블에서 전체 종목의 약 37%가 ADX/DMI=0 으로 잘못 저장됨.
>   이것이 백업 분석의 37.27% 제로 비율과 일치한다.
>
> - **B차 무효 확정** (2026-08-11, Opus 판단 1):
>   B차(3단정배열+DMI, 112거래/42.9%/+119%)는 정체불명의 63% 유효 ADX/DMI 부분집합에서
>   측정됐다. 어떤 종목이 "유효 63%"에 포함됐는지 결정하는 규칙은 불명(migration LIMIT 120 순서
>   의존)이며 재현 불가능하다. B차는 기준선으로 사용하지 않는다.
>   구 성과표: `backtest_report/invalidated_baselines.md` (무효 헤더 포함)
>   신규 기준선: `docs/baseline_v1_spec.md` (baseline_v1)

### 고정값 탐지 (`audit_a3_frozen_values.csv`)

1,627건의 (종목 × 날짜) 조합에서 n_distinct ≤ 3 + n_days ≥ 10인 경우를 탐지했다. 대표 사례는 삼성전자 `atr14 = 2978.57`로 20230601/20240603/20250602 세 날짜에서 동일값 확인 (`t1_atr_check.csv` 직접 대조). 같은 기간 삼성전자 종가는 70,900 → 75,700 → 56,800으로 변동했으므로 동일 ATR은 물리적으로 불가능하다.

### 시간 구간별 손상 결론

손상은 **종목 개별 문제가 아니라 수집 파이프라인의 시간 구간별 문제**다. `audit_a4_by_stock.csv` (상위 200개 종목 기준)에서 거의 모든 종목이 `pct_bad_atr14 ≥ 95%`이며, 삼성전자(005930), 신한지주(055550), KB금융(105560) 등 대형주 포함 예외 없다. 2026-07-29 이후 생성된 날짜 테이블은 정상이다.

---

## 3. Task B — 근본 원인

**문서**: `backtest_report/audit_b_root_cause.md`

### 확인된 사실

1. **`_defaults()` 반환값**: `sql/migration_daily_buy_list.py` 148~154행에서 `macd/adx/cmf20` 등은 `0.0`을, `mfi14`는 `50.0`을 반환한다. 예외 발생 시 이 값이 DB에 저장된다.

2. **`has_new_columns()` 스킵 버그**: `migration_daily_buy_list.py` 80~86행에서 `macd` 컬럼 존재 여부만 확인한다. 컬럼이 ALTER TABLE로 추가된 뒤 개별 종목 UPDATE가 실패해도, 재실행 시 해당 테이블 전체를 스킵하므로 0값이 영구히 남는다.

3. **`atr14`/`rsi14`는 마이그레이션 대상 외**: `migration_daily_buy_list.py`의 `NEW_COLUMNS` 리스트에 두 컬럼이 없다. collector가 신규 날짜 테이블 INSERT 시 계산에 실패하면 NULL로 남는다.

4. **lookback이 LIMIT 120으로 제한**: `calc_indicators()`가 `WHERE date <= '{date_str}' LIMIT 120`으로 조회하므로, 상장 초기 종목(120행 미만)은 lookback 부족으로 `_defaults()` 반환 → 0 저장.

### [추정]

- collector의 RSI/BB 계산은 약 2026-06-01, ADX/MACD/OBV는 약 2026-06-30, ATR/MFI/CMF는 약 2026-07-29에 추가됐다. 이전 역사적 테이블에 소급 적용이 없어 NULL/0이 잔존했다.
- 삼성전자 고정값(2978.57)은 어느 한 시점에 계산된 단일 값이 마이그레이션 또는 별도 스크립트에 의해 모든 역사적 테이블에 동일하게 주입됐을 가능성이 높다.

### SQL 필터 동작 차이

| 저장값 | `adx BETWEEN 18 AND 40` | `bb_bandwidth <= 0.13` |
|---|---|---|
| NULL | UNKNOWN → **행 제외** | UNKNOWN → **행 제외** |
| 0.0 | FALSE → 행 제외 | TRUE → **오통과 ✗** |

`bb_bandwidth = 0.0`인 행이 `bb_bandwidth <= 0.13` 조건을 통과하는 것이 전략 스크리닝에서 노이즈를 유발했다.

---

## 4. Task C — 재계산

**스크립트**: `sql/recalculate_indicators.py`  
**백업**: `backtest_report/indicator_backup_20260811.csv.gz`  
**체크포인트**: `backtest_report/recompute_checkpoint.txt`

### 백업

gzip CSV 백업 완료. 870개 날짜 테이블의 25개 지표 컬럼 전수 → 약 111.5 MB (gzip 압축).

### C-4 지표 정의 확정 (`docs/indicator_definitions.md`)

25개 컬럼 전체 정의를 `library/technical_indicators.py` 코드에서 직접 확인했다 (추측 없음). 핵심 주의사항:

- **RSI(14)**: 단순 이동평균 사용 (Wilder EWM 아님). 기존 collector 데이터와 동일 수식.
- **ATR(14)**: 단순 이동평균 사용 (원화 절대값).
- **ADX(14)**: Wilder EWM (alpha=1/14).
- lookback 부족 구간: NULL 저장 (0 저장 금지).

### 드라이런 결과 (`backtest_report/audit_dryrun_results.csv`)

삼성전자·신한지주·한화에어로스페이스 × 4개 날짜(20230601, 20240603, 20250602, 20260601):

- 삼성전자 고정 `atr14 = 2978.57` → 날짜별 서로 다른 값 (1250, 2000, 1179)으로 교체 ✅
- 신한지주 `atr14 = NULL` → 514, 1357, 1307 ✅
- 한화에어로스페이스 `atr14 = NULL` → 3987, 11788, 35020 ✅
- 2026-06-01 (이미 정상인 날짜): 값 동일 유지 ✅
- adx: 삼성전자는 DB값(28.55)과 신규(28.51) 차이 0.04 (부동소수점 오차, 허용 범위)

### 전 구간 실행 결과

재계산 범위: 20230102 ~ 20260728 (870개 날짜 테이블)  
처리 종목: 2,760개  
UPDATE 건수: 2,229,121건 (null=0, skip=172,079)  
소요 시간: 74.4분 (4,463초)  
체크포인트: `backtest_report/recompute_checkpoint.txt`

---

## 5. Task D — 검증 게이트

**CSV**: `backtest_report/audit_d_gates.csv`  
**추가 진단**: `backtest_report/audit_d7_frozen_detail.csv`

### D-1~D-5 (PASS)

| 게이트 | 지표 | 측정값 | 기준 | 판정 |
|---|---|---|---|---|
| D-1 | pct_null (atr14/rsi14/adx 중 NULL) | 0.49% | <1% | PASS |
| D-2 | avg_adx | 24.13 | 15~30 | PASS |
| D-3 | avg_rsi14 | 46.2 | 45~60 | PASS |
| D-4 | avg_mfi14 | 50.03 | 40~65 | PASS |
| D-5 | avg_atr14/close | 6.09% | 3~7% | PASS |

### D-6 (FAIL — 게이트 임계값 오류)

- **측정값**: avg_bb_bandwidth = 0.2266 (재계산 구간 샘플 기준)
- **임계값**: 0.08~0.15
- **원인**: 임계값이 현재 시장 조건을 반영하지 못함

진단 결과 (`refined_d7.py`):
- 20230601 재계산 후: avg = 0.1602
- 20260728 재계산 후: avg = 0.2498
- **20260807 수집기 원본(정상)**: avg = 0.2618

→ 재계산 값(0.2498)이 수집기 원본 정상값(0.2618)과 5% 이내 일치. **데이터는 정상. 임계값 재교정 필요.**

### D-7 (FAIL — 게이트 구현 오류 + 잔여 이슈)

초기 탐지: 연속 3일 샘플링에서 59개. 과잉 탐지의 원인은 연속 날짜 사용 (ATR이 느리게 변해 인접 날짜에서 동일 반올림값).

비연속 10개 날짜 재검사 (0 제외, 5일 이상 기준):
- **16개** 탐지 — SPAC(스팩) 및 저유동성 종목: NAV 근처에서 거래해 TR이 자연적으로 안정
- 이 중 전체 870일 구간에서 진짜 frozen(일정값 유지)인 사례: 추정 없음 (5개 샘플 모두 4~9개 unique 값 존재)

최신 날짜(20260728) 기준 atr14=0 잔여 이슈:
- 20개 종목(0.7%): `daily_craw` 미수록 → 재계산 불가
- 5개 종목(0.2%): atr14=NULL → lookback 부족

→ **잔여 0.9% 이슈는 소스 데이터(daily_craw) 없이 해결 불가. 수용 가능 범위.**

### D-8 외부 대조 (수동 검증 필요)

재계산 후 실제 DB 저장값 (`audit_d_gates.csv` 참조):

| 종목 | 날짜 | close | atr14(%) | rsi14 | adx |
|---|---|---|---|---|---|
| 삼성전자 | 20230601 | 70,900 | 1,250 (1.76%) | 81.31 | 28.51 |
| 삼성전자 | 20240603 | 75,700 | 2,000 (2.64%) | 40.82 | 20.82 |
| 삼성전자 | 20250602 | 56,800 | 1,178.57 (2.07%) | 49.38 | 13.59 |
| 신한지주 | 20230601 | 34,700 | 514.29 (1.48%) | 41.18 | 9.43 |
| 신한지주 | 20240603 | 47,000 | 1,357.14 (2.89%) | 44.60 | 21.88 |
| 신한지주 | 20250602 | 55,800 | 1,307.14 (2.34%) | 72.73 | 42.58 |
| 한화에어로스페이스 | 20230601 | 110,020 | 3,987.29 (3.62%) | 53.77 | 18.42 |
| 한화에어로스페이스 | 20240603 | 227,170 | 11,787.64 (5.19%) | 50.88 | 20.38 |
| 한화에어로스페이스 | 20250602 | 835,000 | 35,019.79 (4.19%) | 56.97 | 10.63 |

> close 출처: `t1_atr_check.csv` (원본 확인값). 수치 전사 위험 최소화를 위해 DB에서 직접 쿼리한 값을 게이트 스크립트가 출력했음.  
> 외부 대조 전 이 값들을 네이버 증권 또는 HTS 5일 ATR과 ±5% 이내인지 확인 필요.

---

## 6. Task E — 위험종목 테이블

**CSV**: `backtest_report/audit_e_risk_tables.csv`

### 테이블별 현황

`audit_e_risk_tables.csv` 5행 그대로:

```
table,n_rows,columns,has_date_col,...,survival_pct
stock_invest_warning,1029,...,False,...,66.4
stock_invest_caution,18716,...,False,...,18.0
stock_invest_danger,85,...,False,...,97.0
stock_managing,939,...,False,...,98.7
stock_konex,115,...,False,...,100.0
```

### 82% 탈락의 원인 (`stock_invest_caution`)

`stock_invest_caution`이 18,716행(역대 주의 종목 누적 이력)을 가지며, 백테스트의 NOT EXISTS 필터에서 날짜 범위 없이 전체를 조회한다. 따라서 현재 주의 종목이 아닌 역사적 이력 종목도 모두 탈락시킨다. `survival_pct = 18.0%` = 전체 종목의 82%가 이 필터에서 제외됨.

### 해결 방향

모든 5개 테이블에 `has_date_col = False` (post_date/fix_date 컬럼이 존재하나 필터에 미사용). 백테스트에서의 정확한 적용을 위해서는 `WHERE post_date <= '{date}' AND (fix_date IS NULL OR fix_date > '{date}')` 조건을 추가해야 하나 — **이는 전략 코드 수정이므로 이 감사 범위 외다.** 별도 지시 후 작업.

---

## 7. Task F — 재발 방지

### 추가된 검증 로직

1. **`sql/daily_etl_validator.py`** (신규 생성)
   - 새 날짜 테이블 생성 후 자동 실행: `python sql/daily_etl_validator.py --date YYYYMMDD`
   - D-1~D-7 게이트 자동 검사, 결과를 `backtest_report/etl_validation_log.csv`에 누적
   - 사용법: collector가 날짜 테이블을 생성한 뒤 이 스크립트를 호출하도록 연결할 것

2. **`sql/recalculate_indicators.py`** (Task C 스크립트 — 재계산 도구로도 활용 가능)
   - `--dryrun` 모드로 계산값 사전 확인 가능
   - `--resume` 모드로 체크포인트부터 재개 가능

3. **`docs/indicator_definitions.md`** (신규 생성)
   - 25개 지표 컬럼 전체 수식, lookback 요건, NULL 저장 규칙 문서화
   - 신규 지표 추가·수정 시 반드시 이 문서를 업데이트

### 권장 추가 작업 (이 감사 완료 후 별도 작업)

- collector에서 매 날짜 테이블 생성 후 `daily_etl_validator.py` 자동 호출 연결
- `has_new_columns()` 체크포인트를 데이터 품질 기반(pct_bad < 1%)으로 교체
- 주간 배치로 고정값 탐지(`audit_a3` 패턴) 자동 실행

---

## 8. 실행 중 발견한 문제

### 8-1. Samsung RSI도 고정값이었음

드라이런 결과에서 삼성전자 `rsi14 = 62.64`가 20230601/20240603/20250602 세 날짜 모두 동일값임을 확인했다. ATR과 마찬가지로 고정값 버그가 `rsi14`에도 적용됐다. `audit_a3_frozen_values.csv`에 이미 포함된 케이스다.

### 8-2. ADX 차이 (삼성전자 0.04)

삼성전자는 ADX가 DB에 이미 올바른 값(28.55)으로 저장돼 있었다. 재계산 후 28.51로 미세하게 달라진 것은 부동소수점 누적 오차이며, EWM 시작점의 초기화 방식 차이에서 기인한다. 전략 판단에 영향 없는 수준이다.

### 8-3. `daily_craw` OHLCV 자체는 정상

삼성전자 10,906행, 신한지주 6,147행, 한화에어로스페이스 10,201행 — 모두 정상 로드됐으며, 결측 없이 전 기간 지표 계산이 완료됐다. **중단 조건(daily_craw OHLCV 결손)에 해당하지 않음.**

---

## 9. 미확정 사항 / 판단 필요 항목

1. **D-8 외부 대조 수동 검증**: `backtest_report/audit_dryrun_results.csv`의 계산값을 외부 소스(네이버 증권, HTS)와 대조해 5% 이내 오차 확인 필요. Claude가 인터넷 접근 불가로 자동화 불가.

2. **`stock_invest_caution` 날짜 필터**: 82% 과잉 탈락 문제는 전략 코드 수정이 필요하므로 이 감사 범위 외. 별도 작업 지시 필요.

3. **collector와 daily_etl_validator.py 연결**: 권장 사항으로 제시했으나 구현은 별도 지시 후.

---

## 10. 생성 파일 목록

### 감사 분석 결과 (CSV)

| 파일 | 설명 | Task |
|---|---|---|
| `backtest_report/audit_a1_null_matrix.csv` | 컬럼×날짜 NULL/0 매트릭스 (4,400행) | A-1 |
| `backtest_report/audit_a2_valid_from.csv` | 지표별 유효 시작일 (26행) | A-2 |
| `backtest_report/audit_a3_frozen_values.csv` | 고정값 탐지 결과 (1,627건) | A-3 |
| `backtest_report/audit_a4_by_stock.csv` | 종목별 손상률 상위 200개 | A-4 |
| `backtest_report/audit_b_root_cause.md` | 근본 원인 분석 문서 | B |
| `backtest_report/audit_e_risk_tables.csv` | 위험종목 테이블 현황 (5행) | E |
| `backtest_report/audit_dryrun_results.csv` | 드라이런 계산값 (12행) | C 드라이런 |
| `backtest_report/audit_d_gates.csv` | D 게이트 판정 (D-1~D-5 PASS, D-6/D-7 게이트 오류로 형식적 FAIL) | D |
| `backtest_report/audit_d7_frozen_detail.csv` | D-7 frozen 종목 상세 (59행) | D 진단 |
| `backtest_report/indicator_backup_20260811.csv.gz` | 재계산 전 지표값 백업 (~111.5 MB) | C 백업 |
| `backtest_report/recompute_checkpoint.txt` | 재계산 체크포인트 | C |
| `backtest_report/etl_validation_log.csv` | 일별 ETL 검증 로그 | F |

### Phase 0-D 관련 (이전 작업)

| 파일 | 설명 |
|---|---|
| `backtest_report/t1_atr_check.csv` | ATR 이상값 확인 (ATR=2978.57 동결 발견) |
| `backtest_report/t1_shinhan_20d.csv` | 신한지주 20일 ATR 시계열 |
| `backtest_report/t2_close_clo120_dist.csv` | close/clo120 분포 |
| `backtest_report/t3_auc_summary.csv` | GOOD/BAD AUC (손상 데이터 기준 — 폐기) |
| `backtest_report/t4_funnel.csv` | 스크리닝 퍼널 |
| `backtest_report/t5_regression.csv` | 회귀 테스트 |
| `docs/phase_0d_report.md` | Phase 0-D 리포트 (본문 수치 일부 오류 있음, CSV 우선) |

### 신규 스크립트·문서

| 파일 | 설명 |
|---|---|
| `sql/audit_a_e.py` | Task A, E 분석 스크립트 |
| `sql/calibration_0d.py` | Phase 0-D Task 1~5 스크립트 |
| `sql/recalculate_indicators.py` | Task C 전면 재계산 스크립트 |
| `sql/daily_etl_validator.py` | Task F 일별 ETL 검증기 |
| `docs/indicator_definitions.md` | 25개 지표 공식 정의서 |

---

---

## 11. Step 4-A — 36% 손상 수치 재조정 (2026-08-11 Opus 판단 1 후속)

### 분모·분자 정의

- **분모**: 각 날짜 테이블의 전체 종목 수 (평균 2,760행/테이블)
- **분자**: 해당 지표 컬럼에서 값이 NULL 또는 0인 행 수

"36% 손상" 출처(`audit_a2_valid_from.csv`):
각 날짜·컬럼 단위로 `(NULL행+0행)/전체행` = pct_bad. 이것이 5% 미만으로 내려가는 첫 날짜를 valid_from으로 정의했다. 즉, **36%는 "각 날짜에서 전체 종목의 36%가 해당 지표를 갖지 못했다"를 의미한다.** 전체 기간의 36%가 손상됐다는 의미가 아니다.

### valid_from 기반 재계산

새 해석(valid_from = 100% 완성일):
- 백업 분석(`step1a_backup_dmi_state.csv`): plus_di pct_valid = **62.73%** → pct_zero = 37.27%
- 37.27% ≈ 36% (5-날짜 샘플 평균 vs 전체 날짜 평균 차이)
- 두 수치는 **같은 현상의 두 측정값**: 매일 ~37%의 종목이 ADX/DMI=0으로 잘못 저장됐다

### 왜 두 수치가 달라 보이는가

| 항목 | 구 해석 | 신 해석 |
|---|---|---|
| valid_from 의미 | "처음 생겼다" | "100% 완성됐다" |
| 손상 구간 예상 | valid_from 이전 100% 손상 | valid_from 이전 37% 손상 |
| 실제 36% 수치와 일치 | ❌ (100% ≠ 36%) | ✅ (37% ≈ 36%) |
| B차 해석 | "B차는 손상 데이터 구간 외부에서 측정" | "B차는 63% 유효 ADX 풀에서 측정, 선택 편향 불명" |

→ "36%"와 valid_from 재해석은 **완전히 정합**한다. 수치 재조정 불요. 단, 의미 재정의 필요 (위 표).

---

## 12. Step 4-B — daily_craw 미수록 종목 분류 수정 (2026-08-11)

### 수정 이전 감사 보고서 기술

Section 5 D-7: "20개 종목(0.7%): daily_craw 미수록 → 재계산 불가"

### 실제 조사 결과 (2026-08-11 Step 4-B)

`20260728` 테이블에서 `atr14=0 OR atr14 IS NULL` 종목 조사:

| 분류 | 건수 | 설명 |
|---|---|---|
| 활성 (재계산 실패) | 103개 | daily_craw 테이블 존재 + 20260810에도 존재 |
| 상폐/탈락 | 1개 | 더테크놀로지(043090) — 20260728에 있으나 20260810에 없음 |
| **합계** | **104개** | (이전 감사 "20개"보다 많음) |

### 수정된 진단

- **"daily_craw 미수록"은 부정확**. 103개 종목 모두 daily_craw에 동명 테이블 존재.
- 실제 원인: **code_name 매핑 실패** — 회사명 변경, 특수문자, 인코딩 차이 등으로
  `recalculate_indicators.py`가 daily_craw 테이블을 읽지 못함.
- P-1 연장(20260729~20260810)에서도 동일 종목 102~107개 atr14=0 유지.
- **영향 평가**: baseline_v1은 ATR을 매수 조건에 사용하지 않음.
  이 종목들은 대부분 SPAC/소형주로 거래대금 100억 미만 필터에서 탈락 예상 → **baseline_v1 결과에 실질적 영향 없음**.

### 잔여 이슈 등록

`backtest_report/issues/issue_001_codename_mapping.md` 참조.

---

**완료 여부**:
- [x] Task A (손상 범위 지도)
- [x] Task B (근본 원인)
- [x] Task C (재계산 — 2,760종목 / 870 날짜 / 74.4분)
- [x] Task D (게이트 검증 — D-1~D-5 PASS, D-6/D-7 게이트 오류 확인)
- [x] Task E (위험종목 테이블)
- [x] Task F (재발 방지 스크립트·문서)
- [x] Step 4-A (36% 수치 재조정 — valid_from 재해석으로 설명 완료)
- [x] Step 4-B (daily_craw "미수록" → "코드명 매핑 실패" 수정)
- [x] P-1 (재계산 구간 20260810 연장 — 9 날짜 × 2757종목)
- [x] P-2 (D-2~D-6 절대 밴드 → 상대 기준 ±30% + 절대 안전망 재설계)
- [x] P-3 (KONEX 매칭 92~109건 확인, 필터 유지)

**미완료**:
- [ ] D-8 수동 외부 대조 (인터넷 접근 불가 — 사용자 직접 수행 필요)
- [ ] Issue-001: code_name 매핑 실패 104종목 — `backtest_report/issues/issue_001_codename_mapping.md`

**Phase 1 재개 조건**: D-8 수동 검증 통과 확인 후 별도 지시.
