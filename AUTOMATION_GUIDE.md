# 🤖 완전 자동화 가이드

컴퓨터가 자동으로 켜지고, 매매하고, 데이터 수집하고, 꺼지는 시스템!

---

## 📋 목차

1. [개요](#개요)
2. [배치 파일 설명](#배치-파일-설명)
3. [Windows 작업 스케줄러 설정](#windows-작업-스케줄러-설정)
4. [전체 자동화 일정](#전체-자동화-일정)
5. [문제 해결](#문제-해결)

---

## 개요

### ✨ 자동화 목표

**완전 무인 자동 매매 시스템:**
1. 🌅 **아침 08:30** - 트레이더 자동 실행
2. 📊 **09:00-15:30** - 고급 전략으로 자동 매매
3. 📥 **저녁 15:40** - trader 종료 + 데이터 수집 + 성과 분석
4. 💤 **저녁 19:00** - 10분 카운트다운 후 컴퓨터 종료

### 🎯 장점

- ✅ **편리함**: 아무 조작 없이 완전 자동 실행
- ✅ **일관성**: 고급 전략이 감정 없이 규칙대로 실행
- ✅ **효율성**: 매수 후보 자동 스캔 + 전략 점수 자동 계산
- ✅ **안정성**: 7PM 종료 전 10분 유예 (작업 중이면 취소 가능)

---

## 배치 파일 설명

모든 배치 파일은 `batch/` 폴더에 있습니다.

### 1. `start_trader.bat` - 트레이더 자동 시작 ⭐

**용도:** 아침에 trader_advanced.py를 완전 자동으로 실행합니다.

**실행 시간:** 평일 08:30

**주요 기능:**
- ✅ 완전 자동화 (모드 선택 불필요)
- ✅ trader_advanced.py 자동 실행
- ✅ 키움 로그인 대기
- ✅ 고급 전략 매수 후보 자동 로드

**수동 실행:**
```cmd
cd C:\path\to\trading_bot\batch
start_trader.bat
```

---

### 2. `after_market_collect.bat` - 장 마감 후 작업 ⭐

**용도:** 장 마감 후 트레이더 종료 + 데이터 수집 + 성과 분석을 자동으로 실행합니다.

**실행 시간:** 평일 15:40

**주요 기능:**
1. 실행 중인 trader_advanced.py 자동 종료
2. collector_v3.py 실행 (데이터 수집)
   - 일봉/분봉 데이터 수집
   - **고급 전략으로 내일 매수 후보 자동 스캔**
   - 멀티팩터 스코어링 자동 적용
3. check_buy_list.py 실행 (매수 후보 확인)
4. performance_report.py 실행 (성과 분석)

**수동 실행:**
```cmd
cd C:\path\to\trading_bot\batch
after_market_collect.bat
```

**💡 특징:**
- 컴퓨터를 종료하지 않음 (7PM까지 계속 작업 가능)
- 고급 전략이 자동으로 적용되어 내일 매수 종목 선정

---

### 3. `auto_shutdown.bat` - 안전한 자동 종료 ⭐

**용도:** 저녁 7시에 10분 카운트다운 후 컴퓨터를 종료합니다.

**실행 시간:** 평일 19:00 (7PM)

**주요 기능:**
1. 10분 카운트다운 시작
2. 매 30초마다 남은 시간 표시
3. Ctrl+C로 취소 가능
4. 10분 후 자동 종료

**수동 실행:**
```cmd
cd C:\path\to\trading_bot\batch
auto_shutdown.bat
```

**💡 안전장치:**
- 7시 이후에도 작업 중이면 Ctrl+C로 취소 가능
- 갑작스러운 종료 방지

---

### 4. `collector_auto_restart.bat` - 컬렉터 자동 재시작

**용도:** collector가 멈췄을 때 자동으로 재시작합니다.

**주요 기능:**
- collector_v3.py 모니터링
- 종료 시 자동 재시작
- 무한 루프로 안정성 보장

---

## Windows 작업 스케줄러 설정

### 📝 작업 스케줄러에 등록할 XML 파일

`scheduler/` 폴더에 있는 3개 XML 파일을 등록하세요:

1. **morning_trader.xml** (08:30 AM)
   - start_trader.bat 실행
   - 평일만 실행

2. **evening_collect.xml** (03:40 PM)
   - after_market_collect.bat 실행
   - 평일만 실행

3. **evening_shutdown.xml** (07:00 PM)
   - auto_shutdown.bat 실행
   - 평일만 실행

### 🔧 작업 스케줄러 등록 방법

**1. 작업 스케줄러 열기:**
```
Win + R → taskschd.msc → Enter
```

**2. XML 파일 가져오기:**
1. 작업 스케줄러 라이브러리 우클릭
2. "작업 가져오기..." 선택
3. `scheduler/morning_trader.xml` 선택
4. 경로 확인 (본인 프로젝트 경로로 수정)
5. 확인

**3. 나머지 XML 파일도 동일하게 가져오기:**
- evening_collect.xml
- evening_shutdown.xml

### ✅ 등록 확인

작업 스케줄러에서 3개 작업이 보여야 합니다:
```
✅ morning_trader      - 다음 실행: 내일 08:30
✅ evening_collect     - 다음 실행: 오늘 15:40
✅ evening_shutdown    - 다음 실행: 오늘 19:00
```

---

## 전체 자동화 일정

### 📅 평일 자동화 타임라인

```
08:30  🌅 trader_advanced.py 자동 시작
        ↓  키움 로그인 → 고급 전략 매수 후보 로드

09:00  📊 장 시작 → 자동 매매 시작
        ↓  멀티팩터 스코어링 기반 매수
        ↓  ATR 기반 동적 손절/익절

15:20  📉 장 마감

15:40  🔄 after_market_collect.bat 실행
        ↓  trader_advanced.py 종료
        ↓  데이터 수집 (collector_v3.py)
        ↓  고급 전략으로 내일 매수 후보 스캔
        ↓  성과 분석 리포트 생성

16:30  ✅ 모든 작업 완료
        ↓  (7PM까지 자유롭게 컴퓨터 사용 가능)

19:00  ⏰ auto_shutdown.bat 실행
        ↓  10분 카운트다운 시작
        ↓  (Ctrl+C로 취소 가능)

19:10  💤 컴퓨터 자동 종료
```

### 🎯 수동으로 확인할 것들

**저녁 시간 (선택사항):**
```bash
# 오늘 성과 확인
python performance_report.py

# 내일 매수 후보 확인
python check_buy_list.py

# 포트폴리오 상태 확인
python monitor.py
```

**주말:**
- 주간 성과 분석
- 전략 파라미터 재검토 (필요 시)

---

## 문제 해결

### 자주 묻는 질문

**Q: 작업 스케줄러에서 실행이 안 됩니다**

**A: 경로 확인**
1. XML 파일 열기 (메모장)
2. `<Command>` 태그의 경로 확인
3. 본인의 프로젝트 경로로 수정

```xml
<Command>C:\Users\USER\Desktop\Personal project\trading_bot\batch\start_trader.bat</Command>
```

**Q: 10분 카운트다운이 너무 짧습니다**

**A: auto_shutdown.bat 수정**
```batch
REM 10분 = 600초
REM 20분으로 변경하려면:
for /L %%i in (1200,-1,1) do (
```

**Q: 종료 없이 데이터만 수집하고 싶습니다**

**A: 이미 분리되어 있습니다!**
- 15:40 - after_market_collect.bat (데이터만 수집)
- 19:00 - auto_shutdown.bat (종료만 담당)

두 작업이 분리되어 있어서 7PM까지 자유롭게 작업 가능합니다.

**Q: 고급 전략이 적용되었는지 확인하려면?**

**A: 매수 후보 확인**
```bash
python check_buy_list.py
```

다음과 같이 전략 정보가 표시되면 성공:
```
[1] 005930     삼성전자
      전략:         모멘텀 돌파
      종합 스코어:  85.3/100
      거래량 비율:  2.5x
```

---

## 💡 추가 팁

### 1. 로그 확인

배치 파일 실행 로그 확인:
```cmd
cd batch
type automation_log.txt
```

### 2. 네트워크 문제 대비

집 인터넷이 불안정하면:
- collector_auto_restart.bat 사용
- 자동 재시작으로 안정성 보장

### 3. 여러 계좌 운영

실전/모의 동시 운영:
- start_trader.bat은 모의투자 자동 실행
- 실전은 수동으로 별도 실행 권장

---

## 🎓 마스터 체크리스트

완전 자동화를 위한 체크리스트:

- [ ] 작업 스케줄러에 3개 XML 등록
- [ ] 각 XML 파일의 경로 확인 및 수정
- [ ] start_trader.bat 수동 테스트
- [ ] after_market_collect.bat 수동 테스트
- [ ] auto_shutdown.bat 수동 테스트 (Ctrl+C로 취소)
- [ ] 하루 전체 루틴 테스트 (주말에 시간 조정해서)
- [ ] 고급 전략 작동 확인 (check_buy_list.py)
- [ ] 1주일 모니터링 후 실전 적용

---

**자동화 완료! 이제 아무것도 안 해도 매매가 진행됩니다. 📈🚀**

_마지막 업데이트: 2025-12-13 (완전 자동화 + 고급 전략 통합)_
