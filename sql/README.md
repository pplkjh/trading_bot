# SQL 스키마 파일

이 디렉토리에는 JackBot 트레이딩 봇의 데이터베이스 스키마 파일들이 포함되어 있습니다.

## 파일 목록

| 파일명 | 설명 | 데이터베이스 |
|--------|------|--------------|
| `jackbot_schema.sql` | 메인 봇 데이터베이스 스키마 | JackBot1_imi1 |
| `daily_buy_list_schema.sql` | 일일 매수 리스트 데이터베이스 스키마 | daily_buy_list |
| `daily_craw_schema.sql` | 일봉 크롤링 데이터베이스 설명 | daily_craw |
| `pred_signal.sql` | AI 예측 신호 테이블 | daily_buy_list |
| `DATABASE_SETUP.md` | **데이터베이스 설정 전체 가이드** | 전체 |

## 빠른 시작

### 1. 데이터베이스 생성

```bash
mysql -u root -p << EOF
CREATE DATABASE IF NOT EXISTS JackBot1_imi1 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS daily_buy_list CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS daily_craw CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
EOF
```

### 2. 스키마 적용 (순서대로 실행)

```bash
cd /path/to/trading_bot

# 1. JackBot1_imi1 메인 데이터베이스
mysql -u root -p JackBot1_imi1 < sql/jackbot_schema.sql

# 2. daily_buy_list 데이터베이스
mysql -u root -p daily_buy_list < sql/daily_buy_list_schema.sql
mysql -u root -p daily_buy_list < sql/pred_signal.sql

# 3. daily_craw는 collector 실행 시 자동 생성
```

### 3. 설정 확인

```bash
# 각 데이터베이스의 테이블 확인
mysql -u root -p JackBot1_imi1 -e "SHOW TABLES;"
mysql -u root -p daily_buy_list -e "SHOW TABLES;"
```

## 파일별 상세 설명

### jackbot_schema.sql
**대상 데이터베이스**: `JackBot1_imi1`

생성되는 테이블:
- `setting_data` - 봇 설정 및 상태 정보
- `jango_data` - 일별 계좌 잔고 및 거래 통계
- `all_item_db` - 모든 매수/매도 거래 내역
- `possessed_item` - 현재 보유 종목 정보
- `realtime_daily_buy_list` - 실시간 일일 매수 대상 종목 리스트
- `today_profit_list` - 오늘 수익 종목 리스트

### daily_buy_list_schema.sql
**대상 데이터베이스**: `daily_buy_list`

생성되는 테이블:
- `stock_insincerity` - 불성실 공시 종목 정보
- `stock_managing` - 관리 종목 정보
- 날짜별 동적 테이블 (YYYYMMDD) - collector가 자동 생성

### pred_signal.sql
**대상 데이터베이스**: `daily_buy_list`

생성되는 테이블:
- `pred_signal` - AI 예측 신호 데이터

### daily_craw_schema.sql
**대상 데이터베이스**: `daily_craw`

이 파일은 설명 문서이며, 실제 테이블은 collector 실행 시 자동으로 생성됩니다.
- 종목별 테이블: `{종목코드}_{종목명}` (예: 005930_삼성전자)

## 중요 사항

1. **실행 순서**: 반드시 위의 순서대로 스키마를 적용하세요.

2. **문자 인코딩**: 모든 데이터베이스는 `utf8mb4`를 사용합니다.
   - 한글 종목명이 포함되어 있어 반드시 utf8mb4 필요

3. **IF NOT EXISTS**: 모든 CREATE TABLE 문에 IF NOT EXISTS가 포함되어 있어
   - 여러 번 실행해도 안전합니다
   - 기존 데이터는 유지됩니다

4. **초기 데이터**: `jackbot_schema.sql`은 setting_data에 초기 row를 자동 삽입합니다.

## 문제 해결

### 권한 오류
```sql
-- MySQL root로 접속하여 실행
CREATE USER IF NOT EXISTS 'bot'@'localhost' IDENTIFIED BY 'qwer1232';
GRANT ALL PRIVILEGES ON JackBot1_imi1.* TO 'bot'@'localhost';
GRANT ALL PRIVILEGES ON daily_buy_list.* TO 'bot'@'localhost';
GRANT ALL PRIVILEGES ON daily_craw.* TO 'bot'@'localhost';
FLUSH PRIVILEGES;
```

### 스키마 재적용
```bash
# 전체 재설정 (주의: 데이터 삭제됨)
mysql -u root -p << EOF
DROP DATABASE IF EXISTS JackBot1_imi1;
DROP DATABASE IF EXISTS daily_buy_list;
DROP DATABASE IF EXISTS daily_craw;
EOF

# 그 다음 위의 "빠른 시작" 절차 다시 실행
```

## 추가 도움말

자세한 설정 방법과 문제 해결은 **`DATABASE_SETUP.md`** 파일을 참조하세요.

이 파일에는 다음 내용이 포함되어 있습니다:
- 사전 요구사항
- 상세 설치 절차
- 테이블 구조 설명
- 설정 확인 방법
- 문제 해결 가이드
- 백업 및 복원 방법
