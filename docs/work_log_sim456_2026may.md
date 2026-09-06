# JackBot simul_num=4/5/6 작업 로그
> 작성: 2026-05-19 | 설계 착수(2026-04-21)부터 현재까지 전 과정 기록
> **최종 실전 배포: 2026-05-26 (sim=6, jackbot4_imi1)**

---

## 11. 최종 실전 배포 (2026-05-26)

### 11-1. Strategy B 스코어링 최종 확정

장기간 스코어링 롤백/변경 반복 끝에 **a5db6c1 버전(BFS + RSI9/14 크로스)** 으로 최종 확정.

- **BFS(Bottom Failure Swing)** 30pt: RSI trough1(<30) → H1 반등 → trough2(trough2>trough1) → 현재>H1
- **RSI9/14 크로스** 40pt: 신선도 기준 (≤3일=40pt, 4-6일=25pt, 7-9일=15pt)
- **RSI다이버전스** 10pt: 가격 저점 하락 + RSI 저점 상승

백테스트 결과 (sell_list_num=31 트레일링스탑, 2026-05-26):
- 총수익률 65.97% / MDD 3.23% / Sharpe 2.13 / 승률 64.4% / 평균보유 10.2일

### 11-2. 매도 로직 최종 확정 (exit analysis 근거)

**sim=4 exit analysis** (`simulator4` DB, 17,477건):
- 평균 max_high_pct +13.47% — 매수 후 최대 상승 여력 풍부
- min_low <-5% 도달 종목: 18.0% → SL-3보다 SL-5가 승률 높음
- SL-5+Trail(3%,5%): 승률 79.6%, 평균 +8.27% ← 채택
- SL-3+Trail(3%,5%): 승률 73.8%, 평균 +8.33%
- Trail 순수: +92.10% — EOD 아티팩트, 무시

**확정된 매도 파라미터 (get_basic_sell_list, open_api.py):**

| | Strategy A | Strategy B |
|--|------------|------------|
| 하드 SL | -5% | -5% |
| Trail 활성화 | 고점+3% | 고점+3% |
| Trail 간격 | 고점-5% | 고점-5% |
| 시간청산 | 15일 | 45일 |

### 11-3. 실전 구현 완료 목록

| 파일 | 변경 내용 | 커밋 |
|------|----------|------|
| hybrid_strategy_v3.py | Strategy B 스코어링 a5db6c1 복원 | 4dc94da |
| simulator_func_mysql.py | sell_list_num=31 트레일링스탑 로직 | 5e893b6 |
| open_api.py | get_basic_sell_list A/B 분기 매도 | f19386c |
| collector_api.py | realtime_daily_buy_list_check sim=4/5/6 | 40809d5 |
| open_api.py | Strategy A 매도 (SL-5+Trail+15일) | 40809d5 |
| cf.py | imi1_simul_num=6, imi1_db_name=jackbot4_imi1 | 8754b83 |

### 11-4. 실전 초기 설정

- DB: jackbot4_imi1 (fresh start, 2026-05-26)
- 초기 자본: 50,000,000원 (jango_data 초기화 완료)
- 보유 종목: 0건 (all_item_db 비어있음)
- collector 첫 실행: 2026-05-26 장 마감 후

### 11-5. 향후 관찰 포인트

1. Strategy A/B 매수 비율 — sim=6에서 A:B 실제 비율 확인
2. 트레일링스탑 발동 빈도 — realtime_position_monitor highest_price 추적 정상 작동 여부
3. 15일/45일 시간청산 — 실제 해당 케이스 발생 시 동작 확인
4. 펀더멘털 스코어 — 향후 collector에서 실전 전용 활성화 예정

---

## 0. 백테스트 구조적 한계 — 반드시 먼저 읽을 것

**우리 백테스트는 "매수 방향성 검증 도구"다. 실전 손익 예측 도구가 아니다.**

| 구분 | 실전 트레이더 | 백테스트 |
|------|------------|---------|
| 매수 시점 | 장 시작 직후 (어제 종가 기준 리스트) | 당일 시가/종가 (동일 기준) |
| 매도 시점 | 장중 실시간 (-3% 손절, 트레일링 즉시) | **EOD 종가에서만 판단** |
| 갭하락 대응 | 즉시 손절 가능 | 불가 (이미 -10%도 다음날 종가에서야 확인) |
| 트레일링 스톱 | 고점 대비 실시간 추적 | 하루 단위로만 반응 → 크게 늦음 |

**따라서 백테스트 수치가 보여주는 것:**
- ✅ 스코어링 로직이 "이후 오르는 종목"을 잘 고르는지 (방향성)
- ✅ 매수 후보 선정 품질 비교 (A vs B, 파라미터 변경 전후)
- ❌ 실전에서 얼마나 벌 수 있는지
- ❌ 매도 전략(손절%/트레일링/시간청산) 품질 → 백테스트로 비교 불가

**펀더멘털 스코어 추가 제약:**
- DART 재무 데이터(ROE, 영업이익 등)는 현재 시점 데이터만 수집됨 (과거 히스토리 없음)
- 백테스트에서 사용 = Look-ahead bias (2023년 6월 테스트를 2026년 재무로 계산)
- RSI 다이버전스, BB스퀴즈는 가격 데이터 기반 → 백테스트에서도 유효
- **결론: 백테스트 브랜치에서 `_score_fundamental` 사용 금지, 실전에서만 활성화**

---

## 1. 설계 착수 (2026-04-21)

### 배경 문제 (simul_num=3 live 관찰)

| 문제 | 내용 |
|------|------|
| 진입 타이밍 불일치 | EOD 급등 종목 선정 → 다음날 아침 이미 고점. 갭상 후 차익실현에 손절 |
| 매도 전략 불일치 | -3% 손절 + +3% 트레일링이 급등 후 진입한 고변동성 종목을 못 견딤 |
| RSI 스코어링 맹점 | RSI 55→45→35 하락 중 종목에도 B1 점수 부여 (바닥 미형성 상태) |

### 결정
- simul_num=3 절대 수정 금지 (5758% 검증 자산)
- simul_num=4/5/6 신규 elif 브랜치로 추가
- **Strategy A**: 돌파 초입 (BreakoutStrategyV3) — 추세 + 모멘텀
- **Strategy B**: 저점 반등 확인 (ReversalStrategyV3) — 과매도 복귀

---

## 2. 초기 구현 (2026-04-27)

| 파일 | 작업 | 상태 |
|------|------|------|
| `library/hybrid_strategy_v3.py` | BreakoutStrategyV3 / ReversalStrategyV3 신규 작성 | ✅ |
| `sql/jackbot4_schema.sql` | jackbot4_imi1 DB 스키마 (strategy_type 컬럼 포함) | ✅ |
| `library/simulator_func_mysql.py` | simul_num=4/5/6 elif + num=22 스코어링 브랜치 추가 | ✅ |
| `library/cf.py` | v4_min_score_a=100 / v4_min_score_b=90 추가 | ✅ |

---

## 3. 1차 백테스트 기준선 (2026-04-28)

> **해석 주의**: 이 수치는 매수 방향성 품질을 보여줌. 실전 수익률이 아님.

| 전략 | 총수익률(방향성지표) | 거래수 | 승률 |
|------|------------------|--------|------|
| Sim 4 (A만) | +8,159% | 15,463회 | 72.5% |
| Sim 5 (B만) | +292.82% | 3,000회 | 65.9% |

---

## 4. 전략 실험기 (2026-04-29 ~ 2026-05-07)

### 4-1. 시도한 변경들

#### ReversalStrategyV3 스코어링 강화
- **의도**: Sim 5 방향성 지표 개선 — RSI 다이버전스, BB스퀴즈, 펀더멘털 스코어 추가
- **변경 내용**:
  - `_score_rsi_reversal` 개편 (RSI 다이버전스 로직 추가)
  - `_score_bb_bounce` BB스퀴즈 로직 추가
  - `_score_fundamental` 함수 추가 (DART ROE/영업이익 연동)
  - `auto_reject` 조건 강화 (보유기간 15→20일, RSI 임계 42→40)
  - simulator_func_mysql.py에 DART 재무 데이터 로딩 블록 약 60줄 추가

- **문제점 (나중에 발견)**:
  - 펀더멘털 스코어: DART 데이터는 현재 시점 값 → 과거 날짜 백테스트에 사용 = Look-ahead bias
  - RSI 다이버전스, BB스퀴즈 자체는 가격 기반이라 백테스트 유효

#### cf.py 파라미터 조정
- v4_min_score_b = 90 → **115** 로 상향 (B 전략 진입 기준 강화)

#### sim=6 로직 변경
- "best score wins" → "A/B 각각 독립 임계값, A 우선"으로 변경

### 4-2. 백테스트 결과 (방향성 검증 관점)

| 전략 | 총수익률 | 거래수 | 판정 |
|------|---------|--------|------|
| Sim 5 변경 후 | +431% | **1,124회** | ❌ 거래수 -62% |

**문제**: 거래수 3,000 → 1,124으로 급락.  
원인: v4_min_score_b=115가 너무 높아 대부분 B 종목 탈락.  
→ 방향성을 검증할 샘플 자체가 너무 적어짐.

---

## 5. 롤백 결정 및 실행 (2026-05-07~12)

### 롤백 이유
- 진입 기준 과도 강화 → 거래수 급감 → 통계적 의미 없음
- 펀더멘털 스코어가 백테스트 결과를 오염시켰을 가능성 (Look-ahead bias)
- 4월 28일 기준선이 샘플 충분하고 비교 가능

### 롤백 방법
```bash
git checkout HEAD -- library/hybrid_strategy_v3.py
git checkout HEAD -- library/cf.py
```
- simulator_func_mysql.py: DART 로딩 블록 수동 제거, sim=6 "best score wins" 복구

### 롤백 후 재백테스트 확인 (2026-05-07)

> **해석 주의**: 아래 수치는 "매수 방향성 품질" 지표. 실전 손익이 아님.

#### Sim 4 (BreakoutStrategyV3 단독)
| 항목 | 값 | 해석 |
|------|-----|------|
| 총수익률 | +8,141% | 방향성 지표 — 오르는 종목을 잘 고름 |
| 거래수 | 16,396회 | 충분한 통계 샘플 |
| 승률 | 71.3% | 매수 종목의 71%가 이후 상승 |
| 평균보유 | 4.3일 | 백테스트 기준 (실전과 다름) |
| Sharpe 9.45 / MDD 6.10% | 백테스트 기준 수치 (실전 예측 불가) | |
| 스코어 역상관 | 150pt+ 승률 57.7% < 120~129pt 승률 76.8% | 고스코어 = 이미 오른 종목 가능성 |

#### Sim 5 (ReversalStrategyV3 단독)
| 항목 | 값 | 해석 |
|------|-----|------|
| 총수익률 | +431% | 방향성 지표 — Sim 4보다 낮음 |
| 거래수 | 3,063회 | 통계적으로 유효한 샘플 |
| 승률 | 65.4% | 매수 종목의 65%가 이후 상승 |
| 평균보유 | 1.5일 | |
| 스코어 정상관 | 150pt+ 승률 77.8% > 120~129pt 승률 64.1% | A와 반대 패턴 — 정상 |

**Sim 5 주의점**: 최대 손절 -22.27% (KD, 3일 보유, 112pt) 발생.  
백테스트 특성상 종가에서만 매도 → 실전에서는 -3% 손절로 컷 가능한 종목이 백테스트에서 -22%로 집계된 것.

---

## 6. 이번 세션 버그 수정 (2026-05-12~19)

### 버그 1: 백테스트 리포트 수익현황 섹션 누락
- **원인**: MDD 수정 과정에서 `d2_dep`, `total_val` 변수 삭제 → `summary_stats` dict NameError → `{}` → 섹션 스킵
- **수정**: 변수 재추가 (`library/simulator_func_mysql.py`)

### 버그 2: trader dashboard cf.initial_capital 오류
- **원인**: `trader_advanced.py`가 `cf.initial_capital` 참조하나 `cf.py`에 미정의
- **수정**: `cf.py`에 `initial_capital = 50_000_000` 추가

### 버그 3: monitor.py 잔액 조회 컬럼 오류
- **원인**: `jango_data`에 `total_evaluation` 컬럼 없음
- **수정**: `d2_deposit`, `total_invest` 컬럼만 조회

### 버그 4: report_generator 속성명 오타 (총자산 0으로 표시)
- **원인**: 존재하지 않는 속성명 참조
  - `total_evaluation_price` → 실제: `change_total_eval_price`
  - `total_evaluation_profit_loss_price` → 실제: `change_total_eval_profit_loss_price`
  - `t_eval = 0` → 총자산이 D+2 예수금만 표시됨
- **수정**: 속성명 교정 (`library/report_generator.py`)
- **참고**: `portfolio_eval_price` fallback이 있어 실제로는 DB 기반값이 표시되고 있었음

### 버그 5: dashboard ↔ report 총자산 불일치
- **원인**: 대시보드는 `추정예탁자산` 기준, 리포트는 `d2_deposit + eval` 기준
- **수정**: 대시보드도 `d2_deposit_before_format`을 직접 사용하도록 통일
  → 양쪽 모두 `d2_deposit + change_total_eval_price` 기준

---

## 7. 신규 기능 추가

### monitor.py 잔액 현황 섹션
- `jango_data` 마지막 레코드에서 D+2 예수금, 총자산, 원금 대비 손익 표시

### 매수 가격 범위 — BB스퀴즈 기반 적응형 상한 (`library/open_api.py`)
- **배경**: collector 5~10분 지연 → trader가 늦게 매수 단계 진입 → 전일종가 대비 갭 발생 → 스킵
- **로직**:
  ```
  갭상승 + BB폭<0.15 (스퀴즈 해소) → 상한 = 전일종가 + ATR×2.5
  갭상승 + BB폭≥0.15 (일반 갭)    → 상한 = 전일종가 + ATR×1.5
  갭하락 or 보합                  → 상한 = 전일종가 + ATR×1.0 (기존)
  ```
- **근거**: BB스퀴즈 해소 시 갭상승 = 압축 해제 에너지 방출 → 더 적극적 진입 허용
- **임시 완화책**: 근본 해결은 collector 타이밍 개선

---

## 8. 미완료 항목

### 8-1. RSI 다이버전스 + BB스퀴즈 스코어링 재도전
- **상태**: 4월 시도는 펀더멘털 오염 + 진입기준 과도 강화로 실패
- **다음 접근**:
  - 펀더멘털 스코어 제외 (Look-ahead bias) — **백테스트에서는 사용 불가**
  - RSI 다이버전스 + BB스퀴즈만 추가 (가격 기반 → 백테스트 유효)
  - v4_min_score_b는 90 유지 (거래수 확보 우선)
  - 변경 후 백테스트로 방향성 승률 변화 확인

### 8-2. 펀더멘털 스코어 실전 전용 구현
- **상태**: 미구현
- **설계 방향**:
  - 백테스트 경로(simulator_func_mysql.py)에서는 `fundamental_data=None` 패스 유지
  - 실전 collector_api.py 경로에서만 최신 DART 데이터로 `_score_fundamental` 활성화
  - 두 경로를 명확히 분리하여 백테스트 오염 방지

### 8-3. exit_strategy.py A/B 매도 파라미터 분기
- **상태**: 미구현
- **중요한 전제**: 이 변경은 백테스트로 검증 불가 (백테스트 매도는 EOD 종가 기준)
- **검증 방법**: 실전 페이퍼 트레이딩 or 실제 운영 관찰
- **설계**:
  - A: losscut=-4% / trailing_start=+3% / ATR배수 2.5 / time_exit=7일
  - B: losscut=-2.5% / trailing_start=+4% / ATR배수 1.5 / time_exit=6일

### 8-4. collector_api.py num=22 브랜치
- **상태**: 미구현 (현재 sim=4/5/6은 백테스트 경로만 있음, 실전 경로 없음)
- **조건**: 백테스트로 매수 방향성 확인 후 구현

### 8-5. Kiwoom DB 리셋 (CP949 버그 후처리)
- **상태**: 코드 수정은 됐으나 기존 깨진 데이터 재수집 미실행
  ```sql
  UPDATE jackbot3_imi1.setting_data SET code_update = '20260416';
  ```
  이후 collector 재실행 필요

### 8-6. collector 실행 시간 앞당기기
- **문제**: Phase 1~3 수집에 시간이 걸려 trader가 5~10분 늦게 매수 진입
- **방향**: bat 파일에서 collector 시작 시간을 더 이르게 조정

---

## 9. 개선 방향 정리

### 단기 — 백테스트로 검증 가능한 것
1. **RSI 다이버전스 + BB스퀴즈만 스코어에 추가** (펀더멘털 제외)
   - 가격 기반이므로 백테스트 유효
   - v4_min_score_b=90 유지하며 방향성 승률 변화 확인

2. **Sim 4 고스코어 역상관 분석**
   - 150pt+ 승률(57.7%) < 120~129pt 승률(76.8%) 현상 원인 파악
   - "이미 오른 종목에 고점 진입" 패턴인지 확인 → 스코어 상한 필터 백테스트

### 중기 — 실전에서만 검증 가능한 것
3. **exit_strategy.py A/B 분기 구현 후 실전 관찰**
   - 백테스트 의미 없음. 소액 실전 또는 페이퍼 트레이딩으로 검증

4. **펀더멘털 스코어 실전 전용 활성화**
   - collector_api.py(실전)에서만 활성화, simulator(백테스트) 경로는 None 유지

### 인프라
5. **collector 타이밍 개선** — bat 파일 실행 시간 앞당기기 (BB 범위 확대의 근본 해결)
6. **Kiwoom DB 리셋** — 깨진 종목명 재수집

---

---

## 12. 백테스팅 & Exit Analysis 전체 기록

### 12-1. Strategy A (sim=4) 백테스트 히스토리

> 스코어링: BreakoutStrategyV3 (전 기간 동일)
> 매도: sell_list_num=20 (익절+6% / 손절-3% / MA5<MA20 데드크로스)

| 파일 생성시각 | 총수익률 | MDD | 승률 | 평균보유 | Sharpe | 특이사항 |
|-------------|---------|-----|------|---------|--------|---------|
| 20260428_125715 | +8,159% | 0.00% | 72.5% | 4.1일 | 0.00 | 초기 기준선 — MDD/Sharpe 버그 (0으로 출력됨) |
| 20260507_144211 | +8,141% | 6.10% | 71.3% | 4.3일 | 9.45 | 버그 수정 후 재측정 — **sim=4 공식 기준선** |
| 20260522_131841 | +8,355% | 6.54% | 70.0% | 4.6일 | 9.71 | 거래수 17,477회 — 최신 기준선 |

**스코어 역상관 관찰 (20260507):**
- 150pt+ 승률 57.7% < 120~129pt 승률 76.8%
- 해석: 고점 진입 종목에 고점수가 몰리는 현상 — 스코어 상한 필터 검토 필요

---

### 12-2. Strategy B (sim=5) 백테스트 히스토리 — 스코어링 + 매도 로직 변천

> ⚠️ 스코어링 버전과 매도 로직이 함께 바뀐 경우가 많아 원인 분석 어려웠음

| 파일 생성시각 | 스코어링 | sell_list_num=31 매도 로직 | 총수익률 | MDD | 승률 | 평균보유 | 결과 해석 |
|-------------|---------|--------------------------|---------|-----|------|---------|---------|
| 20260524_023438 | (확인 필요) | 익절+6% / 손절-8% / MA데드크로스 | +184.30% | 15.08% | 52.8% | 15.1일 | MA데드크로스 63.6% — 승률 낮음 |
| **20260524_165754** | **a5db6c1 BFS+RSI9/14크로스** | MA데드크로스 | **+59.68%** | **6.83%** | **70.6%** | **5.5일** | ✅ **최고 승률 — 이 버전 복원 목표가 됨** |
| 20260524_202951 | (확인 필요) | 익절+6% / 손절-8% / MA데드크로스 | +19.26% | 39.51% | 31.0% | 45.7일 | 손절 63.3% 폭발 — 스코어링 문제 |
| 20260524_233443 | (확인 필요) | 익절+6% / 손절-8% / MA데드크로스 | +97.63% | 15.74% | 44.4% | 23.8일 | 중간 실험 |
| 20260525_023143 | **208d32f (잘못 복구)** | RSI피크이탈 + 45일 시간청산 | +29.48% | 22.40% | 38.5% | 30.1일 | ❌ 208d32f는 RSI저점깊이+연속상승일 — 잘못된 버전 |
| 20260525_043254 | **208d32f (잘못 복구)** | RSI피크이탈 + 45일 시간청산 | +42.67% | 22.40% | 38.5% | 30일 | ❌ 스코어링 롤백 실수 확인 |
| **20260525_105404** | **a5db6c1 (올바르게 복구)** | RSI피크이탈 + 45일 시간청산 | **+94.27%** | **10.09%** | **58.4%** | **31.2일** | ✅ 스코어링 복구 확인 — 매도 로직 비교용 |
| **20260526_130629** | **a5db6c1** | **트레일링(SL-5%+3%활성화,5%트레일)+45일** | **+65.97%** | **3.23%** | **64.4%** | **10.2일** | ✅ **최종 채택 — MDD 최소, Sharpe 2.13** |

**핵심 교훈:**
- 스코어링 버전: **a5db6c1 (BFS+RSI9/14크로스)** = 165754의 70.6% 승률 원천
  - 208d32f (RSI저점깊이+연속상승일)로 잘못 복구 시 승률 38.5%로 폭락
- 매도 로직: MA데드크로스(70.6%) > 트레일링(64.4%) > RSI피크이탈(58.4%) — 단기 승률은 MA가 높지만
  - MDD: MA(6.83%) vs 트레일링(3.23%) — **리스크 관리는 트레일링이 압도적으로 우수**
  - 트레일링을 최종 선택한 이유: 실전에서 알고리즘 실시간 추적 가능 + MDD 최소화

---

### 12-3. Exit Strategy Analysis 결과

#### Strategy B (sim=5) — exit_analysis_simulator5_20260524_170847.txt
> 기반 백테스트: 165754 (a5db6c1, MA데드크로스, 218건)
> 백테스트 원본: 평균 +2.75%, 승률 70.6%

| 전략 | 평균수익 | 승률 | 발동 분포 |
|------|---------|------|---------|
| TP+6/SL-3 | +2.71% | 65.6% | SL:31.2% / TP:60.1% |
| SL-3+Trail(3%,5%) | +4.24% | 73.4% | SL:24.3% / Trail:69.3% |
| **SL-5+Trail(3%,5%)** | **+4.16%** | **78.4%** | **SL:18.8% / Trail:74.3%** |
| MA_DeadCross | +3.05% | 49.1% | 평균보유 26.8일 ❌ |
| Trail 순수 | +87.02% | 91.7% | EOD 아티팩트 — 무시 |

- max_high_pct >+3%: 59.6% / 평균 최대 상승: +10.32%
- min_low_pct <-5%: 12.8% (SL-5가 SL-3보다 불필요 손절 줄임)

#### Strategy B (sim=5) — exit_analysis_simulator5_20260525_110620.txt
> 기반 백테스트: 105404 (a5db6c1, RSI피크이탈+45d, 166건)
> 백테스트 원본: 평균 +5.70%, 승률 58.4%

| 전략 | 평균수익 | 승률 | 발동 분포 |
|------|---------|------|---------|
| TP+6/SL-3 | +2.79% | 65.7% | SL:31.3% / TP:62.0% |
| SL-3+Trail(3%,5%) | +4.84% | 72.9% | SL:25.3% / Trail:70.5% |
| **SL-5+Trail(3%,5%)** | **+4.88%** | **78.9%** | **SL:19.3% / Trail:76.5%** ← 채택 근거 |
| MA_DeadCross | +4.21% | 48.8% | 평균보유 33.0일 ❌ |
| RSI>55+SL-5 | +5.38% | 68.7% | 참고용 |

- max_high_pct >+3%: 86.7% / 평균 최대 상승: +22.07%
- min_low_pct <-5%: 41.0% — 중장기 보유로 손실 노출 증가
- **SL-5+Trail 두 분석 모두 78~79% 승률로 일관** → 채택 결정

#### Strategy A (sim=4) — exit_analysis_simulator4_20260526_142444.txt
> 기반 백테스트: 20220522 (BreakoutStrategyV3, sell_list_num=20, 17,477건)
> 백테스트 원본: 평균 +4.81%, 승률 70.0%

| 전략 | 평균수익 | 승률 | 발동 분포 |
|------|---------|------|---------|
| TP+6/SL-3 | +2.79% | 64.4% | SL:35.5% / TP:64.1% |
| SL-3+Trail(3%,5%) | +8.33% | 73.8% | SL:26.1% / Trail:73.7% |
| **SL-5+Trail(3%,5%)** | **+8.27%** | **79.6%** | **SL:20.3% / Trail:79.4%** ← 채택 |
| MA_DeadCross | +4.60% | 45.8% | 평균보유 28.0일 ❌ |
| RSI>55+SL-5 | +7.96% | 66.5% | 참고용 |

- max_high_pct >+3%: 94.6% (거의 전 종목이 3% 이상 오름)
- min_low_pct <-5%: 18.0% → SL-5 충분히 안전
- SL-3 vs SL-5: 수익률 차이 0.06%p 미미, 승률 차이 5.8%p → SL-5 채택

---

### 12-4. 최종 채택 파라미터 도출 근거

| | Strategy A | Strategy B |
|--|------------|------------|
| 근거 분석 | exit_analysis_simulator4_20260526 (17,477건) | exit_analysis_simulator5_20260525_110620 (166건) |
| 하드 SL | -5% (SL-3 대비 승률 +5.8%p, 수익 동등) | -5% (SL-3 대비 승률 +6%p, 수익 동등) |
| Trail 활성화 | 고점+3% | 고점+3% |
| Trail 간격 | 고점-5% | 고점-5% |
| 시간청산 | 15일 (단기 돌파 특성) | 45일 (중장기 반등 특성) |
| 백테스트 승률 | 79.6% (exit analysis 기준) | 78.9% (exit analysis 기준) |

---

### 12-5. Strategy A 스코어링 버전별 score_component_analysis 결과 비교

> **비교 기준**: Pearson r (컴포넌트 × sell_rate). 백테스트 기간 동일 (2023-01~2026-06, 835일)
> r > 0: 점수 높을수록 수익 증가 (정상). r < 0: 점수 높을수록 수익 감소 (설계 오류)

| 컴포넌트 | v3.2 (70pt 돌파강도) | v3.3 (50pt 돌파강도) | **v3.4+inst_flow** (50pt 셋업품질) | 변화 |
|----------|---------------------|---------------------|-----------------------------------|------|
| score_a | **-0.2468** ★★★ 역상관 | **-0.2748** ★★★ 역상관 | **+0.0801** ★★ | 역전 ✅ |
| score_b | +0.0664 | — | +0.0649 | 유지 |
| score_c | +0.0194 | — | +0.0552 | 개선 |
| score_d | +0.0538 | — | +0.0719 | 개선 |
| score_e | -0.0015 | -0.0296 | +0.0124 | 미미 |
| score_f | — (없음) | — | +0.0680 | 추가 |
| score_g(inst_flow) | — | — | A: -0.0271 없음 / B: -0.0713→+0.0343 (역방향 재설계) | B역방향 ✅ |
| 패널티 | -0.0422 | -0.3043 ★★★ | -0.3268 ★★★ | 강화 ✅ |
| **composite** | **-0.0864** 역상관 | **-0.0513** 역상관 | **+0.0159** 양전환 | ✅ |

**핵심 원인 분석:**
- v3.3 → v3.4: `penalty -= breakout_score` 제거 (역U자 패널티 → 극단값 직접 패널티로 교체)
  - score_a=70pt 고득점 종목(좋은 돌파)이 동시에 최대 패널티도 받던 역설 해소
  - 결과: score_a r = -0.2748 → +0.0801 (완전 역전), composite도 음→양 전환
- v3.2 → v3.3: score_a 50pt로 축소 + 역U자 패널티 추가 → 음의 상관 심화 (역효과)
- A전략 score_g: r=-0.0271 (없음). B전략 score_g: r=-0.0713 → 역방향 재설계 후 r=+0.0343 (2026-06-13)

---

## 13. score_g 전파 완성 + B전략 최적화 (2026-06-10 ~ 2026-06-13)

### 13-1. score_g 전파 체인 버그 수정

**발견**: `_score_inst_flow()` 계산은 됐지만 DB에 저장이 전혀 안 되고 있었음.
- `calculate_total_score()` base dict에 `'score_g'` 키 누락 → result dict에 미포함
- simulator_func_mysql.py에서 참조 불가 → 백테스트 전체 기간 score_g=NULL

**수정 위치 (7곳 동시):**

| 파일 | 위치 | 변경 내용 |
|------|------|---------|
| `hybrid_strategy_v3.py` | calculate_total_score() base dict | `'score_g': 0.0` 초기값 추가 |
| `hybrid_strategy_v3.py` | base.update() | `'score_g': round(sg, 2)` 반환값 추가 |
| `simulator_func_mysql.py` | df_realtime_daily_buy_list 로드 | `'score_g'` 컬럼 목록 추가 |
| `simulator_func_mysql.py` | row_dict 저장 — 단일전략 | `row_dict['score_g'] = result['score_g']` |
| `simulator_func_mysql.py` | row_dict 저장 — sim=6 | `row_dict['score_g'] = best_result['score_g']` |
| `simulator_func_mysql.py` | score_cols/df_all_item/for_col/레포트 SQL | `'score_g'` 전체 추가 |
| `sql/jackbot4_schema.sql` + DB ALTER TABLE | all_item_db / realtime_daily_buy_list | score_g DECIMAL(6,2) 컬럼 8개 테이블 추가 |

### 13-2. score_component_analysis.py 개선

| 기능 | 내용 |
|------|------|
| score_g 감지 버그 수정 | `LIKE 'score_%'` → `LIKE 'score_%%'` (pymysql이 `%_`를 format char로 해석 → ValueError → fallback 반환 버그) |
| `--from=YYYYMMDD` 옵션 추가 | buy_date 기준 필터링. inst_flow 데이터가 20240122부터만 존재 → 2023 데이터 오염 제거용 |

**사용법:**
```
python score_component_analysis.py 6 --from=20240122
```

### 13-3. score_analyze.py `--resume` 옵션 추가

중단된 백테스트를 이어서 실행하는 기능.
- `python score_analyze.py 6 --resume` → `mode='continue'` (jango_data 마지막 날짜 이후부터)
- 기본 실행은 `mode='reset'` (DB 드롭 후 처음부터)

### 13-4. trading_dashboard.py 개선

보유 종목 합계 행에 **총 매수금액** 추가:
```
합계  총 매수금액 xx,xxx,xxx원   총 평가금액 xx,xxx,xxx원   총 평가손익 [+] +xxx,xxx원 (+x.xx%)
```

### 13-5. B전략 score_g 역방향 재설계

**분석 근거 (`python score_component_analysis.py 6 --from=20240122`):**

| 전략 | score_g Pearson r | 판정 |
|------|-----------------|------|
| A전략 | -0.0326 | 없음 — 정방향 유지 |
| B전략 | -0.0713 | 없음이지만 음의 방향 → 역방향 재설계 |

**역방향 설계 근거 (B전략 = 과매도 반등 포착):**
- 기관/외국인 관심 없는 종목 = 시장 소외 = 과매도 심화 = reversal premium 더 높음
- avg 수익: 기관 비관심군 +6.89% vs 기관 관심군 +5.03% (2024+ 클린 데이터)

**재설계 로직 (`_score_inst_flow`, ReversalStrategyV3):**
```
inst_net_buy ≤ 0  → 12pt 만점 (순매도/비활성 = 과매도 가능성)
inst_net_buy > 0  → ratio 0→5% 구간에서 12→0pt 선형 감소
foreign_net_buy ≤ 0 →  8pt 만점
foreign_net_buy > 0 → ratio 0→3% 구간에서 8→0pt 선형 감소
```

**재설계 후 상관관계:**
- B전략 score_g r: -0.0713 → **+0.0343** (방향 전환 확인)

**재설계 후 B전략 composite 구간별 성과 (완벽한 단조증가):**

| 구간 | WR | avg수익 | R |
|------|-----|--------|---|
| 0~59 | 53.9% | +1.90% | — |
| 60~79 | 64.6% | +4.06% | — |
| 80~99 | 71.7% | +6.46% | — |
| 100~119 | 75.1% | +8.92% | — |
| 120~139 | 80.4% | +11.16% | — |

### 13-6. v4_min_score_b 업데이트 (cf.py)

```python
v4_min_score_b: 90 → 110
```

**근거:** 역방향 재설계 후 백테스트에서 >=110 구간 WR 77.8%, avg +10.32%, R=2.13, n=761.
이전 >=110에서는 n=246으로 통계 불충분했으나 역방향 재설계 후 3배 증가.
score_analyze.py 3개 지표(WR/avg/R) 모두 동일하게 110 권장.

### 13-7. B전략 score_d BB사이클 재설계

**문제 발견 (score_component_analysis 구간별 분석):**

| score_d 구간 | n | WR | avg |
|-------------|---|----|-----|
| 0~2 (조건 미충족) | 3,649 | 65.6% | +5.64% |
| 6~8 (터치O, pos 0.40~0.55) | 6,236 | **71.5%** | **+5.99%** ← best |
| 8+ (터치O, pos 0.10~0.40) | 1,304 | **59.1%** | **+3.59%** ← worst |

- 현재 설계는 pos 0.10~0.40(바닥 인근)에 4pt 만점 → 이 구간이 실제로 worst
- pos 0.40~0.55(반등 초기, 부분 점수 구간)가 오히려 best

**재설계:**
```
Before: pos 0.10~0.40 → 4pt 만점, pos 0.40~0.55 → 선형감소(4→0)
After:  pos  <0.30    → 0pt (바닥 인근, 반등 미확인)
        pos 0.30~0.55 → 4pt 만점 (반등 초기 확인 구간)
        pos 0.55~0.65 → 선형감소(4→0)
```

### 13-8. B전략 펀더멘털 스코어링 실전 활성화 (score_b)

**배경:**
- `collect_stock_fundamental()` (collector_api.py) 는 매 거래일 OPT10001 데이터를 `daily_buy_list.sf_YYYYMMDD` 테이블에 저장 중
- 저장 컬럼: roe, pbr, per, credit_rate (신용비율) 등
- 그러나 `num=22` 브랜치 (simulator_func_mysql.py) 에서 이 데이터를 전혀 불러오지 않아 `score_b` 는 항상 0pt

**백테스트 look-ahead bias 방지:**
- 백테스트 날짜 기준 과거 `sf_YYYYMMDD` 테이블이 없음 → `fd=None` → `score_b=0` 자동 처리
- 실전 당일 수집된 `sf_YYYYMMDD` 는 존재 → 실전에서만 활성화

**`_score_fundamental()` 재설계 (ReversalStrategyV3, 40pt 만점):**

| 항목 | 점수 | 기준 |
|------|------|------|
| ROE | 20pt | >15%→20 / >10%→15 / >5%→8 / >0%→3 / ≤0%→-15 |
| PBR | 12pt | <0→-10 / <0.5→12 / <1.0→9 / <1.5→5 / <2.5→2 |
| PER | 5pt | <0→-10 / 5~12→5 / ~20→2 |
| 신용비율 | 3pt | <1%→3 / <3%→1 / ≥5%→-5 |

- 패널티(-10, -15)로 재무 위험 종목 차단
- fundamental_data=None → 0pt (백테스트/데이터 없음 경우 중립 처리)

**num=22 브랜치 변경 (simulator_func_mysql.py):**
```python
# kospi_index 로딩 이후 sf_ 펀더멘털 로딩 추가
fundamental_dict = {}
sf_row = engine_daily_buy_list.execute(
    "SELECT TABLE_NAME FROM information_schema.tables "
    "WHERE table_schema='daily_buy_list' AND TABLE_NAME LIKE 'sf_2%%' "
    f"AND TABLE_NAME <= 'sf_{date_rows_today}' "
    "ORDER BY TABLE_NAME DESC LIMIT 1"
).fetchone()
if sf_row:
    sf_table = sf_row[0]
    fund_df = pd.read_sql(f"SELECT code, roe, pbr, per, credit_rate FROM `{sf_table}`", engine_daily_buy_list)
    for _, fr in fund_df.iterrows():
        fundamental_dict[str(fr['code']).zfill(6)] = {'roe': fr['roe'], 'pbr': fr['pbr'], 'per': fr['per'], 'credit_rate': fr['credit_rate']}
# 스코어링 호출 시: fd = fundamental_dict.get(code) or None 전달
```

**BreakoutStrategyV3 시그니처 변경:**
```python
def calculate_total_score(self, row, df_120, market_data=None, fundamental_data=None):
    # fundamental_data 무시 (A전략은 펀더멘털 미사용)
```

---

## 10. 작업 원칙 (이 프로젝트에서 반드시 지킬 것)

1. simul_num=3 코드/DB 절대 수정 금지
2. 백테스트 = 방향성 검증. 매도 파라미터 비교나 실전 수익 예측으로 사용 금지
3. 펀더멘털 스코어는 백테스트에서 비활성화 (Look-ahead bias)
4. 새 기능은 반드시 elif 추가, 기존 브랜치 수정 없음
5. 코드 전에 설계 먼저, 납득 후 구현
