# SQL 스키마 파일 가이드 (v1.5.0)

이 폴더에는 자동매매 시스템에 필요한 데이터베이스 스키마 파일들이 있습니다.

**버전 1.5.0 주요 변경사항:**
- ✅ 하이브리드 전략 지원 (RSI, Bollinger Bands, ATR)
- ✅ realtime_daily_buy_list에 전략 컬럼 8개 추가
- ✅ 완전 재설치 지원 (DROP TABLE IF EXISTS)

---

## 📋 파일 목록

| 파일 | 용도 | 실행 순서 | v1.5.0 변경 |
|------|------|----------|------------|
| `init_databases.sql` | 데이터베이스 생성 및 사용자 권한 설정 | ① 가장 먼저 | DROP DB 주석 추가 |
| `stock_item_all_schema.sql` | 종목 리스트 테이블 생성 | ② 두 번째 | DROP TABLE 추가 |
| `jackbot_schema.sql` | 매매 실행 테이블 생성 | ③ 세 번째 | 하이브리드 전략 컬럼 추가 |
| `REBUILD_DATABASE.md` | DB 재구축 가이드 | (참고용) | 신규 |

---

## 🚀 빠른 시작 (처음 설치)

### 방법 1: 전체 자동 설치 (권장)

```bash
# MySQL root로 로그인해서 전체 실행
cd /home/user/trading_bot/sql

# 1. 데이터베이스 및 사용자 생성
mysql -u root -p --default-character-set=utf8mb4 < init_databases.sql

# 2. stock_item_all 테이블 생성
mysql -u bot -p --default-character-set=utf8mb4 daily_buy_list < stock_item_all_schema.sql

# 3. 매매 관련 테이블 생성 (모의투자)
mysql -u bot -p --default-character-set=utf8mb4 jackbot1_imi1 < jackbot_schema.sql

# 완료!
```

비밀번호 입력:
- `root` 비밀번호: MySQL root 비밀번호
- `bot` 비밀번호: `qwer1232` (init_databases.sql에서 설정한 비밀번호)

---

### 방법 2: MySQL Workbench 사용

1. MySQL Workbench 실행
2. root 계정으로 연결
3. 각 파일을 열어서 실행 (순서대로):
   - `init_databases.sql`
   - `stock_item_all_schema.sql`
   - `jackbot_schema.sql`

---

## ✅ 설치 확인

```sql
-- MySQL에 로그인
mysql -u bot -p
-- 비밀번호: qwer1234

-- 데이터베이스 목록 확인
SHOW DATABASES;
```

**예상 결과:**
```
+--------------------+
| Database           |
+--------------------+
| daily_buy_list     |
| daily_craw         |
| jackbot1_imi1      |
| jackbot1           |
| min_craw           |
+--------------------+
```

```sql
-- 테이블 확인
USE daily_buy_list;
SHOW TABLES;
```

**예상 결과:**
```
+---------------------------+
| Tables_in_daily_buy_list  |
+---------------------------+
| pred_signal               |
| stock_item_all            |
+---------------------------+
```

```sql
USE jackbot1_imi1;
SHOW TABLES;
```

**예상 결과:**
```
+-------------------------+
| Tables_in_jackbot1_imi1 |
+-------------------------+
| all_item_db             |
| jango_data              |
| possessed_item          |
| realtime_daily_buy_list |
| setting_data            |
+-------------------------+
```

---

## 📊 데이터베이스 구조 설명

### 1. **daily_craw** - 일봉 데이터 저장소
- 종목별로 테이블 생성 (동적)
- 예: `005930` (삼성전자 테이블)
- collector_v3.py가 자동 생성

### 2. **daily_buy_list** - 매수 후보 분석
- `stock_item_all`: 전체 종목 리스트
- `pred_signal`: AI 예측 시그널
- 날짜별 매수 후보 테이블 (동적 생성)

### 3. **min_craw** - 분봉 데이터 저장소
- 종목별로 테이블 생성 (동적)
- collector_v3.py가 자동 생성

### 4. **jackbot1_imi1** - 모의투자 매매 실행
- `setting_data`: 시스템 설정
- `jango_data`: 일별 자산 추적
- `all_item_db`: 전체 매매 기록
- `possessed_item`: 현재 보유 종목
- `realtime_daily_buy_list`: 내일 매수 종목

### 5. **jackbot1** - 실전 투자 (구조 동일)
- jackbot1_imi1과 동일한 테이블 구조

---

## 🔧 비밀번호 변경하기

기본 비밀번호 `qwer1232`를 변경하려면:

```sql
-- MySQL에 root로 로그인
mysql -u root -p

-- bot 사용자 비밀번호 변경
ALTER USER 'bot'@'localhost' IDENTIFIED BY '새로운비밀번호';
FLUSH PRIVILEGES;
```

**주의:** 비밀번호 변경 후 `library/cf.py` 파일도 수정해야 합니다!

```python
# library/cf.py
db_passwd = '새로운비밀번호'
```

---

## 🔄 완전 재설치 (기존 데이터 삭제)

**⚠️ 경고: 모든 데이터가 삭제됩니다!**

v1.5.0 하이브리드 전략 도입으로 DB 구조가 변경되었습니다.
기존 데이터를 모두 삭제하고 새로 시작하려면:

### Windows 환경:

```bash
# 1. MySQL root로 접속
mysql -u root -p

# 2. 다음 명령어들을 순서대로 실행
```

```sql
-- 기존 데이터베이스 완전 삭제
DROP DATABASE IF EXISTS daily_craw;
DROP DATABASE IF EXISTS daily_buy_list;
DROP DATABASE IF EXISTS min_craw;
DROP DATABASE IF EXISTS jackbot1_imi1;
DROP DATABASE IF EXISTS jackbot1;

-- 기존 사용자 삭제
DROP USER IF EXISTS 'bot'@'localhost';

-- 종료
EXIT;
```

```bash
# 3. SQL 스크립트 순서대로 실행 (배포용)
cd C:/Users/USER/Desktop/Personal\ project/trading_bot/sql

mysql -u root -p --default-character-set=utf8mb4 < init_databases.sql
mysql -u bot -p --default-character-set=utf8mb4 daily_buy_list < stock_item_all_schema.sql
mysql -u bot -p --default-character-set=utf8mb4 jackbot1_imi1 < jackbot_schema.sql

# 비밀번호 입력:
# - root: MySQL root 비밀번호
# - bot: qwer1232 (init_databases.sql에서 설정한 기본값)
```

```bash
# 4. 데이터 수집 시작 (약 23시간)
cd ..
python collector_v3.py
```

**결과:**
- ✅ 완전히 깨끗한 DB
- ✅ 하이브리드 전략 지원 (RSI, Bollinger, ATR)
- ✅ realtime_daily_buy_list에 전략 컬럼 포함
- ✅ 약 700개 날짜 테이블 자동 생성 (collector가 수행)

---

## 🆘 문제 해결

### 오류: "ERROR 1396: Operation CREATE USER failed"

**원인:** 'bot' 사용자가 이미 존재

**해결:**
```sql
-- 기존 사용자 삭제 후 다시 생성
DROP USER IF EXISTS 'bot'@'localhost';
-- 그 다음 init_databases.sql 다시 실행
```

### 오류: "ERROR 1044: Access denied"

**원인:** 권한 부족

**해결:**
```sql
-- root 권한으로 다시 권한 부여
GRANT ALL PRIVILEGES ON *.* TO 'bot'@'localhost';
FLUSH PRIVILEGES;
```

### 오류: "ERROR 1007: Can't create database; database exists"

**원인:** 데이터베이스가 이미 존재

**해결:**
```sql
-- 기존 데이터 삭제하고 새로 시작 (주의: 데이터 손실!)
DROP DATABASE IF EXISTS daily_craw;
DROP DATABASE IF EXISTS daily_buy_list;
DROP DATABASE IF EXISTS jackbot1_imi1;

-- 그 다음 init_databases.sql 다시 실행
```

---

## 📌 다음 단계

스키마 설치 완료 후:

1. **설정 파일 수정**
   ```bash
   # library/cf.py 파일 수정
   nano library/cf.py
   ```
   - `db_passwd`: MySQL 비밀번호
   - `imi1_accout`: 모의투자 계좌번호

2. **데이터 수집 시작**
   ```bash
   python collector_v3.py
   ```
   - 최초 실행: 6-8시간 소요
   - 전체 종목 데이터 수집

3. **트레이더 실행**
   ```bash
   python trader.py
   ```
   - `1` 입력: 모의투자 시작

---

## 📚 참고 문서

- [QUICK_START.md](../QUICK_START.md) - 10분 빠른 시작
- [USER_MANUAL.md](../USER_MANUAL.md) - 완전 사용 설명서
- [ADVANCED_STRATEGY_GUIDE.md](../ADVANCED_STRATEGY_GUIDE.md) - 고급 전략

---

**작성일**: 2024-11-18
**버전**: 1.0
