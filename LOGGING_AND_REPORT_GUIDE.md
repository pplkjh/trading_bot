# 📊 로깅 & 리포트 기능 가이드

자동 매매 시스템의 로깅 및 성과 분석 기능 사용 가이드입니다.

---

## 🎯 주요 기능

### 1. 중요 이벤트 로깅 ✅
매수/매도/수익률 등 중요한 이벤트를 별도 파일에 기록합니다.

**로그 파일 위치**:
```
logs/trading_events.log          # 오늘 로그
logs/trading_events.log.20251121 # 과거 로그 (날짜별)
```

**기록되는 이벤트**:
- 📈 매수 체결 (종목, 가격, 수량, 총액, 사유)
- 📉 매도 체결 (종목, 가격, 수익, 수익률, 사유)
- 💰 잔고 변화
- 🎯 내일 매수 후보
- 📊 일일 수익 요약
- 🔔 장 시작/종료
- 🚀 시스템 시작/종료

**예시**:
```
2025-11-21 09:05:32 | 📈 [매수] 삼성전자(005930) | 가격: 75,000원 | 수량: 10주 | 총액: 750,000원 | 사유: 하이브리드 전략
2025-11-21 14:35:12 | 🟢 [매도] 삼성전자(005930) | 가격: 77,000원 | 총액: 770,000원 | 수익: +20,000원 (+2.67%) | 사유: 목표 수익률 달성
2025-11-21 15:30:00 | 📊 [일일 요약] 2025-11-21
2025-11-21 15:30:00 | 🟢 총 수익: +45,000원 (+1.23%) | 익절: 3건 | 손절: 1건
2025-11-21 15:30:00 | 💰 잔고: 5,250,000원 | 보유 종목: 2개
```

---

### 2. 로그 자동 삭제 ✅
10일 이상 지난 로그 파일을 자동으로 삭제하여 디스크 공간을 절약합니다.

**실행 방법**:
```bash
# 테스트 (삭제하지 않고 목록만 확인)
python cleanup_old_logs.py --dry-run

# 실제 삭제 (10일 지난 로그)
python cleanup_old_logs.py

# 보관 기간 변경 (예: 7일)
python cleanup_old_logs.py --days 7
```

**자동화**:
Windows 스케줄러에 등록하여 매일 자동 실행:
```
작업: Cleanup Old Logs
프로그램: python
인수: cleanup_old_logs.py
시작 위치: C:\path\to\trading_bot
트리거: 매일 02:00
```

---

### 3. 매매 성과 분석 리포트 ✅
DB에서 매매 이력을 분석하여 예쁜 HTML 리포트를 생성합니다.

**실행 방법**:
```bash
# 기본 (JackBot1_imi1 DB 분석)
python generate_trading_report.py

# 다른 DB 분석
python generate_trading_report.py --db JackBot1_imi1

# 출력 파일 지정
python generate_trading_report.py --output my_report.html
```

**리포트 내용**:
- 📊 전체 통계 (총 거래 횟수, 총 수익, 평균 수익률, 승률)
- 📈 수익 추이 그래프 (차트)
- 🎯 종목별 수익 TOP 10
- 💼 현재 보유 종목
- 📅 일별 성과 분석

**리포트 예시**:
![리포트 예시](https://via.placeholder.com/800x600?text=Trading+Report+Sample)

**파일 위치**:
```
reports/trading_report_20251121_153045.html
```

**브라우저에서 열기**:
```
file:///C:/path/to/trading_bot/reports/trading_report_20251121_153045.html
```

---

### 4. 스마트 자동 종료 ✅
주말/휴장일에는 바로 종료, 평일에는 21시에 자동 종료합니다.

**실행 방법**:
```batch
batch\smart_shutdown.bat
```

**동작 방식**:
- **주말 (토/일)**: 30초 후 즉시 종료
- **평일 (21시 이전)**: 21시에 자동 종료 예약
- **평일 (21시 이후)**: 60초 후 종료

**Windows 스케줄러 등록**:
```
작업: Smart Shutdown
프로그램: C:\path\to\trading_bot\batch\smart_shutdown.bat
트리거: 매일 16:30 (데이터 수집 완료 후)
```

---

## 🔧 trader_advanced.py에 로깅 추가하기

### 매수 체결 시 로깅
```python
from library.trading_logger import trading_logger

# 매수 체결 후
trading_logger.log_buy(
    code=code,
    name=name,
    price=purchase_price,
    quantity=quantity,
    total_value=total_value,
    reason="하이브리드 전략"
)
```

### 매도 체결 시 로깅
```python
# 매도 체결 후
trading_logger.log_sell(
    code=code,
    name=name,
    price=sell_price,
    quantity=quantity,
    total_value=total_value,
    profit=profit,
    profit_rate=profit_rate,
    reason="목표 수익률 달성"
)
```

### 일일 요약 로깅
```python
# 장 마감 후
trading_logger.log_daily_summary(
    date=today,
    total_profit=total_profit,
    total_profit_rate=total_profit_rate,
    win_count=win_count,
    loss_count=loss_count,
    balance=balance,
    position_count=position_count
)
```

### 시스템 이벤트 로깅
```python
# Trader 시작
trading_logger.log_system_event('START', 'Trader Advanced 시작')

# Trader 종료
trading_logger.log_system_event('STOP', '장 마감 후 30분 경과로 자동 종료')

# 에러 발생
trading_logger.log_system_event('ERROR', f'매수 스캔 오류: {error_message}')
```

---

## 📅 일일 루틴

### 자동화된 워크플로우:
```
08:30 → 컴퓨터 자동 켜기 (BIOS)
08:50 → Trader 시작
09:00 → 장 시작, 매매 시작
      ├─ 매수/매도 이벤트 자동 로깅
      └─ logs/trading_events.log 에 기록
15:00 → 장 마감
15:30 → Trader 자동 종료
      └─ 일일 요약 로그 기록
15:35 → Collector 데이터 수집
16:30 → 성과 리포트 자동 생성
      └─ reports/trading_report_YYYYMMDD.html
21:00 → 컴퓨터 자동 종료 (평일)
      └─ 주말은 즉시 종료
```

---

## 🚀 빠른 시작

### 1. 로깅 시스템 설정
```bash
# logs 폴더 생성 (자동)
# 코드에서 trading_logger import만 하면 자동 설정됨
```

### 2. 리포트 생성 테스트
```bash
python generate_trading_report.py
```

### 3. 로그 정리 테스트
```bash
python cleanup_old_logs.py --dry-run
```

### 4. 스마트 종료 테스트
```bash
batch\smart_shutdown.bat
```

---

## 📝 로그 파일 구조

```
trading_bot/
├── log/
│   ├── jackbot.log              # 디버그 로그 (모든 로그)
│   └── jackbot.log.20251121     # 과거 디버그 로그
├── logs/
│   ├── trading_events.log       # 중요 이벤트 전용 (오늘)
│   └── trading_events.log.20251121  # 과거 이벤트 로그
└── reports/
    └── trading_report_20251121_153045.html  # 성과 리포트
```

---

## 💡 팁

### 로그 실시간 모니터링
```bash
# Windows (PowerShell)
Get-Content logs\trading_events.log -Wait

# Linux/Mac
tail -f logs/trading_events.log
```

### 매주 일요일에 주간 리포트 생성
```batch
REM weekly_report.bat
@echo off
python generate_trading_report.py --output reports/weekly_report_%date:~0,4%%date:~5,2%%date:~8,2%.html
```

### 텔레그램 알림 (향후 추가 가능)
```python
# TODO: 텔레그램 봇 연동
# - 매수/매도 즉시 알림
# - 일일 요약 알림
# - 에러 발생 알림
```

---

## 🔍 트러블슈팅

### Q: 로그가 생성되지 않아요
```
A: logs 폴더 권한 확인
   - 수동으로 생성: mkdir logs
   - 권한 확인: icacls logs
```

### Q: 리포트에 데이터가 없어요
```
A: DB에 거래 이력이 있는지 확인
   - 최소 1건 이상의 매도 완료 필요
   - all_item_db 테이블에 sell_date != '0' 확인
```

### Q: 로그 파일이 너무 커요
```
A: 자동 삭제 스크립트 실행
   - python cleanup_old_logs.py --days 7
   - 보관 기간을 7일로 단축
```

---

## 📚 참고 자료

- `library/trading_logger.py` - 로깅 시스템 구현
- `cleanup_old_logs.py` - 로그 정리 스크립트
- `generate_trading_report.py` - 리포트 생성기
- `batch/smart_shutdown.bat` - 스마트 종료

---

**마지막 업데이트**: 2025-11-21
**작성자**: Claude Code Optimization Session
