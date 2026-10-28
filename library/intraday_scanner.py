"""
Strategy D — 장중 데이트레이딩 종목 스캐너
OPT10028 (시가대비등락률 상위) + OPT10063 (기관+외국 동시순매수) 교집합 필터
→ realtime_urgent_candidates 테이블 저장 (trader_advanced.py에서 20분마다 호출)
"""
import time
import logging
from library import cf

logger = logging.getLogger(__name__)

_MIN_CHANGE_RATE = 2.0   # 시가대비 최소 상승률 (%)
_MIN_INST_NET    = 0     # 기관 순매수금액 최소값 (0 = 순매수면 모두 포함)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS realtime_urgent_candidates (
  code             VARCHAR(10)  NOT NULL PRIMARY KEY,
  code_name        VARCHAR(100),
  current_price    INT          DEFAULT 0,
  change_rate      FLOAT        DEFAULT 0,
  volume           BIGINT       DEFAULT 0,
  inst_net_buy     BIGINT       DEFAULT 0,
  foreign_net_buy  BIGINT       DEFAULT 0,
  scanned_at       DATETIME     DEFAULT NOW()
) CHARACTER SET utf8
"""

_ALTER_ADD_FOREIGN = (
    "ALTER TABLE realtime_urgent_candidates "
    "ADD COLUMN foreign_net_buy BIGINT DEFAULT 0"
)


def run_intraday_scan(open_api, engine_JB):
    """
    OPT10028 + OPT10063 스캔 후 교집합 종목을 realtime_urgent_candidates에 저장.
    trader_advanced.py의 run() 루프에서 20분마다 호출.
    """
    try:
        # 1. OPT10028 — 시가대비 등락률 상위
        open_api.rq_opt10028()
        time.sleep(cf.TR_REQ_TIME_INTERVAL)
        map10028 = {r['code']: r for r in open_api.intraday_scan_opt10028}

        # 2. OPT10063 — 기관+외국 동시순매수 스크리닝 (투자자별=7)
        open_api.rq_opt10063()
        time.sleep(cf.TR_REQ_TIME_INTERVAL)
        map10063 = {r['code']: r for r in open_api.intraday_scan_opt10063}

        # 3. OPT10063 — 외국계 순매수 금액 별도 요청 (투자자별=6)
        open_api.rq_opt10063_foreign()
        time.sleep(cf.TR_REQ_TIME_INTERVAL)
        map10063_foreign = {r['code']: r['foreign_net_buy']
                            for r in open_api.intraday_scan_opt10063_foreign}

        if not map10028:
            logger.warning("[D스캔] OPT10028 결과 없음 (장 외 시간 or API 오류)")
            return
        if not map10063:
            logger.warning("[D스캔] OPT10063 결과 없음")
            return

        # 4. 교집합 + 최소 등락률 필터
        common = set(map10028.keys()) & set(map10063.keys())
        candidates = []
        for code in common:
            a = map10028[code]
            b = map10063[code]
            if a['change_rate'] < _MIN_CHANGE_RATE:
                continue
            if b['inst_net_buy'] <= _MIN_INST_NET:
                continue
            candidates.append({
                'code':            code,
                'code_name':       a['code_name'],
                'current_price':   a['current_price'],
                'change_rate':     a['change_rate'],
                'volume':          a['volume'],
                'inst_net_buy':    b['inst_net_buy'],
                'foreign_net_buy': map10063_foreign.get(code, 0),
            })

        # 4. DB 저장
        engine_JB.execute(_CREATE_TABLE_SQL)
        # 기존 테이블에 foreign_net_buy 컬럼 없으면 자동 추가
        try:
            engine_JB.execute(_ALTER_ADD_FOREIGN)
        except Exception:
            pass  # 이미 존재하면 무시
        engine_JB.execute("DELETE FROM realtime_urgent_candidates")
        for c in candidates:
            engine_JB.execute(
                """
                INSERT INTO realtime_urgent_candidates
                  (code, code_name, current_price, change_rate, volume,
                   inst_net_buy, foreign_net_buy, scanned_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                ON DUPLICATE KEY UPDATE
                  code_name=VALUES(code_name), current_price=VALUES(current_price),
                  change_rate=VALUES(change_rate), volume=VALUES(volume),
                  inst_net_buy=VALUES(inst_net_buy),
                  foreign_net_buy=VALUES(foreign_net_buy),
                  scanned_at=NOW()
                """,
                (c['code'], c['code_name'], c['current_price'],
                 c['change_rate'], c['volume'],
                 c['inst_net_buy'], c['foreign_net_buy'])
            )

        logger.info(
            f"[D스캔] OPT10028={len(map10028)}건 / OPT10063={len(map10063)}건 "
            f"→ 교집합 {len(candidates)}건 저장"
        )

    except Exception as e:
        logger.error(f"[D스캔] 실패: {e}")
        import traceback
        traceback.print_exc()
