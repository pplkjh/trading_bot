# SQL 데이터베이스 설치 가이드

트레이딩봇 자동매매 시스템에 필요한 데이터베이스를 설정합니다.

---

## 빠른 시작 (1분이면 완료!)

```bash
cd c:\Personal_project\trading_bot\sql

# 전체 데이터베이스 및 테이블 생성
mysql -u root -p < 01_setup_all.sql
```

**끝!** 이제 `python collector_v3.py`를 실행하면 됩니다.

---

## 📋 파일 목록

### 필수 파일

| 파일 | 용도 |
|------|------|
| `01_setup_all.sql` | **전체 설치** - 데이터베이스, 권한, 테이블 모두 생성 (처음 한 번만 실행) |

### 문제 해결 파일 (필요시에만 사용)

| 파일 | 용도 |
|------|------|
| `02_fix_charset.sql` | 한글 깨짐 문제 해결 (utf8mb4 변환) |
| `03_reset_tables.sql` | 테이블 초기화 (문제 발생시 복구용) |

---

## 🗄️ 생성되는 데이터베이스

`01_setup_all.sql` 실행 시 다음 데이터베이스와 테이블이 생성됩니다:

### 1. daily_buy_list - 매수 후보 분석
- `stock_item_all`: 전체 종목 리스트
- `pred_signal`: AI 예측 시그널

### 2. daily_craw - 일봉 데이터
- 종목별로 동적 생성 (collector_v3.py가 자동 생성)

### 3. min_craw - 분봉 데이터
- 종목별로 동적 생성 (collector_v3.py가 자동 생성)

### 4. JackBot1_imi1 - 모의투자
- `setting_data`: 시스템 설정
- `jango_data`: 일별 자산 추적
- `all_item_db`: 전체 매매 기록
- `possessed_item`: 현재 보유 종목
- `realtime_daily_buy_list`: 내일 매수 종목
- `today_profit_list`: 당일 종목별 손익

### 5. JackBot1 - 실전투자
- JackBot1_imi1과 동일한 구조

---

## ✅ 설치 확인

```sql
-- MySQL에 로그인
mysql -u root -p

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
| JackBot1_imi1      |
| JackBot1           |
| min_craw           |
+--------------------+
```

```sql
-- JackBot1_imi1 테이블 확인
USE JackBot1_imi1;
SHOW TABLES;
```

**예상 결과:**
```
+-------------------------+
| Tables_in_JackBot1_imi1 |
+-------------------------+
| all_item_db             |
| jango_data              |
| possessed_item          |
| realtime_daily_buy_list |
| setting_data            |
| today_profit_list       |
+-------------------------+
```

---

## 🆘 문제 해결

### 문제 1: 한글이 깨져서 보여요

```bash
mysql -u root -p < 02_fix_charset.sql
```

### 문제 2: "Unknown column 'today_profit'" 에러

**원인:** `today_profit_list` 테이블이 없거나 구조가 잘못됨

**해결:**
```bash
# 테이블 초기화 후 재생성
mysql -u root -p < 03_reset_tables.sql
mysql -u root -p < 01_setup_all.sql
```

### 문제 3: "Access denied for user 'bot'@'localhost'"

**원인:** 이전 버전에서 'bot' 사용자를 사용했으나, 현재는 'root' 사용자 사용

**해결:** 이미 해결됨! `01_setup_all.sql`은 'root' 사용자로 실행됩니다.

### 문제 4: "Can't create database; database exists"

**원인:** 데이터베이스가 이미 존재

**해결:** 괜찮습니다! `CREATE DATABASE IF NOT EXISTS`를 사용하므로 에러가 발생하지 않습니다. 만약 완전히 새로 시작하고 싶다면:

```sql
-- 주의: 모든 데이터가 삭제됩니다!
DROP DATABASE IF EXISTS daily_craw;
DROP DATABASE IF EXISTS daily_buy_list;
DROP DATABASE IF EXISTS min_craw;
DROP DATABASE IF EXISTS JackBot1_imi1;
DROP DATABASE IF EXISTS JackBot1;

-- 그 다음 01_setup_all.sql 다시 실행
```

---

## 📌 다음 단계

데이터베이스 설치 완료 후:

### 1. 설정 파일 확인
```python
# library/cf.py 파일 확인
# 데이터베이스 사용자가 'root'로 설정되어 있는지 확인
```

### 2. 데이터 수집 시작
```bash
python collector_v3.py
```
- 최초 실행: 6-8시간 소요
- 전체 종목 데이터 수집

### 3. 자동매매 시작
```bash
python trader.py
```
- `1` 입력: 모의투자 시작

---

## 🗂️ 이전 파일들 (old/ 폴더로 이동됨)

다음 파일들은 참고용으로 `old/` 폴더에 보관되어 있습니다:

- `init_databases.sql` → `01_setup_all.sql`에 통합
- `stock_item_all_schema.sql` → `01_setup_all.sql`에 통합
- `jackbot_schema.sql` → `01_setup_all.sql`에 통합
- `fix_charset.sql` → `02_fix_charset.sql`로 업데이트
- `reset_tables.sql` → `03_reset_tables.sql`로 업데이트
- `cleanup_kind_tables.sql` → `03_reset_tables.sql`에 통합
- `pred_signal.sql` → `01_setup_all.sql`에 통합

---

**작성일**: 2025-11-23
**버전**: 2.0 (통합 버전)
