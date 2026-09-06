# JackBot v2 전략 현황 문서
> 최종 업데이트: 2026-04-06  
> 대상: simul_num=3 (HybridStrategyV2, db_to_realtime_daily_buy_list_num=21)

---

## 1. 시스템 파라미터

| 항목 | 값 |
|------|----|
| invest_unit | 1,000,000원 |
| limit_money | 300,000원 (최소 잔고, 사실상 최대 9포지션) |
| sell_point | 6% (시뮬 기준값, 실전은 트레일링으로 대체) |
| losscut_point | -3% |
| v2_min_score | 120점 (220점 만점 중 약 55%) |
| sell_list_num | 20 (시뮬), 100 (실전 exit_strategy.py) |

---

## 2. 매수 후보 선정 (스코어링)

### 파이프라인
1. SQL 사전필터: daily_buy_list 날짜 테이블에서 모멘텀/추세/과매도 신호 상위 200개 선별
2. Python HybridStrategyV2 스코어링 (220점 만점)
3. v2_min_score(120점) 이상 종목만 realtime_daily_buy_list에 저장

### 스코어링 카테고리 (220점 만점)

#### A. 모멘텀 (50pt) — 동적 가중치 적용
| 항목 | 배점 | 조건 |
|------|------|------|
| A1. 거래량급증 | 20pt | vol5/vol20 ≥ 1.5배 → 만점, 선형 |
| A2. MA정배열 | 15pt | clo5>clo10>clo20>clo40>clo60 충족률×15 |
| A3. MACD | 5pt | macd>signal→3pt, histogram>0→2pt |
| A4. ATR돌파 | 10pt | close > prev_close + ATR×0.5 → 10pt (이진) |

#### B. 평균회귀 (20pt) — 동적 가중치 적용
| 항목 | 배점 | 조건 |
|------|------|------|
| B1. RSI과매도 | 10pt | RSI≤30→10pt, 30<RSI≤40→선형 |
| B3. BB하단근접 | 10pt | position≤0.2→10pt, 0.2<pos≤0.4→선형 |

**동적 가중치**: ADX≥25(추세장) → A×1.2/B×0.8, ADX≤20(횡보장) → A×0.8/B×1.2

#### C. 추세강도 (50pt) — 고정
| 항목 | 배점 | 조건 |
|------|------|------|
| C1. ADX | 25pt | ADX≥25→25pt, 20~25→선형, 15~20→0.5배 선형 |
| C2. BB수렴도 | 15pt | bw<0.05→15pt, 0.05~0.1→선형 |
| C3. +DI>-DI | 10pt | 방향성 차이 비율×50, max 10pt |

#### D. 거래량/수급 (50pt) — 고정
| 항목 | 배점 | 조건 |
|------|------|------|
| D1. OBV추세 | 15pt | OBV(today) > OBV_MA20 → 15pt (이진) |
| D2. CMF | 15pt | cmf>0.1→15pt, 0<cmf≤0.1→선형 |
| D3. 거래량-가격동조 | 10pt | 최근 6일 (가격↑&거래량↑) 일수 × 2.5 |
| D4. 외인소진률 ★신규 | 10pt | ≥30%→10pt, 15~30%→선형 |

#### E. 시장상대강도 (40pt) — 고정
| 항목 | 배점 | 조건 |
|------|------|------|
| E1. RS vs 코스피 | 15pt | 20일 수익률 기준, rs>1.1→15pt, 1.0~1.1→선형 |
| E2. BB스퀴즈 | 10pt | bw가 20일 최솟값 1~1.5배 범위 내, close>bb_middle→10pt |
| E3. 캔들패턴 | 5pt | candle_pattern_score (DB 컬럼) |
| E4. 52주신고가근접 ★신규 | 10pt | high_250_rate≥0%→10pt, -10~0%→선형 |

#### F. 다중시간프레임 (10pt) — 고정
| 항목 | 배점 | 조건 |
|------|------|------|
| F1. 주봉추세(MA25) | 10pt | close>MA25 AND MA25상승→10pt, close>MA25만→5pt |

#### 리스크 패널티
| 항목 | 패널티 | 조건 |
|------|--------|------|
| 변동성 | -20pt / -10pt | ATR/close > 8% / 5% |
| MFI과매수 | -15pt / -8pt | MFI14 > 90 / 80 |
| 신용비율 ★신규 | -10pt / -5pt | credit_rate ≥ 10% / 5% |
| RSI고점꺾임 | -15pt / -8pt | RSI>60 고점 이후 -3pt/일 / -1.5pt/일 하락 |
| RSI저점반등 | +10pt / +5pt | RSI<40 저점 이후 +2pt/일 / +1pt/일 상승 |

### 펀더멘탈 수급지표 데이터 소스
- **저장**: `daily_buy_list.sf_YYYYMMDD` 날짜별 테이블 (7일 주기 수집)
- **항목**: foreign_rate(외인소진률), credit_rate(신용비율), high_250_rate(250일고가비율)
- **백테스트**: 시뮬 날짜 기준 가장 가까운 sf 테이블 사용 (lookahead 방지)
- **DART ROE 보너스**: ROE≥15%→+15pt, ROE≥5%→선형 (별도 dart DB)

---

## 3. 매도 전략

### 실전 (sell_list_num=100, exit_strategy.py)

우선순위 높은 순서로 체크:

#### Priority 110: 고정 손절 (최우선)
- 조건: `current_return ≤ -3%`
- **30분 유예**: 매수 후 30분간 비활성화 (시초가 노이즈 방지)
- 유예 중 여부는 대쉬보드에 ⏰ 표시

#### Priority 100: ATR 손절
- 조건: `current_price ≤ entry_price - ATR×2.0`
- 실질적으로 고정 손절(-3%)이 항상 먼저 발동되어 거의 미작동

#### Priority 90: 트레일링 스톱 (익절 핵심)
- **활성화**: 수익률 ≥ +5%
- **손절선**: `highest_price × (1 - 0.03)` (최고가 대비 -3%)
- 최고가가 올라갈수록 손절선도 따라 올라감 → 수익 보호
- 대쉬보드에 🟢 트레일링 표시

#### Priority 60: 시간 기반 청산
- 6일 이상 보유 + 수익 상태 → 익절 (모멘텀 소진 판단)
- 15일 이상 보유 → 무조건 강제 청산

### 시뮬 (sell_list_num=20)
```sql
rate >= 6%    → 익절
rate <= -3%   → 손절
ma5 < ma20    → MA 데드크로스 손절
```

### 백테스트 결과 (2026-04-06 기준, 2023-01-02~2026-03-03)

| 지표 | 값 |
|------|----|
| 총수익률 | **+5,758.22%** |
| MDD | 51.51% |
| 승률 | 61.0% |
| 손익비 R | 2.39 |
| Sharpe(연) | 1.11 |
| 평균보유 | 5.8일 |
| 총 거래 | 10,579회 |
| 평균익절 | +12.47% |
| 평균손절 | -5.22% |
| 최대손절 | -31.72% |

**매도 근거 분포**:
- 익절(+6%) 58.2% / 손절(-3%) 35.4% / MA데드크로스 6.5%

**스코어 구간별 승률**:
- 150pt 이상: 71.9% / 130~149pt: 65.1% / 120~129pt: 57.2%

---

## 4. 데이터 수집 구조

### collector_v3.py 실행 흐름
1. KIND 크롤링 (종목 리스트 최신화)
2. daily_crawler (OHLCV 일봉 수집)
3. daily_buy_list 날짜 테이블 생성 (기술지표 계산 포함)
4. realtime_daily_buy_list 스코어링 (HybridStrategyV2)
5. kospi/kosdaq 지수 수집
6. **펀더멘탈 수집** (7일 주기, `sf_YYYYMMDD` 테이블)
   - 크래시 대비 100건 checkpoint
   - 재시작 시 이미 수집된 코드 skip (재개 모드)
   - 서버 스로틀 감지 시 최대 3회 retry + 5초 대기

### 완료 확인 (check_collector_done.py)
1. `setting_data.today_buy_list` == 오늘 날짜 → 스코어링 완료
2. 최근 `sf_2*` 테이블 날짜 확인 → 7일 주기 미경과 OR 오늘 건수 ≥ 95% → OK

---

## 5. 실전 매매 흐름 (trader_advanced.py)

1. **매수**: realtime_daily_buy_list에서 스코어 순으로 매수 시도
2. **포지션 추적**: `realtime_position_monitor` 테이블에 highest_price 기록
3. **매도 체크**: exit_strategy.py `get_exit_signals()` 호출 (우선순위 순)
4. **대쉬보드** (trading_dashboard.py):
   - ⏰ 손절유예 중 (매수 후 30분 이내)
   - 🟢 트레일링 활성 (수익 ≥ +5%)
   - ⚪ 대기 중

---

## 6. DB 구조 요약

| DB | 주요 테이블 | 용도 |
|----|------------|------|
| `daily_craw` | `종목명` (테이블명) | OHLCV 일봉 히스토리 |
| `daily_buy_list` | `YYYYMMDD` | 날짜별 기술지표 |
| `daily_buy_list` | `sf_YYYYMMDD` | 날짜별 펀더멘탈 수급지표 |
| `daily_buy_list` | `stock_item_all` | 전체 종목 코드/이름 |
| `jackbot3_imi1` | `all_item_db` | 매수/매도 이력 |
| `jackbot3_imi1` | `realtime_daily_buy_list` | 당일 매수 후보 |
| `jackbot3_imi1` | `realtime_position_monitor` | 보유 포지션 최고가 추적 |
| `jackbot3_imi1` | `setting_data` | 수집 완료 상태 |
