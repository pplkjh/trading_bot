"""
JackBot v4 Scoring System
simul_num=7: BreakoutStrategyV4 + ReversalStrategyV4 (A+B 혼합)

[설계 원칙 — Market-Gated A+B]
Layer 1: NASDAQ Regime Gate — 매수 실행 여부 결정 (score가 아님)
  feature_discovery Run 9: NASDAQ 신호가 개별주 신호보다 2배 중요
  nasdaq Perm #1-3 (0.074~0.085) > bb_position #4 (0.039)

  BEAR     (n5d < -3%  OR  n1d < -1.5%)  → A+B 모두 중단
  OVERHEAT (n5d > +10%)                   → A 중단, B 허용 (평균회귀는 유효)
  BULL     (n5d ≥ +2%  AND n1d > 0%)     → A+B 적극 실행
  NEUTRAL  (나머지)                        → A+B 정상 실행

Layer 2: 개별주 스코어링 (게이트 통과 후에만 실행)
  score_a ~ score_g: sim=6 v3와 동일
  score_h:           NASDAQ 환경 보너스 (0~15pt, 패널티 없음 — 게이트가 담당)

[sim=6 대비 변경점]
1. NASDAQ → hard gate (이전: score_h 내 -15~+20pt 소프트 스코어)
2. BreakoutStrategyV4: atr_rate 패널티 제거
   feature_discovery Run 4: atr_rate r=+0.0911 (big_win 전체 1위 양의 신호)
3. score_h: -15~+20pt → 0~15pt (패널티 제거, 게이트로 이관)

[DB]
simul_num=7 → simulator7 (백테스트) / jackbot7_imi1 (실전)
"""

from library.hybrid_strategy_v3 import BreakoutStrategyV3, ReversalStrategyV3


# ============================================================
# Layer 1: NASDAQ Regime Gate
# ============================================================

def _classify_nasdaq_regime(n5, n1):
    """NASDAQ 시장 환경 분류 — Layer 1 execution gate

    Returns: 'BULL' | 'NEUTRAL' | 'BEAR' | 'OVERHEAT'

    BEAR:     nasdaq_5d < -3%  OR  nasdaq_1d < -1.5%  → A+B 모두 중단
    OVERHEAT: nasdaq_5d > +10%                         → A 중단, B 허용
    BULL:     nasdaq_5d ≥ +2%  AND nasdaq_1d > 0%     → 적극 실행
    NEUTRAL:  나머지                                    → 정상 실행
    데이터 없음: 'NEUTRAL' (graceful degradation)
    """
    try:
        n5v = float(n5) if n5 is not None else None
        n1v = float(n1) if n1 is not None else None
    except (TypeError, ValueError):
        return 'NEUTRAL'

    if n5v is None or n1v is None:
        return 'NEUTRAL'
    if n5v < -0.03 or n1v < -0.015:
        return 'BEAR'
    if n5v > 0.10:
        return 'OVERHEAT'
    if n5v >= 0.02 and n1v > 0.0:
        return 'BULL'
    return 'NEUTRAL'


# ============================================================
# Layer 2: NASDAQ 환경 보너스 (게이트 통과 후)
# ============================================================

def _score_nasdaq_context(row: dict) -> float:
    """NASDAQ 환경 보너스 — 0pt ~ +15pt (패널티 없음)

    BEAR/OVERHEAT는 게이트가 이미 처리. 여기서는 BULL/NEUTRAL 범위 내
    환경 우호도를 미세 구분하여 보너스만 부여.

    nasdaq_5d_ret 기준:
      BULL sweet spot [+2%, +8%]:  10pt → 15pt (선형)
      과열 직전      [+8%, +10%]:  8pt
      약한 양신호    [0%,  +2%):   5pt
      중립           [-3%, 0%):    0pt  (게이트 통과 = 패널티 없음)
      OVERHEAT B:    (>+10%):      0pt  (B는 허용되지만 보너스 없음)
    """
    try:
        n5 = float(row.get('nasdaq_5d_ret') or 0)
    except (TypeError, ValueError):
        return 0.0

    if n5 > 0.10:        # OVERHEAT: B는 허용, 보너스는 없음
        return 0.0
    elif n5 >= 0.08:     # [+8%, +10%): 과열 직전
        score = 8.0
    elif n5 >= 0.02:     # BULL sweet spot [+2%, +8%): 10→15pt 선형
        score = 10.0 + 5.0 * (n5 - 0.02) / 0.06
    elif n5 >= 0.00:     # 약한 양신호 [0%, +2%)
        score = 5.0
    else:                # [-3%, 0%): 중립, 패널티 없음
        score = 0.0

    return min(15.0, round(score, 2))


# ============================================================
# Strategy A v4: 돌파 초입 + Market Gate
# ============================================================

class BreakoutStrategyV4(BreakoutStrategyV3):
    """
    BreakoutStrategyV3 개선판 (sim=7용)

    변경점:
    1. NASDAQ Regime Gate (Layer 1)
       BEAR/OVERHEAT 시 auto_reject — 시장 환경이 개별주 신호보다 우선
    2. atr_rate 패널티 제거
       feature_discovery Run 4: atr_rate r=+0.0911 (big_win 전체 1위 양의 신호)
    3. score_h: -15~+20pt → 0~15pt (패널티 제거, 게이트로 이관)
    """

    def calculate_total_score(self, row: dict, df_120, market_data=None) -> dict:
        base = {
            'total': 0.0, 'score_a': 0.0, 'score_b': 0.0, 'score_c': 0.0,
            'score_d': 0.0, 'score_e': 0.0, 'score_f': 0.0, 'score_g': 0.0,
            'score_h': 0.0,
            'score_penalty': 0.0, 'auto_reject': False,
            'reject_reason': '', 'strategy_type': 'A'
        }

        # ── Layer 1: NASDAQ Regime Gate ──────────────────────────
        regime = _classify_nasdaq_regime(
            row.get('nasdaq_5d_ret'), row.get('nasdaq_1d_ret')
        )
        if regime in ('BEAR', 'OVERHEAT'):
            base['auto_reject'] = True
            base['reject_reason'] = f'NASDAQ_{regime}'
            base['total'] = -999.0
            return base

        # ── Layer 2: 개별주 스코어링 ─────────────────────────────
        reject = self._auto_reject(row)
        if reject:
            base['auto_reject'] = True
            base['reject_reason'] = reject
            base['total'] = -999.0
            return base

        sa = self._score_setup_quality(row, df_120)
        sb = self._score_bb_and_ma(row)
        sc = self._score_adx_early(row, df_120)
        sd = self._score_macd_crossover(row, df_120)
        se = self._score_rsi_cross50(row, df_120)
        sf = self._score_compression(row)
        sg = self._score_inst_flow(row)
        sh = _score_nasdaq_context(row)
        penalty = self._penalty(row)

        total = sa + sb + sc + sd + se + sf + sg + sh + penalty

        base.update({
            'total':         round(total, 2),
            'score_a':       round(sa, 2),
            'score_b':       round(sb, 2),
            'score_c':       round(sc, 2),
            'score_d':       round(sd, 2),
            'score_e':       round(se, 2),
            'score_f':       round(sf, 2),
            'score_g':       round(sg, 2),
            'score_h':       round(sh, 2),
            'score_penalty': round(penalty, 2),
        })
        return base

    def _penalty(self, row: dict) -> float:
        """v3 대비 atr_rate 패널티 제거 — RSI/ADX/d1/vol 극단값만 유지"""
        penalty = 0.0

        try:
            rsi = float(row.get('rsi14') or 50)
            if rsi > 65:
                penalty -= 15
        except (TypeError, ValueError):
            pass

        try:
            adx = float(row.get('adx') or 0)
            if adx > 30:
                penalty -= 10
        except (TypeError, ValueError):
            pass

        try:
            d1 = float(row.get('d1_diff_rate') or 0)
            if d1 > 5.0:
                penalty -= 15
            elif d1 > 4.0:
                penalty -= 8
        except (TypeError, ValueError):
            pass

        try:
            vol5 = float(row.get('vol5') or 0)
            vol20 = float(row.get('vol20') or 1)
            if vol20 > 0:
                ratio = vol5 / vol20
                if ratio > 4.5:
                    penalty -= 12
                elif ratio > 3.5:
                    penalty -= 6
        except (TypeError, ZeroDivisionError, ValueError):
            pass

        return penalty


# ============================================================
# Strategy B v4: RSI 사이클 + Market Gate
# ============================================================

class ReversalStrategyV4(ReversalStrategyV3):
    """
    ReversalStrategyV3 개선판 (sim=7용)

    변경점:
    1. NASDAQ Regime Gate (Layer 1)
       BEAR 시 auto_reject. OVERHEAT는 허용 (시장 과열 중 아직 못 오른 종목 = B 기회)
    2. score_h: -15~+20pt → 0~15pt (패널티 제거, 게이트로 이관)
    3. atr_rate 패널티: v3 유지 (B는 안정적 평균회귀 목적, 고변동성 제한 합리적)
    """

    def calculate_total_score(self, row: dict, df_120, market_data=None, fundamental_data=None) -> dict:
        base = {
            'total': 0.0, 'score_a': 0.0, 'score_b': 0.0, 'score_c': 0.0,
            'score_d': 0.0, 'score_e': 0.0, 'score_f': 0.0, 'score_g': 0.0,
            'score_h': 0.0,
            'score_penalty': 0.0, 'auto_reject': False,
            'reject_reason': '', 'strategy_type': 'B'
        }

        # ── Layer 1: NASDAQ Regime Gate ──────────────────────────
        # B는 OVERHEAT 허용 (과열 시장에서 아직 못 오른 저점 종목 = 평균회귀 기회)
        regime = _classify_nasdaq_regime(
            row.get('nasdaq_5d_ret'), row.get('nasdaq_1d_ret')
        )
        if regime == 'BEAR':
            base['auto_reject'] = True
            base['reject_reason'] = 'NASDAQ_BEAR'
            base['total'] = -999.0
            return base

        # ── Layer 2: 개별주 스코어링 ─────────────────────────────
        rsi_series = None
        rsi9_series = None
        if df_120 is not None and len(df_120) >= 30:
            from library.hybrid_strategy_v3 import _calc_rsi_series, _calc_rsi9_series
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
        sg = self._score_inst_flow(row)
        sh = _score_nasdaq_context(row)
        penalty = self._penalty(row)

        total = sa + sb + sc + sd + se + sf + sg + sh + penalty

        base.update({
            'total':         round(total, 2),
            'score_a':       round(sa, 2),
            'score_b':       round(sb, 2),
            'score_c':       round(sc, 2),
            'score_d':       round(sd, 2),
            'score_e':       round(se, 2),
            'score_f':       round(sf, 2),
            'score_g':       round(sg, 2),
            'score_h':       round(sh, 2),
            'score_penalty': round(penalty, 2),
        })
        return base
