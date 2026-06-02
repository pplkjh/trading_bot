# 데이터베이스 재구축 가이드

**마지막 업데이트**: 2026-06-02  
**현재 아키텍처**: simul_num=6 (Strategy A + B 혼합, jackbot4_imi1)

---

## 시스템 구성 요약

| DB | 용도 | 스키마 파일 |
|---|---|---|
| `jackbot4_imi1` | 실전 트레이딩 (sim=4/5/6) | `sql/jackbot4_schema.sql` |
| `daily_buy_list` | 일봉 기술지표 (날짜별 테이블) | collector_v3.py가 자동 생성 |
| `daily_craw` | 일봉 OHLCV 원본 | collector가 자동 유지 |
| `simulator4` | Strategy A 백테스트 | 백테스트 실행 시 자동 생성 |
| `simulator5` | Strategy B 백테스트 | 백테스트 실행 시 자동 생성 |

---

## 1. 실전 DB 재구축 (jackbot4_imi1)

### 1-1. DB 생성 및 스키마 적용

```bash
# DB 생성
mysql -u bot -p -e "CREATE DATABASE IF NOT EXISTS jackbot4_imi1 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 스키마 적용
mysql -u bot -p --default-character-set=utf8mb4 jackbot4_imi1 < sql/jackbot4_schema.sql
```

생성되는 테이블:
- `setting_data` — 봇 설정 (invest_unit 등)
- `jango_data` — 일별 자산 현황
- `all_item_db` — 매매 기록 (strategy_type A/B 구분)
- `possessed_item` — 현재 보유 종목 (Kiwoom 동기화용)
- `realtime_daily_buy_list` — 당일 매수 후보
- `realtime_position_monitor` — 보유 종목 최고가 추적
- `intraday_tracker` — 분봉 추적 (RSI/VWAP)

### 1-2. setting_data 초기화

```sql
USE jackbot4_imi1;
UPDATE setting_data SET
    invest_unit = 1000000,
    limit_money = 300000;
```

---

## 2. 매수 후보 DB 재구축 (daily_buy_list)

### 2-1. 기존 날짜 테이블 삭제 (필요 시)

```python
import pymysql
from library.cf import *

con = pymysql.connect(user=db_id, passwd=db_passwd, host=db_ip,
                      db='daily_buy_list', charset='utf8', port=int(db_port))
cursor = con.cursor()
cursor.execute("""
    SELECT TABLE_NAME FROM information_schema.TABLES
    WHERE TABLE_SCHEMA='daily_buy_list' AND TABLE_NAME REGEXP '^[0-9]{8}$'
""")
tables = [r[0] for r in cursor.fetchall()]
for t in tables:
    cursor.execute(f"DROP TABLE IF EXISTS `{t}`")
    print(f"삭제: {t}")
con.commit()
con.close()
print(f"총 {len(tables)}개 테이블 삭제 완료")
```

### 2-2. Collector 실행 (약 23시간)

```bash
python collector_v3.py
```

각 날짜 테이블에 포함된 주요 컬럼:
- `code`, `code_name`, `close`, `volume`, `d1_diff_rate`
- `ma5`, `ma10`, `ma20`, `ma40`, `ma60`, `ma120`
- `rsi14`, `bb_upper`, `bb_middle`, `bb_lower`, `bb_bandwidth`
- `atr14`, `adx`, `plus_di`, `minus_di`
- `macd`, `macd_signal`, `macd_histogram`
- `vol5`, `vol20`, `cmf20`, `mfi14`, `obv`
- `composite_score`, `score_a~f`, `score_penalty`, `strategy_type`

### 2-3. 검증

```python
import pymysql
from library.cf import *

con = pymysql.connect(user=db_id, passwd=db_passwd, host=db_ip,
                      db='daily_buy_list', charset='utf8', port=int(db_port))
cursor = con.cursor()
cursor.execute("""
    SELECT COUNT(*) FROM information_schema.TABLES
    WHERE TABLE_SCHEMA='daily_buy_list' AND TABLE_NAME REGEXP '^[0-9]{8}$'
""")
print(f"날짜 테이블: {cursor.fetchone()[0]}개")

cursor.execute("""
    SELECT TABLE_NAME FROM information_schema.TABLES
    WHERE TABLE_SCHEMA='daily_buy_list' AND TABLE_NAME REGEXP '^[0-9]{8}$'
    ORDER BY TABLE_NAME DESC LIMIT 1
""")
latest = cursor.fetchone()[0]
cursor.execute(f"SELECT COUNT(*) FROM `{latest}`")
print(f"최신 날짜({latest}) 종목 수: {cursor.fetchone()[0]}개")
con.close()
```

예상 결과: 날짜 테이블 ~700개, 종목 수 ~2,700~2,800개

---

## 3. 백테스트 DB (simulator4, simulator5)

백테스트 실행 시 자동 생성됩니다. 별도 스키마 적용 불필요.

```bash
# Strategy A 백테스트 (simulator4 자동 생성/초기화)
python score_analyze.py A

# Strategy B 백테스트 (simulator5 자동 생성/초기화)
python score_analyze.py B

# 둘 다
python score_analyze.py AB

# 장중 트레이더와 병행 시 (백테스트 생략, 기존 결과만 분석)
python score_analyze.py AB --analyze-only
```

---

## 4. 전체 재구축 순서 (처음부터 시작)

```
1. DB 생성 + 스키마 적용    (5분)
   └── mysql < sql/jackbot4_schema.sql

2. Collector 실행           (약 23시간)
   └── python collector_v3.py

3. 트레이더 시작
   └── python trader_advanced.py

4. 백테스트 (선택)
   └── python score_analyze.py AB
```

---

## 5. 주요 파라미터 (cf.py 기준)

| 파라미터 | 값 | 설명 |
|---|---|---|
| `imi1_simul_num` | 6 | 실전 운영 알고리즘 (A+B 혼합) |
| `imi1_db_name` | jackbot4_imi1 | 실전 DB |
| `v4_min_score_a` | 100 | Strategy A 최소 매수 스코어 |
| `v4_min_score_b` | 90 | Strategy B 최소 매수 스코어 (백테스트 기준, 실전 펀더멘털 +40pt 가점) |

---

## 6. 매도 로직 (백테스트 vs 실전)

| | 백테스트 (방향성 검증) | 실전 |
|---|---|---|
| **Strategy A** | 익절 +6% / 손절 -5% / 20일 시간청산 | 하드SL -5% / 트레일링(ATR×ADX배율) / 15일 |
| **Strategy B** | 익절 +6% / 손절 -5% / 45일 시간청산 | 하드SL -5% / 트레일링(ATR×1.0) / 45일 |

> ⚠️ 백테스트는 일봉 기준 **매수 방향성 검증**만 목적. 실전 분봉 매도와 직접 비교 불가.

---

## 7. 트러블슈팅

### realtime_daily_buy_list 비어 있음
```python
import pymysql
from library.cf import *
from datetime import datetime
con = pymysql.connect(user=db_id, passwd=db_passwd, host=db_ip,
                      db='daily_buy_list', charset='utf8', port=int(db_port))
cursor = con.cursor()
today = datetime.now().strftime('%Y%m%d')
cursor.execute(f"SELECT COUNT(*) FROM information_schema.TABLES "
               f"WHERE TABLE_SCHEMA='daily_buy_list' AND TABLE_NAME='{today}'")
print('오늘 테이블:', '있음' if cursor.fetchone()[0] else '없음 → collector 실행 필요')
con.close()
```

### all_item_db strategy_type 이 전부 'A' 로 표시됨
신규 매수 종목은 자동 저장되지만, 기존 보유 종목은 수동 수정 필요:
```sql
-- 예: 코드 102370이 B 전략 종목인 경우
UPDATE jackbot4_imi1.all_item_db
SET strategy_type = 'B'
WHERE code = '102370' AND sell_date = '0';
```

### 백테스트 DB 초기화 필요 시
```bash
# score_analyze.py 실행 시 reset 후 자동 재백테스트
python score_analyze.py A   # simulator4 초기화 + 재백테스트
```
