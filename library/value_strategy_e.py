"""
library/value_strategy_e.py

Strategy E — 지속 성장주 스크리너 (Opus 설계 기반)
- 반등주·테마주·급등주 제외
- 6단 MA 정배열 + 모든 MA 상승 중 + 눌림목 진입
- 소형주·조작주 차단: 거래대금 100억 이상
- 투자위험 지정 종목 제외
"""
import logging
from typing import List

logger = logging.getLogger(__name__)


class ValueStrategyE:
    _debug_done = False

    # ── 기술적 기준 ──────────────────────────────────────────────────
    MIN_TRADING_VALUE  = 10_000_000_000  # 일평균 거래대금 100억 (소형주·조작주 차단)
    MAX_ATR_RATE       = 0.030           # ATR14/close ≤ 3.0% (Opus 원안)
    MAX_BB_BW          = 0.13            # 볼린저밴드폭 ≤ 0.13 (Opus 원안)
    MIN_ADX            = 18              # ADX 최소 (추세 존재)
    MAX_ADX            = 35              # ADX 최대 (Opus 원안)
    MIN_TREND_RATIO    = 1.05            # close/clo120 최소 (Opus 원안)
    MAX_TREND_RATIO    = 1.25            # close/clo120 최대 (Opus 원안)
    MIN_MA20_RATIO     = 1.03            # clo20/clo120 최소 (Opus 원안)
    MAX_MA20_RATIO     = 1.15            # clo20/clo120 최대 (Opus 원안)
    MIN_RSI            = 40              # RSI 최소 (Opus 원안)
    MAX_RSI            = 58              # RSI 최대 (Opus 원안)
    MAX_POSITIONS      = 3               # 일별 최대 신규 후보 수

    def screen(self, date_str: str, engine_dbl) -> list:
        """
        date_str  : YYYYMMDD (시뮬레이션 기준일)
        engine_dbl: daily_buy_list DB SQLAlchemy engine
        Returns: list[dict] — realtime_daily_buy_list 행, 최대 3개
        """
        _dbg = not ValueStrategyE._debug_done

        try:
            rows = engine_dbl.execute(
                f"""
                SELECT a.*,
                       ROUND((a.close / a.clo120 - 1) * 100, 2) AS trend_score
                FROM `{date_str}` a
                WHERE
                    -- ① 소형주·조작주 차단 (거래대금 100억)
                    (a.vol20 + 0.0) * a.close >= {self.MIN_TRADING_VALUE}

                    -- ② 6단 MA 정배열 (clo5>clo20>clo40>clo60>clo80>clo120)
                    --    삼성전자/신한지주급 안정 대형주만 통과 — 절대 완화 금지
                    AND a.clo5  > a.clo20
                    AND a.clo20 > a.clo40
                    AND a.clo40 > a.clo60
                    AND a.clo60 > a.clo80
                    AND a.clo80 > a.clo120

                    -- ③ 모든 주요 MA 상승 중 (우상향이 기간으로 검증됨)
                    AND a.clo20  > a.yes_clo20
                    AND a.clo60  > a.yes_clo60
                    AND a.clo120 > a.yes_clo120

                    -- ④ 검증된 우상향 범위 (너무 급등하지 않고 꾸준히 올라온 상태)
                    AND a.close / a.clo120 BETWEEN {self.MIN_TREND_RATIO} AND {self.MAX_TREND_RATIO}
                    AND a.clo20  / a.clo120 BETWEEN {self.MIN_MA20_RATIO} AND {self.MAX_MA20_RATIO}

                    -- ⑤ 안정성: 저변동성 + 추세 방향성 (테마주·급등주 배제)
                    AND a.atr14 / a.close  <= {self.MAX_ATR_RATE}
                    AND a.bb_bandwidth     <= {self.MAX_BB_BW}
                    AND a.adx BETWEEN {self.MIN_ADX} AND {self.MAX_ADX}
                    AND a.plus_di > a.minus_di

                    -- ⑥ 거래량 정상 (급등 직전 과열 배제)
                    AND a.vol20 / a.vol120 BETWEEN 0.7 AND 1.8

                    -- ⑦ 눌림목 진입 타이밍 (MA20 부근 조정, MA60 위)
                    AND a.close BETWEEN a.clo40 * 0.97 AND a.clo20 * 1.03
                    AND a.close > a.clo60
                    AND a.rsi14 BETWEEN {self.MIN_RSI} AND {self.MAX_RSI}
                    AND a.vol5  < a.vol20 * 1.1
                    AND a.macd  > 0

                    -- ⑦ 투자위험·관리·KONEX 제외
                    AND NOT EXISTS (SELECT 1 FROM stock_invest_warning w WHERE w.code = a.code)
                    AND NOT EXISTS (SELECT 1 FROM stock_invest_caution c WHERE c.code = a.code)
                    AND NOT EXISTS (SELECT 1 FROM stock_invest_danger  d WHERE d.code = a.code)
                    AND NOT EXISTS (SELECT 1 FROM stock_managing       m WHERE m.code = a.code)
                    AND NOT EXISTS (SELECT 1 FROM stock_konex          k WHERE k.code = a.code)

                ORDER BY a.close / a.clo120 DESC
                LIMIT {self.MAX_POSITIONS}
                """
            ).fetchall()

        except Exception as e:
            # 첫 에러는 콘솔에 출력 (원인 파악용)
            if _dbg:
                print(f"[E DEBUG] {date_str}: SQL 오류 — {e}")
                ValueStrategyE._debug_done = True
            logger.error("[E] %s: 기술적 필터 실패: %s", date_str, e)
            return []

        if _dbg:
            print(f"[E DEBUG] {date_str}: 기술적 필터 통과 {len(rows)}개 "
                  f"(4단정배열+ATR5%+RSI35-70 기준)")
            ValueStrategyE._debug_done = True

        if not rows:
            return []

        result = []
        for r in rows:
            row = dict(r)
            row['composite_score'] = float(row.get('trend_score') or 0)
            row['score_a']       = 0
            row['score_b']       = 0
            row['score_c']       = 0
            row['score_d']       = 0
            row['score_e']       = 0
            row['score_f']       = 0
            row['score_g']       = 0
            row['score_h']       = 0
            row['score_penalty'] = 0
            row['strategy_type'] = 'E'
            result.append(row)

        if result:
            logger.info("[E] %s: 최종 %d개 | TOP: %s (trend_score=%.1f%%)",
                        date_str, len(result),
                        result[0].get('code_name', '?'),
                        result[0]['composite_score'])
        return result
