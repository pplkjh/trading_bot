"""
library/value_strategy_e.py

Strategy E — baseline_v2 매수 스크리너
========================================
수립일: 2026-08-12  (baseline_v1 → v2 전환)

v1 대비 4가지 변경:
  1) vol20*close >= 100억  →  vol120*close >= 300억  (크기 필터로 교체)
  2) vol20 <= vol120 * 2.5  (신규: 단기 거래량 급증 배제)
  3) atr14 / close <= 0.06  (신규: 고변동성 소형주 제거)
  4) ORDER BY: clo120 모멘텀 → vol120*close 내림차순  (유동시총 대형 우선)

변경하지 않은 것:
  - 3단 정배열, DMI, 위험종목 제외
  - 매도 규칙 (v1: SL -15% / MA60 / RSI≥80)
  - 포트폴리오 파라미터 (슬롯 5, 종목당 200만원, LIMIT 5=cf.e_max_positions)

이전 버전: backtest_report/bv1_backtest_result.md (Calmar -0.41)

회귀 테스트 (Step 2, 2026-08-12): 목표 6종목 전원 PASS
  삼성전자246일 / 신한지주271일 / KB금융282일
  한화에어로스페이스236일 / HD현대중공업169일 / SK스퀘어167일
"""
import logging

logger = logging.getLogger(__name__)


class ValueStrategyE:
    _debug_done = False

    # ── baseline_v2 파라미터 ────────────────────────────────────────────
    MIN_VOL120_VALUE   = 30_000_000_000   # vol120*close >= 300억 (v1: vol20*close 100억)
    MAX_ATR_RATE       = 0.06             # atr14/close <= 6% (신규)
    MAX_VOL20_RATIO    = 2.5              # vol20 <= vol120 * 2.5 (신규: 급증 배제)
    MAX_POSITIONS      = 5               # cf.e_max_positions 일치

    def screen(self, date_str: str, engine_dbl) -> list:
        """
        date_str  : YYYYMMDD (시뮬레이션 기준일)
        engine_dbl: daily_buy_list DB SQLAlchemy engine
        Returns: list[dict] — realtime_daily_buy_list 행, 최대 5개

        baseline_v2 매수 조건:
          3단정배열 + DMI + vol120*close>=300억 + vol20/vol120<=2.5
          + ATR<=6% + 위험종목 제외
          ORDER BY vol120*close DESC (유동시총 대형주 우선)
        """
        _dbg = not ValueStrategyE._debug_done

        # YYYYMMDD → YYYY-MM-DD (위험종목 테이블 DATE 비교용)
        date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

        try:
            rows = engine_dbl.execute(
                f"""
                SELECT a.*,
                       ROUND((a.vol120 + 0.0) * a.close / 100000000, 1)
                           AS liq_cap_100m
                FROM `{date_str}` a
                WHERE
                    -- ① vol120*close >= 300억 (유동시총 대용 크기 필터)
                    (a.vol120 + 0.0) * a.close >= {self.MIN_VOL120_VALUE}

                    -- ② 단기 거래량 급증 배제 (모멘텀 피크 진입 방지)
                    AND a.vol20 <= a.vol120 * {self.MAX_VOL20_RATIO}

                    -- ③ 3단 정배열 (close > clo20 > clo60 > clo120)
                    AND a.close > a.clo20
                    AND a.clo20 > a.clo60
                    AND a.clo60 > a.clo120

                    -- ④ DMI 방향성 (상승 추세 확인)
                    AND a.plus_di > a.minus_di

                    -- ⑤ 고변동성 소형주 제거 (ATR/가격 <= 6%)
                    AND a.atr14 <= a.close * {self.MAX_ATR_RATE}

                    -- ⑥ 투자주의 (단기 지정, fix_date = 해제일)
                    AND NOT EXISTS (
                        SELECT 1 FROM stock_invest_caution c
                        WHERE c.code = a.code
                          AND c.post_date <= '{date_fmt}'
                          AND c.fix_date  >= '{date_fmt}'
                    )

                    -- ⑦ 투자경고 (cleared_date = 실제 해제일, NULL = 현재 지정 중)
                    AND NOT EXISTS (
                        SELECT 1 FROM stock_invest_warning w
                        WHERE w.code = a.code
                          AND w.post_date <= '{date_fmt}'
                          AND (w.cleared_date IS NULL OR w.cleared_date >= '{date_fmt}')
                    )

                    -- ⑧ 투자위험 (warning과 동일 구조)
                    AND NOT EXISTS (
                        SELECT 1 FROM stock_invest_danger d
                        WHERE d.code = a.code
                          AND d.post_date <= '{date_fmt}'
                          AND (d.cleared_date IS NULL OR d.cleared_date >= '{date_fmt}')
                    )

                    -- ⑨ 관리·KONEX (날짜 컬럼 없음 — 현재 등록 전체 제외)
                    AND NOT EXISTS (SELECT 1 FROM stock_managing m WHERE m.code = a.code)
                    AND NOT EXISTS (SELECT 1 FROM stock_konex    k WHERE k.code = a.code)

                -- 유동시총 내림차순 (대형주 우선, v1: clo120 모멘텀)
                ORDER BY (a.vol120 + 0.0) * a.close DESC
                LIMIT {self.MAX_POSITIONS}
                """
            ).fetchall()

        except Exception as e:
            logger.error("[E] %s: 스크리닝 실패: %s", date_str, e)
            return []

        if _dbg:
            logger.debug("[E] %s: baseline_v2 통과 %d개 (vol120*close>=300억 + ATR<=6%% + 정배열 + DMI)",
                         date_str, len(rows))
            ValueStrategyE._debug_done = True

        if not rows:
            return []

        result = []
        for r in rows:
            row = dict(r)
            # composite_score = 유동시총(억원) — ORDER BY 기준과 일치
            row['composite_score'] = float(row.get('liq_cap_100m') or 0)
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
            logger.info("[E] %s: 최종 %d개 | TOP: %s (liq_cap=%.0f억)",
                        date_str, len(result),
                        result[0].get('code_name', '?'),
                        result[0]['composite_score'])
        return result
