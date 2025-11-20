# ⚡ 빠른 시작 가이드 (Quick Start)

10분 안에 시작하는 자동 매매 프로그램!

---

## 🎯 목표

모의투자로 자동 매매 시작하기 (약 10-15분 소요)

---

## ✅ 준비물 체크리스트

- [ ] Windows 10/11 (64bit)
- [ ] Python 3.8+ 설치됨
- [ ] MySQL 설치 및 실행 중
- [ ] 키움증권 모의투자 계좌
- [ ] 영웅문 HTS 및 OpenAPI+ 설치됨

---

## 📝 5단계로 시작하기

### Step 1: 패키지 설치 (2분)

```bash
pip install PyQt5 pandas numpy pymysql sqlalchemy
```

### Step 2: 데이터베이스 생성 (3분)

```sql
-- MySQL에 접속 후 실행
CREATE DATABASE daily_craw;
CREATE DATABASE daily_buy_list;
CREATE DATABASE JackBot1_imi1;

-- 사용자 생성
CREATE USER 'bot'@'localhost' IDENTIFIED BY 'qwer1234';
GRANT ALL PRIVILEGES ON *.* TO 'bot'@'localhost';
FLUSH PRIVILEGES;
```

### Step 3: 설정 파일 수정 (2분)

**`library/cf.py` 파일에서 3곳만 수정:**

```python
# 1. MySQL 비밀번호
db_passwd = 'qwer1234'  # 위에서 설정한 비밀번호

# 2. 모의투자 계좌번호
imi1_accout = "8032914911"  # 본인 계좌번호로 변경

# 3. 데이터 시작일 (선택)
start_daily_buy_list = '20240101'  # 2024년 1월부터 수집
```

**계좌번호 확인 방법:**
1. 키움 영웅문 로그인
2. 상단 계좌번호 확인 (10자리)
3. 복사해서 붙여넣기

### Step 4: 기본 데이터 수집 (30분-1시간)

```bash
# 데이터 수집 시작
python collector_v3.py
```

**화면에 이렇게 나오면 성공:**
```
로그인 창 팝업 → 키움 로그인
"데이터 수집 시작..."
"005930(삼성전자) 수집 중..."
```

⏰ **첫 실행은 시간이 걸립니다!**
- 커피 한 잔 하고 오세요 ☕
- 백그라운드 실행: `nohup python collector_v3.py &`

### Step 5: 모의투자 시작 (1분)

```bash
# 트레이더 실행
python trader.py
```

**입력:**
1. `1` 입력 (모의투자 선택)
2. 로그인 창에서 키움 로그인
3. 완료! 🎉

**이제 자동으로:**
- 매일 09:00 - 매수/매도 자동 실행
- 실시간 가격 모니터링
- 손절/익절 자동 처리

---

## 📊 첫날 확인할 것

### 1. 데이터 수집 완료 확인

```sql
-- MySQL에서 실행
USE daily_buy_list;
SELECT COUNT(*) FROM stock_item_all;
-- 결과: 2000개 이상이면 성공
```

### 2. 오늘 매수한 종목 확인

```sql
USE JackBot1_imi1;

-- 보유 종목
SELECT code_name, purchase_price, rate
FROM all_item_db
WHERE sell_date IS NULL;
```

### 3. 계좌 잔고 확인

```sql
-- 현재 자산
SELECT total_asset, d2_deposit
FROM jango_data
ORDER BY date DESC
LIMIT 1;
```

---

## 🎓 다음 단계

### 1일차 완료 후:
- ✅ 모의투자 1주일 운영
- ✅ 매일 성과 확인
- ✅ 문제 없으면 계속 진행

### 1주일 후:
```bash
# 백테스팅으로 전략 검증
python simulator.py
# 입력: 1 (시뮬레이터 번호)
# 입력: reset (새로 시작)
```

### 1개월 후:
```bash
# 고급 전략 사용
python run_advanced_strategy.py --mode scan
```

---

## 🆘 자주 묻는 질문 (FAQ)

### Q1: "계좌번호가 존재하지 않습니다" 오류
**A:** `library/cf.py`의 `imi1_accout` 확인
- 모의투자 계좌는 10자리 (예: 8032914911)
- 3개월마다 갱신 필요

### Q2: 데이터 수집이 너무 느려요
**A:** 정상입니다!
- 키움 API는 1초에 최대 3-4회 호출 제한
- 전체 종목 수집에 6-8시간 소요
- 한 번만 느리고, 다음부터는 빠름 (업데이트만)

### Q3: 매수가 안 됩니다
**A:** 체크사항:
1. 잔고 충분한지 확인 (종목당 50만원 이상)
2. 장 시간인지 확인 (09:00-15:30)
3. 매수 조건 만족하는 종목이 있는지 확인

### Q4: trader.py를 닫으면 매매가 멈추나요?
**A:** 네!
- trader.py는 **반드시 계속 실행** 되어 있어야 함
- 백그라운드 실행: `nohup python trader.py &`

### Q5: 실전 투자는 언제 시작하나요?
**A:** 최소 1개월 모의투자 후!
- 모의투자에서 수익 확인
- 전략 이해 완료
- 리스크 관리 숙지
- 소액으로 시작 (100-500만원)

---

## 🚀 고급 기능 미리보기

### 매수 종목 추천받기

```bash
python run_advanced_strategy.py --mode scan --top 10
```

**출력:**
```
[1] 005930 (삼성전자)
  현재가:         72,000원
  종합 스코어:    85.3/100
  추천 수량:      20주
  손절가:         68,400원
  목표가:         78,300원
```

### 성과 분석

```bash
python run_advanced_strategy.py --mode analyze
```

**출력:**
```
📊 PERFORMANCE REPORT
====================================
🎯 수익률 지표:
  총 수익률:        25.50%
  연평균 수익률:    18.30%

📈 리스크 조정 수익률:
  Sharpe Ratio:     1.35

💼 매매 통계:
  승률:             58.5%
```

---

## 📱 일일 체크리스트

### 매일 해야 할 일 (5분)

**오전 (08:50):**
- [ ] trader.py 실행 중인지 확인
- [ ] 로그 확인 (오류 없는지)

**오후 (15:40):**
- [ ] collector_v3.py 실행 (데이터 수집)
- [ ] 오늘 수익률 확인

**주말:**
- [ ] 주간 성과 리포트 확인
- [ ] 필요 시 파라미터 조정

---

## 🎁 보너스 팁

### Tip 1: 자동 시작 설정

**Windows 시작 프로그램에 등록:**
1. `Win + R` → `shell:startup`
2. trader.py 바로가기 생성
3. 재부팅 시 자동 실행!

### Tip 2: 알림 설정

```python
# 큰 손실/수익 시 알림 (카카오톡, 이메일 등)
# library/simulator_func_mysql.py에서 커스터마이징
```

### Tip 3: 로그 모니터링

```bash
# 실시간 로그 보기
tail -f trading.log
```

---

## 📞 도움이 필요하면

1. **전체 매뉴얼:** `USER_MANUAL.md` 참조
2. **고급 전략:** `ADVANCED_STRATEGY_GUIDE.md` 참조
3. **코드 문의:** GitHub Issues

---

## ✅ 완료 체크리스트

시작 전 확인:
- [ ] 패키지 설치 완료
- [ ] 데이터베이스 생성 완료
- [ ] cf.py 설정 완료
- [ ] 데이터 수집 완료
- [ ] trader.py 실행 성공

**모두 체크되었다면 축하합니다! 🎉**

**이제 자동 매매의 세계로!** 🚀

---

_자세한 내용은 USER_MANUAL.md를 참조하세요_
