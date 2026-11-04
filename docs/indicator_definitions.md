# 지표 정의서 (Indicator Definitions)

작성일: 2026-08-11  
최종 수정: 2026-08-14  
기준 파일: `sql/recalculate_indicators.py`, `sql/task5_build_expansion.py`

---

## 1. ATR(14) — Average True Range

- **정의**: True Range의 단순 14일 이동평균 (원화 절대값)
- **True Range** = max(high−low, |high−prev_close|, |low−prev_close|)
- `min_periods=14` — 14일 미만 데이터 시 NULL
- **단위**: 원화 (close와 동일 단위)
- **칼럼명**: `atr14`

## 2. RSI(14) — Relative Strength Index

- **정의**: gain/loss의 단순 14일 이동평균 (Wilder EWM 아님)
- `avg_gain = gain.rolling(14, min_periods=14).mean()`
- `rsi = 100 − 100 / (1 + avg_gain / avg_loss)`, avg_loss=0이면 100
- `min_periods=14` — 14일 미만 데이터 시 NULL
- **범위**: 0~100 (이론적)
- **칼럼명**: `rsi14`

## 3. Bollinger Bands (20, 2σ)

- **중심선**: 20일 단순 이동평균, `min_periods=20`
- **상단**: middle + 2 × std(20일, ddof=1)
- **하단**: middle − 2 × std(20일, ddof=1)
- **bb_bandwidth**: (upper − lower) / middle
- **칼럼명**: `bb_upper`, `bb_middle`, `bb_lower`, `bb_bandwidth`

## 4. ADX(14) — Average Directional Index (Wilder EWM)

- **정의**: Wilder EWM (alpha = 1/14), `min_periods=14`
- **Plus DI**: +DM EWM / ATR EWM × 100
- **Minus DI**: −DM EWM / ATR EWM × 100
- **ADX**: |+DI − −DI| / (+DI + −DI) × 100 의 EWM
- **칼럼명**: `adx`, `plus_di`, `minus_di`

## 5. MACD (12, 26, 9)

- EWM span 기반 (adjust=False)
- `min_periods`: EMA12=12, EMA26=26 → EMA26 NaN 구간은 MACD도 NULL
- **칼럼명**: `macd`, `macd_signal`, `macd_histogram`

## 6. OBV — On-Balance Volume

- 전일 대비 상승 시 +volume, 하락 시 -volume 누적합
- lookback 불필요 (첫 거래일부터 계산 가능)
- **칼럼명**: `obv`

## 7. MFI(14) — Money Flow Index

- Typical Price = (high + low + close) / 3
- Positive/Negative Money Flow 14일 합계 비율
- neg_flow=0이면 MFI=100; pos_flow=0이면 MFI=0
- `min_periods=14`
- **칼럼명**: `mfi14`

## 8. 저장 규칙 (Zero Storage Policy)

### 원칙 1 — lookback 부족 → NULL

lookback 데이터가 계산 기준(min_periods)에 미달하는 구간은 반드시 NULL을 저장한다.
0 저장 금지. 이는 `_defaults()` 반환값 0이 필터를 통과하는 손상 버그를 방지하기 위한 강제 규칙이다.

### 원칙 2 — 계산 결과 0도 NULL로 저장한다

계산 결과가 수학적으로 정확히 0인 경우에도 NULL로 저장한다.
이는 데이터 손상 정정이 아니라 **필터 안전성을 위한 정책 결정**이다.

**근거**: `atr14=0`이면 Strategy E의 `atr14/close ≤ 0.06` 조건이 TRUE로 통과하여
거래정지 종목이 "저변동성 우량주"로 잘못 분류된다.
NULL이면 SQL WHERE 조건이 UNKNOWN → 행 자동 배제.

**대상 컬럼 (0→NULL 강제)**:

| 컬럼 | 0이 발생하는 수학적 조건 | 필터 영향 |
|------|----------------------|---------|
| `atr14` | TR=0 (가격 완전 고정) | ATR≤6% 통과 위험 ⚠️ |
| `rsi14` | 14일 전구간 하락 (gain=0) | 필터 적용 시 오분류 위험 |
| `adx` | 방향성 지수=0 | ADX 필터 통과 위험 |
| `plus_di` | 상승 방향성 없음 | plus_di>minus_di 조건 영향 |
| `minus_di` | 하락 방향성 없음 | 동상 |
| `mfi14` | 14일 전구간 자금 유출 | MFI 필터 통과 위험 |
| `bb_bandwidth` | 20일 가격 완전 고정 (std=0) | bb_bandwidth≤0.13 통과 위험 ⚠️ |
| `bb_upper`, `bb_middle`, `bb_lower` | 동상 | 동상 |
| `clo120`, `vol120` (정수 반올림) | 극초저가·극초저거래량 | vol120×close≥300억 탈락 (영향 미미) |

**제외 컬럼 (0이 정상값)**:
- `macd`, `macd_histogram`: 추세 전환점에서 자연스러운 0
- `cmf20`: Chaikin Money Flow 중립값이 0
- `obv`: 방향 누적합이 0 가능

### 원칙 3 — 0→NULL 교정 이력

| 날짜 | 대상 | 교정 건수 | 스크립트 |
|------|------|---------|---------|
| 2026-08-14 | 신규 빌드 2017~2022 (1108 테이블) | 112,340건 | `sql/task5e_zero_check.py` |
| 2026-08-14 | 기존 2023~2026 (882 테이블) | 167,923건 → 잔여 0건 ✅ | `sql/task5e2_legacy_zero_fix.py` |

## 9. CMF(20) — Chaikin Money Flow

- Close Location Value: (close−low−(high−close)) / (high−low)
- CMF = 20일 (CLV×volume) 합 / 20일 volume 합
- `min_periods=20`
- **범위**: −1 ~ +1 (0 = 중립, 정상값)
- **칼럼명**: `cmf20`

## 10. Ichimoku (일목균형표)

- 전환선 (tenkan): (9일 최고+최저) / 2
- 기준선 (kijun): (26일 최고+최저) / 2
- 선행스팬A (senkou_a): (tenkan+kijun) / 2
- 선행스팬B (senkou_b): (52일 최고+최저) / 2, `min_len=52`
- **칼럼명**: `ichimoku_tenkan`, `ichimoku_kijun`, `ichimoku_senkou_a`, `ichimoku_senkou_b`

## 11. Pivot Points (전일 기준)

- Pivot = (전일 high + low + close) / 3
- S1 = 2×Pivot − 전일 high / S2 = Pivot − (전일 high − low)
- R1 = 2×Pivot − 전일 low / R2 = Pivot + (전일 high − low)
- **칼럼명**: `pivot`, `pivot_s1`, `pivot_s2`, `pivot_r1`, `pivot_r2`

## 12. 이동평균 (MA)

- 종가 이동평균: `clo5`, `clo10`, `clo20`, `clo40`, `clo60`, `clo80`, `clo100`, `clo120`
- 전일 종가 이동평균: `yes_clo5` ... `yes_clo120`
- 이격률: `clo5_diff_rate` ... `clo120_diff_rate` = (close/cloN - 1) × 100
- 거래량 이동평균: `vol5`, `vol10`, `vol20`, `vol40`, `vol60`, `vol80`, `vol100`, `vol120`
- 모두 `min_periods=N` (N미만 데이터 시 NULL)
- **저장 형태**: 정수 반올림 (int)

## 13. 일간 수익률

- `d1_diff_rate` = (close / 전일 close − 1) × 100
- **단위**: 퍼센트

## 14. 캔들 패턴 점수

- 망치형(4점), 장악형(4점), 도지(2점) — 동시 성립 시 합산, 최대 10점
- **칼럼명**: `candle_pattern_score`

---

## 연결 문서

- `sql/recalculate_indicators.py` — 25개 지표 전면 재계산 (2023-2026)
- `sql/task5_build_expansion.py` — 확장 구간 빌드 (2017-2022)
- `sql/daily_etl_validator.py` — D-1~D-7 게이트 검증
- `backtest_report/audit_b_root_cause.md` — 손상 근본 원인 분석
