# JackBot — Future Claude Work Brief
> Written: 2026-04-21 | Read this FIRST before any strategy/scoring work

---

## 1. 현재 시스템 상태 (건드리면 안 되는 것)

**simul_num=3는 성역이다. 절대 손대지 마라.**

- 3년 백테스트: +5,758% 총수익률, 승률 60%, Sharpe 1.19, MDD 55%
- DB: `jackbot3_imi1` (all_item_db, setting_data, realtime_position_monitor)
- 스코어링: `library/hybrid_strategy_v2.py` — 200pt 만점, min_score=120
- 매수 리스트 생성: `db_to_realtime_daily_buy_list_num=21` (collector_api.py)
- 매도: `sell_list_num=100` (exit_strategy.py의 ATR 기반 청산)
- 파라미터: invest_unit=1,000,000 / losscut=-3% / sell_point=6%
- 트레일링: aggressive 프로필 기준 +3% 활성화, ATR×2.5 배수

**절대 수정 금지 파일:**
- `library/hybrid_strategy_v2.py`
- `jackbot3_imi1` DB 스키마/데이터
- `exit_strategy.py`의 simul_num=3 파라미터 부분
- `cf.py`의 기존 상수 (추가는 가능, 수정 불가)

---

## 2. 발견된 문제점 (live 트레이딩 2026-04-20~21 관찰)

### 문제 A: EOD 선정 → 다음날 아침 진입 타이밍 불일치
- 수집기가 어제 종가 기준으로 "급등 + MA정배열 + ADX 높음" 종목 선정
- 다음날 아침 매수하면 그 급등은 이미 시장이 알고 있는 상태
- 결과: 갭 상승 출발 후 차익실현 매물에 바로 손절당함
- 증거: 손절들이 대부분 -3% 즉시 손절, 익절은 "6일 후 시간청산 0.02%"

### 문제 B: 매도 전략이 매수 전략 특성과 불일치
- 매수: 모멘텀 급등 종목 (변동성 높음)
- 매도: -3% 기본손절 + +3% 트레일링 활성화
- 불일치: 급등 종목은 변동성이 커서 -3%가 바로 뚫림, +3% 도달 전에 손절
- 트레일링 스톱 자체는 코드상 정상 작동 중 (exit_strategy.py에 올바르게 구현됨)
  - 단지 발동 조건(+3% 이상 수익 달성 후)을 만족하는 종목이 드물어서 로그에 안 보임

### 문제 C: RSI 스코어링이 하락 중인 종목에도 높은 점수 줌
- B1: RSI≤40이면 점수 부여 (RSI가 내려가는 중인지 올라가는 중인지 무관)
- _rsi_slope_score: RSI>60 고점 하락 패널티 있음, RSI<40 저점 상승 보너스 있음
- 누락된 케이스: RSI 55→45→35로 내려가는 중 (아직 바닥 미형성) → B1 5pt + 패널티 0
- **BUT: 이 문제는 simul_num=3을 수정하지 않기로 결정. simul_num=4에서 새로 설계.**

---

## 3. 결정된 방향: simul_num=4 신규 전략

### 핵심 원칙
- simul_num=3는 그대로 운영 병행
- simul_num=4를 완전히 새로 설계 (elif 추가 방식, 기존 코드 수정 없음)
- **반드시 백테스트 먼저, 결과 확인 후 실전 배포**

### 전략 컨셉: A+B 듀얼 전략

**Strategy A: 추세 눌림목 진입**
- 조건: 다주/다월 상승 추세 유지 + 최근 2-3일 단기 눌림목 발생
- 진입: RSI가 45-55 구간으로 내려왔다가 오늘 반등 캔들
- 핵심: "어제 급등한 종목" NOT, "수 주째 올라가고 있는 종목이 잠깐 쉬는 것" YES
- EOD 적합성: ✅ (오늘 눌림 확인 → 내일 아침 재상승 진입)
- 매도: 추세 지속형, 넓은 트레일링, 10일 시간청산

**Strategy B: 저점 반등 확인 진입**
- 조건: RSI가 ≤35였다가 현재 상승 반전 2일 이상 확인됨
- 진입: BB하단 이탈 후 복귀 + 반등일 거래량 급증
- 핵심: 바닥에서 올라오는 것 확인 후 진입 (하락 중 진입 아님)
- EOD 적합성: ✅ (어제 종가에서 반등 패턴 확인 → 내일 아침 진입)
- 매도: 단기 회복형, MA20 회복 or +5% 목표, 4일 시간청산

### 구현 순서 (아직 시작 안 됨)
1. **스코어링 수식 설계** — A와 B 각각 어떤 지표로, 몇 점 배분할지 유저와 합의
2. **hybrid_strategy_v3.py 작성** — A점수/B점수 따로 계산, strategy_type 반환
3. **jackbot4_imi1 DB 생성** — jackbot3_imi1 스키마 복사 + strategy_type 컬럼 추가
4. **simulator_func_mysql.py** — simul_num=4 elif 브랜치 추가
5. **collector_api.py** — db_to_realtime_daily_buy_list_num=22 브랜치 추가
6. **cf.py** — v4 전용 상수 추가
7. **exit_strategy.py** — strategy_type별 매도 파라미터 분기 (simul_num=4 only)
8. **백테스트** 2023-2026 → 결과 비교
9. **실전 배포** (백테스트 통과 시만)

---

## 4. 유저가 중요하게 여기는 것 (절대 잊지 말 것)

1. **simul_num=3 백테스트 5758%는 검증된 자산** — 갈아엎자고 제안하지 말 것
2. **백테스트 없이 실전 배포 제안 금지** — 반드시 시뮬레이터 먼저
3. **DB 구조 변경에 매우 민감** — 기존 DB 건드리면 안 됨, 새 DB 사용
4. **과한 추상화/리팩토링 금지** — 필요한 것만, 최소한으로
5. **bat 파일에 한글 절대 금지** — CMD가 CP949로 읽어서 UTF-8 한글이 깨짐
6. **기능 변경 전 "왜 이렇게 해야 하는지" 납득을 구함** — 코드 먼저 짜지 말 것

---

## 5. 최근 완료된 버그 수정 (2026-04-20~21, 이미 코드에 반영됨)

| 파일 | 수정 내용 | 상태 |
|---|---|---|
| `library/open_api.py` | 미체결 대기 중 로그 — set 기반 1회만 출력, 체결 시 초기화 | ✅ 완료 |
| `trader_advanced.py` | 매도 스킵(10회 초과) — _sell_skip_warned set, 1회만 출력 | ✅ 완료 |
| `trader_advanced.py` | 매도 쿨다운 로그 — elapsed<6 체크로 시작 시만 출력 | ✅ 완료 |
| `batch/start_trader.bat` | 로그 한글 깨짐 — chcp 65001 + PowerShell UTF-8 | ✅ 완료 |
| `library/open_api.py` | GetMasterCodeName CP949 디코딩 — latin-1→cp949 변환 | ✅ 완료 (DB 리셋 필요) |
| `library/trading_dashboard.py` | 포지션 테이블에 스톱가 컬럼 추가 | ✅ 완료 |
| `trader_advanced.py` | 대시보드 trailing_stop_price 계산 및 전달 | ✅ 완료 |

### 미완료 (코드 수정 필요)
- **Kiwoom 한글 DB 리셋**: GetMasterCodeName 버그 수정 후 stock_item_all 테이블 재수집 필요
  ```sql
  UPDATE jackbot3_imi1.setting_data SET code_update = '20260416';
  -- 이후 collector 재실행 → 깨진 종목명 재수집
  ```

---

## 6. 시스템 아키텍처 빠른 참조

```
collector_auto_restart.bat
  → Phase 1: collector_v3.py --phase 1  (OHLCV + 기술지표, ~3500 API calls)
  → Phase 2: collector_v3.py --phase 2  (펀더멘털, ~2769 API calls)
  → Phase 3: collector_v3.py --phase 3  (스코어링, API 없음)
  → start_trader.bat → trader_advanced.py (장중 실행)

trader_advanced.py 핵심 루프 (~5초마다):
  1. opw00018 조회 (보유종목 현재가)
  2. realtime_position_monitor 업데이트 (highest_price)
  3. get_advanced_sell_list() → exit_strategy.py → 매도 시그널
  4. get_advanced_buy_list() → daily_buy_list DB → 매수 후보
  5. 대시보드 갱신
```

---

## 7. 다음 작업 시 시작점

**현재 상태**: simul_num=4 개념 합의 완료, 스코어링 수식은 아직 미정

**다음 할 일**: 유저와 함께 simul_num=4 스코어링 수식 구체화
- Strategy A(눌림목)와 B(저점반등) 각각 어떤 지표를 쓸지
- 두 전략의 진입 조건을 어떻게 코드로 표현할지
- 유저가 "급등 후 멈칫" 패턴이 싫다고 했으니 A에서 "전일 거래량 급증"은 오히려 감점 요소가 되어야 함

**작업 시작 전 확인사항**:
1. 이 문서 읽었는가?
2. simul_num=3 코드 건드리지 않는 방법인가?
3. 백테스트 포함된 계획인가?
