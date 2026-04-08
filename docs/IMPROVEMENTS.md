# JackBot 개선 사항 노트

> 마지막 업데이트: 2026-03-23
> 전략: simul_num=3 / HybridStrategyV2 (200pt) / 단기 모멘텀 (평균보유 1~8일)

---

## 🔴 즉시 수정 필요 (버그/불일치)

### 1. 실전 봇 vs 백테스트 매도 전략 불일치 ★★★
**문제**: 실전 봇과 백테스트가 완전히 다른 매도 로직을 사용 중

| | 실전 봇 (trader_advanced.py) | 백테스트 (sell_list_num=20) |
|--|--|-|
| 손절 | exit_strategy.py: 고정 -5% OR ATR 2× 손절 | 고정 -3% |
| 익절 | exit_strategy.py: 트레일링 스톱 (수익 +5% 활성화, 거리 3%) | 고정 +6% |
| 기타 | 시간 기반 (15일), 팩터 스코어 청산 | MA5 < MA20 데드크로스 |
| fallback | exit_strategy 실패 시 get_basic_sell_list() (-3%/+6%) | 없음 |

**핵심 문제**: 백테스트 결과(수익률, MDD, 승률)가 실전을 대표하지 않음.
둘 중 하나를 선택해서 통일해야 함.

**방향 제안**: 백테스트를 실전 로직에 맞추거나, 실전을 단순화해서 백테스트와 일치시킴.
→ 단기 모멘텀 전략에는 **단순 고정 +6%/-3% + MA5이탈** (sell_list_num=20)이 더 적합할 수 있음.

**관련 파일**: `library/exit_strategy.py`, `library/open_api.py:get_basic_sell_list()`, `trader_advanced.py:use_advanced_sell`

---

### 2. 트레일링 스톱과 고정 익절의 구조적 모순 ★★★
**문제**: exit_strategy.py가 트레일링(+5% 활성화)과 고정 손절(-5%)을 동시에 운용.
- 트레일링 스톱 활성화 기준(+5%)이 백테스트 익절 기준(+6%)보다 낮아서
  충분히 오르기 전에 트레일링이 걸려 조기 청산될 수 있음
- 단기 매매(1~8일)에서 "트레일링이 익절 목표보다 나은가?" 검증 필요

**현재 exit_strategy.py 설정**:
```python
trailing_stop_activation = 0.05   # +5% 수익 시 트레일링 활성화
trailing_stop_distance   = 0.03   # 현재가에서 3% 하락 시 청산
fixed_stop_loss_pct      = -0.05  # 고정 -5% 손절 (백테스트의 -3%와 다름)
```

**방향 제안**:
A) 실전도 백테스트처럼 단순화: 트레일링 없애고 고정 +6%/-3%만 사용
B) 트레일링 개선: +3% 수익 시 손절선을 매수가로 올림(본전 보장) → +6% 도달 시 트레일링 전환

---

### 3. 매수 허용 범위 하한선 조정 필요 ★★
**현재**: `min_buy_limit = prev_close * (1 + losscut_pct)` = prev_close × 0.97 (-3%)
**문제**: 추세/모멘텀 스코어 종목이 -3% 갭하로 열리면 진입 신호가 깨진 것
- OBV상승, CMF양수, ADX강세 → 모두 전날 종가 기준 신호
- -3% 갭하 = 밤사이 매도세 지배 = 신호 위반

**방향**: `min_buy_limit = prev_close - atr14 * 0.5` (-0.5×ATR, 장 시작 노이즈만 허용)
- ATR 3% 종목: 허용 갭하 -1.5% (현재 -3%보다 타이트)
- ATR 2% 종목: 허용 갭하 -1.0%

**관련 파일**: `library/open_api.py:1046`

---

## 🟡 스코어링 개선 (hybrid_strategy_v2.py)

### 4. 시장 환경 패널티 추가 ★★★ (MDD 직접 감소 효과)
**현재**: E1(RS vs KOSPI 15pt)은 상대강도만 봄. 절대적 하락장 무시.
**추가**: 코스피 5일 추세 패널티

```python
# 코스피 5일 수익률
kospi_5d_ret = (kospi_today - kospi_5d_ago) / kospi_5d_ago
if kospi_5d_ret < -0.03:   # 하락장
    total -= 30
elif kospi_5d_ret < -0.01: # 약세장
    total -= 10
```

**효과**: MDD 핵심 원인(동반 하락)을 진입 단계에서 차단
**난이도**: 쉬움 (스코어링 로직 추가만)

---

### 5. 갭 + 거래량 조합 보너스 ★★
**현재**: A1(거래량급증 20pt) + A4(ATR돌파 10pt)가 분리 채점
**추가**: 갭상 + 거래량 동시 발생 보너스 (기관 진입 신호)

```python
gap_rate = (close - prev_close) / prev_close
if gap_rate > 0.01 and vol5 > vol20 * 2.0:  # 1% 갭상 + 거래량 2배
    total += 15  # 돌파갭 보너스
```

**난이도**: 쉬움

---

### 6. 가격 모멘텀 가속도 ★★
**현재**: A2(MA정배열)는 추세 존재 여부만. 가속 중인지 모름.
**추가**: 단기 수익률 가속 체크

```python
ret_5 = clo5_diff_rate  # 5일 수익률 (already in DB)
ret_10 = clo10_diff_rate
if ret_5 > 0.03 and ret_5 > ret_10 * 0.6:  # 모멘텀 가속
    total += 10
elif ret_5 < 0 and ret_10 > 0:              # 모멘텀 감속 경고
    total -= 10
```

**난이도**: 쉬움 (기존 컬럼 활용)

---

### 7. 52주 신고가 근처 점수 ★★
**근거**: 저항선 없는 구간, 단기 모멘텀의 핵심 (CAN SLIM 기법)
**필요**: daily_buy_list 테이블에 `high_52wk` 컬럼 추가 필요

```python
pct_from_52wk = (close - high_52wk) / high_52wk
if pct_from_52wk > -0.05:   # 52주 고가 95% 이상 → 돌파 직전
    total += 20
elif pct_from_52wk > -0.10:
    total += 10
```

**난이도**: 중간 (DB 컬럼 추가, migration 필요)

---

### 8. ATR 역사적 백분위수 ★
**현재**: C2(BB수렴 15pt)로 간접 측정
**추가**: ATR이 최근 60일 중 낮은 분위에 있을 때 폭발 임박 신호

**난이도**: 어려움 (migration, 추가 컬럼 필요)

---

## 🟢 매도 전략 개선 (중장기)

### 9. 단계적 트레일링 스톱 ✅ 적용 완료 (2026-03-23)

**실전 (use_advanced_sell=True / exit_strategy.py)**

| 우선순위 | 발동 조건 | 결과 |
|---------|-----------|------|
| 110 | 현재가 ≤ 매수가×0.97 | 고정 -3% 손절 |
| 105 | 최고가 +3% 이상 찍은 뒤 현재가 ≤ 매수가×0.995 | 본전 보장 청산 (noise 방지 -0.5% 버퍼) |
| 100 | 현재가 ≤ 매수가 - 2×ATR | ATR 손절 |
| 90 | +5% 이후 최고가에서 3% 하락 | 트레일링 스톱 |

- 모멘텀 종목이 +3% 찍고 매수가로 복귀 = 추세 실패 신호 → 본전 청산
- 장중 noise 방지: 매수가 터치가 아닌 매수가 -0.5% 이하에서 발동

**백테스트 (sell_list_num=20)**: 고정 +6%/-3% + MA5<MA20 유지 (변경 없음)

**관련 파일**: `library/exit_strategy.py` — `fixed_stop_loss_pct=-0.03`, `breakeven_activation=0.03`, `breakeven_buffer=-0.005`

---

### 10. 매도 타이밍 개선 - MA5 단기 이탈 ★
**현재**: sell_list_num=20에 `ma5 < ma20` (데드크로스) 있음
**추가**: `현재가 < ma5 × 0.98` (MA5 이탈) - 단기 추세 꺾임 조기 감지

---

## 📝 인프라/안정성 개선

### 11. 실전 봇 크래시 원인 분석 (2026-03-23 11:18)
- 증상: exit code=1, 84분 무로그(DeduplicateFilter 정상), 재시작 실패
- 추정 원인: start_trader.bat의 for/f 시간 파싱 실패 → CURRENT_HHMM=0 → goto END
- **적용 완료**: PowerShell 시간 파싱으로 교체, 기본값 1200 설정
- **적용 완료**: trader_advanced.py에 30분 heartbeat 로그 추가

### 12. 일일 요약 DB 기반으로 전환
- 증상: 재시작 후 trade_history 초기화 → 매도 0건 오표시
- **적용 완료**: all_item_db에서 오늘 sell_date 기준으로 조회

---

## ✅ 완료된 개선사항

- [x] RSI 슬로프/변곡점 스코어링 반영 (hybrid_strategy_v2.py)
- [x] 매수 상한 0.5×ATR → 1.0×ATR (갭상 모멘텀 확인)
- [x] 매수 하한 1×ATR → losscut 연동 (-3%) [→ #3에서 추가 개선 예정]
- [x] pre-market junk data 방지 (ref_date = get_latest_complete_date())
- [x] 장중 collector 재실행 시 중복매수 방지 (all_item_db 기준 삭제)
- [x] DB 패스워드 로그 노출 제거 예정 (simulator_func_mysql.py:671,685)
- [x] monitor.py RSI/ADX/CMF/MFI/MACD/ATR/갭상하 정보 표시
- [x] monitor.py 매수 스킵 사유 표시 (가격 범위 초과)

---

## 🔢 백테스트 결과 기록 (비교 기준)

### 현재 설정 (2026-03 기준)
- 기간: 2023-01-02 ~ 2026-03-03 (769일)
- 총수익률: **+3,147%**
- MDD: **74.93%** ← 개선 필요
- 승률: **46.3%**
- 손익비 R: **2.27**
- 평균익절: +11.43% / 평균손절: -5.04%
- 평균보유: 6.1일

### 목표
- MDD < 40% (시장환경 패널티 + 분산)
- 승률 > 50%
- 손익비 R > 2.0 유지
