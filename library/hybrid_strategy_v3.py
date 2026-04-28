"""
JackBot v3 Scoring System
simul_num=4: BreakoutStrategyV3  (Strategy A — 돌파 초입)
simul_num=5: ReversalStrategyV3  (Strategy B — 저점 반등)
simul_num=6: 두 전략 중 점수 높은 쪽 선택 (A+B 혼합)

[simul_num=3과의 차이]
simul_num=3 문제: MA정배열 + 높은 ADX = 이미 수개월 달려버린 종목 → 다음날 아침 고점 매수
v3 해결책:
  A: 횡보 후 오늘 막 돌파한 종목 포착 (초입) — 아직 MA 완전 정배열 전, ADX 낮다가 올라오는 중
  B: 낙폭 과대 → RSI 바닥 확인 후 반등 시작한 종목 포착 — 아직 하락 중 진입 아님

[배점]
  Strategy A: 200pt 만점
    돌파강도(d1_diff+거래량) 70 + BB돌파위치 40 + MACD전환초입 30
    + RSI50돌파초입 30 + 단기MA정렬시작 20 + ADX초입 10
  Strategy B: 200pt 만점
    RSI저점깊이+반등강도 70 + BB하단반등 30 + 반등거래량 30
    + BB현재위치 25 + MACD전환 25 + 캔들패턴 20

[매도 파라미터 — exit_strategy.py 연동]
  A: 손절 -4% / 트레일링 활성화 +3% / ATR배수 2.5 / 시간청산 7일
  B: 손절 -2.5% / 트레일링 활성화 +4% / ATR배수 1.5 / 시간청산 6일
"""


def _calc_rsi_series(df_120):
    """df_120(daily_craw)에서 Wilder's EMA 방식 RSI 시계열 계산 — v2와 동일한 방식"""
    try:
        close = df_120['close'].reset_index(drop=True)
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1 / 14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, float('nan'))
        return (100 - (100 / (1 + rs))).fillna(50)
    except Exception:
        return None


def _calc_bb_lower_series(df_120):
    """df_120에서 볼린저 하단밴드 시계열 계산"""
    try:
        close = df_120['close']
        bb_middle = close.rolling(20).mean()
        bb_std = close.rolling(20).std()
        return bb_middle - 2 * bb_std
    except Exception:
        return None


# ============================================================
# Strategy A: 돌파 초입 (BreakoutStrategyV3)
# ============================================================

class BreakoutStrategyV3:
    """
    횡보/압축 후 오늘 저항선 돌파 + 거래량 급증 → 상승 추세 시작 초입 매수

    자동 탈락 조건 (auto_reject):
      - d1_diff_rate < 1.5%       : 오늘 돌파 없음
      - vol5/vol20 < 1.2          : 거래량 급증 없음
      - close ≤ bb_middle         : 밴드 하단에 위치
      - RSI > 68                  : 이미 과열
      - ADX > 33                  : 성숙한 추세 (늦은 진입 위험)
      - 완전 MA정배열              : 이미 수개월 달려버린 종목
    """

    def calculate_total_score(self, row: dict, df_120, market_data=None) -> dict:
        """
        Returns
        -------
        dict with keys:
          total, score_a, score_b, score_c, score_d, score_e, score_f,
          score_penalty, auto_reject, reject_reason, strategy_type
        """
        base = {
            'total': 0.0, 'score_a': 0.0, 'score_b': 0.0, 'score_c': 0.0,
            'score_d': 0.0, 'score_e': 0.0, 'score_f': 0.0,
            'score_penalty': 0.0, 'auto_reject': False,
            'reject_reason': '', 'strategy_type': 'A'
        }

        reject = self._auto_reject(row)
        if reject:
            base['auto_reject'] = True
            base['reject_reason'] = reject
            base['total'] = -999.0
            return base

        # score_a: 돌파 강도 (d1_diff_rate + 거래량 급증) — 70pt
        sa = self._score_breakout_strength(row)
        # score_b: BB 돌파 위치 + 단기MA 정렬 시작 — 60pt
        sb = self._score_bb_and_ma(row)
        # score_c: ADX 초입 — 10pt
        sc = self._score_adx_early(row)
        # score_d: MACD 전환 초입 (df_120 필요) — 30pt
        sd = self._score_macd_crossover(row, df_120)
        # score_e: RSI 50 상향 돌파 초입 (df_120 필요) — 30pt
        se = self._score_rsi_cross50(row, df_120)
        # score_f: 미사용
        sf = 0.0

        penalty = self._penalty(row)

        total = sa + sb + sc + sd + se + sf + penalty

        base.update({
            'total':         round(total, 2),
            'score_a':       round(sa, 2),
            'score_b':       round(sb, 2),
            'score_c':       round(sc, 2),
            'score_d':       round(sd, 2),
            'score_e':       round(se, 2),
            'score_f':       round(sf, 2),
            'score_penalty': round(penalty, 2),
        })
        return base

    def _auto_reject(self, row: dict):
        try:
            d1 = float(row.get('d1_diff_rate') or 0)
            if d1 < 1.5:
                return 'd1_diff_rate < 1.5% (돌파 없음)'
        except (TypeError, ValueError):
            pass

        try:
            vol5 = float(row.get('vol5') or 0)
            vol20 = float(row.get('vol20') or 1)
            if vol20 > 0 and vol5 / vol20 < 1.2:
                return 'vol_ratio < 1.2 (거래량 급증 없음)'
        except (TypeError, ZeroDivisionError):
            pass

        try:
            close = float(row.get('close') or 0)
            bb_mid = float(row.get('bb_middle') or 0)
            if bb_mid > 0 and close <= bb_mid:
                return 'close <= bb_middle (밴드 하단)'
        except (TypeError, ValueError):
            pass

        try:
            rsi = float(row.get('rsi14') or 50)
            if rsi > 68:
                return f'RSI {rsi:.1f} > 68 (과열)'
        except (TypeError, ValueError):
            pass

        try:
            adx = float(row.get('adx') or 0)
            if adx > 33:
                return f'ADX {adx:.1f} > 33 (성숙 추세)'
        except (TypeError, ValueError):
            pass

        # 완전 MA정배열 체크 — 이미 수개월 달려버린 종목
        try:
            ma_vals = [float(row.get(k) or 0)
                       for k in ('clo5', 'clo10', 'clo20', 'clo40', 'clo60')]
            if all(v > 0 for v in ma_vals):
                if all(ma_vals[i] > ma_vals[i + 1] for i in range(len(ma_vals) - 1)):
                    return '완전 MA정배열 (이미 늦은 진입)'
        except (TypeError, ValueError):
            pass

        return None

    def _score_breakout_strength(self, row: dict) -> float:
        """d1_diff_rate(35pt) + 거래량급증(35pt) = 70pt"""
        score = 0.0

        # d1_diff_rate: 2.5~5% 구간 만점
        try:
            d1 = float(row.get('d1_diff_rate') or 0)
            if 1.5 <= d1 < 2.5:
                score += 35 * (d1 - 1.5) / 1.0
            elif 2.5 <= d1 <= 5.0:
                score += 35
            elif 5.0 < d1 <= 8.0:
                score += 35 * (8.0 - d1) / 3.0  # 5~8% 구간 감점 (갭 과대)
        except (TypeError, ValueError):
            pass

        # 거래량 급증: vol5/vol20
        try:
            vol5 = float(row.get('vol5') or 0)
            vol20 = float(row.get('vol20') or 1)
            if vol20 > 0:
                ratio = vol5 / vol20
                if ratio >= 2.0:
                    score += 35
                elif ratio >= 1.2:
                    score += 35 * (ratio - 1.2) / 0.8
        except (TypeError, ZeroDivisionError):
            pass

        return score

    def _score_bb_and_ma(self, row: dict) -> float:
        """BB 돌파 위치(40pt) + 단기MA 정렬 시작(20pt) = 60pt"""
        score = 0.0

        # BB 위치: close > bb_upper 이면 만점
        try:
            close = float(row.get('close') or 0)
            bb_upper = float(row.get('bb_upper') or 0)
            bb_middle = float(row.get('bb_middle') or 0)
            if bb_upper > bb_middle > 0:
                if close >= bb_upper:
                    score += 40
                elif close > bb_middle:
                    # bb_middle ~ bb_upper 구간 선형
                    score += 40 * (close - bb_middle) / (bb_upper - bb_middle)
        except (TypeError, ZeroDivisionError):
            pass

        # 단기MA 정렬 시작: clo5 > clo20 (10pt) + clo20 > yes_clo20 (10pt)
        try:
            clo5 = float(row.get('clo5') or 0)
            clo20 = float(row.get('clo20') or 0)
            if clo5 > 0 and clo20 > 0 and clo5 > clo20:
                score += 10
        except (TypeError, ValueError):
            pass

        try:
            clo20 = float(row.get('clo20') or 0)
            yes_clo20 = float(row.get('yes_clo20') or 0)
            if clo20 > 0 and yes_clo20 > 0 and clo20 > yes_clo20:
                score += 10
        except (TypeError, ValueError):
            pass

        return score

    def _score_adx_early(self, row: dict) -> float:
        """ADX 초입 범위 (18~28): 10pt"""
        try:
            adx = float(row.get('adx') or 0)
            if 18 <= adx <= 28:
                return 10.0
            elif 15 <= adx < 18:
                return 10 * (adx - 15) / 3
            elif 28 < adx <= 33:
                return 10 * (33 - adx) / 5
        except (TypeError, ValueError):
            pass
        return 0.0

    def _score_macd_crossover(self, row: dict, df_120) -> float:
        """MACD 전환 초입: histogram>0(15pt) + 최근 5일 내 음→양 전환(15pt) = 30pt"""
        score = 0.0

        try:
            hist = float(row.get('macd_histogram') or 0)
            if hist > 0:
                score += 15

                # 최근 5일 내 histogram이 음수였는지 확인 (신선한 크로스오버)
                if df_120 is not None and len(df_120) >= 6 and 'macd_histogram' in df_120.columns:
                    recent_hist = df_120['macd_histogram'].iloc[-6:-1]
                    if any(float(v) < 0 for v in recent_hist if v == v):
                        score += 15
        except (TypeError, ValueError, KeyError):
            pass

        return score

    def _score_rsi_cross50(self, row: dict, df_120) -> float:
        """RSI 50 상향 돌파 초입: RSI 50~62 구간(20pt) + 최근 5일 내 50 하향에서 전환(10pt) = 30pt"""
        score = 0.0

        try:
            rsi_now = float(row.get('rsi14') or 50)

            if 50 <= rsi_now <= 62:
                # 50~58 구간 만점, 58~62 구간 감소
                if rsi_now <= 58:
                    score += 20
                else:
                    score += 20 * (62 - rsi_now) / 4

            elif 45 <= rsi_now < 50:
                score += 20 * (rsi_now - 45) / 5  # 막 50 돌파 전 준비 구간

        except (TypeError, ValueError):
            pass

        # 최근 5일 내 RSI가 50 이하였는지 확인 (신선한 50 크로스오버)
        try:
            if df_120 is not None and len(df_120) >= 6:
                rsi_series = _calc_rsi_series(df_120)
                if rsi_series is not None and len(rsi_series) >= 6:
                    recent_rsi = rsi_series.iloc[-6:-1]
                    if any(float(v) < 50 for v in recent_rsi):
                        score += 10
        except Exception:
            pass

        return score

    def _penalty(self, row: dict) -> float:
        penalty = 0.0

        # RSI > 65: 과열 징후
        try:
            rsi = float(row.get('rsi14') or 50)
            if rsi > 65:
                penalty -= 15
        except (TypeError, ValueError):
            pass

        # ADX > 30: 성숙 추세 진입 위험
        try:
            adx = float(row.get('adx') or 0)
            if adx > 30:
                penalty -= 10
        except (TypeError, ValueError):
            pass

        # 변동성 패널티 (v2와 동일)
        try:
            atr14 = float(row.get('atr14') or 0)
            close = float(row.get('close') or 1)
            if close > 0:
                atr_rate = atr14 / close
                if atr_rate > 0.07:
                    penalty -= 15
                elif atr_rate > 0.05:
                    penalty -= 8
        except (TypeError, ZeroDivisionError):
            pass

        return penalty


# ============================================================
# Strategy B: 저점 반등 (ReversalStrategyV3)
# ============================================================

class ReversalStrategyV3:
    """
    낙폭 과대 → RSI 바닥 확인 + 반등 시작 → 단기 회복 구간 포착

    자동 탈락 조건 (auto_reject):
      - RSI today < RSI yesterday    : 아직 하락 중 (핵심 — 낙도 붙잡기 방지)
      - RSI > 55                     : 이미 많이 회복됨
      - 최근 15일 내 trough RSI > 42 : 과매도 구간 진입 없음
    """

    def calculate_total_score(self, row: dict, df_120, market_data=None) -> dict:
        base = {
            'total': 0.0, 'score_a': 0.0, 'score_b': 0.0, 'score_c': 0.0,
            'score_d': 0.0, 'score_e': 0.0, 'score_f': 0.0,
            'score_penalty': 0.0, 'auto_reject': False,
            'reject_reason': '', 'strategy_type': 'B'
        }

        # RSI 시계열이 필요하므로 먼저 계산
        rsi_series = None
        if df_120 is not None and len(df_120) >= 30:
            rsi_series = _calc_rsi_series(df_120)

        reject = self._auto_reject(row, rsi_series)
        if reject:
            base['auto_reject'] = True
            base['reject_reason'] = reject
            base['total'] = -999.0
            return base

        # score_a: RSI 저점 깊이 + 반등 강도 — 70pt
        sa = self._score_rsi_reversal(rsi_series)
        # score_b: BB 하단 반등 + BB 현재 위치 — 55pt
        sb = self._score_bb_bounce(row, df_120)
        # score_c: 반등 거래량 — 30pt
        sc = self._score_reversal_volume(row)
        # score_d: MACD 전환 — 25pt
        sd = self._score_macd(row)
        # score_e: 캔들 패턴 — 20pt
        se = self._score_candle(row)
        # score_f: 미사용
        sf = 0.0

        penalty = self._penalty(row)

        total = sa + sb + sc + sd + se + sf + penalty

        base.update({
            'total':         round(total, 2),
            'score_a':       round(sa, 2),
            'score_b':       round(sb, 2),
            'score_c':       round(sc, 2),
            'score_d':       round(sd, 2),
            'score_e':       round(se, 2),
            'score_f':       round(sf, 2),
            'score_penalty': round(penalty, 2),
        })
        return base

    def _auto_reject(self, row: dict, rsi_series) -> str:
        # RSI 아직 하락 중 — 가장 중요한 필터
        try:
            rsi_now = float(row.get('rsi14') or 50)
            if rsi_series is not None and len(rsi_series) >= 2:
                rsi_yesterday = float(rsi_series.iloc[-2])
                if rsi_now < rsi_yesterday:
                    return f'RSI 하락 중 ({rsi_yesterday:.1f} → {rsi_now:.1f})'
            if rsi_now > 55:
                return f'RSI {rsi_now:.1f} > 55 (이미 충분히 회복)'
        except (TypeError, ValueError):
            pass

        # 최근 15일 내 과매도 구간(RSI<42) 미진입 시 탈락
        try:
            if rsi_series is not None and len(rsi_series) >= 16:
                recent_search = rsi_series.iloc[-16:-1]
                trough_rsi = float(recent_search.min())
                if trough_rsi > 42:
                    return f'최근 15일 RSI 최저 {trough_rsi:.1f} > 42 (과매도 없음)'
        except Exception:
            pass

        return None

    def _score_rsi_reversal(self, rsi_series) -> float:
        """RSI 저점 깊이(35pt) + 반등 강도(35pt) = 70pt"""
        score = 0.0
        if rsi_series is None or len(rsi_series) < 16:
            return score

        try:
            recent = rsi_series.iloc[-16:].reset_index(drop=True)
            rsi_now = float(recent.iloc[-1])
            search = recent.iloc[:-1]  # 과거 15일

            trough_idx = int(search.idxmin())
            trough_rsi = float(search.iloc[trough_idx])
            days_since_trough = 15 - trough_idx
            rise_from_trough = rsi_now - trough_rsi

            # 저점 깊이 (35pt)
            if trough_rsi <= 25:
                score += 35
            elif trough_rsi <= 30:
                score += 25
            elif trough_rsi <= 35:
                score += 15
            elif trough_rsi <= 42:
                score += 8

            # 반등 강도 (35pt)
            if rise_from_trough > 0 and days_since_trough > 0:
                rise_rate = rise_from_trough / days_since_trough
                if rise_rate >= 2.0:
                    score += 35
                elif rise_rate >= 1.5:
                    score += 28
                elif rise_rate >= 1.0:
                    score += 20
                elif rise_rate >= 0.5:
                    score += 10
                else:
                    score += 5  # 상승 중이긴 함

        except Exception:
            pass

        return score

    def _score_bb_bounce(self, row: dict, df_120) -> float:
        """BB 하단 반등(30pt) + BB 현재 위치(25pt) = 55pt"""
        score = 0.0

        # BB 현재 위치: (close - bb_lower) / (bb_upper - bb_lower) → 0.15~0.40 구간 만점
        try:
            close = float(row.get('close') or 0)
            bb_upper = float(row.get('bb_upper') or 0)
            bb_lower = float(row.get('bb_lower') or 0)
            bb_range = bb_upper - bb_lower
            if bb_range > 0:
                pos = (close - bb_lower) / bb_range
                if 0.15 <= pos <= 0.40:
                    score += 25
                elif 0.10 <= pos < 0.15:
                    score += 25 * (pos - 0.10) / 0.05
                elif 0.40 < pos <= 0.55:
                    score += 25 * (0.55 - pos) / 0.15
        except (TypeError, ZeroDivisionError):
            pass

        # BB 하단 이탈 후 복귀: 최근 5일 내 종가 or 저가가 bb_lower 아래였는지 확인
        try:
            if df_120 is not None and len(df_120) >= 25:
                bb_lower_series = _calc_bb_lower_series(df_120)
                if bb_lower_series is not None:
                    # 오늘 제외 최근 5거래일 확인
                    recent_close = df_120['close'].iloc[-6:-1].values
                    recent_low = df_120['low'].iloc[-6:-1].values
                    recent_bb_l = bb_lower_series.iloc[-6:-1].values
                    penetrated = any(
                        (recent_close[i] <= recent_bb_l[i] or recent_low[i] <= recent_bb_l[i])
                        for i in range(len(recent_close))
                        if recent_bb_l[i] == recent_bb_l[i]  # nan 제외
                    )
                    if penetrated:
                        score += 30
                    else:
                        # bb_lower 근처였다면 부분 점수
                        bb_lower_now = float(row.get('bb_lower') or 0)
                        close_now = float(row.get('close') or 0)
                        if bb_lower_now > 0 and close_now < bb_lower_now * 1.05:
                            score += 15
        except Exception:
            pass

        return score

    def _score_reversal_volume(self, row: dict) -> float:
        """반등 거래량 (vol5/vol20): 30pt"""
        try:
            vol5 = float(row.get('vol5') or 0)
            vol20 = float(row.get('vol20') or 1)
            if vol20 > 0:
                ratio = vol5 / vol20
                if ratio >= 1.8:
                    return 30.0
                elif ratio >= 1.5:
                    return 25.0
                elif ratio >= 1.2:
                    return 15.0
                elif ratio >= 1.0:
                    return 5.0
        except (TypeError, ZeroDivisionError):
            pass
        return 0.0

    def _score_macd(self, row: dict) -> float:
        """MACD 전환 신호: 25pt"""
        score = 0.0
        try:
            hist = float(row.get('macd_histogram') or 0)
            macd = float(row.get('macd') or 0)
            signal = float(row.get('macd_signal') or 0)
            if hist > 0 and macd > signal:
                score += 25
            elif hist > 0:
                score += 15
            elif macd > signal:
                score += 10
        except (TypeError, ValueError):
            pass
        return score

    def _score_candle(self, row: dict) -> float:
        """캔들 패턴 점수: 20pt (망치형, 도지 등 반전 패턴)"""
        try:
            return min(20.0, float(row.get('candle_pattern_score') or 0))
        except (TypeError, ValueError):
            return 0.0

    def _penalty(self, row: dict) -> float:
        penalty = 0.0

        # RSI > 53: 회복 구간 상단 접근 (auto_reject가 >55 이므로 53~55 구간 경고)
        try:
            rsi = float(row.get('rsi14') or 50)
            if rsi > 53:
                penalty -= 10
        except (TypeError, ValueError):
            pass

        # 변동성 패널티
        try:
            atr14 = float(row.get('atr14') or 0)
            close = float(row.get('close') or 1)
            if close > 0:
                atr_rate = atr14 / close
                if atr_rate > 0.08:
                    penalty -= 10
        except (TypeError, ZeroDivisionError):
            pass

        return penalty
