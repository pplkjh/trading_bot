# Strategy E 진단 및 롤백 지시서

> **이 문서는 이전에 전달한 `trading_bot_strategy_prompt.md`를 대체한다.**
> 그 명세대로 구현한 결과가 실패했으므로, 새 기능 개발을 중단하고 진단 모드로 전환한다.
> 이전 명세의 매수 조건은 더 이상 기준이 아니다.

---

## 0. 현재 상황

> **[2026-08-11 갱신]** 기존 A/B/C/D차 및 1~4차 성과표 전체 무효화.
> 측정 구간(2023-01-02~2026-08-10)의 ADX/DMI 컬럼 37%가 손상 데이터였음이 확인됐다
> (데이터 무결성 감사: `backtest_report/data_integrity_audit_report.md`).
>
> **B차 무효 확정**: B차(112거래/42.9%/+119%)는 정체불명의 63% 유효 ADX/DMI 부분집합에서
> 측정됐으며, 선택 편향이 불명하고 재현이 불가능하다.
>
> 구 성과표 원본: `backtest_report/invalidated_baselines.md`
> 새 기준선:      `docs/baseline_v1_spec.md`

현재 `value_strategy_e.py`는 **baseline_v1** 조건으로 초기화됐다:
- 3단 정배열 (close > clo20 > clo60 > clo120)
- DMI 방향성 (plus_di > minus_di)
- 거래대금 100억 이상
- 위험종목 제외 (날짜 필터 적용)

---

## 1. Phase 0 — 진단 (여기부터 시작. 코드 수정 금지)

**새 전략을 짜지 마라. 조건을 바꾸지 마라. 아래 두 개만 실행하고 결과를 보고한 뒤 멈춰라.**

### 0-A. 단위 버그 확인

전체 시장 유니버스에서 3.6년간 5건은 비정상적으로 적다. 단위 불일치를 먼저 의심한다. 예를 들어 `bb_bandwidth`가 비율(0.12)이 아니라 퍼센트(12.0)로 저장돼 있으면 `<= 0.13` 조건이 전 종목을 탈락시킨다.

임의의 날짜 테이블 3개(예: 20230601, 20240601, 20250601)에 대해 실행하고 결과를 표로 보고:

```sql
SELECT
  COUNT(*) AS n,
  MIN(bb_bandwidth), AVG(bb_bandwidth), MAX(bb_bandwidth),
  MIN(atr14/close),  AVG(atr14/close),  MAX(atr14/close),
  MIN(rsi14),        AVG(rsi14),        MAX(rsi14),
  MIN(adx),          AVG(adx),          MAX(adx),
  MIN(vol20/vol120), AVG(vol20/vol120), MAX(vol20/vol120),
  SUM(bb_bandwidth <= 0.13)          AS pass_bb,
  SUM(atr14/close  <= 0.030)         AS pass_atr,
  SUM(vol20*close  >= 10000000000)   AS pass_amount
FROM `20240603`;
```

`pass_bb`가 0에 가까우면 단위 버그 확정이다. 그 경우 즉시 보고하고 멈춰라.

### 0-B. 조건별 퍼널 분석 (가장 중요)

지금까지 전략을 통째로 갈아엎으며 7회 반복했지만, **어느 조건이 몇 개를 죽이는지 아무도 모른다.** 이걸 먼저 측정한다.

4차 매수 조건을 아래 순서로 **하나씩 누적 추가**하면서 각 단계 생존 종목 수를 세라. 기간은 전체(2023-01-02~2026-08-10), 날짜별 평균과 총합을 함께 낸다.

```
step  0: 전체 종목
step  1: + vol20*close >= 1e10
step  2: + clo5>clo20 AND clo20>clo40 AND clo40>clo60      (4단)
step  3: + clo60>clo80 AND clo80>clo120                     (6단)
step  4: + clo20>yes_clo20 AND clo60>yes_clo60 AND clo120>yes_clo120
step  5: + close/clo120 BETWEEN 1.05 AND 1.25
step  6: + clo20/clo120 BETWEEN 1.03 AND 1.15
step  7: + atr14/close <= 0.030
step  8: + bb_bandwidth <= 0.13
step  9: + adx BETWEEN 18 AND 35 AND plus_di > minus_di
step 10: + vol20/vol120 BETWEEN 0.7 AND 1.8
step 11: + close BETWEEN clo40*0.97 AND clo20*1.03
step 12: + close > clo60
step 13: + rsi14 BETWEEN 40 AND 58
step 14: + vol5 < vol20*1.1
step 15: + macd > 0
step 16: + 위험종목 제외 (NOT EXISTS 5종)
```

출력 형식:

| step | 조건 | 일평균 생존 | 총 생존 | 직전 대비 잔존율 |
|---|---|---|---|---|

**추가로**: step 3(6단 정배열)까지 통과한 집합 안에서 `rsi14`의 분포(10분위)를 출력하라. `rsi14 <= 58`인 비율이 몇 %인지가 진단 3번을 검증한다.

### 0-C. 목표 종목 개별 추적

삼성전자(005930), 신한지주(055550), KB금융(105560), 한화에어로스페이스(012450), HD현대중공업(329180) 5종목에 대해, 전체 기간 중 각 조건을 통과한 **일수**를 개별 컬럼으로 집계하라. 특히 `6단 정배열`과 `rsi14 BETWEEN 40 AND 58`의 **교집합 일수**를 반드시 포함할 것.

**Phase 0의 세 결과를 보고하고 내 확인을 받기 전에 Phase 1로 넘어가지 마라.**

---

## 2. Phase 1 — 백테스트 기간 확장

조건 변경보다 우선순위가 높다.

1. `daily_buy_list`의 **가장 오래된 날짜 테이블**이 언제인지 확인해 보고하라.
2. 가능한 최대 구간으로 백테스트 기간을 확장하라. 2015년부터 있다면 샘플이 3배가 된다. **전략을 전혀 건드리지 않고 통계적 유의성을 확보하는 유일한 방법이다.**
3. 리포트는 반드시 국면별로 분리 출력:
   - 2015~2019 (횡보장)
   - 2020~2021 (급등장)
   - 2022 (하락장)
   - 2023~현재 (밸류업·조선·방산·AI 국면)

   통합 수치만 보면 안 된다. 2023~2026은 특수 국면이라 일반화가 불가능하다.

4. `sf_` 테이블(시총·외국인·신용비율)이 2026-04-07부터만 존재하는 문제:
   - 과거 구간은 거래대금(`vol20 * close`) 필터로 대체한다. 시총 필터의 상당 부분을 대체한다.
   - 2026-04 이후 구간에서만 시총 필터 ON/OFF 두 버전을 돌려 차이를 측정하고, 그 차이를 과거 구간 결과의 보정 참고치로 리포트에 명시하라. 과거 구간에 시총 필터를 적용한 척하지 마라.
5. 위험종목 테이블이 현재 상태 기준이라 과거 지정 이력이 없는 점은 **한계로 리포트에 명시**하고 넘어간다. 이는 백테스트를 낙관 편향시킨다.

---

## 3. Phase 2 — B차 기준선 재현

확장된 기간에서 **B차 조건을 그대로** 재현하라.

```
매수: 3단 정배열 (close > MA20 > MA60 > MA120) + DMI (plus_di > minus_di)
매도: SL -15% / MA60 이탈 / RSI > 80
정렬/제한: B차 당시 설정 그대로
```

이것이 **기준선(baseline)**이다. 이후 모든 변경은 이 기준선 대비 델타로만 평가한다. 재현 결과를 반드시 저장해 두어라.

---

## 4. Phase 3 — 단일 변수 애블레이션

**한 번에 하나씩만 바꾼다. 두 개 이상 동시 변경 금지.** 각 단계마다 기준선 대비 4개 지표 델타를 보고하고 내 확인을 받는다.

| 순서 | 변경 내용 | 관찰 포인트 |
|---|---|---|
| 3-1 | + KOSPI 레짐 게이트 (KOSPI < MA120이면 신규매수 중단) | MDD 감소폭 |
| 3-2 | + SL -15% → -12% | 승률·평균손실 변화 |
| 3-3 | + 매도 Rule 3 `close<MA60 AND MA20<MA60` 이중확인 | D차에서 악화됐던 조건. 기간 확장 후 재검증 |
| 3-4 | + Rule 4 트레일링 (max_rate, 아래 5장 참조) | `TRAIL_PROTECT` 발생 비율 |
| 3-5 | + 매도 Rule 2 `close < MA120` 추세 종료 | 조기청산 과다 여부 |
| 3-6 | + 4단 정배열 (`clo5>clo20>clo60>clo120`) | 거래수 감소폭 |
| 3-7 | + ATR ≤ 4.5% | 거래수 감소폭 |
| 3-8 | + 섹터 상한 2종목 | MDD 감소폭 |

**중단 규칙**: 어느 단계에서든 거래 수가 직전 대비 50% 이상 감소하면 즉시 멈추고 보고하라. 그 조건은 채택하지 않는다.

### 명시적으로 되살리지 않을 조건

아래는 진단 결과 유해한 것으로 판단됐다. 내가 명시적으로 지시하기 전까지 넣지 마라.

- `close BETWEEN clo40*0.97 AND clo20*1.03` (눌림목 위치) — 진입점을 손절선에 붙임
- `rsi14 BETWEEN 40 AND 58` — 정배열 조건과 자기모순
- `bb_bandwidth <= 0.13` — ATR와 중복, 단위 버그 위험원
- 6단 정배열의 `clo80`, `clo100` 항 — 정보량 거의 없음
- `ORDER BY close/clo120 DESC` — 역선택. `ORDER BY (clo120/yes_clo120) DESC, close/clo120 ASC`로 교체

---

## 5. max_rate 구현 (Phase 3-4에서 사용)

### 스키마
```sql
ALTER TABLE all_item_db ADD COLUMN max_rate DECIMAL(6,2) NOT NULL DEFAULT 0;
```
매수 체결 시 0으로 INSERT.

### 시뮬레이터 일일 루프 — 순서가 결정적

```python
for date in trading_dates:
    for pos in open_positions:
        row = get_daily_row(pos.code, date)
        if row is None:          # 거래정지 등
            continue

        # 1) 종가 기준 수익률 갱신
        pos.rate = (row.close / pos.purchase_price - 1) * 100

        # 2) 매도 판정 — 반드시 '갱신 전' max_rate 사용
        reason = evaluate_sell_rules(pos, row, date)
        if reason:
            close_position(pos, date, row.close, reason)
            continue

        # 3) 생존 포지션만 max_rate 갱신
        pos.max_rate = max(pos.max_rate, pos.rate)
```

**2번과 3번의 순서를 바꾸지 마라.** 또한 **당일 고가(`high`)로 max_rate를 갱신하지 마라.** 장중 +13% 찍고 종가 +4%로 마감한 날 같은 날 안에 Rule 4가 발동해 종가 청산되는 결과가 나오는데, 일봉 종가 체결 시뮬레이터에서 이는 사실상 look-ahead다. 백테스트는 반드시 종가 기준으로 갱신한다.

실전(`daily_position_monitor`)에서는 실시간 현재가로 갱신해도 되지만, 그 경우 Rule 4 발동이 백테스트보다 잦아진다. 두 수치가 벌어지는 것은 정상이며, 리포트에 그 사실을 명시하라.

### 매도 판정
```python
def evaluate_sell_rules(pos, row, date):
    hold = (date - pos.buy_date).days
    if pos.rate <= -12.0:                                    return 'SL_HARD'
    if row.close < row.ma120:                                return 'TREND_END'
    if row.close < row.ma60 and row.ma20 < row.ma60:         return 'MA60_CONFIRMED'
    if pos.max_rate >= 12 and pos.rate <= pos.max_rate - 8:  return 'TRAIL_PROTECT'
    if row.rsi14 >= 78 and pos.rate >= 20:                   return 'TP_OVERHEAT'
    if pos.rate >= 35:                                       return 'TP_TARGET'
    if hold >= 110 and pos.rate < 5:                         return 'TIME_STOP'
    return None
```
분기 순서는 우선순위다. 손절이 항상 최우선이다.

### 검증
백테스트 후 `sell_reason` 분포를 출력하라. **`TRAIL_PROTECT` 비중이 5% 미만이면 Rule 4는 사실상 작동하지 않는 것이다.** 그 경우 "Rule 4로 승률이 오를 것"이라는 가설은 기각이며, 즉시 보고하라.

---

## 6. 리포트 형식 (모든 백테스트에 공통)

**아래 4개를 항상 한 표에 함께 출력하라. 일부만 보고하지 마라.**

```
거래 수 | 승률(95% 신뢰구간 포함) | 손익비(R) | MDD
```

추가 필수 항목:
- CAGR (총자산 기준, 미투자 현금 포함)
- **평균 자본 투입률(%)** — 3차의 MDD 5.96%가 리스크 관리가 아니라 미투자였음을 드러내는 지표
- 평균 보유일수, 최대 연속 손실 횟수
- `sell_reason`별 청산 건수 분포
- 월별 신호 발생 건수
- 국면별(2015~2019 / 2020~2021 / 2022 / 2023~) 분리 수치

**거래 수가 30건 미만이면 승률·MDD 수치에 "표본 부족, 판단 불가" 경고를 리포트 상단에 붙여라.** 10거래의 승률 30%는 신뢰구간이 ±28%p 수준이라 아무 의미가 없다.

---

## 7. 절대 하지 말 것

1. **Phase 0을 건너뛰지 마라.** 어느 조건이 몇 개를 죽이는지 모르는 상태에서 8번째 전략을 만드는 것은 정보량이 0이다.
2. **한 번에 두 개 이상의 조건을 바꾸지 마라.** 지금까지 실패한 이유가 이것이다.
3. **MDD가 낮다고 좋은 결과로 보고하지 마라.** 자본 투입률을 함께 확인하라. 미투자는 리스크 관리가 아니다.
4. **승률만으로 판단하지 마라.** 손익비 3.6~5.4는 정상적인 추세추종 프로필이며, 그런 시스템의 승률은 구조적으로 35~50%다.
5. **파라미터 자동 최적화(그리드 서치, 유전 알고리즘)를 돌리지 마라.** 조건이 15개를 넘어 과최적화가 확정적이다. 민감도 분석으로 영향만 보고하고 값 변경은 확인받아라.
6. **거래대금 100억 필터와 위험종목 제외(NOT EXISTS 5종)는 절대 완화하지 마라.** 수익률 개선 목적이라도 안 된다. 안전장치이지 최적화 파라미터가 아니다.
7. **컬럼명·라이브러리 시그니처를 추측하지 마라.** 확인 불가하면 멈추고 물어봐라.
8. **새 전략(5차, Strategy F 등)을 제안하지 마라.** 지금 필요한 건 새 아이디어가 아니라 기존 결과의 원인 규명이다.

---

## 8. 목표 재설정

승률 80%는 이 전략 클래스에서 달성 가능성이 낮다. 손익비 3.6~5.4를 내는 추세추종 시스템의 승률은 구조적으로 35~50%이며, B차의 42.9% / +119%는 이미 건강한 결과다.

**새 KPI: B차의 수익률(+119%)을 유지하면서 MDD를 33% → 20% 이하로 낮춘다.**

이는 레짐 게이트 + 손절 강화 + 섹터 상한으로 달성 가능하며, 승률 80%와 달리 실현 가능한 목표다. 최적화 대상 지표를 승률에서 **MDD 대비 수익률(Calmar 비율)** 로 바꾸고, 모든 애블레이션 단계에서 이 값을 함께 보고하라.
