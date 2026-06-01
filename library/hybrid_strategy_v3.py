"""
JackBot v3 Scoring System
simul_num=4: BreakoutStrategyV3  (Strategy A — 돌파 초입)
simul_num=5: ReversalStrategyV3  (Strategy B — RSI 사이클 중장기)
simul_num=6: 두 전략 중 점수 높은 쪽 선택 (A+B 혼합)

[simul_num=3과의 차이]
simul_num=3 문제: MA정배열 + 높은 ADX = 이미 수개월 달려버린 종목 → 다음날 아침 고점 매수
v3 해결책:
  A: 횡보 후 오늘 막 돌파한 종목 포착 (초입) — 아직 MA 완전 정배열 전, ADX 낮다가 올라오는 중
  B: RSI 과매도 바닥 패턴 확인 후 중장기 사이클 상승 구간 포착

[배점]
  Strategy A: 200pt 만점  (v3.2 — 상관분석 심층 연구 기반 재조정 2026-05-29)
    score_a. 돌파강도 50pt  — d1_diff+거래량, 역U자 (피크 2.5~4% / 1.5~3x)
             ※ penalty: d1_diff>5% -10pt, vol_ratio>4.5x -8pt (갭 과대 = 다음날 역전 위험)
    score_b. BB돌파위치+단기MA 60pt
    score_c. ADX방향성 10pt — ADX초입(15~28) + +DI>-DI + ADX상승 확인 (df_120 활용)
    score_d. MACD전환초입 30pt
    score_e. RSI50돌파초입 30pt
    score_f. BB활성도 20pt — bb_bandwidth 기반 실거래 품질 (구: 압축도, 방향 역전)
             ※ 상관분석(r=-0.0945): 타이트BB=가짜돌파/유동성부족, 활성BB=실매수세

  Strategy B: 200pt 만점  (v3.2 — 상관분석 심층 연구 기반 재조정 2026-05-29)
    score_a. RSI 신호 65pt       (BFS 25 + 다이버전스 8 + RSI9/14크로스 32)
    score_b. 펀더멘털 품질 40pt   (실전 전용, PER/ROA)
    score_c. 장기 추세 55pt      (MA120 장기추세 28 + RSI 50선 접근 27)  ← 상향 (r=+0.081)
    score_d. BB 사이클 위치 10pt  (BB하단터치 6 + BB현재위치 4)  ← 추가 하향 (r=+0.011)
    score_e. 거래량+MACD 15pt
    score_f. 회복 모멘텀 15pt    (RSI 저점 이후 일평균 상승속도) ← 상향 (r=+0.1316 최고)

[매도 전략 — sell_list_num=31]
  B: 하드SL -5% / 트레일링스탑(max_high_pct>=3, rate<=max_high_pct-5) / 45일 시간청산
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


def _calc_adx_series(df_120):
    """df_120(daily_craw)에서 ADX/+DI/-DI 시계열 계산.
    Returns (adx_series, plus_di_series, minus_di_series) 또는 (None, None, None).
    """
    try:
        from library.technical_indicators import calculate_adx
        adx_s, plus_di_s, minus_di_s = calculate_adx(
            df_120['high'], df_120['low'], df_120['close']
        )
        return adx_s, plus_di_s, minus_di_s
    except Exception:
        return None, None, None


def _calc_rsi9_series(df_120):
    """RSI 9일 시계열 (EWM alpha=1/9) — RSI 9/14 크로스 신호용"""
    try:
        close = df_120['close'].reset_index(drop=True)
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1 / 9, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / 9, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, float('nan'))
        return (100 - (100 / (1 + rs))).fillna(50)
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

        # score_a: 돌파 강도 — 50pt (역U자: d1_diff 2.5~4% 피크, vol_ratio 1.5~3x 피크)
        sa = self._score_breakout_strength(row)
        # score_b: BB 돌파 위치 + 단기MA 정렬 시작 — 60pt
        sb = self._score_bb_and_ma(row)
        # score_c: ADX 방향성 초입 (df_120 필요) — 10pt
        sc = self._score_adx_early(row, df_120)
        # score_d: MACD 전환 초입 (df_120 필요) — 30pt
        sd = self._score_macd_crossover(row, df_120)
        # score_e: RSI 50 상향 돌파 초입 (df_120 필요) — 30pt
        se = self._score_rsi_cross50(row, df_120)
        # score_f: BB 압축도 — 20pt (bb_bandwidth 기반 횡보 압축 품질)
        sf = self._score_compression(row)

        penalty = self._penalty(row, score_a=sa)

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
        """돌파 강도 — 역U자형 (피크 구간에서 만점, 과도하면 감점)

        d1_diff_rate (25pt):
          1.5~2.5% : 선형 상승 (0 → 25pt)
          2.5~4.0% : 만점 25pt  ← 적당한 돌파
          4.0~6.0% : 선형 하강 (25 → 0pt)
          6.0% 초과: 0pt (이미 갭 급등, 다음날 추격 위험)

        거래량 급증 vol5/vol20 (25pt):
          1.2~1.5x : 선형 상승 (0 → 25pt)
          1.5~3.0x : 만점 25pt  ← 건강한 수요 급증
          3.0~5.0x : 선형 하강 (25 → 0pt)
          5.0x 초과: 0pt (투기성 단타 급등 의심)

        합계: 50pt
        """
        score = 0.0

        # d1_diff_rate: 2.5~4.0% 피크, 역U자
        try:
            d1 = float(row.get('d1_diff_rate') or 0)
            if 1.5 <= d1 < 2.5:
                score += 25 * (d1 - 1.5) / 1.0        # 0 → 25pt
            elif 2.5 <= d1 <= 4.0:
                score += 25                             # 만점
            elif 4.0 < d1 <= 6.0:
                score += 25 * (6.0 - d1) / 2.0        # 25 → 0pt
            # d1 > 6.0: 0pt (갭 과대, 이미 오른 종목)
        except (TypeError, ValueError):
            pass

        # 거래량 급증: 1.5~3.0x 피크, 역U자
        try:
            vol5 = float(row.get('vol5') or 0)
            vol20 = float(row.get('vol20') or 1)
            if vol20 > 0:
                ratio = vol5 / vol20
                if 1.2 <= ratio < 1.5:
                    score += 25 * (ratio - 1.2) / 0.3  # 0 → 25pt
                elif 1.5 <= ratio <= 3.0:
                    score += 25                          # 만점
                elif 3.0 < ratio <= 5.0:
                    score += 25 * (5.0 - ratio) / 2.0  # 25 → 0pt
                # ratio > 5.0: 0pt (투기성 급등)
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

    def _score_adx_early(self, row: dict, df_120) -> float:
        """ADX 방향성 초입 — 10pt

        기존 문제: ADX 레벨(18~28)만 확인 → -DI>+DI(하락추세)도 점수 부여 (r=+0.019)
        개선:
          ① +DI > -DI 필수 (row의 plus_di/minus_di 사용)
          ② ADX 15~28 구간 기본 7pt
          ③ df_120으로 ADX 시계열 재계산 → 5일 전 대비 상승 중이면 +3pt (최대 10pt)

        조건 미달 시 0pt:
          - plus_di ≤ minus_di (하락 방향)
          - ADX < 15 (추세 없음)
          - ADX > 30 (성숙 추세, penalty와 중복)
        """
        try:
            adx      = float(row.get('adx')      or 0)
            plus_di  = float(row.get('plus_di')  or 0)
            minus_di = float(row.get('minus_di') or 0)
        except (TypeError, ValueError):
            return 0.0

        # ① 방향성 필수: +DI > -DI
        if plus_di <= minus_di or (plus_di + minus_di) <= 0:
            return 0.0

        # ② ADX 레벨 기본 점수
        if adx < 15:
            return 0.0
        elif adx <= 25:
            level_score = 7.0
        elif adx <= 30:
            level_score = 7.0 * (30.0 - adx) / 5.0
        else:
            return 0.0  # ADX > 30: 성숙 추세

        # ③ ADX 상승 방향 보너스 (df_120에서 재계산)
        adx_rising = False
        try:
            if df_120 is not None and len(df_120) >= 20:
                adx_s, _, _ = _calc_adx_series(df_120)
                if adx_s is not None and len(adx_s) >= 6:
                    adx_rising = float(adx_s.iloc[-1]) > float(adx_s.iloc[-6])
        except Exception:
            pass

        bonus = 3.0 if adx_rising else 0.0
        return round(min(10.0, level_score + bonus), 2)

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

    def _score_compression(self, row: dict) -> float:
        """BB 활성도 — 돌파 종목의 실거래 품질 지표 (구: BB압축도, 방향 역전)

        [상관분석 결과 및 연구 근거]
        - 상관분석(r=-0.0945): 과도한 압축(tight BB) 종목이 오히려 더 낮은 수익률
        - John Bollinger의 "head fake" 경고: 좁은 BB + 낮은 유동성 = 가짜돌파 트랩
        - 실거래 품질: 최근 20일 활발히 거래된 종목(moderate~wide BB)이 돌파 지속성 높음
        - 과도한 압축 종목 = 기관 관심 없음, 유동성 부족 → 단일 세력 단발성 급등 의심
        - 한국 개별주 모멘텀 역전 효과 연구: 진짜 수요 없는 좁은 BB 종목의 돌파는 반전 위험

        [방향 역전: 타이트 → 패널티, 활성 → 보상]
        bb_bandwidth ≥ 0.10  → 20pt  (활성 거래, 건강한 변동성, 실매수세 확인)
        0.07 < bw < 0.10     → 선형 상승 (10 → 20pt)
        0.05 < bw ≤ 0.07     → 선형 상승  (0 → 10pt)
        bw ≤ 0.05            →  0pt  (유동성 부족, 가짜돌파 의심)

        합계: 20pt
        """
        try:
            bw = float(row.get('bb_bandwidth') or 0)
            if bw <= 0:
                return 0.0
            if bw <= 0.05:
                return 0.0                                     # 유동성 부족, 가짜돌파
            elif bw <= 0.07:
                return 10.0 * (bw - 0.05) / 0.02             # 0 → 10pt
            elif bw <= 0.10:
                return 10.0 + 10.0 * (bw - 0.07) / 0.03     # 10 → 20pt
            else:
                return 20.0                                    # 활성 거래, 만점
        except (TypeError, ValueError):
            return 0.0

    def _penalty(self, row: dict, score_a: float = 0) -> float:
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

        # score_a 극단값 패널티 — 실증 r=-0.2738, 30pt 임계점 기반
        # 근거: 한국 개별주 단기 모멘텀 역전 효과 (학술 연구 확인)
        #   score_a 0~30pt: 승률 80%+, avg +8%  ← 건강한 돌파
        #   score_a 30~50pt: 승률 67%,  avg +2%  ← 과도한 돌파 → 개인 추격 / 기관 출회
        # 역U자로 이미 원재료(d1, vol) 극단값은 0pt 처리됨
        # 단, d1 & vol 동시 피크 = score_a 40~50pt 구간은 composite 추가 억제 필요
        if score_a > 40:
            penalty -= 20   # d1+vol 동시 최대 → 강한 반전 위험
        elif score_a > 30:
            penalty -= 10   # d1+vol 고점 권 → 중간 반전 위험

        # 기존 d1/vol 극단 패널티 유지 (score_a가 0pt로 떨어지는 구간 추가 억제)
        try:
            d1 = float(row.get('d1_diff_rate') or 0)
            if d1 > 5.0:
                penalty -= 10   # 5% 초과 갭 → 다음날 갭 메우기 역전 위험
            elif d1 > 4.0:
                penalty -= 5
        except (TypeError, ValueError):
            pass

        try:
            vol5 = float(row.get('vol5') or 0)
            vol20 = float(row.get('vol20') or 1)
            if vol20 > 0:
                ratio = vol5 / vol20
                if ratio > 4.5:
                    penalty -= 8   # 4.5x 초과 거래량 → 투기성 단타 역전 의심
                elif ratio > 3.5:
                    penalty -= 3
        except (TypeError, ZeroDivisionError, ValueError):
            pass

        return penalty


# ============================================================
# Strategy B: 중장기 RSI 사이클 (ReversalStrategyV3)
# ============================================================

class ReversalStrategyV3:
    """
    RSI 과매도 바닥 패턴 확인 후 중장기 사이클 상승 구간 포착

    [배점] 200pt 만점 (v3.2 — 2026-05-29, 백테스트 시 펀더멘털 B 제외 → 최대 160pt)
      A. RSI 신호                    65pt  (BFS 25 + 다이버전스 8 + RSI9/14크로스 32)
      B. 펀더멘털 품질               40pt  ← 실전 전용, 백테스트=0
      C. 장기 추세                   55pt  (MA120 장기추세 28 + RSI 50선 접근 27) [r=+0.081]
      D. BB 사이클 위치              10pt  (BB하단터치 6 + BB현재위치 4) ← 추가 하향 [r=+0.011]
      E. 거래량 + MACD               15pt
      F. 회복 모멘텀                 15pt  (RSI 저점 이후 일평균 상승속도) ← 상향 [r=+0.1316]

    자동 탈락 조건 (auto_reject):
      - 최근 30일 내 RSI trough > 30         : 진짜 과매도 없음
      - RSI9 < RSI14 AND RSI 하락 중         : 하락 모멘텀 지속
      - RSI > 55                             : 이미 충분히 회복됨

    매도 전략: sell_list_num=31
      - 하드 SL -5% / 트레일링스탑(max_high_pct>=3, rate<=max_high_pct-5) / 45일 시간청산
    """

    def calculate_total_score(self, row: dict, df_120, market_data=None, fundamental_data=None) -> dict:
        base = {
            'total': 0.0, 'score_a': 0.0, 'score_b': 0.0, 'score_c': 0.0,
            'score_d': 0.0, 'score_e': 0.0, 'score_f': 0.0,
            'score_penalty': 0.0, 'auto_reject': False,
            'reject_reason': '', 'strategy_type': 'B'
        }

        rsi_series = None
        rsi9_series = None
        if df_120 is not None and len(df_120) >= 30:
            rsi_series = _calc_rsi_series(df_120)
            rsi9_series = _calc_rsi9_series(df_120)

        reject = self._auto_reject(row, rsi_series, rsi9_series)
        if reject:
            base['auto_reject'] = True
            base['reject_reason'] = reject
            base['total'] = -999.0
            return base

        sa = self._score_rsi_signals(row, rsi_series, rsi9_series, df_120)
        sb = self._score_fundamental(fundamental_data)
        sc = self._score_long_trend(row, rsi_series, df_120)
        sd = self._score_bb_cycle(row, df_120)
        se = self._score_volume_macd(row)
        sf = self._score_recovery_momentum(rsi_series)
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

    def _auto_reject(self, row: dict, rsi_series, rsi9_series) -> str:
        try:
            rsi_now = float(row.get('rsi14') or 50)
            if rsi_now > 55:
                return f'RSI {rsi_now:.1f} > 55 (이미 충분히 회복)'
        except (TypeError, ValueError):
            pass

        # 최근 30일 내 RSI trough > 30 → 진짜 과매도 없음
        try:
            if rsi_series is not None and len(rsi_series) >= 30:
                trough_rsi = float(rsi_series.iloc[-30:-1].min())
                if trough_rsi > 30:
                    return f'최근 30일 RSI 최저 {trough_rsi:.1f} > 30 (과매도 미달)'
        except Exception:
            pass

        # RSI9 < RSI14 AND RSI14 하락 중 → 하락 모멘텀 지속
        try:
            if (rsi9_series is not None and rsi_series is not None
                    and len(rsi9_series) >= 4 and len(rsi_series) >= 4):
                rsi9_now = float(rsi9_series.iloc[-1])
                rsi14_now = float(rsi_series.iloc[-1])
                rsi14_3d = float(rsi_series.iloc[-4])
                if rsi9_now < rsi14_now and rsi14_now < rsi14_3d:
                    return f'RSI9({rsi9_now:.1f}) < RSI14({rsi14_now:.1f}) & RSI 하락 중'
        except Exception:
            pass

        return None

    def _score_rsi_signals(self, row: dict, rsi_series, rsi9_series, df_120) -> float:
        """A. Bottom Failure Swing(25pt) + RSI 다이버전스(8pt) + RSI9/14 크로스(32pt) = 65pt"""
        score = 0.0
        score += self._bfs_score(rsi_series)
        score += self._divergence_score(rsi_series, df_120)
        score += self._rsi9_cross_score(rsi_series, rsi9_series)
        return score

    def _bfs_score(self, rsi_series) -> float:
        """RSI Bottom Failure Swing 패턴 탐지 — 25pt
        trough1(<30) → H1 반등 → trough2(>trough1) → 현재 RSI > H1 = BFS 완성
        """
        if rsi_series is None or len(rsi_series) < 30:
            return 0.0
        try:
            n = len(rsi_series)
            rsi = rsi_series.values.astype(float)

            # trough1: 최근 60일(최소 5일 전) 내 30 이하 가장 최근 지점
            search_start = max(0, n - 60)
            search_end = n - 5
            trough1_idx = None
            for i in range(search_end - 1, search_start - 1, -1):
                if rsi[i] <= 30:
                    trough1_idx = i
                    break
            if trough1_idx is None:
                return 0.0

            trough1_val = float(rsi[trough1_idx])

            # H1: trough1 이후 최댓값 (의미있는 반등 최소 5pt 이상)
            post_t1 = rsi[trough1_idx:]
            h1_local = int(post_t1.argmax())
            h1_idx = trough1_idx + h1_local
            h1_val = float(post_t1[h1_local])
            if h1_val - trough1_val < 5 or h1_idx >= n - 1:
                return 0.0

            # trough2: H1 이후 최솟값
            post_h1 = rsi[h1_idx + 1:]
            if len(post_h1) == 0:
                return 0.0
            trough2_val = float(post_h1.min())

            # BFS 성립: trough2 > trough1 (더 낮은 저점 없음)
            if trough2_val <= trough1_val:
                return 0.0

            current_rsi = float(rsi[n - 1])
            if current_rsi > h1_val:
                return 25.0  # BFS 완성: 현재 RSI가 H1 돌파
            # H1 돌파 전 — 진행률 비례 부분 점수
            denom = max(h1_val - trough2_val, 0.1)
            progress = (current_rsi - trough2_val) / denom
            return min(12.0, max(0.0, 12.0 * progress))
        except Exception:
            pass
        return 0.0

    def _divergence_score(self, rsi_series, df_120) -> float:
        """RSI 강세 다이버전스 — 8pt (가격 낮은 저점 + RSI 높은 저점)"""
        if rsi_series is None or df_120 is None or len(df_120) < 20:
            return 0.0
        try:
            close = df_120['close'].reset_index(drop=True)
            n = len(close)
            z1_s, z1_e = max(0, n - 30), max(1, n - 15)
            z2_s, z2_e = max(0, n - 15), n - 1
            if z1_s >= z1_e or z2_s >= z2_e:
                return 0.0

            p1_idx = z1_s + int(close.iloc[z1_s:z1_e].values.argmin())
            p2_idx = z2_s + int(close.iloc[z2_s:z2_e].values.argmin())
            price1 = float(close.iloc[p1_idx])
            price2 = float(close.iloc[p2_idx])
            rsi1 = float(rsi_series.iloc[p1_idx])
            rsi2 = float(rsi_series.iloc[p2_idx])

            if price2 < price1 * 0.99 and rsi2 > rsi1 + 2:
                return 8.0
            elif price2 < price1 and rsi2 > rsi1:
                return 4.0
        except Exception:
            pass
        return 0.0

    def _rsi9_cross_score(self, rsi_series, rsi9_series) -> float:
        """RSI 9/14 골든크로스 — 32pt (단기 모멘텀 가속 신호)"""
        if rsi9_series is None or rsi_series is None:
            return 0.0
        try:
            n9, n14 = len(rsi9_series), len(rsi_series)
            if n9 < 2 or n14 < 2:
                return 0.0

            rsi9 = rsi9_series.values.astype(float)
            rsi14 = rsi_series.values.astype(float)

            if rsi9[-1] <= rsi14[-1]:
                # 크로스 없음 — 갭 축소 중인지 확인 (예비 신호)
                if n9 >= 4 and n14 >= 4:
                    gap_now = rsi14[-1] - rsi9[-1]
                    gap_3d = rsi14[-4] - rsi9[-4]
                    if gap_now < 3 and gap_now < gap_3d:
                        return 4.0
                return 0.0

            # RSI9 > RSI14: 마지막으로 RSI9 <= RSI14 였던 날 탐색
            cross_days_ago = None
            limit = min(10, n9, n14)
            for k in range(1, limit):
                if rsi9[-1 - k] <= rsi14[-1 - k]:
                    cross_days_ago = k
                    break

            if cross_days_ago is None:
                return 12.0   # 10일 이상 유지 — 오래된 크로스
            elif cross_days_ago <= 3:
                return 32.0   # 신선한 크로스 (0~2일 전 발생)
            elif cross_days_ago <= 7:
                return 20.0   # 3~6일 전
            else:
                return 12.0   # 7~9일 전
        except Exception:
            pass
        return 0.0

    def _score_long_trend(self, row: dict, rsi_series, df_120) -> float:
        """C. MA120 장기 추세(28pt) + RSI 50선 접근(27pt) = 55pt
        상관분석(r=+0.081)에서 가장 유효한 컴포넌트 → 비중 상향 (40→55pt)
        """
        score = 0.0

        try:
            if df_120 is not None and len(df_120) >= 120:
                close_s = df_120['close'].reset_index(drop=True)
                ma120_today = float(close_s.iloc[-120:].mean())
                close_now = float(row.get('close') or 0)
                if close_now > 0 and ma120_today > 0:
                    ratio = close_now / ma120_today
                    if ratio >= 1.0:
                        if len(close_s) >= 130:
                            ma120_10d = float(close_s.iloc[-130:-10].mean())
                            score += 28 if ma120_today >= ma120_10d else 21
                        else:
                            score += 21
                    elif ratio >= 0.95:
                        score += 11
                    elif ratio >= 0.85:
                        score += 4
        except Exception:
            pass

        try:
            rsi_now = float(row.get('rsi14') or 30)
            if rsi_now >= 45:
                score += 27
            elif rsi_now >= 38:
                score += 16
            elif rsi_now >= 30:
                score += 8
            else:
                score += 3
        except (TypeError, ValueError):
            pass

        return score

    def _score_fundamental(self, fundamental_data) -> float:
        """B. 펀더멘털 품질 — 40pt (실전 전용, fundamental_data=None → 0)"""
        if fundamental_data is None:
            return 0.0
        score = 0.0
        try:
            roa = fundamental_data.get('roa')
            if roa is not None:
                roa = float(roa)
                if roa > 10:
                    score += 20
                elif roa > 5:
                    score += 12
                elif roa > 0:
                    score += 5
                else:
                    score -= 10
        except (TypeError, ValueError):
            pass

        try:
            per = fundamental_data.get('per')
            if per is not None:
                per = float(per)
                if per < 0:
                    score -= 15
                elif 5 <= per <= 15:
                    score += 20
                elif 15 < per <= 25:
                    score += 10
        except (TypeError, ValueError):
            pass

        return score

    def _score_bb_cycle(self, row: dict, df_120) -> float:
        """D. BB 하단 터치 후 복귀(6pt) + BB 현재 위치(4pt) = 10pt
        상관분석(r=+0.011)에서 거의 무효 → 비중 추가 하향 (25→15→10pt)
        해방된 5pt는 r=+0.1316 최고 상관의 score_f(회복모멘텀)로 이전
        """
        score = 0.0

        try:
            if df_120 is not None and len(df_120) >= 25:
                bb_lower_series = _calc_bb_lower_series(df_120)
                if bb_lower_series is not None:
                    recent_close = df_120['close'].iloc[-11:-1].values
                    recent_low = df_120['low'].iloc[-11:-1].values
                    recent_bb_l = bb_lower_series.iloc[-11:-1].values
                    if any(
                        (recent_close[k] <= recent_bb_l[k] or recent_low[k] <= recent_bb_l[k])
                        for k in range(len(recent_close))
                        if recent_bb_l[k] == recent_bb_l[k]
                    ):
                        score += 6  # 9 → 6pt
        except Exception:
            pass

        try:
            close = float(row.get('close') or 0)
            bb_upper = float(row.get('bb_upper') or 0)
            bb_lower = float(row.get('bb_lower') or 0)
            bb_range = bb_upper - bb_lower
            if bb_range > 0:
                pos = (close - bb_lower) / bb_range
                if 0.10 <= pos <= 0.40:
                    score += 4  # 6 → 4pt
                elif 0.40 < pos <= 0.55:
                    score += 4 * (0.55 - pos) / 0.15
        except (TypeError, ZeroDivisionError):
            pass

        return score

    def _score_recovery_momentum(self, rsi_series) -> float:
        """F. 회복 모멘텀 — RSI 저점 이후 일평균 상승 속도 = 15pt (10→15pt 상향)

        Strategy B는 RSI 과매도 이후 반등 구간을 포착하는 전략.
        RSI 저점에서 현재까지 얼마나 빠르게 회복하는지가 매수 강도를 반영한다.
        상관분석(r=+0.1316): Strategy B 전체 컴포넌트 중 최고 상관 → 비중 상향.
        해방 재원: score_d (BB사이클, r=+0.011) 5pt 이전.

        계산:
          - 최근 30일 내 RSI 최저점(trough) 탐색 (trough ≤ 35 조건)
          - daily_gain = (현재 RSI - trough) / 저점 이후 경과일

        ≥ 3pt/일 → 15pt  (강한 회복, 단기 반전 모멘텀)
        ≥ 2pt/일 → 10pt
        ≥ 1pt/일 →  5pt
        < 1pt/일 →  0pt  (회복 속도 불충분)
        """
        try:
            if rsi_series is None or len(rsi_series) < 10:
                return 0.0
            series = rsi_series.reset_index(drop=True)
            n = len(series)
            rsi_now = float(series.iloc[-1])

            # 최근 30일 내 RSI 최저점 탐색 (trough ≤ 35)
            lookback = series.iloc[max(0, n - 30):-1]
            if lookback.empty:
                return 0.0
            trough_val = float(lookback.min())
            if trough_val > 35:
                return 0.0  # 진짜 과매도 바닥 없음

            trough_local_idx = int(lookback.values.argmin())
            trough_abs_idx = (n - 30 if n >= 30 else 0) + trough_local_idx
            days_since = (n - 1) - trough_abs_idx
            if days_since <= 0:
                return 0.0

            daily_gain = (rsi_now - trough_val) / days_since
            if daily_gain >= 3.0:
                return 15.0   # 10 → 15pt
            elif daily_gain >= 2.0:
                return 10.0   #  7 → 10pt
            elif daily_gain >= 1.0:
                return 5.0    #  4 →  5pt
            else:
                return 0.0
        except Exception:
            return 0.0

    def _score_volume_macd(self, row: dict) -> float:
        """E. 반등 거래량(8pt) + MACD 전환(7pt) = 15pt"""
        score = 0.0

        try:
            vol5 = float(row.get('vol5') or 0)
            vol20 = float(row.get('vol20') or 1)
            if vol20 > 0:
                ratio = vol5 / vol20
                if ratio >= 1.5:
                    score += 8
                elif ratio >= 1.2:
                    score += 5
                elif ratio >= 1.0:
                    score += 2
        except (TypeError, ZeroDivisionError):
            pass

        try:
            hist = float(row.get('macd_histogram') or 0)
            macd = float(row.get('macd') or 0)
            signal = float(row.get('macd_signal') or 0)
            if hist > 0 and macd > signal:
                score += 7
            elif hist > 0 or macd > signal:
                score += 4
        except (TypeError, ValueError):
            pass

        return score

    def _penalty(self, row: dict) -> float:
        penalty = 0.0
        try:
            atr14 = float(row.get('atr14') or 0)
            close = float(row.get('close') or 1)
            if close > 0 and atr14 / close > 0.08:
                penalty -= 10
        except (TypeError, ZeroDivisionError):
            pass
        return penalty
