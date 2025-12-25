# 📋 데이터베이스 완전 재구축 가이드

하이브리드 전략 도입 (v1.5.0)으로 인한 DB 구조 변경
- 기술적 지표 5개 추가 (RSI, Bollinger Bands, ATR)
- realtime_daily_buy_list에 전략 컬럼 추가

---

## ⚠️ 주의사항

- **모든 날짜 테이블이 삭제됩니다** (약 700개)
- **collector 재실행 시간: 약 23시간**
- **realtime_daily_buy_list 테이블 재생성**

---

## 🚀 재구축 절차 (Windows)

### 1단계: 기존 날짜 테이블 삭제

```bash
python reset_daily_buy_list_db.py
```

입력: `yes`

결과:
- daily_buy_list의 모든 날짜 테이블 (YYYYMMDD) 삭제
- stock_item_all, pred_signal 등은 유지

---

### 2단계: realtime_daily_buy_list 테이블 재생성

#### 방법 A: SQL 스크립트 사용 (권장)

```bash
# MySQL 접속 (한글 깨짐 방지)
mysql -u bot -p --default-character-set=utf8mb4 jackbot1_imi1

# 비밀번호 입력: qwer1232 (또는 설정한 비밀번호)
```

```sql
-- 기존 테이블 삭제
DROP TABLE IF EXISTS realtime_daily_buy_list;

-- 새 구조로 재생성
SOURCE C:/Users/USER/Desktop/Personal project/trading_bot/sql/jackbot_schema.sql;
```

#### 방법 B: Python으로 재생성

```bash
python -c "
import pymysql
from library.cf import *

con = pymysql.connect(user=db_id, passwd=db_passwd, host=db_ip, db=imi1_db_name, charset='utf8', port=int(db_port))
cursor = con.cursor()

# 기존 테이블 삭제
cursor.execute('DROP TABLE IF EXISTS realtime_daily_buy_list')
print('✅ 기존 realtime_daily_buy_list 삭제 완료')

# 새 테이블 생성
with open('sql/jackbot_schema.sql', 'r', encoding='utf-8') as f:
    sql = f.read()
    # realtime_daily_buy_list 부분만 추출 (간단히 전체 실행)
    for statement in sql.split(';'):
        if 'realtime_daily_buy_list' in statement:
            cursor.execute(statement)

con.commit()
con.close()
print('✅ 새 realtime_daily_buy_list 생성 완료')
"
```

---

### 3단계: Collector 실행 (약 23시간)

```bash
python collector_v3.py
```

진행 상황:
- 날짜별 테이블 생성 (약 700개)
- 각 날짜마다 2789개 종목 처리
- 종목별로 120일 데이터 읽어서 RSI, Bollinger, ATR 계산

예상 시간:
- 날짜당 약 2분
- 총 700개 날짜 × 2분 = 약 23시간

---

### 4단계: 검증

```bash
# 1. 테이블 개수 확인
python -c "
import pymysql
from library.cf import *

con = pymysql.connect(user=db_id, passwd=db_passwd, host=db_ip, db='daily_buy_list', charset='utf8', port=int(db_port))
cursor = con.cursor()

cursor.execute(\"\"\"
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = 'daily_buy_list'
    AND TABLE_NAME REGEXP '^[0-9]{8}$'
\"\"\")

count = cursor.fetchone()[0]
print(f'📊 날짜 테이블 개수: {count}개')

cursor.execute(\"\"\"
    SELECT TABLE_NAME
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = 'daily_buy_list'
    AND TABLE_NAME REGEXP '^[0-9]{8}$'
    ORDER BY TABLE_NAME DESC
    LIMIT 1
\"\"\")

latest = cursor.fetchone()[0]
print(f'📅 최신 날짜: {latest}')

cursor.execute(f'SELECT COUNT(*) FROM `{latest}`')
stock_count = cursor.fetchone()[0]
print(f'📊 최신 날짜 종목 수: {stock_count}개')

con.close()
"

# 2. 기술적 지표 확인
python check_columns.py

# 3. 매수 후보 확인
python check_buy_list.py
```

예상 결과:
- 날짜 테이블: 약 700개
- 최신 날짜 종목 수: 2789개 (이전 19개 → 수정 후)
- 기술적 지표 컬럼: 5/5개 ✅
- 매수 후보: date_based + hybrid 전략 모두 표시

---

## 🔧 트러블슈팅

### 문제 1: collector가 중간에 멈춤

**원인**: 네트워크 오류, DB 연결 끊김

**해결**:
```bash
# collector는 기존 테이블은 스킵하므로 그냥 재실행
python collector_v3.py
```

---

### 문제 2: realtime_daily_buy_list에 전략 컬럼 없음

**원인**: 테이블이 재생성되지 않음

**해결**:
```bash
python -c "
import pymysql
from library.cf import *

con = pymysql.connect(user=db_id, passwd=db_passwd, host=db_ip, db=imi1_db_name, charset='utf8', port=int(db_port))
cursor = con.cursor()

# 컬럼 추가
cursor.execute('ALTER TABLE realtime_daily_buy_list ADD COLUMN strategy_type VARCHAR(50) DEFAULT \"basic\"')
cursor.execute('ALTER TABLE realtime_daily_buy_list ADD COLUMN composite_score DECIMAL(10,2) DEFAULT 0')
cursor.execute('ALTER TABLE realtime_daily_buy_list ADD COLUMN volume_ratio DECIMAL(10,2) DEFAULT 1.0')
cursor.execute('ALTER TABLE realtime_daily_buy_list ADD COLUMN rsi14 DECIMAL(10,2) DEFAULT 50.0')
cursor.execute('ALTER TABLE realtime_daily_buy_list ADD COLUMN bb_upper INT DEFAULT 0')
cursor.execute('ALTER TABLE realtime_daily_buy_list ADD COLUMN bb_middle INT DEFAULT 0')
cursor.execute('ALTER TABLE realtime_daily_buy_list ADD COLUMN bb_lower INT DEFAULT 0')
cursor.execute('ALTER TABLE realtime_daily_buy_list ADD COLUMN atr14 INT DEFAULT 0')

con.commit()
con.close()
print('✅ 컬럼 추가 완료')
"
```

---

### 문제 3: 종목 수가 여전히 19개

**원인**: daily_buy_list.py 수정 전 버전 실행

**해결**:
```bash
# 1. daily_buy_list.py 버전 확인
python -c "from library.daily_buy_list import *; dbl = daily_buy_list()"

# 출력: "daily_buy_list Version: #version 1.5.0 - 하이브리드 전략 지원 (RSI, Bollinger, ATR)"

# 2. 버전이 1.5.0이 아니면 git에서 최신 버전 가져오기
git pull origin main

# 3. 해당 날짜 테이블 삭제 후 재생성
python reset_since_date.py  # 20251216부터 삭제
python collector_v3.py
```

---

## 📊 재구축 전후 비교

| 항목 | 이전 | 이후 |
|------|------|------|
| **daily_buy_list 컬럼** | 44개 | 48개 (+5) |
| **기술적 지표** | 없음 | RSI, BB, ATR |
| **종목 처리** | 19개 (버그) | 2789개 ✅ |
| **전략 타입** | date_based만 | date_based + hybrid |
| **realtime_daily_buy_list 컬럼** | 기본 | +8개 (전략 관련) |

---

## ✅ 완료 체크리스트

- [ ] `reset_daily_buy_list_db.py` 실행 (날짜 테이블 삭제)
- [ ] `realtime_daily_buy_list` 테이블 재생성
- [ ] `collector_v3.py` 실행 (약 23시간)
- [ ] `check_columns.py` 검증 (5/5개 컬럼)
- [ ] `check_buy_list.py` 검증 (hybrid 전략 확인)
- [ ] 시뮬레이터 테스트 (`simulator_v2.py`)
- [ ] 실전 투자 전 충분한 백테스팅

---

**재구축 일자**: ________
**담당자**: ________
**소요 시간**: ________

---

**버전**: 1.5.0
**작성일**: 2024-12-21
**작성자**: Claude Sonnet 4.5
