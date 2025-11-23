# 🤖 완전 자동화 가이드

컴퓨터가 자동으로 켜지고, 매매하고, 데이터 수집하고, 꺼지는 시스템!

---

## 📋 목차

1. [개요](#개요)
2. [배치 파일 설명](#배치-파일-설명)
3. [Windows 작업 스케줄러 설정](#windows-작업-스케줄러-설정)
4. [BIOS 자동 전원 켜기 설정](#bios-자동-전원-켜기-설정)
5. [전체 자동화 일정](#전체-자동화-일정)
6. [문제 해결](#문제-해결)

---

## 개요

### ✨ 자동화 목표

**완전 무인 자동 매매 시스템:**
1. 🌅 **아침 08:30** - 컴퓨터 자동 켜기 (BIOS 설정)
2. 🚀 **아침 08:30** - 트레이더 자동 실행
3. 📊 **09:00-15:30** - 자동 매매 진행
4. 📥 **저녁 15:40** - 데이터 자동 수집
5. 💤 **저녁 20:00** - 컴퓨터 자동 종료

### 🎯 장점

- ✅ **편리함**: 출근 중에도 자동 매매
- ✅ **일관성**: 감정 없이 규칙대로 실행
- ✅ **효율성**: 전기세 절약 (필요할 때만 켜짐)
- ✅ **안정성**: 매일 같은 루틴 반복

---

## 배치 파일 설명

모든 배치 파일은 `batch/` 폴더에 있습니다.

### 1. `start_trader.bat` - 트레이더 시작

**용도:** 아침에 자동으로 trader.py를 실행합니다.

**실행 시간:** 평일 08:30

**주요 기능:**
- 기존 프로세스 확인 및 종료
- 모의투자/실전투자 선택
- trader.py 자동 실행
- 키움 로그인 대기

**수동 실행:**
```cmd
cd C:\path\to\trading_bot\batch
start_trader.bat
```

**로그:**
- `automation_log.txt`에 기록

---

### 2. `collect_data.bat` - 데이터 수집

**용도:** 장 마감 후 데이터를 자동으로 수집합니다.

**실행 시간:** 평일 15:40

**주요 기능:**
1. collector_v3.py 실행 (데이터 수집)
2. 내일 매수 후보 미리 스캔
3. 오늘 성과 분석

**수동 실행:**
```cmd
cd C:\path\to\trading_bot\batch
collect_data.bat
```

**소요 시간:** 약 30분-1시간

---

### 3. `auto_shutdown.bat` - 자동 종료

**용도:** 데이터 수집 후 컴퓨터를 자동으로 종료합니다.

**실행 시간:** 평일 20:00 (데이터 수집 완료 후)

**주요 기능:**
1. 실행 중인 trader.py 종료
2. 데이터 수집 실행
3. 임시 파일 정리
4. 컴퓨터 종료/절전 모드

**종료 옵션:**
- `1` - 종료 (Shutdown)
- `2` - 절전 모드 (Sleep)
- `3` - 최대 절전 모드 (Hibernate)
- `4` - 취소

**수동 실행:**
```cmd
cd C:\path\to\trading_bot\batch
auto_shutdown.bat
```

---

### 4. `daily_routine.bat` - 통합 루틴

**용도:** 시간대에 따라 적절한 작업을 자동 실행합니다.

**주요 기능:**
- 주말 확인 (토/일요일은 실행 안 함)
- 시간대별 자동 작업 선택
  - 09:00 이전 → 트레이더 시작
  - 16:00 이후 → 데이터 수집 & 종료
  - 장 중 → 트레이더 상태 확인

**수동 실행:**
```cmd
cd C:\path\to\trading_bot\batch
daily_routine.bat
```

---

## Windows 작업 스케줄러 설정

### 방법 1: XML 파일 직접 가져오기 (추천)

#### Step 1: 경로 수정

`scheduler/` 폴더의 XML 파일들을 메모장으로 열어서 경로를 수정합니다.

**수정 필요한 부분:**
```xml
<Command>C:\path\to\trading_bot\batch\start_trader.bat</Command>
<WorkingDirectory>C:\path\to\trading_bot</WorkingDirectory>
```

**예시:**
```xml
<Command>C:\Users\YourName\Documents\trading_bot\batch\start_trader.bat</Command>
<WorkingDirectory>C:\Users\YourName\Documents\trading_bot</WorkingDirectory>
```

#### Step 2: 작업 스케줄러 열기

1. `Win + R` → `taskschd.msc` 입력 → Enter
2. 또는 검색창에 "작업 스케줄러" 검색

#### Step 3: 작업 가져오기

**아침 트레이더 시작 (08:30):**
1. 작업 스케줄러 → 작업 가져오기
2. `scheduler/morning_trader.xml` 선택
3. 이름: "Trading Bot - Morning Start"
4. 확인

**저녁 데이터 수집 (15:40):**
1. 작업 가져오기
2. `scheduler/evening_collect.xml` 선택
3. 이름: "Trading Bot - Data Collection"
4. 확인

**저녁 자동 종료 (20:00) - 선택사항:**
1. 작업 가져오기
2. `scheduler/evening_shutdown.xml` 선택
3. 이름: "Trading Bot - Auto Shutdown"
4. ⚠️ **기본값: 비활성화 (Enabled=false)**
5. 사용하려면 우클릭 → 사용

---

### 방법 2: 수동으로 작업 만들기

#### 아침 트레이더 시작 설정

**1. 기본 작업 만들기:**
- 이름: `Trading Bot - Morning Start`
- 설명: `평일 08:30에 자동으로 트레이더 실행`

**2. 트리거 설정:**
- 새로 만들기 클릭
- 시작: `매일`
- 시작 날짜: 오늘
- 시작 시간: `08:30:00`
- 고급 설정:
  - ✅ 사용
  - 다음 요일에만 실행: 월, 화, 수, 목, 금
  - ✅ 작업을 실행하기 위해 절전 모드 해제

**3. 작업 설정:**
- 프로그램/스크립트: `C:\path\to\trading_bot\batch\start_trader.bat`
- 시작 위치: `C:\path\to\trading_bot`

**4. 조건 설정:**
- ❌ 배터리 사용 시 시작 안 함 (체크 해제)
- ✅ 작업 실행 위해 절전 모드 해제

**5. 설정:**
- ✅ 요청 시 작업 실행
- ❌ 실행 실패 시 다시 시작 간격 설정 (체크 해제)

---

#### 저녁 데이터 수집 설정

**1. 기본 작업 만들기:**
- 이름: `Trading Bot - Data Collection`
- 설명: `평일 15:40에 자동으로 데이터 수집`

**2. 트리거 설정:**
- 시작: `매일`
- 시작 시간: `15:40:00`
- 다음 요일에만 실행: 월, 화, 수, 목, 금

**3. 작업 설정:**
- 프로그램/스크립트: `C:\path\to\trading_bot\batch\collect_data.bat`
- 시작 위치: `C:\path\to\trading_bot`

**4. 조건 설정:**
- ✅ 네트워크 연결 시에만 시작
- ❌ 배터리 사용 시 시작 안 함 (체크 해제)

---

#### 저녁 자동 종료 설정 (선택사항)

**⚠️ 주의:** 컴퓨터가 매일 자동으로 꺼집니다!

**1. 기본 작업 만들기:**
- 이름: `Trading Bot - Auto Shutdown`
- 설명: `평일 20:00에 자동으로 컴퓨터 종료`

**2. 트리거 설정:**
- 시작: `매일`
- 시작 시간: `20:00:00`
- 다음 요일에만 실행: 월, 화, 수, 목, 금

**3. 작업 설정:**
- 프로그램/스크립트: `C:\path\to\trading_bot\batch\auto_shutdown.bat`
- 시작 위치: `C:\path\to\trading_bot`

**4. 초기 설정:**
- ❌ 작업 사용 (처음엔 비활성화)
- 테스트 후 활성화 권장

---

## BIOS 자동 전원 켜기 설정

컴퓨터가 꺼진 상태에서도 정해진 시간에 자동으로 켜지도록 설정합니다.

### 지원 여부 확인

- ✅ 대부분의 데스크톱 메인보드 지원
- ⚠️ 일부 노트북은 미지원
- ✅ BIOS/UEFI에 "RTC Alarm" 또는 "Power On by RTC" 기능 필요

---

### 설정 방법 (일반적인 BIOS)

#### Step 1: BIOS 진입

1. 컴퓨터 재부팅
2. 부팅 중 `Del`, `F2`, `F10`, 또는 `Esc` 키 연타
   - (메인보드 제조사마다 다름)

#### Step 2: Power Management 메뉴 찾기

BIOS 메뉴 이름은 제조사마다 다르지만, 다음 중 하나를 찾으세요:
- `Power Management Setup`
- `ACPI Configuration`
- `Advanced → Power Management`
- `Power → Automatic Power On`

#### Step 3: RTC Alarm 설정

**찾아야 할 옵션:**
- `RTC Alarm` 또는 `Resume by RTC Alarm`
- `Power On by RTC`
- `Wake Up by RTC`

**설정:**
1. `RTC Alarm` → `Enabled`
2. `Date` → `Every Day` 또는 `0`
3. `Hour` → `08` (오전 8시)
4. `Minute` → `25` (25분)
5. `Second` → `00`

**⏰ 권장 시간: 08:25**
- 작업 스케줄러가 08:30에 실행되므로 5분 여유

#### Step 4: 저장 및 종료

1. `F10` 키 (또는 `Save & Exit`)
2. `Yes` 선택

---

### 제조사별 BIOS 설정 예시

#### ASUS 메인보드

```
Advanced → APM Configuration
  → Restore AC Power Loss: Power On
  → Power On By RTC: Enabled
    → RTC Alarm Date: 0 (Every Day)
    → RTC Alarm Hour: 08
    → RTC Alarm Minute: 25
```

#### MSI 메인보드

```
Settings → Advanced → Power Management Setup
  → Resume By RTC Alarm: Enabled
  → Date: 0
  → Hour: 08
  → Minute: 25
```

#### Gigabyte 메인보드

```
BIOS Features → Power On By RTC
  → Enabled
  → Wake up day: Every Day
  → Wake up hour: 08
  → Wake up minute: 25
```

#### ASRock 메인보드

```
Advanced → ACPI Configuration
  → Restore on AC/Power Loss: Power On
  → RTC Alarm Power On: Enabled
    → Date: 0
    → Hour: 08
    → Minute: 25
```

---

### BIOS 설정 후 테스트

**테스트 방법:**
1. BIOS에서 시간을 현재 시간 +5분으로 설정
2. 컴퓨터 종료
3. 5분 기다리기
4. 자동으로 켜지면 성공! ✅
5. BIOS에서 실제 시간으로 다시 설정

---

## 전체 자동화 일정

### 평일 (월-금) 스케줄

| 시간 | 작업 | 설명 | 방법 |
|------|------|------|------|
| **08:25** | 🌅 컴퓨터 자동 켜기 | BIOS RTC Alarm | BIOS 설정 |
| **08:30** | 🚀 트레이더 시작 | trader.py 자동 실행 | 작업 스케줄러 |
| **09:00** | 📊 장 시작 | 자동 매매 시작 | trader.py |
| **09:00-15:30** | 💹 자동 매매 | 매수/매도 자동 실행 | trader.py |
| **15:30** | 📉 장 마감 | 매매 종료 | trader.py |
| **15:40** | 📥 데이터 수집 | 오늘 데이터 수집 | 작업 스케줄러 |
| **16:10** | 📊 성과 분석 | 오늘 수익 확인 | collect_data.bat |
| **16:20** | 🔍 내일 준비 | 매수 후보 스캔 | collect_data.bat |
| **20:00** | 💤 자동 종료 | 컴퓨터 종료 (선택) | 작업 스케줄러 |

### 주말 (토-일)

- ℹ️ 모든 작업 스킵 (주말 확인 로직)
- 컴퓨터는 자동으로 켜지지 않음

---

## 문제 해결

### Q1: BIOS에서 RTC Alarm을 찾을 수 없어요

**A: 다른 이름으로 찾아보세요**
- `Wake Up Event Setup`
- `Resume by Alarm`
- `PME Event Wake Up`
- `Power On by RTC`

**대안:**
- BIOS 매뉴얼 확인
- 제조사 홈페이지에서 BIOS 업데이트

---

### Q2: 설정 시간에 컴퓨터가 안 켜져요

**체크리스트:**
1. ✅ BIOS 시간이 정확한지 확인
2. ✅ `Restore AC Power Loss` 설정 확인
   - `Power On` 또는 `Last State` 로 설정
3. ✅ 전원 케이블이 연결되어 있는지 확인
4. ✅ 완전 종료했는지 확인 (절전 모드 X)
   - `shutdown /s /t 0` 명령으로 종료

**Windows 빠른 시작 비활성화:**
1. 제어판 → 전원 옵션
2. 전원 단추 작동 설정
3. 현재 사용할 수 없는 설정 변경
4. ❌ 빠른 시작 켜기 (체크 해제)
5. 저장

---

### Q3: 작업 스케줄러가 실행되지 않아요

**체크리스트:**
1. ✅ 경로가 정확한지 확인
   - `C:\path\to\trading_bot\batch\...` 수정
2. ✅ 파일 권한 확인
   - 배치 파일 우클릭 → 속성 → 보안
3. ✅ 로그 파일 확인
   - `automation_log.txt` 내용 확인
4. ✅ 수동 실행 테스트
   - 배치 파일을 직접 더블클릭해서 실행

**작업 스케줄러 로그 확인:**
1. 작업 스케줄러 열기
2. 해당 작업 우클릭 → 속성
3. 기록 탭 → 로그 확인

---

### Q4: 트레이더가 자동으로 시작되지 않아요

**원인:**
- 키움 로그인이 필요해서 멈춰있을 수 있음

**해결:**
1. **자동 로그인 불가능** (키움 정책)
2. 대안:
   - 아침에 수동으로 로그인
   - 또는 작업 스케줄러를 08:30 → 08:00으로 변경
   - 출근 전에 로그인 완료

---

### Q5: 데이터 수집이 너무 오래 걸려요

**정상 소요 시간:**
- 첫 실행: 6-8시간
- 일일 업데이트: 30분-1시간

**최적화 팁:**
1. `library/cf.py`에서 `TR_REQ_TIME_INTERVAL` 조정
   ```python
   TR_REQ_TIME_INTERVAL = 0.3  # 0.2로 줄이면 빠름 (오류 위험)
   ```
2. 주말에 한 번만 전체 수집
3. 평일은 업데이트만

---

### Q6: 종료 시간을 변경하고 싶어요

**방법 1: 배치 파일 수정**
- `auto_shutdown.bat`의 타임아웃 시간 조정

**방법 2: 작업 스케줄러 수정**
1. 작업 스케줄러 열기
2. `Trading Bot - Auto Shutdown` 찾기
3. 우클릭 → 속성
4. 트리거 탭 → 편집
5. 시작 시간 변경 (예: 21:00)
6. 확인

---

## 보안 및 주의사항

### ⚠️ 중요 주의사항

1. **실전 투자 자동화:**
   - 충분한 모의투자 테스트 후 사용
   - 첫 주는 수동 모니터링 권장
   - 예상치 못한 손실 발생 가능

2. **BIOS 설정:**
   - 잘못된 설정은 부팅 불가 초래 가능
   - 기본 설정 백업 권장
   - 제조사 매뉴얼 참조

3. **자동 종료:**
   - 중요 작업 중 종료될 수 있음
   - 처음엔 비활성화 권장
   - 테스트 후 활성화

4. **네트워크:**
   - 안정적인 인터넷 연결 필수
   - 키움 API 접속 필요

5. **정전 대비:**
   - UPS(무정전 전원장치) 권장
   - 갑작스런 종료 대비

---

## 최종 체크리스트

### 초기 설정 (한 번만)

- [ ] 배치 파일 경로 수정 완료
- [ ] 작업 스케줄러 등록 완료
  - [ ] Morning Trader (08:30)
  - [ ] Data Collection (15:40)
  - [ ] Auto Shutdown (20:00) - 선택
- [ ] BIOS RTC Alarm 설정 완료 (08:25)
- [ ] Windows 빠른 시작 비활성화
- [ ] 수동 테스트 완료
  - [ ] start_trader.bat 실행 성공
  - [ ] collect_data.bat 실행 성공
  - [ ] auto_shutdown.bat 실행 성공

### 일일 체크 (처음 1-2주)

- [ ] 아침: 컴퓨터가 자동으로 켜졌는지 확인
- [ ] 아침: 트레이더가 실행되었는지 확인
- [ ] 저녁: 데이터 수집이 완료되었는지 확인
- [ ] 저녁: automation_log.txt 확인

### 주간 체크

- [ ] 로그 파일 확인 (`automation_log.txt`)
- [ ] 성과 확인
- [ ] 오류 발생 여부 확인

---

## 🎉 완성!

모든 설정을 완료하면:

**평일:**
```
08:25 - 💻 컴퓨터 자동 켜짐 (BIOS)
08:30 - 🚀 트레이더 자동 시작
09:00 - 📊 자동 매매 시작
15:30 - 📉 매매 종료
15:40 - 📥 데이터 자동 수집
20:00 - 💤 컴퓨터 자동 종료
```

**당신이 할 일:**
- 출근 전 키움 로그인 (5분)
- 주말에 로그 확인 (10분)
- 끝! ✨

**완전 무인 자동 매매 시스템 완성!** 🎊

---

_마지막 업데이트: 2025-11-20_
