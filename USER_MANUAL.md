# 자동 주식 매매 프로그램 완전 매뉴얼

## 📚 목차

1. [시작하기 전에](#1-시작하기-전에)
2. [초기 설정](#2-초기-설정)
3. [데이터 수집](#3-데이터-수집)
4. [백테스팅 (전략 검증)](#4-백테스팅-전략-검증)
5. [모의 투자 (Paper Trading)](#5-모의-투자-paper-trading)
6. [실전 투자](#6-실전-투자)
7. [일일 운영 루틴](#7-일일-운영-루틴)
8. [고급 전략 사용](#8-고급-전략-사용)
9. [문제 해결](#9-문제-해결)

---

## 1. 시작하기 전에

### 1.1 필요한 것들

#### ✅ 하드웨어 요구사항
- **OS**: Windows 10/11 (64bit) - 키움 API가 Windows 전용
- **RAM**: 최소 8GB (16GB 권장)
- **저장공간**: 최소 50GB (데이터 누적 고려)

#### ✅ 소프트웨어 설치
```bash
# Python 3.8 이상 (64bit)
python --version

# MySQL 설치 및 실행 확인
mysql --version
```

#### ✅ 키움증권 계정
- 키움증권 계좌 개설
- 모의투자 신청 (https://www.kiwoom.com/)
- 영웅문 HTS 설치
- OpenAPI+ 모듈 설치

#### ✅ Python 패키지 설치
```bash
pip install PyQt5
pip install pandas
pip install numpy
pip install pymysql
pip install sqlalchemy
pip install selenium
pip install tensorflow  # AI 모델 사용 시
```

---

## 2. 초기 설정

### 2.1 데이터베이스 설정

#### Step 1: MySQL 데이터베이스 생성

```sql
-- MySQL에 접속 후 실행
CREATE DATABASE daily_craw;
CREATE DATABASE daily_buy_list;
CREATE DATABASE min_craw;
CREATE DATABASE JackBot1_imi1;

-- 사용자 생성 (선택사항)
CREATE USER 'bot'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON *.* TO 'bot'@'localhost';
FLUSH PRIVILEGES;
```

#### Step 2: 데이터베이스 스키마 생성

```bash
# sql 폴더의 스키마 파일들 실행
cd sql
mysql -u bot -p daily_buy_list < daily_buy_list_schema.sql
mysql -u bot -p JackBot1_imi1 < jango_data.sql
```

### 2.2 설정 파일 수정

**`library/cf.py` 파일 수정:**

```python
# 1. MySQL 설정
db_id = 'bot'                    # MySQL 사용자명
db_passwd = 'your_password'      # MySQL 비밀번호
db_ip = 'localhost'
db_port = '3306'

# 2. 키움 모의투자 계좌번호
imi1_accout = "8032914911"  # 본인의 모의투자 계좌번호 (10자리)

# 3. 실전 계좌번호 (나중에 설정)
real_account = ""  # 일단 비워둠

# 4. DART API 키 (기업 공시 정보용 - 선택사항)
dart_api_key = 'your_dart_api_key'  # https://opendart.fss.or.kr/ 에서 발급
```

**⚠️ 중요:**
- 모의투자 계좌번호는 키움 영웅문 로그인 후 확인 가능
- 모의투자 계좌는 3개월마다 갱신 필요
- 실전 계좌는 충분한 테스트 후에만 설정!

### 2.3 키움 OpenAPI 로그인 테스트

```bash
# 간단한 로그인 테스트
python -c "
from library.open_api import *
kiwoom = Kiwoom()
print('로그인 성공!')
"
```

**로그인 창이 뜨면 성공!**

---

## 3. 데이터 수집

### 3.1 첫 데이터 수집 (초기 셋업)

데이터 수집은 **시장 마감 후 (오후 3:30 이후)** 실행하는 것이 좋습니다.

#### Step 1: 종목 리스트 수집

```bash
# collector_v3.py 실행
python collector_v3.py
```

**이 프로그램이 하는 일:**
1. 전체 KOSPI, KOSDAQ, KONEX 종목 리스트 수집
2. 각 종목별 일봉 데이터 수집 (과거 ~ 현재)
3. 각 종목별 분봉 데이터 수집 (최근 1년)
4. 기술적 지표 계산 (이동평균선 등)
5. `daily_buy_list` 데이터베이스에 집계

**⏱️ 소요시간:** 최초 실행 시 약 6-8시간 (전체 종목 수집)

**주의사항:**
- API 호출 제한이 있어 천천히 진행됩니다
- 중간에 중단되면 다시 실행하면 이어서 진행됩니다
- 백그라운드에서 실행하려면: `nohup python collector_v3.py &`

#### Step 2: 데이터 수집 확인

```sql
-- MySQL에서 확인
USE daily_buy_list;

-- 종목 수 확인
SELECT COUNT(*) FROM stock_item_all;

-- 특정 종목 데이터 확인 (삼성전자)
SELECT * FROM `005930` ORDER BY ref_date DESC LIMIT 10;

-- 집계 데이터 확인
SELECT * FROM realtime_daily_buy_list LIMIT 10;
```

### 3.2 일일 데이터 수집 (자동화)

#### Windows 작업 스케줄러 등록

**방법 1: 수동 등록**
1. Windows 작업 스케줄러 열기
2. "기본 작업 만들기" 클릭
3. 이름: "주식 데이터 수집"
4. 트리거: 매일, 오후 3:40
5. 작업: `python C:\path\to\trading_bot\collector_v3.py`

**방법 2: XML 파일 사용**
```bash
# scheduler 폴더에 있는 XML 파일 import
# 작업 스케줄러 > 작업 가져오기 > XML 선택
```

---

## 4. 백테스팅 (전략 검증)

### 4.1 기본 백테스팅

실전 투자 전에 **반드시** 전략을 백테스팅으로 검증해야 합니다!

#### Step 1: 시뮬레이터 설정

**`library/simulator_func_mysql.py` 파일 수정:**

```python
# Line 116-153 부근
simul_start_date = "20230101"  # 백테스트 시작일
simul_end_date = "20241115"    # 백테스트 종료일 (오늘)
start_invest_price = 10000000  # 초기 자본금 (1000만원)

# 매매 전략 설정
invest_unit = 500000           # 종목당 투자금액
sell_point = 5                 # 익절 기준 (5%)
losscut = -2                   # 손절 기준 (-2%)
```

#### Step 2: 백테스트 실행

```bash
# 시뮬레이터 실행
python simulator.py
```

**프로그램 실행 시 선택:**
1. 시뮬레이터 번호 입력: `1` (처음 실행)
2. reset/continue 선택: `reset` (새로 시작)

**⏱️ 소요시간:** 2년치 백테스트 기준 약 30분-1시간

#### Step 3: 결과 확인

```sql
-- 성과 확인
USE simulator1;

-- 일일 수익률 확인
SELECT date, total_asset, sum_valuation_profit, today_earning_rate
FROM jango_data
ORDER BY date DESC
LIMIT 30;

-- 전체 매매 내역
SELECT code_name, buy_date, sell_date,
       purchase_price, present_price, sell_rate
FROM all_item_db
WHERE sell_date IS NOT NULL
ORDER BY sell_date DESC;

-- 승률 계산
SELECT
    COUNT(*) as total_trades,
    SUM(CASE WHEN sell_rate > 0 THEN 1 ELSE 0 END) as winning_trades,
    SUM(CASE WHEN sell_rate > 0 THEN 1 ELSE 0 END) / COUNT(*) * 100 as win_rate,
    AVG(sell_rate) as avg_return
FROM all_item_db
WHERE sell_date IS NOT NULL;
```

### 4.2 고급 전략 백테스팅

새로 추가된 고급 전략 성과 확인:

```bash
# 고급 전략으로 매수 후보 스캔 (과거 데이터로 테스트)
python run_advanced_strategy.py --mode scan --portfolio 10000000 --top 20

# 결과가 CSV로 저장됨
# buy_list_YYYYMMDD_HHMMSS.csv
```

### 4.3 성과 분석

```bash
# 상세 성과 분석
python run_advanced_strategy.py --mode analyze --db simulator1
```

**출력 지표:**
- 총 수익률, 연평균 수익률 (CAGR)
- Sharpe Ratio (위험 대비 수익)
- Maximum Drawdown (최대 낙폭)
- 승률, Profit Factor

**좋은 전략의 기준:**
- ✅ Sharpe Ratio > 1.0
- ✅ 승률 > 50%
- ✅ Profit Factor > 1.5
- ✅ Maximum Drawdown < 20%

---

## 5. 모의 투자 (Paper Trading)

백테스팅 결과가 만족스러우면 모의투자로 실시간 테스트!

### 5.1 모의투자 시작

#### Step 1: 설정 확인

```python
# library/cf.py 확인
imi1_accout = "8032914911"  # 본인의 모의투자 계좌번호
imi1_simul_num = 1          # 봇 번호 (여러 전략 테스트 시 2, 3... 증가)
```

#### Step 2: 트레이더 실행

```bash
# trader.py 실행
python trader.py
```

**프로그램 실행 시 입력:**
1. `1` 입력 (모의투자)
2. 로그인 창에서 키움 로그인

**프로그램이 자동으로:**
1. 장 시작 전 (09:00): 매수 후보 목록 생성
2. 장 시작 (09:00): 매도 주문 실행 (손절/익절 조건 확인)
3. 장 중 (09:00-15:30): 매수 주문 실행, 실시간 모니터링
4. 장 마감 후: 일일 결과 저장

### 5.2 모의투자 모니터링

#### 실시간 확인

```sql
-- 현재 보유 종목
SELECT code_name, purchase_price, present_price, rate, holding_amount
FROM JackBot1_imi1.all_item_db
WHERE sell_date IS NULL;

-- 오늘 매매 내역
SELECT code_name, purchase_price, present_price, sell_rate, buy_date, sell_date
FROM JackBot1_imi1.all_item_db
WHERE DATE(buy_date) = CURDATE() OR DATE(sell_date) = CURDATE();

-- 일일 성과
SELECT date, total_asset, sum_valuation_profit, today_earning_rate
FROM JackBot1_imi1.jango_data
ORDER BY date DESC
LIMIT 10;
```

#### trader.py 콘솔 로그

프로그램 실행 중 콘솔에서 실시간 로그 확인:
```
[09:00:05] 매도 체크 시작...
[09:00:10] 삼성전자(005930) 익절 매도 (+5.2%)
[09:00:30] 매수 체크 시작...
[09:01:00] SK하이닉스(000660) 매수 체결 (50,000원 x 20주)
```

### 5.3 모의투자 기간

**권장 기간:** 최소 1개월 이상
- 다양한 시장 상황 경험
- 전략의 실전 작동 확인
- 버그 및 문제점 발견

---

## 6. 실전 투자

⚠️ **경고:** 모의투자에서 충분히 검증한 후에만 실전 투자를 시작하세요!

### 6.1 실전 계좌 설정

```python
# library/cf.py 수정
real_account = "1234567890"  # 본인의 실제 계좌번호 (10자리)
real_simul_num = 1
```

### 6.2 실전 투자 시작

```bash
python trader.py
```

**프로그램 실행 시:**
1. `2` 입력 (실전투자) ⚠️
2. 키움 로그인 (실전 계좌)
3. 초기 자본금 확인

**첫 실전 투자 팁:**
- 💡 소액으로 시작 (100-500만원)
- 💡 처음 1-2주는 매일 모니터링
- 💡 예상치 못한 상황 대비 수동 개입 준비
- 💡 손절 기준 엄수!

---

## 7. 일일 운영 루틴

### 7.1 평일 (거래일) 루틴

#### 🌅 장 시작 전 (08:30 - 09:00)

```bash
# 1. 데이터베이스 연결 확인
mysql -u bot -p -e "SELECT 1"

# 2. 고급 전략으로 매수 후보 미리 확인 (선택)
python run_advanced_strategy.py --mode scan --top 20
```

#### 📈 장 중 (09:00 - 15:30)

```bash
# trader.py가 자동으로 실행되어 있어야 함
# 콘솔 로그 모니터링
tail -f trading.log  # 로그 파일이 있다면
```

**자동 실행 내용:**
- 09:00: 손절/익절 조건 종목 매도
- 09:00-09:30: 매수 후보 종목 매수
- 실시간: 가격 모니터링, 트레일링 스톱 체크

#### 🌆 장 마감 후 (15:30 - 18:00)

```bash
# 1. 데이터 수집 (자동 실행 설정 권장)
python collector_v3.py

# 2. 오늘 성과 확인
python -c "
import pymysql
from library.cf import *
con = pymysql.connect(user=db_id, passwd=db_passwd, host=db_ip, db='JackBot1_imi1')
cursor = con.cursor()
cursor.execute('SELECT * FROM jango_data ORDER BY date DESC LIMIT 1')
print(cursor.fetchone())
con.close()
"

# 3. 내일 매수 후보 미리 확인
python run_advanced_strategy.py --mode scan --top 20
```

### 7.2 주말 루틴

```bash
# 1. 주간 성과 분석
python run_advanced_strategy.py --mode analyze

# 2. 전략 파라미터 재검토
# - 승률이 낮으면 진입 조건 강화
# - 손익비가 낮으면 손절/익절 기준 조정

# 3. 백테스팅 재실행 (파라미터 변경 시)
python simulator.py
```

### 7.3 월간 루틴

```sql
-- 월간 성과 리포트
SELECT
    DATE_FORMAT(date, '%Y-%m') as month,
    MIN(total_asset) as min_asset,
    MAX(total_asset) as max_asset,
    (MAX(total_asset) - MIN(total_asset)) / MIN(total_asset) * 100 as monthly_return
FROM jango_data
GROUP BY DATE_FORMAT(date, '%Y-%m')
ORDER BY month DESC
LIMIT 6;
```

---

## 8. 고급 전략 사용

### 8.1 매수 후보 스캔

```bash
# 기본 스캔 (1000만원 포트폴리오, Top 20)
python run_advanced_strategy.py --mode scan

# 커스터마이징
python run_advanced_strategy.py --mode scan --portfolio 50000000 --top 10
```

**출력 정보:**
- 종합 스코어 (0-100)
- 전략 타입 (모멘텀/평균회귀/하이브리드)
- 추천 수량 및 투자금액
- 손절가 / 목표가
- 리스크 스코어

### 8.2 Python에서 직접 사용

**매수 종목 선정:**

```python
from library.advanced_strategy_system import create_optimized_buy_list

# 매수 리스트 생성
buy_list = create_optimized_buy_list(
    portfolio_value=10000000,
    risk_profile='aggressive',  # 'conservative', 'moderate', 'aggressive'
    top_n=20
)

# 결과 출력
for idx, row in buy_list.iterrows():
    print(f"{row['code']}: {row['composite_score']:.1f}점 - {row['strategy_type']}")
```

**청산 종목 확인:**

```python
from library.advanced_strategy_system import create_optimized_sell_list
from datetime import datetime

# 현재 보유 포지션
positions = [
    {
        'code': '005930',
        'entry_price': 70000,
        'entry_date': datetime(2024, 11, 1),
        'shares': 20,
        'highest_price': 72000
    }
]

# 청산 시그널 생성
sell_list = create_optimized_sell_list(positions)

for signal in sell_list:
    if signal['decision']['should_exit']:
        print(f"[청산] {signal['code']}: {signal['decision']['reason']}")
```

### 8.3 전략 파라미터 조정

```python
from library.advanced_strategy_system import AdvancedStrategySystem

# 커스텀 설정
custom_config = {
    'min_factor_score': 75.0,       # 진입 기준 강화
    'max_positions': 8,              # 포지션 수 제한
    'max_position_pct': 0.20,        # 큰 포지션
    'atr_stop_multiplier': 1.5,      # 타이트한 손절
    'trailing_stop_activation': 0.03, # 빠른 트레일링
}

system = AdvancedStrategySystem(
    portfolio_value=10000000,
    risk_profile='aggressive',
    strategy_config=custom_config
)

buy_list = system.generate_buy_signals(top_n=10)
```

---

## 9. 문제 해결

### 9.1 데이터 수집 오류

**증상:** collector_v3.py 실행 시 오류

```bash
# 해결 1: API 연결 확인
python -c "from library.open_api import *; Kiwoom()"

# 해결 2: 데이터베이스 연결 확인
mysql -u bot -p

# 해결 3: 부분 수집 재시도
# collector_v3.py는 이어서 수집 가능 (중단된 곳부터 재개)
```

### 9.2 trader.py 오류

**증상:** "계좌번호가 존재하지 않습니다"

```python
# library/cf.py에서 계좌번호 확인
# 모의투자 계좌는 3개월마다 갱신 필요!

# 영웅문 HTS에서 계좌번호 확인:
# 로그인 > 계좌번호 복사 > cf.py 업데이트
```

**증상:** 매수/매도가 실행되지 않음

```python
# 1. 잔고 확인
# 현금이 부족하면 매수 불가

# 2. 조건 확인
# 매수: 스코어가 기준(70점) 이상인지
# 매도: 손절(-2%) 또는 익절(+5%) 도달했는지

# 3. 로그 확인
# trader.py 콘솔 출력에서 상세 로그 확인
```

### 9.3 성과가 기대에 미치지 못함

**체크리스트:**

```bash
# 1. 백테스팅 결과와 비교
python run_advanced_strategy.py --mode analyze

# 2. 시장 환경 확인
# 약세장에서는 모든 전략의 성과 저하

# 3. 파라미터 재조정
# simulator_func_mysql.py의 sell_point, losscut 조정

# 4. 진입 조건 강화
# min_factor_score를 70 → 75로 증가
```

### 9.4 데이터베이스 용량 문제

```sql
-- 오래된 분봉 데이터 삭제 (1년 이상 된 것)
USE min_craw;
-- 각 테이블에서 오래된 데이터 삭제

-- 백업 후 정리
mysqldump -u bot -p daily_craw > backup_daily_craw.sql
```

---

## 📋 빠른 참조 (Cheat Sheet)

### 필수 명령어

```bash
# 데이터 수집
python collector_v3.py

# 백테스팅
python simulator.py

# 모의투자
python trader.py
# 입력: 1

# 실전투자 ⚠️
python trader.py
# 입력: 2

# 고급 전략 스캔
python run_advanced_strategy.py --mode scan

# 성과 분석
python run_advanced_strategy.py --mode analyze
```

### 주요 설정 파일

| 파일 | 용도 | 주요 설정 |
|------|------|----------|
| `library/cf.py` | 전역 설정 | DB 정보, 계좌번호, API 키 |
| `library/simulator_func_mysql.py` | 백테스팅 | 시작일, 종료일, 초기자본 |
| `library/advanced_strategy_system.py` | 고급 전략 | 리스크 프로필, 파라미터 |

### 중요 데이터베이스

| DB 이름 | 용도 |
|---------|------|
| `daily_craw` | 일봉 원본 데이터 |
| `daily_buy_list` | 집계 데이터, 매수 후보 |
| `JackBot1_imi1` | 모의투자 매매 내역 |
| `simulator1` | 백테스팅 결과 |

---

## 🎓 학습 순서 추천

### 초보자 (1-2주)
1. ✅ 초기 설정 완료
2. ✅ 데이터 수집 1회 성공
3. ✅ 백테스팅 1회 실행 및 결과 확인
4. ✅ SQL로 결과 조회 연습

### 중급자 (2-4주)
1. ✅ 모의투자 시작
2. ✅ 일일 루틴 익히기
3. ✅ 고급 전략 사용해보기
4. ✅ 파라미터 조정 실험

### 고급자 (1-2개월)
1. ✅ 실전 투자 (소액)
2. ✅ 전략 커스터마이징
3. ✅ 성과 최적화
4. ✅ 리스크 관리 고도화

---

## 📞 지원 및 문의

- **문제 발생 시:** 로그 파일 확인 (`trading.log`)
- **버그 리포트:** GitHub Issues
- **개선 제안:** Pull Request 환영

---

## ⚠️ 면책 조항

- 이 프로그램은 교육 및 연구 목적입니다
- 투자 손실에 대한 책임은 사용자에게 있습니다
- 충분한 테스트 없이 실전 투자 금지
- 과거 수익률이 미래를 보장하지 않습니다

---

**행운을 빕니다! 📈🚀**

_마지막 업데이트: 2024-11-18_
