# 트레이딩 봇 데이터베이스 설정 가이드

이 문서는 JackBot 트레이딩 봇의 데이터베이스를 설정하는 방법을 설명합니다.

## 목차
1. [사전 요구사항](#사전-요구사항)
2. [데이터베이스 개요](#데이터베이스-개요)
3. [설치 절차](#설치-절차)
4. [테이블 구조 설명](#테이블-구조-설명)
5. [설정 확인](#설정-확인)
6. [문제 해결](#문제-해결)

---

## 사전 요구사항

- **MySQL 서버**: 5.7 이상 권장
- **문자 인코딩**: UTF-8 (utf8mb4)
- **사용자 권한**: 데이터베이스 생성 및 테이블 생성 권한 필요
- **Python 환경**: Python 3.7 이상 (32비트 또는 64비트)

---

## 데이터베이스 개요

JackBot 트레이딩 봇은 3개의 주요 데이터베이스를 사용합니다:

### 1. **JackBot1_imi1** (메인 봇 데이터베이스)
- **용도**: 봇의 설정, 거래 내역, 잔고 정보 저장
- **테이블 수**: 6개 (고정)
- **주요 테이블**:
  - `setting_data`: 봇 설정 및 상태
  - `jango_data`: 일별 계좌 잔고 통계
  - `all_item_db`: 모든 거래 내역
  - `possessed_item`: 현재 보유 종목
  - `realtime_daily_buy_list`: 실시간 매수 대상 종목
  - `today_profit_list`: 당일 수익 종목

### 2. **daily_buy_list** (일일 매수 리스트 데이터베이스)
- **용도**: 일별 매수 대상 종목 및 예측 신호 저장
- **테이블 수**: 3개 고정 + 날짜별 동적 테이블
- **주요 테이블**:
  - `pred_signal`: AI 예측 신호
  - `stock_insincerity`: 불성실 공시 종목
  - `stock_managing`: 관리 종목
  - `YYYYMMDD`: 날짜별 매수 리스트 (자동 생성)

### 3. **daily_craw** (일봉 데이터 데이터베이스)
- **용도**: 종목별 일봉(OHLCV) 데이터 저장
- **테이블 수**: 종목별 동적 테이블 (수천 개)
- **테이블 형식**: `{종목코드}_{종목명}` (예: 005930_삼성전자)

---

## 설치 절차

### Step 1: MySQL 접속 및 데이터베이스 생성

```bash
# MySQL 접속
mysql -u root -p
```

```sql
-- 데이터베이스 생성
CREATE DATABASE IF NOT EXISTS JackBot1_imi1 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS daily_buy_list CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS daily_craw CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 데이터베이스 확인
SHOW DATABASES;

-- MySQL 접속 종료
EXIT;
```

### Step 2: JackBot1_imi1 스키마 적용

```bash
cd /path/to/trading_bot
mysql -u root -p JackBot1_imi1 < sql/jackbot_schema.sql
```

**실행 결과 예시:**
```
Enter password: ********
status
✓ setting_data 테이블 생성 완료!
status
✓ jango_data 테이블 생성 완료!
status
✓ all_item_db 테이블 생성 완료!
...
```

### Step 3: daily_buy_list 스키마 적용

```bash
# 기본 테이블 생성
mysql -u root -p daily_buy_list < sql/daily_buy_list_schema.sql

# pred_signal 테이블 생성
mysql -u root -p daily_buy_list < sql/pred_signal.sql
```

### Step 4: daily_craw 데이터베이스 준비

```bash
# daily_craw는 고정 테이블이 없으므로 데이터베이스만 생성됨
# 종목별 테이블은 collector 실행 시 자동 생성
```

### Step 5: 테이블 생성 확인

```bash
# 각 데이터베이스의 테이블 확인
mysql -u root -p -e "USE JackBot1_imi1; SHOW TABLES;"
mysql -u root -p -e "USE daily_buy_list; SHOW TABLES;"
mysql -u root -p -e "USE daily_craw; SHOW TABLES;"
```

---

## 테이블 구조 설명

### JackBot1_imi1 데이터베이스

#### 1. setting_data (봇 설정)
```sql
-- 봇의 현재 상태와 설정을 저장
-- 단 1개의 row만 존재 (항상 최신 상태 유지)
```
주요 컬럼:
- `invest_unit`: 현재 투자 단위 금액
- `code_update`: 종목 정보 마지막 업데이트 날짜
- `today_buy_list`: 오늘 매수 리스트 생성 날짜

#### 2. jango_data (잔고 데이터)
```sql
-- 날짜별 계좌 잔고 및 거래 통계
-- 매일 1개의 row가 추가됨
```
주요 컬럼:
- `date`: 날짜 (YYYYMMDD)
- `today_earning_rate`: 당일 수익률
- `total_asset`: 총 자산
- `today_buy_count`: 당일 매수 건수

#### 3. all_item_db (거래 내역)
```sql
-- 모든 매수/매도 거래를 기록
-- 매수 시 1개 row 추가, 매도 시 해당 row 업데이트
```
주요 컬럼:
- `code`: 종목코드 (6자리)
- `buy_date`: 매수 일시 (YYYYMMDDHHMI)
- `sell_date`: 매도 일시
- `rate`: 수익률

#### 4. possessed_item (보유 종목)
```sql
-- 현재 보유 중인 종목 스냅샷
-- 매일 전체 교체(replace)됨
```

#### 5. realtime_daily_buy_list (실시간 매수 리스트)
```sql
-- 오늘 또는 내일 매수할 종목 리스트
-- 매일 갱신됨
```

#### 6. today_profit_list (당일 수익 종목)
```sql
-- 오늘 수익이 발생한 종목 기록
```

### daily_buy_list 데이터베이스

#### 1. pred_signal (AI 예측 신호)
```sql
-- AI 모델의 예측 결과 저장
-- ref_date + code가 primary key
```
주요 컬럼:
- `ref_date`: 기준 날짜
- `code`: 종목코드
- `pred_ret_5`: 5일 예상 수익률
- `pred_ret_15`: 15일 예상 수익률
- `regime`: 시장 regime 분류

#### 2. 날짜별 테이블 (YYYYMMDD)
```sql
-- 해당 날짜의 매수 대상 종목 리스트
-- collector에 의해 자동 생성
```

### daily_craw 데이터베이스

#### 종목별 테이블 ({code}_{name})
```sql
-- 종목별 일봉(OHLCV) 데이터
-- 예: 005930_삼성전자, 000660_SK하이닉스
```
주요 컬럼:
- `date`: 날짜
- `open`, `high`, `low`, `close`: OHLC 가격
- `volume`: 거래량
- `clo5` ~ `clo120`: 이동평균선
- `vol5` ~ `vol120`: 거래량 이동평균

---

## 설정 확인

### 1. library/cf.py 설정 확인

```python
# 데이터베이스 설정
db_id = 'bot'                    # MySQL 사용자명
db_ip = 'localhost'              # MySQL 서버 IP
db_passwd = 'qwer1232'           # MySQL 비밀번호
db_port = '3306'                 # MySQL 포트

# 봇 데이터베이스 이름
imi1_simul_num = 1
imi1_db_name = "JackBot" + str(imi1_simul_num) + "_imi1"  # JackBot1_imi1

# 공용 데이터베이스
real_daily_craw_db_name = "daily_craw"
real_daily_buy_list_db_name = "daily_buy_list"
```

### 2. 데이터베이스 연결 테스트

```python
from sqlalchemy import create_engine

# 연결 문자열
engine = create_engine(
    f"mysql+mysqldb://bot:qwer1232@localhost:3306/JackBot1_imi1",
    encoding='utf-8'
)

# 테스트 쿼리
result = engine.execute("SELECT * FROM setting_data LIMIT 1")
print(result.fetchall())
```

### 3. 초기 데이터 확인

```bash
# setting_data 초기 row 확인
mysql -u root -p JackBot1_imi1 -e "SELECT * FROM setting_data;"

# 결과: 모든 값이 0 또는 '0'으로 초기화된 1개의 row 존재
```

---

## 문제 해결

### 1. "Access denied" 오류

**증상:**
```
ERROR 1045 (28000): Access denied for user 'bot'@'localhost'
```

**해결:**
```sql
-- MySQL 접속
mysql -u root -p

-- 사용자 생성 및 권한 부여
CREATE USER IF NOT EXISTS 'bot'@'localhost' IDENTIFIED BY 'qwer1232';
GRANT ALL PRIVILEGES ON JackBot1_imi1.* TO 'bot'@'localhost';
GRANT ALL PRIVILEGES ON daily_buy_list.* TO 'bot'@'localhost';
GRANT ALL PRIVILEGES ON daily_craw.* TO 'bot'@'localhost';
FLUSH PRIVILEGES;
```

### 2. "Unknown database" 오류

**증상:**
```
ERROR 1049 (42000): Unknown database 'JackBot1_imi1'
```

**해결:**
- Step 1의 데이터베이스 생성 SQL을 다시 실행
- 데이터베이스 이름 철자 확인 (대소문자 구분)

### 3. "Table already exists" 경고

**증상:**
```
Table 'setting_data' already exists
```

**해결:**
- 이는 정상입니다. SQL 파일에서 `CREATE TABLE IF NOT EXISTS`를 사용하므로
- 기존 테이블은 유지되고 새 테이블만 생성됩니다

### 4. UTF-8 인코딩 오류

**증상:**
```
Incorrect string value: '\xED\x95\x9C\xEA\xB5\xAD...'
```

**해결:**
```sql
-- 데이터베이스 문자셋 변경
ALTER DATABASE JackBot1_imi1 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER DATABASE daily_buy_list CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER DATABASE daily_craw CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 기존 테이블 문자셋 변경
ALTER TABLE JackBot1_imi1.setting_data CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- (나머지 테이블도 동일)
```

### 5. collector 실행 시 테이블 미생성

**증상:**
- `collector_v3.py` 실행 후에도 daily_craw에 테이블이 생성되지 않음

**해결:**
- 키움 OpenAPI 로그인 상태 확인
- `library/cf.py`의 API 설정 확인
- `TR_REQ_TIME_INTERVAL` 값 조정 (API 호출 간격)

---

## 다음 단계

데이터베이스 설정이 완료되면:

1. **collector 실행**: 종목 데이터 수집
   ```bash
   python collector_v3.py
   ```

2. **trader 실행**: 자동 매매 시작
   ```bash
   python trader.py
   ```

3. **simulator 테스트**: 백테스팅
   ```bash
   python simulator.py
   ```

---

## 추가 정보

- **스키마 파일 위치**: `sql/` 디렉토리
  - `jackbot_schema.sql`: JackBot1_imi1 스키마
  - `daily_buy_list_schema.sql`: daily_buy_list 스키마
  - `daily_craw_schema.sql`: daily_craw 설명
  - `pred_signal.sql`: pred_signal 테이블

- **백업 방법**:
  ```bash
  # 전체 데이터베이스 백업
  mysqldump -u root -p JackBot1_imi1 > backup_jackbot_$(date +%Y%m%d).sql
  mysqldump -u root -p daily_buy_list > backup_daily_buy_$(date +%Y%m%d).sql

  # 복원
  mysql -u root -p JackBot1_imi1 < backup_jackbot_20231215.sql
  ```

- **성능 최적화**:
  - 인덱스 확인: 주요 검색 컬럼에 인덱스 생성됨
  - 정기 `OPTIMIZE TABLE` 실행 권장
  - 오래된 데이터 아카이빙 고려

---

문의사항이나 문제가 있으시면 GitHub Issues에 등록해주세요.
