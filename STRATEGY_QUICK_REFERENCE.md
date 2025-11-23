# 전략 빠른 참조표

## 🔢 전략 번호 요약

| 번호 | 전략명 | 매수 조건 | 매도 조건 | 자본금 | 매수단위 | 보유기간 |
|------|--------|----------|----------|--------|---------|---------|
| **1** | 🚀 **고급 통합** | 거래량↑ + 5MA>20MA + 변동성필터 | 동적 트레일링 (15% 익절) | 1천만 | 100만 | 3-10일 |
| 21 | 5/20 골든크로스 | 5MA > 20MA | +5% / -2% | 1천만 | 50만 | 5-15일 |
| 22 | 5/40 골든크로스 | 5MA > 40MA | +8% / -2% | 5천만 | 100만 | 10-30일 |
| 23 | 전일 상승 | D1 > 1% | +10% / -2% | 1천만 | 300만 | 1-5일 |
| 27 | 절대모멘텀 (code) | 100D > 1% | 100D < 1% | 1천만 | 100만 | 20-60일 |
| 28 | 절대모멘텀 (query) | 100D > 1% | 100D < 1% | 1천만 | 100만 | 20-60일 |
| 29 | 절대모멘텀 + 손절 | 100D > 1% | 100D < 1% or -2% | 1천만 | 100만 | 20-60일 |
| 30 | 상대모멘텀 | 상위 순위 | 하위 순위 | 1천만 | 100만 | 20-60일 |
| 31 | AI 알고리즘 | AI 모델 | AI 모델 | 1천만 | 100만 | 가변 |
| 32 | 우량주 필터 | 감사정상 + 고신용 | +10% / -2% | 1천만 | 100만 | 15-30일 |
| 33 | 거래량 급증 | 거래량 2배↑ | +10% / -2% | 1천만 | 100만 | 1-3일 |
| 34 | 래리윌리엄스 | 변동성 돌파 | +10% / -2% | 1천만 | 100만 | 1-5일 |
| 36 | ETF | 5MA > 20MA | +10% / -2% | 1천만 | 100만 | 7-30일 |

---

## 📊 전략 비교 차트

### 공격성 순위
```
높음 ▲
  ↑  #23 (전일 상승)
  │  #33 (거래량 급증)
  │  #1 (고급 통합)
  │  #21 (5/20 골든크로스)
  │  #27-30 (모멘텀)
  │  #22 (5/40 골든크로스)
  ↓  #32 (우량주)
낮음 ▼
```

### 거래 빈도
```
높음 ▲
  ↑  #23, #33, #34 (단기)
  │  #1, #21 (스윙)
  │  #22, #32 (중기)
  ↓  #27-30 (장기)
낮음 ▼
```

### 복잡도
```
높음 ▲
  ↑  #1 (고급: 다중필터)
  │  #31 (AI)
  │  #33-34 (실시간)
  │  #27-30 (모멘텀)
  │  #22, #23, #32
  ↓  #21 (단순)
낮음 ▼
```

---

## 🎯 시나리오별 추천

### 상황 1: 처음 시작하는 초보자
```
추천: #21 (5/20 골든크로스)
이유: 가장 단순하고 이해하기 쉬움
설정: 자본 1천만원, 매수 50만원
```

### 상황 2: 공격적으로 단기 수익 추구
```
추천: #1 (고급 통합) 또는 #23 (전일 상승)
이유: 빠른 매매, 높은 수익률
설정: 자본 1천만원, 매수 100-300만원
```

### 상황 3: 안정적 장기 투자
```
추천: #22 (5/40 골든크로스) 또는 #32 (우량주)
이유: 우량주 중심, 장기 보유
설정: 자본 3-5천만원, 매수 100만원
```

### 상황 4: 추세 추종 전략
```
추천: #27-30 (모멘텀 전략)
이유: 장기 추세 확인 후 진입
설정: 자본 1천만원, 매수 100만원
```

### 상황 5: 실시간 단타 매매
```
추천: #33 (거래량 급증) 또는 #34 (래리윌리엄스)
이유: 분봉 데이터 활용, 실시간 대응
요구: use_min = True 설정 필요
```

---

## 💡 실행 명령어 치트시트

### 백테스트 실행
```bash
# 전략 #1 백테스트
python simulator_v2.py
# 입력: 1 → y

# 전략 #21 백테스트
python simulator_v2.py
# 입력: 21 → y

# 이어서 실행 (continue)
python simulator_v2.py
# 입력: 1 → n
```

### 데이터 수집
```bash
# 매일 15:40 이후 실행
python collector_v3.py
```

### 결과 확인 (MySQL)
```sql
-- 전략 #1 결과
USE simulator1;
SELECT * FROM jango_data ORDER BY date DESC LIMIT 10;

-- 전략 #21 결과
USE simulator21;
SELECT * FROM jango_data ORDER BY date DESC LIMIT 10;
```

### 고급 전략 매수 후보 스캔
```bash
python run_advanced_strategy.py --mode scan
```

---

## 📈 성과 지표 계산

### SQL 쿼리 모음

**총 수익률:**
```sql
USE simulator1;  -- 전략 번호에 맞게 변경

SELECT
    (total_invest_price - 10000000) / 10000000 * 100 as total_return_pct,
    total_invest_price as final_capital,
    total_valuation_profit as realized_profit
FROM jango_data
ORDER BY date DESC
LIMIT 1;
```

**승률 계산:**
```sql
SELECT
    COUNT(*) as total_trades,
    SUM(CASE WHEN sell_rate > 0 THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN sell_rate > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate,
    AVG(sell_rate) as avg_return,
    MAX(sell_rate) as best_trade,
    MIN(sell_rate) as worst_trade
FROM all_item_db
WHERE sell_date != 0;
```

**월별 수익:**
```sql
SELECT
    SUBSTRING(date, 1, 6) as month,
    COUNT(*) as trades,
    SUM(total_valuation_profit) as monthly_profit,
    AVG(total_valuation_profit) as avg_daily_profit
FROM jango_data
GROUP BY SUBSTRING(date, 1, 6)
ORDER BY month;
```

**보유 종목 현황:**
```sql
SELECT
    code_name,
    buy_date,
    buy_price,
    present_price,
    rate as return_pct,
    valuation_profit as unrealized_profit
FROM all_item_db
WHERE sell_date = 0
ORDER BY rate DESC;
```

---

## ⚡ 빠른 문제 해결

### Q: 시뮬레이터 실행 시 에러
```bash
# MySQL sql_mode 확인
mysql> SELECT @@sql_mode;

# ONLY_FULL_GROUP_BY 제거
mysql> SET SESSION sql_mode=(SELECT REPLACE(@@sql_mode,'ONLY_FULL_GROUP_BY',''));
```

### Q: 오늘 데이터가 없음
```bash
# collector 실행 (15:40 이후)
python collector_v3.py

# setting_data 확인
USE JackBot1_imi1;
SELECT daily_crawler, daily_buy_list FROM setting_data;

# 재수집 필요 시
UPDATE setting_data SET daily_crawler='20000101', daily_buy_list='20000101';
```

### Q: 시뮬레이터 초기화
```sql
-- 데이터베이스 삭제 후 재실행
DROP DATABASE simulator1;  -- 전략 번호에 맞게

-- 또는 Python에서
python simulator_v2.py
# 입력: 1 → y (초기화)
```

---

## 📝 체크리스트

### 백테스트 전 확인사항
- [ ] MySQL 실행 중
- [ ] 데이터 수집 완료 (collector 실행)
- [ ] sql_mode 설정 확인
- [ ] 전략 번호 확인

### 실전 전 확인사항
- [ ] 백테스트 결과 만족
- [ ] Kiwoom OpenAPI 로그인
- [ ] 모의투자 계좌 확인
- [ ] 리스크 관리 계획 수립

---

**마지막 업데이트:** 2025-11-19
**다음 전략 번호:** #2 (예약됨)
