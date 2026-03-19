"""
JackBot v2 확장 Scoring 시스템 — 안정적 자동매매 최적화판 (200점 만점)
simul_num=3 전용. 기존 hybrid_strategy.py (v1)는 수정하지 않음.

[변경 배경]
백테스트 결과 MDD 90.47% / 승률 41.8% 문제 해결을 위해
추세 따라가기를 강화하고 평균회귀(낙도 붙잡기)를 줄임.
갭하락 위험 종목은 변동성 패널티로 사전 차단.

카테고리별 배점:
  A. 모멘텀        50점 (거래량급증 20 + MA정배열 15 + MACD 5 + ATR돌파 10)
  B. 평균회귀      20점 ★감소 (RSI 10 + 볼린저하단 10)
  C. 추세강도      50점 ★증가 (ADX 25 + BB수렴 15 + DI방향 10)
  D. 거래량/수급   40점 ★증가 (OBV 15 + CMF 15 + 거래량-가격동조 10)
  E. 시장상대강도  30점 (RS 15 + BB스퀴즈 10 + 캔들패턴 5)
  F. 다중시간프레임 10점 ★감소 (주봉추세 10)
  합계            200점
  변동성 패널티   최대 -20점 (갭하락 위험 종목 사전 차단)
  과매수 패널티   최대 -15점 (MFI 과열 종목 차단)
  RSI추세 점수    -10 ~ +10점 (고점 소진 패널티 / 과매도 회복 보너스)
"""
from library.technical_indicators import calculate_rs_vs_market, calculate_rsi


class HybridStrategyV2:
    def __init__(self):
        self.min_total_score = 90        # cf.v2_min_score와 일치

    def calculate_total_score(self, row: dict, df_120, fundamental_data=None, market_data=None) -> float:
        """전체 200점 만점 scoring 메인 함수

        Parameters:
        -----------
        row : dict
            daily_buy_list 테이블에서 가져온 1행 (dict 변환 필수)
        df_120 : pd.DataFrame
            해당 종목의 최근 120일 daily_craw 데이터 (date 오름차순)
        fundamental_data : dict or None
            현재 사용 안 함 (백테스트는 dart ROE 보너스를 별도 적용)
        market_data : pd.Series or None
            코스피 지수 최근 20일 close

        Returns:
        --------
        float : 총점 (최대 200점, 변동성 패널티로 음수 가능)
        """
        # A. 모멘텀 (동적 가중치 적용)
        c_score, adx_val = self.score_trend_strength(row)
        mom_mult, mr_mult = self._get_dynamic_weights(adx_val)

        a_score = self.score_momentum(row, df_120) * mom_mult
        b_score = self.score_mean_reversion(row) * mr_mult
        d_score = self.score_volume_flow(row, df_120)
        e_score = self.score_market_context(row, df_120, market_data)
        f_score = self.score_multi_timeframe(row, df_120)

        # 리스크 패널티
        penalty = (self._volatility_penalty(row)
                   + self._overbought_penalty(row)
                   + self._rsi_slope_score(row, df_120))

        total = a_score + b_score + c_score + d_score + e_score + f_score + penalty
        return round(total, 2)

    # === A. 모멘텀 (50점) ===
    def score_momentum(self, row: dict, df_120) -> float:
        score = 0.0

        # A1. 거래량 급증 (20점) — vol5/vol20 비율 ★ 증가
        try:
            if row.get('vol20') and row['vol20'] > 0:
                vol_ratio = row['vol5'] / row['vol20']
                score += min(20, max(0, (vol_ratio - 1.0) * 40))
        except (KeyError, TypeError, ZeroDivisionError):
            pass

        # A2. MA 정배열 (15점) — clo5 > clo10 > clo20 > clo40 > clo60
        try:
            ma_keys = ['clo5', 'clo10', 'clo20', 'clo40', 'clo60']
            ma_vals = [row[k] for k in ma_keys if row.get(k) and row[k] > 0]
            if len(ma_vals) >= 2:
                pairs_ok = sum(1 for i in range(len(ma_vals))
                               for j in range(i + 1, len(ma_vals))
                               if ma_vals[i] > ma_vals[j])
                total_pairs = len(ma_vals) * (len(ma_vals) - 1) // 2
                if total_pairs > 0:
                    score += (pairs_ok / total_pairs) * 15
        except (KeyError, TypeError):
            pass

        # A3. MACD 신호 (5점) ★ 감소 (후행지표)
        try:
            if row.get('macd') and row.get('macd_signal'):
                if row['macd'] > row['macd_signal']:
                    score += 3
                if row.get('macd_histogram') and row['macd_histogram'] > 0:
                    score += 2
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

    # === B. 평균회귀 (20점) ★ 대폭 감소 ===
    def score_mean_reversion(self, row: dict) -> float:
        """낙도 붙잡기 위험 제거 — RSI + 볼린저만 유지"""
        score = 0.0

        # B1. RSI 과매도 (10점)
        try:
            rsi = row.get('rsi14', 50)
            if rsi and rsi <= 30:
                score += 10
            elif rsi and rsi <= 40:
                score += 10 * (40 - rsi) / 10
        except TypeError:
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

        return score

    # === C. 추세강도 (50점) ★ 대폭 증가 ===
    def score_trend_strength(self, row: dict):
        score = 0.0
        adx_val = row.get('adx', 0) or 0

        # C1. ADX (25점) ★ 증가 — 추세장 진입의 핵심
        if adx_val >= 25:
            score += 25
        elif adx_val >= 20:
            score += 25 * (adx_val - 20) / 5
        elif adx_val >= 15:
            score += 25 * (adx_val - 15) / 10 * 0.5

        # C2. 볼린저 밴드 수렴도 (15점) — bandwidth 낮을수록 폭발 임박
        try:
            bw = row.get('bb_bandwidth', 0) or 0
            if 0 < bw < 0.05:
                score += 15
            elif bw < 0.1:
                score += 15 * (0.1 - bw) / 0.05
        except TypeError:
            pass

        # C3. NEW: +DI > -DI 방향성 확인 (10점) ★ 신규
        try:
            plus_di = row.get('plus_di', 0) or 0
            minus_di = row.get('minus_di', 0) or 0
            if plus_di > 0 and minus_di > 0:
                if plus_di > minus_di:
                    # 방향성 차이가 클수록 더 높은 점수
                    di_gap = (plus_di - minus_di) / max(plus_di + minus_di, 1) * 100
                    score += min(10, di_gap * 0.5)
        except (KeyError, TypeError, ZeroDivisionError):
            pass

        return score, adx_val

    def _get_dynamic_weights(self, adx: float):
        """ADX에 따라 모멘텀/평균회귀 가중치 조절"""
        if adx >= 25:
            return 1.2, 0.8   # 추세장 → 모멘텀 강화
        elif adx <= 20:
            return 0.8, 1.2   # 횡보장 → 평균회귀 강화
        return 1.0, 1.0

    # === D. 거래량/수급 (40점) ★ 증가 ===
    def score_volume_flow(self, row: dict, df_120) -> float:
        score = 0.0

        # D1. OBV 추세 (15점) ★ 증가
        try:
            if df_120 is not None and len(df_120) >= 20 and 'obv' in df_120.columns:
                obv_ma20 = df_120['obv'].rolling(20).mean().iloc[-1]
                if obv_ma20 and row.get('obv', 0) > obv_ma20:
                    score += 15
        except (KeyError, TypeError, IndexError):
            pass

        # D2. CMF 매수압력 (15점) ★ 증가
        try:
            cmf = row.get('cmf20', 0) or 0
            if cmf > 0.1:
                score += 15
            elif cmf > 0:
                score += 15 * (cmf / 0.1)
        except TypeError:
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

    # === E. 시장 상대강도 (30점) — 재배분 ===
    def score_market_context(self, row: dict, df_120, market_data=None) -> float:
        score = 0.0

        # E1. RS vs 코스피 (15점) ★ 증가 — 시장보다 강한 종목만
        try:
            if (market_data is not None and len(market_data) >= 20
                    and df_120 is not None and len(df_120) >= 20):
                stock_ret = ((df_120['close'].iloc[-1] - df_120['close'].iloc[-20])
                             / df_120['close'].iloc[-20])
                market_ret = ((market_data.iloc[-1] - market_data.iloc[-20])
                              / market_data.iloc[-20])
                rs = calculate_rs_vs_market(stock_ret, market_ret)
                if rs > 1.1:
                    score += 15
                elif rs > 1.0:
                    score += 15 * (rs - 1.0) / 0.1
        except (KeyError, TypeError, IndexError, ZeroDivisionError):
            pass

        # E2. 볼린저 스퀴즈 (10점)
        try:
            bw = row.get('bb_bandwidth', 0) or 0
            if (df_120 is not None and 'bb_bandwidth' in df_120.columns
                    and len(df_120) >= 20):
                bw_min_20 = df_120['bb_bandwidth'].tail(20).min()
                if bw_min_20 and bw > bw_min_20 and bw < bw_min_20 * 1.5:
                    if row.get('close', 0) > row.get('bb_middle', 0):
                        score += 10
                    else:
                        score += 5
        except (KeyError, TypeError):
            pass

        # E3. 캔들 패턴 (5점) ★ 감소
        try:
            score += min(5, row.get('candle_pattern_score', 0) or 0)
        except TypeError:
            pass

        return score

    # === F. 다중 시간프레임 (10점) ★ 대폭 감소 ===
    def score_multi_timeframe(self, row: dict, df_120) -> float:
        score = 0.0

        # F1. 주봉 추세 일치 (10점) — 25일 MA(≈5주) 위 + 상승
        try:
            if df_120 is not None and len(df_120) >= 30:
                ma25 = df_120['close'].rolling(25).mean()
                if row.get('close', 0) > ma25.iloc[-1]:
                    if ma25.iloc[-1] > ma25.iloc[-6]:
                        score += 10  # MA 위 + MA 자체도 상승
                    else:
                        score += 5   # MA 위이지만 MA 하락 중
        except (KeyError, TypeError, IndexError):
            pass

        # F2. 일목균형표: 제거 (복잡하고 장기 지표 — 단기 자동매매엔 부적합)

        return score

    # === 리스크 패널티 ===
    def _volatility_penalty(self, row: dict) -> float:
        """갭하락 위험이 높은 고변동성 종목에 패널티 적용"""
        try:
            atr14 = row.get('atr14', 0) or 0
            close = row.get('close', 1) or 1
            atr_rate = atr14 / close
            if atr_rate > 0.08:    # ATR > 8% (초고변동성 → 갭하락 위험)
                return -20
            elif atr_rate > 0.05:  # ATR > 5%
                return -10
        except (TypeError, ZeroDivisionError):
            pass
        return 0.0

    def _overbought_penalty(self, row: dict) -> float:
        """MFI 과매수 패널티 — 단기 자금 과열로 반전 위험이 높은 종목 차단"""
        try:
            mfi = row.get('mfi14', 0) or 0
            if mfi > 90:   # 극단적 과매수
                return -15
            elif mfi > 80: # 과매수
                return -8
        except TypeError:
            pass
        return 0.0

    def _rsi_slope_score(self, row: dict, df_120) -> float:
        """RSI 동적 꺽임 감지 — 실제 고점/저점 기준 일당 변화율로 판단

        고점 꺽임 패널티 (RSI>60 고점 이후 하락 중):
          일당 -3pt 이상  → -15pt
          일당 -1.5pt 이상 → -8pt

        저점 꺽임 보너스 (RSI<40 저점 이후 상승 중):
          일당 +2pt 이상  → +10pt
          일당 +1pt 이상  →  +5pt
        """
        try:
            if df_120 is None or len(df_120) < 30:
                return 0.0

            # Wilder's EMA 방식으로 rolling RSI(14) 계산 — DB rsi14 와 동일
            close = df_120['close'].reset_index(drop=True)
            delta = close.diff()
            gain = delta.where(delta > 0, 0.0)
            loss = -delta.where(delta < 0, 0.0)
            avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
            rs = avg_gain / avg_loss.replace(0, float('nan'))
            rsi_series = (100 - (100 / (1 + rs))).fillna(50)

            # 최근 16개 RSI (오늘 포함) — 고점/저점 탐색은 오늘 제외 15일치
            if len(rsi_series) < 16:
                return 0.0

            recent = rsi_series.iloc[-16:].reset_index(drop=True)  # index 0~15
            rsi_now = float(recent.iloc[-1])                        # index 15 = 오늘
            search  = recent.iloc[:-1]                              # index 0~14 = 과거 15일

            # 고점 꺽임: 최근 15일 내 RSI>60 고점 → 오늘까지 하락 중
            peak_idx = int(search.idxmax())
            peak_rsi = float(search.iloc[peak_idx])
            days_since_peak = 15 - peak_idx          # 고점으로부터 오늘까지 거래일 수
            fall_from_peak  = rsi_now - peak_rsi     # 음수 = 하락

            if peak_rsi > 60 and fall_from_peak < 0 and days_since_peak > 0:
                fall_rate = fall_from_peak / days_since_peak
                if fall_rate <= -3.0:
                    return -15
                elif fall_rate <= -1.5:
                    return -8

            # 저점 꺽임 보너스: 최근 15일 내 RSI<40 저점 → 오늘까지 상승 중
            trough_idx = int(search.idxmin())
            trough_rsi = float(search.iloc[trough_idx])
            days_since_trough = 15 - trough_idx
            rise_from_trough  = rsi_now - trough_rsi  # 양수 = 상승

            if trough_rsi < 40 and rise_from_trough > 0 and days_since_trough > 0:
                rise_rate = rise_from_trough / days_since_trough
                if rise_rate >= 2.0:
                    return 10
                elif rise_rate >= 1.0:
                    return 5

        except Exception:
            pass
        return 0.0
