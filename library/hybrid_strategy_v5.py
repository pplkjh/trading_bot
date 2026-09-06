"""
sim=8: BreakoutStrategyV5 + ReversalStrategyV5
Condition-Based System (scoring 제거)

[설계 원칙]
feature_discovery Run1~9: 주요 피처들이 선형이 아닌 threshold 효과
  → 점수 합산(sim=3~7) 대신 조건 통과/실패로 매수 결정

[구조]
Layer 1: NASDAQ Regime Gate (sim=7과 동일)
Layer 2: Required Conditions — 전부 통과해야 함
Layer 3: Optional Conditions — N/M 이상 통과해야 함

[col 매핑]
  composite_score = 통과한 optional 조건 수 (ranking/tie-break용)
  score_a~score_e = 각 optional 조건 결과 (0=실패, 1=통과)
  auto_reject=True → required 미통과 or optional N/M 미달

[Strategy A 근거 — big_win 타겟 (Run4)]
  vol_ratio:    threshold 효과, CatBoost #1
  atr_rate:     big_win Pearson #1 (+0.091) — 기존 패널티 반전
  bb_bandwidth: big_win Pearson #2 (+0.070), max Perm #1

[Strategy B 근거 — win/h15 타겟 (Run1~8)]
  bb_position:  전 Run 압도적 #1 (h15 r=-0.158), threshold 효과
  rsi14:        h5~h10 일관된 역상관 (#3)
  atr_rate:     win Perm #2, 반등 에너지 필요
"""

from library.hybrid_strategy_v4 import _classify_nasdaq_regime


# ============================================================
# 공통 유틸
# ============================================================

def _bb_position(row: dict):
    """(close - bb_lower) / (bb_upper - bb_lower). 계산 불가시 None."""
    try:
        close = float(row.get('close') or 0)
        bb_l  = float(row.get('bb_lower')  or 0)
        bb_u  = float(row.get('bb_upper')  or 0)
        if bb_u > bb_l and bb_l > 0:
            return (close - bb_l) / (bb_u - bb_l)
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    return None


def _vol_ratio(row: dict):
    """vol5 / vol20. 계산 불가시 None."""
    try:
        vol5  = float(row.get('vol5')  or 0)
        vol20 = float(row.get('vol20') or 1)
        if vol20 > 0:
            return vol5 / vol20
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    return None


def _atr_rate(row: dict):
    """atr14 / close. 계산 불가시 None."""
    try:
        close = float(row.get('close') or 0)
        atr   = float(row.get('atr14') or 0)
        if close > 0:
            return atr / close
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    return None


# ============================================================
# Strategy A v5: Breakout — Condition-Based
# ============================================================

class BreakoutStrategyV5:
    """
    Required (전부 통과 필수):
      ① vol_ratio_5_20 > 1.5       Run1~5 threshold effect
      ② atr_rate       > 0.02      big_win Pearson #1 (+0.091)
      ③ bb_bandwidth   > 0.05      big_win Pearson #2 (+0.070)

    Optional (5개 중 2개 이상):
      score_a: bb_position < 0.65   극단 상단 아님
      score_b: rsi14 < 55           과매수 아님
      score_c: mfi14 > 30           자금유입, big_win Perm #2
      score_d: close > ichimoku_kijun  기준선 위 (h5 LASSO 강신호)
      score_e: plus_di > minus_di   방향성 우위
    """

    REQUIRED_OPT = 2

    def calculate_total_score(self, row: dict, df_120, market_data=None, fundamental_data=None) -> dict:
        base = {
            'total': 0.0,
            'score_a': 0.0, 'score_b': 0.0, 'score_c': 0.0,
            'score_d': 0.0, 'score_e': 0.0, 'score_f': 0.0,
            'score_g': 0.0, 'score_h': 0.0,
            'score_penalty': 0.0,
            'auto_reject': False, 'reject_reason': '',
            'strategy_type': 'A',
        }

        # Layer 1: NASDAQ Gate
        regime = _classify_nasdaq_regime(row.get('nasdaq_5d_ret'), row.get('nasdaq_1d_ret'))
        if regime in ('BEAR', 'OVERHEAT'):
            base['auto_reject'] = True
            base['reject_reason'] = f'NASDAQ_{regime}'
            base['total'] = -999.0
            return base

        # Layer 2: Required conditions
        vol_r = _vol_ratio(row)
        if vol_r is None or vol_r < 1.5:
            base['auto_reject'] = True
            base['reject_reason'] = f'vol_ratio {vol_r:.2f}<1.5' if vol_r is not None else 'vol_ratio=None'
            base['total'] = -999.0
            return base

        atr_r = _atr_rate(row)
        if atr_r is None or atr_r < 0.02:
            base['auto_reject'] = True
            base['reject_reason'] = f'atr_rate {atr_r:.3f}<0.02' if atr_r is not None else 'atr_rate=None'
            base['total'] = -999.0
            return base

        try:
            bw = float(row.get('bb_bandwidth') or 0)
        except (TypeError, ValueError):
            bw = 0.0
        if bw < 0.05:
            base['auto_reject'] = True
            base['reject_reason'] = f'bb_bandwidth {bw:.3f}<0.05'
            base['total'] = -999.0
            return base

        # Layer 3: Optional conditions
        opt = [0.0] * 5

        bbpos = _bb_position(row)
        if bbpos is not None and bbpos < 0.65:
            opt[0] = 1.0

        try:
            if float(row.get('rsi14') or 50) < 55:
                opt[1] = 1.0
        except (TypeError, ValueError):
            pass

        try:
            if float(row.get('mfi14') or 50) > 30:
                opt[2] = 1.0
        except (TypeError, ValueError):
            pass

        try:
            close  = float(row.get('close')          or 0)
            kijun  = float(row.get('ichimoku_kijun')  or 0)
            if close > 0 and kijun > 0 and close > kijun:
                opt[3] = 1.0
        except (TypeError, ValueError):
            pass

        try:
            pdi = float(row.get('plus_di')  or 0)
            mdi = float(row.get('minus_di') or 0)
            if pdi > mdi:
                opt[4] = 1.0
        except (TypeError, ValueError):
            pass

        opt_count = sum(opt)
        if opt_count < self.REQUIRED_OPT:
            base['auto_reject'] = True
            base['reject_reason'] = f'opt {int(opt_count)}/{self.REQUIRED_OPT} 미달'
            base['total'] = -999.0
            return base

        base.update({
            'total':   float(opt_count),
            'score_a': opt[0], 'score_b': opt[1], 'score_c': opt[2],
            'score_d': opt[3], 'score_e': opt[4],
        })
        return base


# ============================================================
# Strategy A v6: Breakout — All Conditions Required (sim=9)
# ============================================================

class BreakoutStrategyV6:
    """
    sim=9 Strategy A: V5 optional 5개를 모두 Required로 격상.
    "N개 이상" 카운팅 없음 — 전부 통과해야 매수.

    Required (전부 통과 필수):
      ① vol_ratio   > 1.5   (V5 Required 유지)
      ② atr_rate    > 0.02  (V5 Required 유지)
      ③ bb_bandwidth > 0.05 (V5 Required 유지)
      ④ NASDAQ gate: not BEAR/OVERHEAT
      ⑤ bb_position < 0.65  (V5 Optional → Required)
      ⑥ rsi14       < 55    (V5 Optional → Required)
      ⑦ mfi14       > 30    (V5 Optional → Required)
      ⑧ close > ichimoku_kijun  (V5 Optional → Required)
      ⑨ +DI > -DI            (V5 Optional → Required)
    """

    def calculate_total_score(self, row: dict, df_120, market_data=None, fundamental_data=None) -> dict:
        base = {
            'total': 0.0,
            'score_a': 0.0, 'score_b': 0.0, 'score_c': 0.0,
            'score_d': 0.0, 'score_e': 0.0, 'score_f': 0.0,
            'score_g': 0.0, 'score_h': 0.0,
            'score_penalty': 0.0,
            'auto_reject': False, 'reject_reason': '',
            'strategy_type': 'A',
        }

        # Layer 1: NASDAQ Gate
        regime = _classify_nasdaq_regime(row.get('nasdaq_5d_ret'), row.get('nasdaq_1d_ret'))
        if regime in ('BEAR', 'OVERHEAT'):
            base['auto_reject'] = True
            base['reject_reason'] = f'NASDAQ_{regime}'
            base['total'] = -999.0
            return base

        # Layer 2: Required (V5와 동일)
        vol_r = _vol_ratio(row)
        if vol_r is None or vol_r < 1.5:
            base['auto_reject'] = True
            base['reject_reason'] = f'vol_ratio {vol_r:.2f}<1.5' if vol_r is not None else 'vol_ratio=None'
            base['total'] = -999.0
            return base

        atr_r = _atr_rate(row)
        if atr_r is None or atr_r < 0.02:
            base['auto_reject'] = True
            base['reject_reason'] = f'atr_rate {atr_r:.3f}<0.02' if atr_r is not None else 'atr_rate=None'
            base['total'] = -999.0
            return base

        try:
            bw = float(row.get('bb_bandwidth') or 0)
        except (TypeError, ValueError):
            bw = 0.0
        if bw < 0.05:
            base['auto_reject'] = True
            base['reject_reason'] = f'bb_bandwidth {bw:.3f}<0.05'
            base['total'] = -999.0
            return base

        # Layer 3: V5 Optional → 전부 Required
        bbpos = _bb_position(row)
        if bbpos is None or bbpos >= 0.65:
            base['auto_reject'] = True
            base['reject_reason'] = f'bb_pos {bbpos:.2f}>=0.65' if bbpos is not None else 'bb_pos=None'
            base['total'] = -999.0
            return base

        try:
            rsi = float(row.get('rsi14') or 55)
        except (TypeError, ValueError):
            rsi = 55.0
        if rsi >= 55:
            base['auto_reject'] = True
            base['reject_reason'] = f'rsi14 {rsi:.1f}>=55'
            base['total'] = -999.0
            return base

        try:
            mfi = float(row.get('mfi14') or 0)
        except (TypeError, ValueError):
            mfi = 0.0
        if mfi <= 30:
            base['auto_reject'] = True
            base['reject_reason'] = f'mfi14 {mfi:.1f}<=30'
            base['total'] = -999.0
            return base

        try:
            close = float(row.get('close') or 0)
            kijun = float(row.get('ichimoku_kijun') or 0)
        except (TypeError, ValueError):
            close, kijun = 0.0, 0.0
        if close <= 0 or kijun <= 0 or close <= kijun:
            base['auto_reject'] = True
            base['reject_reason'] = f'close {close:.0f}<=kijun {kijun:.0f}'
            base['total'] = -999.0
            return base

        try:
            pdi = float(row.get('plus_di') or 0)
            mdi = float(row.get('minus_di') or 0)
        except (TypeError, ValueError):
            pdi, mdi = 0.0, 0.0
        if pdi <= mdi:
            base['auto_reject'] = True
            base['reject_reason'] = f'+DI {pdi:.1f}<=-DI {mdi:.1f}'
            base['total'] = -999.0
            return base

        # 전 조건 통과
        base.update({
            'total':   5.0,
            'score_a': 1.0,  # bb_pos
            'score_b': 1.0,  # rsi
            'score_c': 1.0,  # mfi
            'score_d': 1.0,  # kijun
            'score_e': 1.0,  # +DI>-DI
        })
        return base


# ============================================================
# Strategy B v5: Mean Reversion — Condition-Based
# ============================================================

class ReversalStrategyV5:
    """
    Required (전부 통과 필수):
      ① bb_position < 0.35         전 Run 압도적 #1 (h15 r=-0.158)
      ② rsi14 < 45                 h5~h10 역상관 일관, h15 Perm #4
      ③ atr_rate > 0.015           win Perm #2, 반등 에너지 최소치
      ④ inst_net_buy > 0           기관 순매수 확인 (supply Perm #7) — 가치함정 제거

    Optional (3개 중 1개 이상):
      score_a: mfi14 < 40          자금 아직 덜 들어옴 (2024+ 부호 반전 반영)
      score_b: vol_ratio > 1.0     거래량 관심 최소
      score_c: bb_bandwidth < 0.15 과도 확장 아님 (B = 수렴 후 반등)
    """

    REQUIRED_OPT = 1

    def calculate_total_score(self, row: dict, df_120, market_data=None, fundamental_data=None) -> dict:
        base = {
            'total': 0.0,
            'score_a': 0.0, 'score_b': 0.0, 'score_c': 0.0,
            'score_d': 0.0, 'score_e': 0.0, 'score_f': 0.0,
            'score_g': 0.0, 'score_h': 0.0,
            'score_penalty': 0.0,
            'auto_reject': False, 'reject_reason': '',
            'strategy_type': 'B',
        }

        # Layer 1: NASDAQ Gate (BEAR만 제외, OVERHEAT 허용)
        regime = _classify_nasdaq_regime(row.get('nasdaq_5d_ret'), row.get('nasdaq_1d_ret'))
        if regime == 'BEAR':
            base['auto_reject'] = True
            base['reject_reason'] = 'NASDAQ_BEAR'
            base['total'] = -999.0
            return base

        # Layer 2: Required conditions
        bbpos = _bb_position(row)
        if bbpos is None or bbpos >= 0.35:
            base['auto_reject'] = True
            base['reject_reason'] = f'bb_position {bbpos:.2f}>=0.35' if bbpos is not None else 'bb_position=None'
            base['total'] = -999.0
            return base

        try:
            rsi = float(row.get('rsi14') or 50)
        except (TypeError, ValueError):
            rsi = 50.0
        if rsi >= 45:
            base['auto_reject'] = True
            base['reject_reason'] = f'rsi14 {rsi:.1f}>=45'
            base['total'] = -999.0
            return base

        atr_r = _atr_rate(row)
        if atr_r is None or atr_r < 0.015:
            base['auto_reject'] = True
            base['reject_reason'] = f'atr_rate {atr_r:.3f}<0.015' if atr_r is not None else 'atr_rate=None'
            base['total'] = -999.0
            return base

        try:
            inst = row.get('inst_net_buy')
            if inst is None or float(inst) <= 0:
                base['auto_reject'] = True
                base['reject_reason'] = f'inst_net_buy {inst}<=0 (기관 미매수)'
                base['total'] = -999.0
                return base
        except (TypeError, ValueError):
            base['auto_reject'] = True
            base['reject_reason'] = 'inst_net_buy 파싱 불가'
            base['total'] = -999.0
            return base

        # Layer 3: Optional conditions (3개 중 1개 이상)
        opt = [0.0] * 3

        try:
            if float(row.get('mfi14') or 50) < 40:
                opt[0] = 1.0
        except (TypeError, ValueError):
            pass

        vol_r = _vol_ratio(row)
        if vol_r is not None and vol_r > 1.0:
            opt[1] = 1.0

        try:
            if float(row.get('bb_bandwidth') or 1.0) < 0.15:
                opt[2] = 1.0
        except (TypeError, ValueError):
            pass

        opt_count = sum(opt)
        if opt_count < self.REQUIRED_OPT:
            base['auto_reject'] = True
            base['reject_reason'] = f'opt {int(opt_count)}/{self.REQUIRED_OPT} 미달'
            base['total'] = -999.0
            return base

        base.update({
            'total':   float(opt_count),
            'score_a': opt[0], 'score_b': opt[1], 'score_c': opt[2],
        })
        return base
