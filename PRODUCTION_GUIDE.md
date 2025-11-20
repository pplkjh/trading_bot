# 🚀 실전 자동매매 시스템 사용 가이드

고급 전략이 통합된 실전 자동매매 시스템 사용 가이드입니다.

---

## 📋 목차

1. [시스템 개요](#시스템-개요)
2. [빠른 시작](#빠른-시작)
3. [고급 트레이더 사용법](#고급-트레이더-사용법)
4. [전략 설정 커스터마이징](#전략-설정-커스터마이징)
5. [모니터링](#모니터링)
6. [자동화 설정](#자동화-설정)
7. [문제 해결](#문제-해결)

---

## 시스템 개요

### ✨ 주요 기능

**1. 고급 매매 전략**
- ✅ 멀티팩터 스코어링 (5가지 팩터 종합 평가)
- ✅ 하이브리드 전략 (모멘텀 60% + 평균회귀 40%)
- ✅ 날짜 기반 전략 통합
- ✅ 동적 리스크 관리 (ATR 기반)
- ✅ 고급 청산 전략 (트레일링 스톱)

**2. 실전 자동화**
- ✅ 아침 자동 시작
- ✅ 자동 매수/매도
- ✅ 저녁 데이터 수집
- ✅ 컴퓨터 자동 종료 (선택)

**3. 모니터링**
- ✅ 실시간 포트폴리오 현황
- ✅ 수익률 추적
- ✅ 성과 분석

### 📁 핵심 파일

```
trading_bot/
├── trader_advanced.py          # 고급 전략 트레이더 (★ 신규)
├── trader.py                    # 기존 트레이더 (호환성 유지)
├── monitor.py                   # 모니터링 스크립트 (★ 신규)
├── library/
│   ├── advanced_trading_engine.py    # 고급 전략 엔진 (★ 신규)
│   ├── advanced_strategy_system.py   # 전략 시스템
│   ├── multi_factor_scoring.py       # 멀티팩터 스코어링
│   ├── hybrid_strategy.py            # 하이브리드 전략
│   ├── risk_manager.py               # 리스크 관리
│   ├── exit_strategy.py              # 청산 전략
│   ├── date_based_strategy.py        # 날짜 기반 전략
│   └── performance_analytics.py      # 성과 분석
├── batch/
│   ├── start_trader.bat              # 트레이더 시작
│   ├── collect_data.bat              # 데이터 수집
│   └── auto_shutdown.bat             # 자동 종료
└── scheduler/
    ├── morning_trader.xml            # 아침 스케줄
    ├── evening_collect.xml           # 저녁 데이터 수집
    └── evening_shutdown.xml          # 저녁 자동 종료
```

---

## 빠른 시작

### 1️⃣ 수동 실행 (테스트용)

```bash
# 고급 전략 트레이더 실행
python trader_advanced.py

# 또는 기존 방식
python trader.py
```

### 2️⃣ 배치 파일로 실행 (Windows)

```cmd
# 트레이더 시작
batch\start_trader.bat

# 데이터 수집
batch\collect_data.bat
```

### 3️⃣ 모니터링

```bash
# 포트폴리오 현황 확인
python monitor.py

# 특정 데이터베이스 확인
python monitor.py --db JackBot1_imi1

# 최근 30일 성과 확인
python monitor.py --days 30
```

---

## 고급 트레이더 사용법

### ⚙️ 전략 설정

`trader_advanced.py`의 `variable_setting()` 함수에서 설정:

```python
def variable_setting(self):
    # 고급 전략 사용 여부
    self.use_advanced_strategy = True   # True: 고급 전략, False: 기존 방식

    # 날짜 기반 전략만 사용
    self.force_date_strategy = False    # True: 날짜 기반만, False: 혼합

    # 고급 매도 전략 사용
    self.use_advanced_exit = True       # True: 고급 청산, False: 기존 방식
```

### 📊 전략 조합

**1. 기본 설정 (권장)** ⭐
```python
use_advanced_strategy = True
force_date_strategy = False
use_advanced_exit = True
```
- 날짜 기반 30% + 하이브리드 70%
- 고급 청산 전략 사용
- 균형잡힌 리스크 관리

**2. 날짜 기반 전용**
```python
use_advanced_strategy = True
force_date_strategy = True
use_advanced_exit = True
```
- 날짜 기반 전략 100%
- 단순하고 빠른 스캔
- 변동성 큰 시장에 적합

**3. 보수적 설정**
```python
use_advanced_strategy = True
force_date_strategy = False
use_advanced_exit = True
```
- `library/advanced_trading_engine.py`에서:
  ```python
  risk_profile='conservative'  # aggressive → conservative
  ```

**4. 기존 방식**
```python
use_advanced_strategy = False
force_date_strategy = False
use_advanced_exit = False
```
- 기존 trader.py와 동일
- 하위 호환성 유지

---

## 전략 설정 커스터마이징

### 1. 리스크 프로필 변경

`library/open_api.py`의 `init_advanced_trading_engine()` 수정:

```python
self.advanced_engine = AdvancedTradingEngine(
    portfolio_value=portfolio_value,
    db_name=self.db_name,
    risk_profile='conservative',  # 'conservative', 'moderate', 'aggressive'
    use_date_based_strategy=True
)
```

**리스크 프로필 비교:**

| 항목 | Conservative | Moderate | Aggressive |
|------|--------------|----------|------------|
| 포지션 크기 | 5% | 10% | 15% |
| 거래당 리스크 | 1% | 2% | 3% |
| 최대 포지션 수 | 15개 | 12개 | 10개 |
| ATR 손절 배수 | 3.0x | 2.5x | 2.0x |

### 2. 전략 가중치 조정

`library/advanced_trading_engine.py`의 config 수정:

```python
self.config = {
    'min_factor_score': 70.0,          # 최소 팩터 스코어
    'min_hybrid_score': 70.0,          # 최소 하이브리드 스코어
    'min_date_score': 70.0,            # 최소 날짜 기반 스코어
    'max_positions': 10,               # 최대 포지션 수
    'max_position_pct': 0.15,          # 단일 포지션 최대 15%
    'max_daily_loss_pct': -0.08,       # 일일 최대 손실 -8%
    'atr_stop_multiplier': 2.0,        # ATR 손절 배수
    'trailing_stop_activation': 0.05,  # 트레일링 스톱 활성화 (5% 수익)
    'max_holding_days': 10,            # 최대 보유 기간
    'date_strategy_weight': 0.3,       # 날짜 기반 전략 가중치 30%
    'hybrid_strategy_weight': 0.7      # 하이브리드 전략 가중치 70%
}
```

### 3. 모멘텀 vs 평균회귀 비율

`library/hybrid_strategy.py`의 가중치 수정:

```python
# 모멘텀 중심 (추세 추종)
strategy = HybridStrategy(
    momentum_weight=0.8,        # 80%
    mean_reversion_weight=0.2   # 20%
)

# 평균회귀 중심 (역추세)
strategy = HybridStrategy(
    momentum_weight=0.3,        # 30%
    mean_reversion_weight=0.7   # 70%
)
```

---

## 모니터링

### 📊 기본 모니터링

```bash
# 전체 현황 확인
python monitor.py

# 출력 예시:
# ================================================================================
# 🤖 트레이딩 봇 모니터링
# 시각: 2025-11-20 15:45:00
# ================================================================================
#
# ✅ 트레이더가 실행 중입니다.
#
# ================================================================================
# 📊 포트폴리오 현황 (JackBot1_imi1)
# ================================================================================
#
# 📈 보유 종목 (5개)
# --------------------------------------------------------------------------------
#
# [1] 005930
#   매수일:     20251118
#   매수가:          70,000원
#   현재가:          72,000원
#   수량:                 20주
#   평가금액:     1,440,000원
#   수익률:            2.86%
#   평가손익:        40,000원
# ...
```

### 📈 최근 성과 조회

```bash
# 최근 7일
python monitor.py --days 7

# 최근 30일
python monitor.py --days 30

# 출력 예시:
# 📈 최근 7일 성과
# --------------------------------------------------------------------------------
# 20251119:  8건 | 평균  3.52% | 승률  62.5% (5승 3패)
# 20251118:  6건 | 평균  2.18% | 승률  66.7% (4승 2패)
# 20251115: 10건 | 평균  1.95% | 승률  60.0% (6승 4패)
# --------------------------------------------------------------------------------
# 전체: 24건 | 승률 62.5% (15승 9패)
```

### 🔔 실시간 알림 (선택사항)

Windows 작업 스케줄러로 정기적 모니터링:

```cmd
# 1시간마다 모니터링
schtasks /create /tn "Trading Monitor" /tr "python C:\path\to\trading_bot\monitor.py" /sc hourly
```

---

## 자동화 설정

### 1️⃣ 배치 파일 경로 수정

`batch/` 폴더의 모든 `.bat` 파일에서 경로 수정:

```batch
REM 예시
cd /d C:\Users\YourName\Documents\trading_bot
```

### 2️⃣ Windows 작업 스케줄러 설정

#### 방법 A: XML 파일 가져오기 (권장)

1. `scheduler/` 폴더의 XML 파일을 메모장으로 열기
2. 경로 수정:
   ```xml
   <Command>C:\Users\YourName\Documents\trading_bot\batch\start_trader.bat</Command>
   <WorkingDirectory>C:\Users\YourName\Documents\trading_bot</WorkingDirectory>
   ```
3. 작업 스케줄러 실행 (`Win + R` → `taskschd.msc`)
4. 작업 가져오기:
   - `morning_trader.xml` → "Trading Bot - Morning Start"
   - `evening_collect.xml` → "Trading Bot - Data Collection"
   - `evening_shutdown.xml` → "Trading Bot - Auto Shutdown" (선택)

#### 방법 B: 수동 설정

[AUTOMATION_GUIDE.md](AUTOMATION_GUIDE.md) 참조

### 3️⃣ BIOS 자동 전원 켜기

[AUTOMATION_GUIDE.md](AUTOMATION_GUIDE.md#bios-자동-전원-켜기-설정) 참조

### 4️⃣ 자동화 일정

| 시간 | 작업 | 설명 |
|------|------|------|
| **08:25** | 🌅 컴퓨터 자동 켜기 | BIOS RTC Alarm |
| **08:30** | 🚀 트레이더 시작 | trader_advanced.py 실행 |
| **09:00** | 📊 장 시작 | 자동 매매 시작 |
| **09:00-15:30** | 💹 자동 매매 | 매수/매도 자동 실행 |
| **15:30** | 📉 장 마감 | 매매 종료 |
| **15:40** | 📥 데이터 수집 | collector_v3.py |
| **16:00** | 🔍 내일 스캔 | 매수 후보 미리 생성 |
| **20:00** | 💤 자동 종료 | 컴퓨터 종료 (선택) |

---

## 문제 해결

### Q1: 고급 전략에서 매수 후보를 찾지 못해요

**원인:**
- 시장 상황이 좋지 않음
- 스코어 기준이 너무 높음

**해결:**
1. `library/advanced_trading_engine.py`에서 스코어 기준 낮추기:
   ```python
   'min_factor_score': 65.0,  # 70.0 → 65.0
   'min_hybrid_score': 65.0,  # 70.0 → 65.0
   'min_date_score': 65.0,    # 70.0 → 65.0
   ```

2. 또는 날짜 기반 전략만 사용:
   ```python
   self.force_date_strategy = True
   ```

### Q2: 고급 엔진 초기화 실패

**오류 메시지:**
```
❌ 고급 매매 엔진 초기화 실패
```

**해결:**
1. 모든 모듈이 설치되었는지 확인:
   ```bash
   python check_packages.py
   ```

2. 데이터베이스 연결 확인:
   - `library/cf.py`의 DB 설정 확인

3. 기존 방식으로 전환:
   ```python
   self.use_advanced_strategy = False
   ```

### Q3: 매도 시그널이 너무 많아요

**원인:**
- 손절 기준이 너무 타이트함

**해결:**
1. `library/advanced_trading_engine.py`에서:
   ```python
   'atr_stop_multiplier': 2.5,  # 2.0 → 2.5 (느슨하게)
   ```

2. 트레일링 스톱 활성화 기준 높이기:
   ```python
   'trailing_stop_activation': 0.08,  # 0.05 → 0.08 (8% 수익 시)
   ```

### Q4: realtime_daily_buy_list 테이블이 없어요

**오류 메시지:**
```
realtime_daily_buy_list 테이블 생성...
```

**해결:**
1. 먼저 기존 collector로 데이터 수집:
   ```bash
   python collector_v3.py
   ```

2. 테이블이 자동 생성되지 않으면:
   ```sql
   CREATE TABLE realtime_daily_buy_list (
       code VARCHAR(20),
       close FLOAT,
       check_item BOOLEAN DEFAULT 0,
       date VARCHAR(20)
   );
   ```

### Q5: 트레이더가 자동으로 시작되지 않아요

**확인사항:**
1. 작업 스케줄러 로그 확인:
   - 작업 스케줄러 → 해당 작업 우클릭 → 속성 → 기록 탭

2. 배치 파일 수동 실행 테스트:
   ```cmd
   batch\start_trader.bat
   ```

3. 경로 확인:
   - 작업 스케줄러의 "작업" 탭에서 경로가 올바른지 확인

---

## 성능 최적화 팁

### 1. 승률 향상

```python
# config 수정
'min_factor_score': 75.0,  # 70 → 75 (더 엄격한 진입)
'max_positions': 8,         # 10 → 8 (집중 투자)
```

### 2. 손익비 개선

```python
# config 수정
'atr_stop_multiplier': 1.5,           # 2.0 → 1.5 (타이트한 손절)
'trailing_stop_activation': 0.03,     # 0.05 → 0.03 (빠른 수익 보호)
```

### 3. 최대 낙폭 감소

```python
# config 수정
'max_position_pct': 0.10,       # 0.15 → 0.10 (작은 포지션)
'max_daily_loss_pct': -0.05,    # -0.08 → -0.05 (엄격한 손실 한도)
```

### 4. 시장 환경별 전략

**상승장:**
```python
# 모멘텀 중심
momentum_weight=0.8,
mean_reversion_weight=0.2
```

**횡보장:**
```python
# 평균회귀 중심
momentum_weight=0.3,
mean_reversion_weight=0.7
```

**약세장:**
```python
# 보수적 설정
risk_profile='conservative'
'max_positions': 5  # 포지션 축소
```

---

## 주의사항

### ⚠️ 중요

1. **충분한 백테스팅**
   - 최소 1개월 이상 모의투자
   - 다양한 시장 상황에서 테스트

2. **점진적 자본 투입**
   - 첫 주: 소액 (10%)
   - 첫 달: 중간 (30%)
   - 안정 후: 전액 (100%)

3. **정기적 모니터링**
   - 매일 저녁 성과 확인
   - 주간 전략 리뷰
   - 월간 파라미터 재최적화

4. **리스크 관리 엄수**
   - 일일 최대 손실 한도 절대 변경 금지
   - 감정적 판단 배제
   - 전략을 신뢰하되 맹신하지 말기

---

## 📞 지원

### 추가 문서

- [ADVANCED_STRATEGY_GUIDE.md](ADVANCED_STRATEGY_GUIDE.md) - 전략 상세 가이드
- [AUTOMATION_GUIDE.md](AUTOMATION_GUIDE.md) - 자동화 설정 가이드
- [STRATEGY_GUIDE.md](STRATEGY_GUIDE.md) - 전략 이론 및 배경
- [USER_MANUAL.md](USER_MANUAL.md) - 기본 사용법

### 문제 발생 시

1. 로그 확인: `automation_log.txt`
2. 데이터베이스 상태 확인: `python monitor.py`
3. 모듈 설치 확인: `python check_packages.py`

---

## 🎉 결론

이 시스템은:
- ✅ 검증된 고급 전략 적용
- ✅ 체계적인 리스크 관리
- ✅ 완전 자동화 가능
- ✅ 실시간 모니터링

**성공적인 자동매매를 위해:**
1. 충분한 백테스팅과 모의투자
2. 점진적 자본 투입
3. 꾸준한 모니터링과 개선
4. 리스크 관리 철저히 준수

**Happy Trading! 🚀**

---

_마지막 업데이트: 2025-11-20_
_버전: 2.0.0 (Advanced Strategy Integrated)_
