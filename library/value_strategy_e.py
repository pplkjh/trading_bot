"""
library/value_strategy_e.py

Strategy E — baseline_v1 매수 스크리너
========================================
수립일: 2026-08-11

이전 4차(6단정배열 눌림목) 조건은 데이터 손상 구간에서 측정된 것으로 무효화됨.
이 파일은 baseline_v1로 초기화. 이전 성과 기록은 backtest_report/invalidated_baselines.md 참조.

매수 조건 (baseline_v1 스펙):
  - 3단 정배열: close > clo20 > clo60 > clo120
  - DMI 방향성:  plus_di > minus_di
  - 거래대금:    vol20 * close >= 100억
  - 위험종목 제외 (날짜 필터 적용):
      caution: post_date <= date AND fix_date >= date
      warning: post_date <= date AND (cleared_date IS NULL OR cleared_date >= date)
      danger:  post_date <= date AND (cleared_date IS NULL OR cleared_date >= date)
      managing/konex: 날짜 필터 없음 (날짜 컬럼 미존재)
  - 정렬: clo120 모멘텀(clo120/yes_clo120) 내림차순, 상위 3개

매도 조건 (시뮬레이터 구현, 여기서 정의 안 함):
  - SL -15% / MA60 이탈 / RSI≥80 (우선순위 순)

시뮬레이션 파라미터:
  - 슬롯: 5, 종목당 200만원, 신호 다음날 종가 체결, 왕복비용 0.23%

참고 문서: docs/baseline_v1_spec.md
"""
import logging

logger = logging.getLogger(__name__)


class ValueStrategyE:
    _debug_done = False

    # ── 기준선 v1 파라미터 ──────────────────────────────────────────────
    MIN_TRADING_VALUE  = 10_000_000_000  # 일평균 거래대금 100억 (소형주·조작주 차단)
    MAX_POSITIONS      = 3               # 일별 최대 신규 후보 수

    def screen(self, date_str: str, engine_dbl) -> list:
        """
        date_str  : YYYYMMDD (시뮬레이션 기준일)
        engine_dbl: daily_buy_list DB SQLAlchemy engine
        Returns: list[dict] — realtime_daily_buy_list 행, 최대 3개

        baseline_v1 매수 조건:
          3단정배열 + DMI + 거래대금100억 + 위험종목 제외(날짜필터)
          ORDER BY clo120 모멘텀 DESC
        """
        _dbg = not ValueStrategyE._debug_done

        # YYYYMMDD → YYYY-MM-DD (위험종목 테이블 DATE 비교용)
        date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

        try:
            rows = engine_dbl.execute(
                f"""
                SELECT a.*,
                       ROUND((a.clo120 / NULLIF(a.yes_clo120, 0) - 1) * 100, 4)
                           AS trend_momentum
                FROM `{date_str}` a
                WHERE
                    -- ① 거래대금 100억 이상 (소형주·조작주 차단)
                    (a.vol20 + 0.0) * a.close >= {self.MIN_TRADING_VALUE}

                    -- ② 3단 정배열 (close > clo20 > clo60 > clo120)
                    AND a.close > a.clo20
                    AND a.clo20 > a.clo60
                    AND a.clo60 > a.clo120

                    -- ③ DMI 방향성 (상승 추세 확인)
                    AND a.plus_di > a.minus_di

                    -- ④ 투자주의 (단기 지정, fix_date = 해제일)
                    AND NOT EXISTS (
                        SELECT 1 FROM stock_invest_caution c
                        WHERE c.code = a.code
                          AND c.post_date <= '{date_fmt}'
                          AND c.fix_date  >= '{date_fmt}'
                    )

                    -- ⑤ 투자경고 (cleared_date = 실제 해제일, NULL = 현재 지정 중)
                    AND NOT EXISTS (
                        SELECT 1 FROM stock_invest_warning w
                        WHERE w.code = a.code
                          AND w.post_date <= '{date_fmt}'
                          AND (w.cleared_date IS NULL OR w.cleared_date >= '{date_fmt}')
                    )

                    -- ⑥ 투자위험 (warning과 동일 구조)
                    AND NOT EXISTS (
                        SELECT 1 FROM stock_invest_danger d
                        WHERE d.code = a.code
                          AND d.post_date <= '{date_fmt}'
                          AND (d.cleared_date IS NULL OR d.cleared_date >= '{date_fmt}')
                    )

                    -- ⑦ 관리·KONEX (날짜 컬럼 없음 — 현재 등록 전체 제외)
                    AND NOT EXISTS (SELECT 1 FROM stock_managing m WHERE m.code = a.code)
                    AND NOT EXISTS (SELECT 1 FROM stock_konex    k WHERE k.code = a.code)

                -- clo120 모멘텀(120일MA 전일 대비 상승률) 내림차순
                ORDER BY (a.clo120 / NULLIF(a.yes_clo120, 0)) DESC
                LIMIT {self.MAX_POSITIONS}
                """
            ).fetchall()

        except Exception as e:
            if _dbg:
                print(f"[E DEBUG] {date_str}: SQL 오류 — {e}")
                ValueStrategyE._debug_done = True
            logger.error("[E] %s: 스크리닝 실패: %s", date_str, e)
            return []

        if _dbg:
            print(f"[E DEBUG] {date_str}: baseline_v1 통과 {len(rows)}개 "
                  f"(3단정배열+DMI+거래대금100억)")
            ValueStrategyE._debug_done = True

        if not rows:
            return []

        result = []
        for r in rows:
            row = dict(r)
            row['composite_score'] = float(row.get('trend_momentum') or 0)
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
            logger.info("[E] %s: 최종 %d개 | TOP: %s (trend_momentum=%.2f%%)",
                        date_str, len(result),
                        result[0].get('code_name', '?'),
                        result[0]['composite_score'])
        return result
