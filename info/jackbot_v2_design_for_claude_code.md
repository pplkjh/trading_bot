# JackBot v2 확장 Scoring 시스템 — Claude Code 구현 가이드

> **이 문서를 읽고 구현해주세요.**
> **절대 원칙: simul_num=1의 기존 코드는 한 줄도 수정하지 않는다. 모든 변경은 simul_num=2 분기로만 추가한다.**

---

## 1. 프로젝트 배경

### 1.1 현재 상태
- JackBot은 한국 주식 자동매매 시스템 (키움증권 OpenAPI 사용)
- 매일 아침 collector_v3.py가 전 종목 OHLCV + 기술적 지표를 수집
- open_api.py가 장 시작 후 매수/매도 실행
- 현재 scoring: 100점 만점 (모멘텀 60 + 평균회귀 40)

### 1.2 목표
- 250점 만점의 7개 카테고리 확장 scoring 시스템을 **별도 알고리즘(simul_num=2)**으로 추가
- 스윙 트레이딩 (보유 7~15일) 최적화
- 기존 simul_num=1은 완전히 보존 → 성능 비교 후 선택 가능

### 1.3 알고리즘 전환 방법
```python
# cf.py에서 이 값만 바꾸면 전환됨
imi1_simul_num = 1  # 기존 방식 (100점)
imi1_simul_num = 2  # 새 방식 (250점)

# DB는 자동 분리됨:
# simul_num=1 → jackbot1_imi1 DB
# simul_num=2 → jackbot2_imi1 DB (완전히 별도)
```

---

## 2. 현재 코드 구조 (반드시 숙지)

### 2.1 핵심 실행 흐름
```
[데이터 수집]
collector_v3.py
  → library/collector_api.py     # Kiwoom API로 일봉(opt10081) 수집 → daily_craw DB
  → library/daily_buy_list.py    # 기술적 지표 계산 → daily_buy_list DB

[트레이딩]
open_api.py
  → library/simulator_func_mysql.py  # 핵심: 알고리즘 분기(variable_setting)
      → variable_setting()           # simul_num에 따라 매수/매도 알고리즘 번호 결정
      → db_to_realtime_daily_buy_list()  # 매수 종목 선정
      → get_sell_list()              # 매도 종목 선정
```

### 2.2 cf.py 구조 (현재)
```python
imi1_simul_num = 1
imi1_db_name = "jackbot" + str(imi1_simul_num) + "_imi1"
# → simul_num=1이면 jackbot1_imi1 DB
# → simul_num=2이면 jackbot2_imi1 DB (자동)
```

### 2.3 simulator_func_mysql.py의 핵심 패턴

**variable_setting()** — simul_num별 분기:
```python
def variable_setting(self):
    # 공통 기본값 설정 ...
    
    if self.simul_num == 1:
        self.simul_start_date = "20230102"
        self.db_to_realtime_daily_buy_list_num = 1  # 매수 알고리즘 번호
        self.sell_list_num = 1                       # 매도 알고리즘 번호
        self.start_invest_price = 10000000
        self.invest_unit = 3000000
        self.limit_money = 1000000
        self.sell_point = 10
        self.losscut_point = -2
        self.invest_limit_rate = 1.01
        self.invest_min_limit_rate = 0.98
        # ... 기존 설정들 ...
    
    # 여기서부터 simul_num in (4,5,6,7,8,9,10...) 분기들
    
    else:
        logger.error("해당 되는 알고리즘이 없습니다.")
        sys.exit(1)
```

**db_to_realtime_daily_buy_list()** — 매수 알고리즘 분기:
```python
def db_to_realtime_daily_buy_list(self, date_rows_today, date_rows_yesterday, i):
    if self.db_to_realtime_daily_buy_list_num == 1:
        # 기존 하이브리드 scoring 기반 매수 종목 선정
        # ... (현재 hybrid_strategy.py 사용)
    
    elif self.db_to_realtime_daily_buy_list_num == 7:
        # 절대모멘텀 (code ver)
    elif self.db_to_realtime_daily_buy_list_num == 8:
        # 절대모멘텀 (query ver)
    elif self.db_to_realtime_daily_buy_list_num == 9:
        # 상대모멘텀 (query ver)
    # ... 등등
```

**get_sell_list()** — 매도 알고리즘 분기:
```python
def get_sell_list(self, i):
    if self.sell_list_num == 1:
        # 단순 익절/손절 (sell_point / losscut_point)
    elif self.sell_list_num == 2:
        # 5/20 이동평균 데드크로스 or 손절
    elif self.sell_list_num == 3:
        # 5/40 이동평균 데드크로스 or 손절
    # ... 등등
```

### 2.4 현재 사용 중인 Kiwoom TR
| TR | 용도 |
|----|------|
| `opt10081` | 주식 일봉 데이터 (OHLCV) |
| `opt10080` | 주식 분봉 데이터 |
| `opt10074` | 주식 당일 실현손익 |
| `opt10076` | 주식 당일 체결 내역 |
| `opt10073` | 주식 기간별 손익 |
| `opw00001` | 예수금 상세현황 |
| `opw00018` | 계좌평가 잔고내역 |
| `opw00015` | 미체결 내역 |

### 2.5 현재 DB 구조
- **`daily_craw` DB**: 종목별 테이블 (예: `005930`), 컬럼 = date, open, high, low, close, volume, clo5~clo120, vol5~vol120, d1_diff_rate 등
- **`daily_buy_list` DB**: 날짜별 테이블 (예: `20250220`), 컬럼 = daily_craw 컬럼들 + rsi14, bb_upper, bb_middle, bb_lower, atr14
- **`stock_item_all` 테이블**: 전 종목 코드/이름 목록

---

## 3. 구현 작업 목록

### ★ 작업 순서가 중요합니다. 반드시 Phase 순서대로 진행하세요.

---

### Phase 1: 기반 인프라 (기존 코드 수정 없음)

#### 작업 1-1: `library/technical_indicators.py` — 함수 추가

기존 파일에 **아래 함수들을 추가**합니다. 기존 `calculate_rsi`, `calculate_bollinger_bands`, `calculate_atr` 함수는 절대 수정하지 마세요.

```python
# ===== v2 확장 지표 함수 (아래를 기존 파일 하단에 추가) =====

import numpy as np

def calculate_ema(series, period):
    """지수이동평균"""
    return series.ewm(span=period, adjust=False).mean()

def calculate_macd(close_series, fast=12, slow=26, signal=9):
    """MACD, Signal, Histogram
    Args:
        close_series: pandas Series (최소 slow+signal 행 이상)
    Returns:
        (macd값, signal값, histogram값) — 각각 최신 1개 float
    """
    ema_fast = calculate_ema(close_series, fast)
    ema_slow = calculate_ema(close_series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return float(macd_line.iloc[-1]), float(signal_line.iloc[-1]), float(histogram.iloc[-1])

def calculate_adx(high_series, low_series, close_series, period=14):
    """ADX (Average Directional Index) — 추세 강도 0~100
    Returns: (adx, plus_di, minus_di) — 각각 최신 1개 float
    """
    # +DM / -DM
    plus_dm = high_series.diff()
    minus_dm = low_series.diff() * -1
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)
    
    # True Range
    tr1 = high_series - low_series
    tr2 = (high_series - close_series.shift(1)).abs()
    tr3 = (low_series - close_series.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Smoothed averages (Wilder's method)
    atr = tr.ewm(alpha=1/period, min_periods=period).mean()
    plus_di_raw = 100 * (plus_dm.ewm(alpha=1/period, min_periods=period).mean() / atr)
    minus_di_raw = 100 * (minus_dm.ewm(alpha=1/period, min_periods=period).mean() / atr)
    
    # DX → ADX
    dx = 100 * (plus_di_raw - minus_di_raw).abs() / (plus_di_raw + minus_di_raw).replace(0, 1)
    adx = dx.ewm(alpha=1/period, min_periods=period).mean()
    
    return float(adx.iloc[-1]), float(plus_di_raw.iloc[-1]), float(minus_di_raw.iloc[-1])

def calculate_obv(close_series, volume_series):
    """On-Balance Volume
    Returns: 최신 OBV 값 (float)
    """
    direction = close_series.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    obv = (volume_series * direction).cumsum()
    return float(obv.iloc[-1])

def calculate_mfi(high_series, low_series, close_series, volume_series, period=14):
    """Money Flow Index — 거래량 가중 RSI (0~100)
    Returns: 최신 MFI 값 (float)
    """
    tp = (high_series + low_series + close_series) / 3
    rmf = tp * volume_series
    tp_diff = tp.diff()
    pos_flow = rmf.where(tp_diff > 0, 0.0).rolling(period).sum()
    neg_flow = rmf.where(tp_diff <= 0, 0.0).rolling(period).sum()
    mfi = 100 - (100 / (1 + pos_flow / neg_flow.replace(0, 1)))
    return float(mfi.iloc[-1])

def calculate_cmf(high_series, low_series, close_series, volume_series, period=20):
    """Chaikin Money Flow (-1 ~ +1)
    Returns: 최신 CMF 값 (float)
    """
    hl_range = (high_series - low_series).replace(0, 1)
    clv = ((close_series - low_series) - (high_series - close_series)) / hl_range
    cmf = (clv * volume_series).rolling(period).sum() / volume_series.rolling(period).sum().replace(0, 1)
    return float(cmf.iloc[-1])

def calculate_ichimoku(high_series, low_series, close_series):
    """일목균형표 핵심 4선
    Returns: (tenkan, kijun, senkou_a, senkou_b) — 각각 float
    """
    tenkan = (high_series.rolling(9).max() + low_series.rolling(9).min()) / 2
    kijun = (high_series.rolling(26).max() + low_series.rolling(26).min()) / 2
    senkou_a = (tenkan + kijun) / 2
    senkou_b = (high_series.rolling(52).max() + low_series.rolling(52).min()) / 2
    return (float(tenkan.iloc[-1]), float(kijun.iloc[-1]),
            float(senkou_a.iloc[-1]), float(senkou_b.iloc[-1]))

def calculate_pivot_points(prev_high, prev_low, prev_close):
    """전일 OHLC 기반 피봇 포인트
    Args: 전일의 high, low, close (각각 float)
    Returns: (pivot, s1, s2, r1, r2)
    """
    pivot = (prev_high + prev_low + prev_close) / 3
    s1 = 2 * pivot - prev_high
    s2 = pivot - (prev_high - prev_low)
    r1 = 2 * pivot - prev_low
    r2 = pivot + (prev_high - prev_low)
    return float(pivot), float(s1), float(s2), float(r1), float(r2)

def detect_candle_pattern(open_val, high_val, low_val, close_val,
                          prev_open, prev_high, prev_low, prev_close):
    """캔들 패턴 감지 — 반전 신호 점수 (0~10)
    Args: 오늘과 전일의 OHLC (각각 float)
    Returns: pattern_score (float, 0~10)
    """
    score = 0.0
    body = abs(close_val - open_val)
    total_range = high_val - low_val if high_val != low_val else 1
    lower_shadow = min(open_val, close_val) - low_val
    upper_shadow = high_val - max(open_val, close_val)
    is_bullish = close_val > open_val
    prev_is_bearish = prev_close < prev_open
    
    # 망치형 (Hammer): 긴 아래꼬리 + 짧은 몸통
    if lower_shadow > body * 2 and upper_shadow < body * 0.3 and is_bullish:
        score += 4
    
    # 상승 장악형 (Bullish Engulfing)
    if (is_bullish and prev_is_bearish and
        open_val <= prev_close and close_val >= prev_open):
        score += 4
    
    # 도지 (Doji): 시가 ≈ 종가
    if body / total_range < 0.1:
        score += 2
    
    return min(10.0, score)

def calculate_bollinger_bandwidth(bb_upper, bb_middle, bb_lower):
    """볼린저 밴드 폭 (스퀴즈 감지용)"""
    if bb_middle == 0 or bb_middle is None:
        return 0.0
    return float((bb_upper - bb_lower) / bb_middle)

def calculate_rs_vs_market(stock_return_20d, market_return_20d):
    """상대강도 (RS) — 종목 수익률 / 시장 수익률
    Args: 20일 수익률 (각각 float, 예: 0.05 = 5%)
    Returns: rs_ratio (>1이면 아웃퍼폼)
    """
    if market_return_20d == 0:
        return 1.0
    return (1 + stock_return_20d) / (1 + market_return_20d)
```

> **import 주의**: 이 함수들은 `pandas`를 사용하므로 파일 상단에 `import pandas as pd`가 있어야 합니다. 기존 파일에 이미 있는지 확인하세요.

---

#### 작업 1-2: `library/hybrid_strategy_v2.py` — **신규 파일 생성**

이 파일은 simul_num=2 전용 scoring 엔진입니다.

**파일 구조 요약**:
```python
"""
JackBot v2 확장 Scoring 시스템 (250점 만점)
simul_num=2 전용. hybrid_strategy.py(v1)는 수정하지 않음.
"""
from library.technical_indicators import *
import pandas as pd

class HybridStrategyV2:
    def __init__(self):
        # v2 설정값
        self.min_total_score = 120      # 최소 매수 기준 (250점 만점)
        self.fundamental_min_score = 15  # 펀더멘털 최소점 (50점 만점)
    
    def calculate_total_score(self, row, df_120, fundamental_data=None, market_data=None):
        """전체 250점 만점 scoring 메인 함수
        
        Args:
            row: daily_buy_list 테이블에서 가져온 1행 (dict 또는 Series)
                 필수 키: close, open, high, low, volume, clo5~clo60, vol5~vol20,
                          rsi14, bb_upper, bb_middle, bb_lower, atr14,
                          + v2 추가 컬럼들 (macd, adx 등)
            df_120: 해당 종목의 최근 120일 daily_craw 데이터 (DataFrame)
            fundamental_data: stock_fundamental 테이블에서 해당 종목 1행 (dict, 없으면 None)
            market_data: 코스피/코스닥 지수 최근 20일 close (Series, 없으면 None)
        
        Returns:
            float: 총점 (0~250+), -1이면 펀더멘털 필터에서 탈락
        """
        # G. 펀더멘털 1단계 필터 (있을 때만)
        g_score = self.score_fundamental(fundamental_data) if fundamental_data else 0
        if fundamental_data and g_score < self.fundamental_min_score:
            return -1  # 탈락
        
        # C. 추세 강도 + 동적 가중치 결정
        c_score, adx_val = self.score_trend_strength(row)
        mom_mult, mr_mult = self._get_dynamic_weights(adx_val)
        
        # A. 모멘텀 (동적 가중치 적용)
        a_score = self.score_momentum(row, df_120) * mom_mult
        
        # B. 평균회귀 (동적 가중치 적용)
        b_score = self.score_mean_reversion(row) * mr_mult
        
        # D. 거래량/수급
        d_score = self.score_volume_flow(row, df_120)
        
        # E. 시장 상대강도 & 변동성
        e_score = self.score_market_context(row, df_120, market_data)
        
        # F. 다중 시간프레임
        f_score = self.score_multi_timeframe(row, df_120)
        
        total = a_score + b_score + c_score + d_score + e_score + f_score + g_score
        return round(total, 2)
    
    # === A. 모멘텀 (50점) ===
    def score_momentum(self, row, df_120):
        score = 0.0
        
        # A1. 거래량 급증 (15점) — vol5/vol20 비율
        try:
            if row['vol20'] and row['vol20'] > 0:
                vol_ratio = row['vol5'] / row['vol20']
                score += min(15, max(0, (vol_ratio - 1.0) * 30))
        except (KeyError, TypeError, ZeroDivisionError):
            pass
        
        # A2. MA 정배열 (15점) — clo5 > clo10 > clo20 > clo40 > clo60
        try:
            ma_keys = ['clo5', 'clo10', 'clo20', 'clo40', 'clo60']
            ma_vals = [row[k] for k in ma_keys if row.get(k) and row[k] > 0]
            if len(ma_vals) >= 2:
                pairs_ok = sum(1 for i in range(len(ma_vals))
                              for j in range(i+1, len(ma_vals))
                              if ma_vals[i] > ma_vals[j])
                total_pairs = len(ma_vals) * (len(ma_vals) - 1) // 2
                if total_pairs > 0:
                    score += (pairs_ok / total_pairs) * 15
        except (KeyError, TypeError):
            pass
        
        # A3. MACD 신호 (10점)
        try:
            if row.get('macd') and row.get('macd_signal'):
                if row['macd'] > row['macd_signal']:
                    score += 5
                if row.get('macd_histogram') and row['macd_histogram'] > 0:
                    score += 5
        except (KeyError, TypeError):
            pass
        
        # A4. ATR 돌파 (10점) — 종가 > 전일종가 + ATR × 0.5
        try:
            if df_120 is not None and len(df_120) >= 2 and row.get('atr14'):
                prev_close = df_120['close'].iloc[-2]
                if row['close'] > prev_close + row['atr14'] * 0.5:
                    score += 10
        except (KeyError, TypeError, IndexError):
            pass
        
        return score
    
    # === B. 평균회귀 (40점) ===
    def score_mean_reversion(self, row):
        score = 0.0
        
        # B1. RSI 과매도 (12점)
        try:
            rsi = row.get('rsi14', 50)
            if rsi and rsi <= 30:
                score += 12
            elif rsi and rsi <= 40:
                score += 12 * (40 - rsi) / 10
        except (TypeError):
            pass
        
        # B2. MFI 과매도 (10점)
        try:
            mfi = row.get('mfi14', 50)
            if mfi and mfi <= 20:
                score += 10
            elif mfi and mfi <= 30:
                score += 10 * (30 - mfi) / 10
        except (TypeError):
            pass
        
        # B3. 볼린저 하단 근접 (10점)
        try:
            bb_range = row['bb_upper'] - row['bb_lower']
            if bb_range > 0:
                position = (row['close'] - row['bb_lower']) / bb_range
                if position <= 0.2:
                    score += 10
                elif position <= 0.4:
                    score += 10 * (0.4 - position) / 0.2
        except (KeyError, TypeError, ZeroDivisionError):
            pass
        
        # B4. 피봇 지지선 반등 (8점)
        try:
            s1 = row.get('pivot_s1')
            if s1 and s1 > 0:
                proximity = abs(row['close'] - s1) / s1
                is_bullish = row['close'] > row['open']
                if proximity < 0.01 and is_bullish:
                    score += 8
                elif proximity < 0.02 and is_bullish:
                    score += 4
        except (KeyError, TypeError, ZeroDivisionError):
            pass
        
        return score
    
    # === C. 추세 강도 (30점) + 동적 가중치 역할 ===
    def score_trend_strength(self, row):
        score = 0.0
        adx_val = row.get('adx', 0) or 0
        
        # C1. ADX (15점)
        if adx_val >= 25:
            score += 15
        elif adx_val >= 20:
            score += 15 * (adx_val - 20) / 5
        
        # C2. 볼린저 밴드 수렴도 (15점) — bandwidth가 낮을수록 폭발 임박
        try:
            bw = row.get('bb_bandwidth', 0) or 0
            if 0 < bw < 0.05:
                score += 15
            elif bw < 0.1:
                score += 15 * (0.1 - bw) / 0.05
        except (TypeError):
            pass
        
        return score, adx_val
    
    def _get_dynamic_weights(self, adx):
        """ADX에 따라 모멘텀/평균회귀 가중치 조절"""
        if adx >= 25:
            return 1.2, 0.8   # 추세장 → 모멘텀 강화
        elif adx <= 20:
            return 0.8, 1.2   # 횡보장 → 평균회귀 강화
        return 1.0, 1.0
    
    # === D. 거래량/수급 (30점) ===
    def score_volume_flow(self, row, df_120):
        score = 0.0
        
        # D1. OBV 추세 (10점)
        try:
            if df_120 is not None and len(df_120) >= 20 and 'obv' in df_120.columns:
                obv_ma20 = df_120['obv'].rolling(20).mean().iloc[-1]
                if obv_ma20 and row.get('obv', 0) > obv_ma20:
                    score += 10
        except (KeyError, TypeError, IndexError):
            pass
        
        # D2. CMF 매수압력 (10점)
        try:
            cmf = row.get('cmf20', 0) or 0
            if cmf > 0.1:
                score += 10
            elif cmf > 0:
                score += 10 * (cmf / 0.1)
        except (TypeError):
            pass
        
        # D3. 거래량-가격 동조 (10점)
        try:
            if df_120 is not None and len(df_120) >= 6:
                recent = df_120.tail(6)
                price_up = recent['close'].diff() > 0
                vol_up = recent['volume'].diff() > 0
                concordance = (price_up & vol_up).sum()
                score += min(10, concordance * 2.5)
        except (KeyError, TypeError):
            pass
        
        return score
    
    # === E. 시장 상대강도 & 변동성 (30점) ===
    def score_market_context(self, row, df_120, market_data=None):
        score = 0.0
        
        # E1. RS vs 코스피/코스닥 (10점) — market_data 있을 때만
        try:
            if market_data is not None and len(market_data) >= 20 and df_120 is not None and len(df_120) >= 20:
                stock_ret = (df_120['close'].iloc[-1] - df_120['close'].iloc[-20]) / df_120['close'].iloc[-20]
                market_ret = (market_data.iloc[-1] - market_data.iloc[-20]) / market_data.iloc[-20]
                rs = calculate_rs_vs_market(stock_ret, market_ret)
                if rs > 1.1:
                    score += 10
                elif rs > 1.0:
                    score += 10 * (rs - 1.0) / 0.1
        except (KeyError, TypeError, IndexError, ZeroDivisionError):
            pass
        
        # E2. 볼린저 스퀴즈 (10점)
        try:
            bw = row.get('bb_bandwidth', 0) or 0
            if df_120 is not None and 'bb_bandwidth' in df_120.columns and len(df_120) >= 20:
                bw_min_20 = df_120['bb_bandwidth'].tail(20).min()
                if bw_min_20 and bw > bw_min_20 and bw < bw_min_20 * 1.5:
                    # 스퀴즈 후 확장 시작 단계
                    if row['close'] > row.get('bb_middle', 0):
                        score += 10
                    else:
                        score += 5
        except (KeyError, TypeError):
            pass
        
        # E3. 캔들 패턴 (10점)
        try:
            score += min(10, row.get('candle_pattern_score', 0) or 0)
        except (TypeError):
            pass
        
        return score
    
    # === F. 다중 시간프레임 (20점) ===
    def score_multi_timeframe(self, row, df_120):
        score = 0.0
        
        # F1. 주봉 추세 일치 (10점) — 25일 MA(≈5주) 위 + 상승
        try:
            if df_120 is not None and len(df_120) >= 30:
                ma25 = df_120['close'].rolling(25).mean()
                if row['close'] > ma25.iloc[-1]:
                    if ma25.iloc[-1] > ma25.iloc[-6]:
                        score += 10  # MA 위 + MA 자체도 상승
                    else:
                        score += 5   # MA 위이지만 MA 하락 중
        except (KeyError, TypeError, IndexError):
            pass
        
        # F2. 일목균형표 구름대 (10점)
        try:
            sa = row.get('ichimoku_senkou_a', 0) or 0
            sb = row.get('ichimoku_senkou_b', 0) or 0
            if sa > 0 and sb > 0:
                cloud_top = max(sa, sb)
                cloud_bottom = min(sa, sb)
                if row['close'] > cloud_top:
                    score += 10
                elif row['close'] > cloud_bottom:
                    score += 5
        except (KeyError, TypeError):
            pass
        
        return score
    
    # === G. 펀더멘털 필터 (50점) ===
    def score_fundamental(self, fd):
        """
        fd: stock_fundamental 테이블의 1행 (dict)
        Returns: 0~50점. 15점 미만이면 calculate_total_score에서 -1 반환 (탈락)
        """
        if fd is None:
            return 0
        
        score = 0.0
        
        # G1. PER 적정성 (10점)
        try:
            per = float(fd.get('per', 0) or 0)
            if per <= 0:
                pass  # 적자
            elif 5 <= per <= 15:
                score += 10
            elif per <= 30:
                score += 10 * (30 - per) / 15
        except (TypeError, ValueError):
            pass
        
        # G2. PBR 안전마진 (8점)
        try:
            pbr = float(fd.get('pbr', 0) or 0)
            if 0 < pbr < 1.0:
                score += 8
            elif pbr <= 2.0:
                score += 6
            elif pbr <= 3.0:
                score += 3
        except (TypeError, ValueError):
            pass
        
        # G3. ROE 수익성 (10점)
        try:
            roe = float(fd.get('roe', 0) or 0)
            if roe >= 15:
                score += 10
            elif roe >= 5:
                score += 10 * (roe - 5) / 10
            elif roe > 0:
                score += 2
        except (TypeError, ValueError):
            pass
        
        # G4. 시가총액 필터 (7점) — 억 단위
        try:
            mc = float(fd.get('market_cap', 0) or 0)
            if 500 <= mc <= 50000:
                score += 7
            elif 200 <= mc < 500:
                score += 3
            elif mc > 50000:
                score += 4
        except (TypeError, ValueError):
            pass
        
        # G5. 외인소진률 (5점)
        try:
            fr = float(fd.get('foreign_rate', 0) or 0)
            if 5 <= fr <= 60:
                score += 5
            elif fr > 60:
                score += 3
        except (TypeError, ValueError):
            pass
        
        # G6. 신용비율 (5점)
        try:
            cr = float(fd.get('credit_rate', 0) or 0)
            if cr < 3:
                score += 5
            elif cr < 5:
                score += 3
            elif cr < 10:
                score += 1
        except (TypeError, ValueError):
            pass
        
        # G7. 52주 레인지 위치 (5점)
        try:
            low_rate = abs(float(fd.get('low_250_rate', 0) or 0))
            if 20 <= low_rate <= 60:
                score += 5
            elif 10 <= low_rate < 20:
                score += 3
            elif low_rate > 60:
                score += 1
        except (TypeError, ValueError):
            pass
        
        return score
```

---

#### 작업 1-3: `cf.py` — 하단에 v2 변수 추가

**기존 변수는 절대 수정하지 마세요.** 파일 맨 끝에 아래를 추가합니다:

```python
# ===== v2 확장 Scoring 설정 (simul_num=2 전용) =====
# 250점 만점 중 최소 매수 기준점
v2_min_score = 120

# 펀더멘털 사전 필터 사용 여부
v2_fundamental_filter = True

# 펀더멘털 최소 점수 (50점 만점 중)
v2_fundamental_min_score = 15

# 펀더멘털 수집 주기 (일)
v2_fundamental_collect_interval = 7

# 동적 가중치 (ADX 기반)
v2_dynamic_weights = True
```

---

### Phase 2: 데이터 수집 확장

#### 작업 2-1: `library/collector_api.py` — OPT10001 수집 함수 추가

**기존 함수를 수정하지 않고**, 클래스에 아래 메서드를 추가합니다:

```python
def collect_stock_fundamental(self):
    """OPT10001 (주식기본정보요청)으로 전 종목 펀더멘털 수집
    → daily_buy_list DB의 stock_fundamental 테이블에 저장
    
    수집 항목: PER, EPS, ROE, PBR, EV, BPS, 매출액, 영업이익, 
              당기순이익, 시가총액, 외인소진률, 신용비율,
              유통주식, 유통비율, 250최고가대비율, 250최저가대비율
    
    ★ 주 1회만 실행: stock_fundamental 테이블의 updated_date를 체크하여
      cf.v2_fundamental_collect_interval일 이상 경과했을 때만 실행
    
    ★ API 부하: 전 종목 × TR_REQ_TIME_INTERVAL = 약 12분
    """
    # 구현:
    # 1. stock_fundamental 테이블 존재 여부 및 updated_date 체크
    # 2. stock_item_all에서 전 종목 코드 가져오기
    # 3. 종목별로 opt10001 TR 호출 (SetInputValue + CommRqData)
    # 4. OnReceiveTrData에서 수신 처리
    # 5. DataFrame으로 정리 → stock_fundamental 테이블에 to_sql
    pass
```

**TR 호출 방법** (기존 opt10081과 동일한 패턴 사용):
```python
# Input
self.dynamicCall("SetInputValue(QString, QString)", "종목코드", code)
# Request
self.dynamicCall("CommRqData(QString, QString, int, QString)",
                 "주식기본정보요청", "opt10001", 0, "0101")
# Output (OnReceiveTrData에서)
per = self.dynamicCall("GetCommData(QString, QString, int, QString)",
                       "opt10001", "주식기본정보요청", 0, "PER").strip()
```

#### 작업 2-2: `library/collector_api.py` — OPT20006 수집 함수 추가

```python
def collect_market_index(self):
    """OPT20006 (업종일봉차트조회)으로 코스피/코스닥 지수 일봉 수집
    → daily_craw DB의 kospi_index, kosdaq_index 테이블에 저장
    
    업종코드: "001" (코스피), "101" (코스닥)
    ★ TR 2번만 호출하므로 부하 무시 가능
    """
    pass
```

#### 작업 2-3: `collector_v3.py` — 추가 수집 호출

collector_v3.py의 수집 로직 끝부분에 v2 데이터 수집을 추가합니다:

```python
# 기존 수집 로직 이후에 추가:
# v2 확장 데이터 수집 (simul_num과 무관하게 항상 수집해도 됨)
try:
    self.collect_market_index()       # 코스피/코스닥 지수 (매일)
    self.collect_stock_fundamental()  # 펀더멘털 (주 1회 자동 체크)
except Exception as e:
    logger.warning(f"v2 확장 데이터 수집 실패 (무시하고 계속): {e}")
```

> 여기서 try/except로 감싸는 이유: v2 수집이 실패해도 기존 수집은 정상 완료되어야 합니다.

#### 작업 2-4: `library/daily_buy_list.py` — 추가 지표 컬럼

daily_buy_list 테이블에 v2 지표 컬럼을 추가합니다.
**기존 rsi14, bb_upper, bb_middle, bb_lower, atr14 컬럼은 그대로 유지**하고 뒤에 append합니다:

```
추가 컬럼:
macd, macd_signal, macd_histogram,
adx, plus_di, minus_di,
obv, mfi14, cmf20,
ichimoku_tenkan, ichimoku_kijun, ichimoku_senkou_a, ichimoku_senkou_b,
pivot, pivot_s1, pivot_s2, pivot_r1, pivot_r2,
candle_pattern_score, bb_bandwidth
```

**구현 방식**: daily_buy_list.py에서 종목별 데이터 처리하는 루프 내에서, 기존 rsi14 등을 계산하는 부분 아래에 새 지표 계산을 추가합니다. 데이터 부족 시 기본값 0.0을 사용합니다.

---

### Phase 3: 매매 로직 연결

#### 작업 3-1: `library/simulator_func_mysql.py` — variable_setting() 분기 추가

**기존 `else` 블록 바로 앞에** `elif self.simul_num == 2:` 분기를 삽입합니다:

```python
        elif self.simul_num == 2:
            # ===== v2: 확장 Scoring (250점 만점, 스윙 7~15일) =====
            self.simul_start_date = "20230102"
            
            # ★ 매수/매도 알고리즘 번호를 새로 할당 (기존과 겹치지 않게)
            self.db_to_realtime_daily_buy_list_num = 20
            self.sell_list_num = 20
            
            # 투자 설정
            self.start_invest_price = 10000000
            self.invest_unit = 3000000
            self.limit_money = 1000000
            self.sell_point = 10    # 스윙: 10% 익절
            self.losscut_point = -5  # 스윙: -5% 손절 (여유 있게)
            
            self.invest_limit_rate = 1.02
            self.invest_min_limit_rate = 0.97
            
            # 분별 시뮬레이션
            self.use_min = True
            self.only_nine_buy = False
            
            # v2 전용 플래그
            self.use_hybrid_v2 = True

        else:
            logger.error("해당 되는 알고리즘이 없습니다.")
            sys.exit(1)
```

#### 작업 3-2: `library/simulator_func_mysql.py` — db_to_realtime_daily_buy_list() 분기 추가

```python
        elif self.db_to_realtime_daily_buy_list_num == 20:
            # ===== v2 확장 scoring 기반 매수 종목 선정 =====
            from library.hybrid_strategy_v2 import HybridStrategyV2
            strategy_v2 = HybridStrategyV2()
            
            realtime_daily_buy_list = []
            
            # 1. daily_buy_list에서 어제(date_rows_yesterday) 데이터 전체 로드
            sql = "SELECT * FROM `" + date_rows_yesterday + "` a " \
                  "WHERE NOT exists (SELECT null FROM stock_konex b WHERE a.code=b.code) " \
                  "AND a.close < '%s'"
            candidates = self.engine_daily_buy_list.execute(sql % (self.invest_unit)).fetchall()
            
            # 2. stock_fundamental 로드 (있으면)
            fundamental_dict = {}
            try:
                fund_df = pd.read_sql("SELECT * FROM stock_fundamental", self.engine_daily_buy_list)
                fundamental_dict = {row['code']: row for _, row in fund_df.iterrows()}
            except:
                pass  # 테이블 없으면 펀더멘털 없이 진행
            
            # 3. 시장 지수 데이터 로드 (있으면)
            market_close = None
            try:
                market_df = pd.read_sql("SELECT * FROM kospi_index ORDER BY date DESC LIMIT 20",
                                       self.engine_daily_craw)
                market_close = market_df['close']
            except:
                pass
            
            # 4. 종목별 scoring
            scored_list = []
            for row in candidates:
                code = row['code']  # 또는 row[4] (인덱스는 실제 구조에 맞게)
                
                # 해당 종목의 최근 120일 daily_craw 데이터 로드
                try:
                    df_120 = pd.read_sql(
                        f"SELECT * FROM `{code}` ORDER BY date DESC LIMIT 120",
                        self.engine_daily_craw
                    )
                    df_120 = df_120.sort_values('date').reset_index(drop=True)
                except:
                    continue
                
                # fundamental data
                fd = fundamental_dict.get(code, None)
                
                # scoring
                total_score = strategy_v2.calculate_total_score(
                    row=row, df_120=df_120,
                    fundamental_data=fd, market_data=market_close
                )
                
                if total_score >= cf.v2_min_score:
                    scored_list.append((row, total_score))
            
            # 5. 점수 내림차순 정렬
            scored_list.sort(key=lambda x: x[1], reverse=True)
            realtime_daily_buy_list = [item[0] for item in scored_list]
```

> **주의**: `row`의 접근 방식(dict vs tuple)은 실제 코드의 fetchall() 반환 형태에 맞춰야 합니다. 기존 다른 `db_to_realtime_daily_buy_list_num` 분기의 패턴을 따라가세요.

#### 작업 3-3: `library/simulator_func_mysql.py` — get_sell_list() 분기 추가

```python
        elif self.sell_list_num == 20:
            # ===== v2 매도 조건 =====
            # 1차: 익절(sell_point) 또는 손절(losscut_point)
            # 2차: 5/20 이동평균 데드크로스
            sql = "SELECT code, rate, present_price, valuation_profit FROM all_item_db " \
                  "WHERE (sell_date = '%s') " \
                  "AND ((rate >= '%s') OR (rate <= '%s') OR (clo5 < clo20)) " \
                  "GROUP BY code"
            sell_list = self.engine_simulator.execute(
                sql % (0, self.sell_point, self.losscut_point)
            ).fetchall()
```

---

### Phase 4: 테스트

#### 테스트 1: 기존 동작 보존 확인
```python
# cf.py에서:
imi1_simul_num = 1  # 기존
# → 실행하여 기존과 동일하게 동작하는지 확인
```

#### 테스트 2: 새 알고리즘 동작 확인
```python
# cf.py에서:
imi1_simul_num = 2  # 신규
# → jackbot2_imi1 DB가 새로 생성되는지 확인
# → v2 scoring이 정상 계산되는지 확인
# → 매수/매도가 정상 실행되는지 확인
```

---

## 4. 파일별 수정 범위 요약

| 파일 | 수정 내용 | 기존 코드 영향 |
|------|---------|------------|
| `cf.py` | 파일 끝에 v2 변수 5개 추가 | ❌ 없음 |
| `library/technical_indicators.py` | 함수 12개 추가 (기존 함수 유지) | ❌ 없음 |
| `library/hybrid_strategy_v2.py` | **신규 파일 생성** | ❌ 없음 |
| `library/collector_api.py` | 메서드 2개 추가 | ❌ 없음 |
| `collector_v3.py` | 끝에 try/except로 v2 수집 호출 추가 | ⚠️ 최소 (실패해도 기존 영향 없음) |
| `library/daily_buy_list.py` | 지표 컬럼 추가 (기존 뒤에 append) | ⚠️ 최소 (하위 호환) |
| `library/simulator_func_mysql.py` | elif 분기 3개 추가 | ❌ 없음 (기존 분기 유지) |

---

## 5. 절대 주의사항

1. **기존 if/elif 분기 수정 금지**: `simul_num == 1` 블록, `db_to_realtime_daily_buy_list_num == 1` 블록, `sell_list_num == 1` 블록 등 기존 코드는 절대 건드리지 마세요.

2. **에러 격리**: 모든 v2 코드에서 기존 데이터에 접근할 때 try/except를 사용합니다. v2 전용 테이블(stock_fundamental, kospi_index 등)이 없어도 기존 시스템은 정상 동작해야 합니다.

3. **DB 분리**: simul_num=2는 `jackbot2_imi1` DB를 사용하므로 기존 `jackbot1_imi1` 데이터에 영향을 주지 않습니다.

4. **daily_buy_list 컬럼 호환성**: 추가 컬럼은 기존 컬럼 뒤에 append하므로, 기존 코드가 `SELECT *`나 위치 기반이 아닌 이름 기반으로 접근하면 문제없습니다. 만약 위치 기반(`row[7]` 등)으로 접근하는 코드가 있다면, 그 부분은 수정하지 말고 v2 분기에서만 이름 기반으로 접근하세요.

5. **API 호출 제한**: Kiwoom OpenAPI 초당 5회 제한. `cf.TR_REQ_TIME_INTERVAL` (현재 0.3초)을 준수하세요. OPT10001 전 종목 수집 시 약 12분 소요됩니다.

6. **구현 순서**: 반드시 Phase 1 → 2 → 3 → 4 순서로. Phase 1이 완성되지 않으면 Phase 3에서 import 에러가 발생합니다.
