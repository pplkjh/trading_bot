"""
DB 헬퍼 — control panel 전용.
pymysql 직접 사용 (SQLAlchemy 불필요).
jackbot4_imi1 + daily_buy_list 두 DB 모두 접근.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymysql
from datetime import datetime
from library.cf import (
    db_id, db_passwd, db_ip, db_port,
    imi1_db_name, initial_capital
)

def _today():
    return datetime.now().strftime('%Y%m%d')

# ── 커넥션 팩토리 ──────────────────────────────────────────────────
def _conn(db=None):
    return pymysql.connect(
        host=db_ip, port=int(db_port),
        user=db_id, passwd=db_passwd,
        db=db or imi1_db_name,
        charset='utf8',
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def _fetch(sql, args=None, db=None):
    """SELECT → list[dict]"""
    with _conn(db) as con:
        with con.cursor() as cur:
            cur.execute(sql, args or ())
            return cur.fetchall()


def _exec(sql, args=None, db=None):
    """INSERT / UPDATE / DELETE"""
    with _conn(db) as con:
        with con.cursor() as cur:
            cur.execute(sql, args or ())
            return cur.lastrowid


# ── manual_orders 테이블 초기화 ───────────────────────────────────
INIT_SQL = """
CREATE TABLE IF NOT EXISTS manual_orders (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  created_at    DATETIME DEFAULT NOW(),
  order_type    ENUM('BUY','SELL','PART_SELL','SELL_ALL','SCAN_D') NOT NULL,
  code          VARCHAR(10),
  code_name     VARCHAR(100),
  quantity      INT DEFAULT 0,
  strategy_type VARCHAR(5) DEFAULT NULL,
  status        ENUM('PENDING','EXECUTED','FAILED','CANCELLED') DEFAULT 'PENDING',
  executed_at   DATETIME,
  result_msg    VARCHAR(500)
) CHARACTER SET utf8
"""

def ensure_manual_orders_table():
    _exec(INIT_SQL)
    # 기존 테이블에 strategy_type 컬럼 없으면 추가 (마이그레이션)
    try:
        _exec("ALTER TABLE manual_orders ADD COLUMN strategy_type VARCHAR(5) DEFAULT NULL")
    except Exception:
        pass  # 이미 존재하면 무시
    # SCAN_D 커맨드 지원: ENUM에 'SCAN_D' 추가
    try:
        _exec("ALTER TABLE manual_orders MODIFY COLUMN order_type "
              "ENUM('BUY','SELL','PART_SELL','SELL_ALL','SCAN_D') NOT NULL")
    except Exception:
        pass


def ensure_jango_schema():
    """jango_data에 total_evaluation 컬럼 자동 추가 (없으면). Control Panel 시작 시 호출."""
    try:
        _exec("ALTER TABLE jango_data ADD COLUMN total_evaluation BIGINT DEFAULT 0")
    except Exception:
        pass  # 이미 존재하면 무시


# ── KPI ───────────────────────────────────────────────────────────
def get_kpis():
    """대시보드 KPI용 집계 쿼리 묶음. dict 반환."""
    rows = _fetch("""
        SELECT
          SUM(CASE WHEN sell_date='0' THEN valuation_profit ELSE 0 END) AS unrealized,
          SUM(CASE WHEN sell_date!='0' AND sell_date IS NOT NULL THEN realized_profit ELSE 0 END) AS realized,
          SUM(CASE WHEN sell_date='0' THEN 1 ELSE 0 END) AS open_count,
          COUNT(CASE WHEN sell_date!='0' AND sell_date IS NOT NULL THEN 1 END) AS total_trades,
          SUM(CASE WHEN sell_date!='0' AND sell_rate>0 THEN 1 ELSE 0 END) AS win_count,
          SUM(CASE WHEN sell_date!='0' AND sell_rate<=0 THEN 1 ELSE 0 END) AS loss_count,
          AVG(CASE WHEN sell_date!='0' AND sell_rate>0  THEN sell_rate END) AS avg_win,
          AVG(CASE WHEN sell_date!='0' AND sell_rate<=0 THEN sell_rate END) AS avg_loss
        FROM all_item_db
    """)
    r = rows[0] if rows else {}

    today_rows = _fetch("""
        SELECT COALESCE(SUM(realized_profit),0) AS today_pnl
        FROM all_item_db
        WHERE sell_date LIKE %s
    """, (_today() + '%',))
    today_pnl = int(today_rows[0]['today_pnl']) if today_rows else 0

    realized   = int(r.get('realized') or 0)
    unrealized = int(r.get('unrealized') or 0)

    n     = int(r.get('total_trades') or 0)
    win_n = int(r.get('win_count') or 0)
    loss_n= int(r.get('loss_count') or 0)
    avg_w = float(r.get('avg_win') or 0)
    avg_l = float(r.get('avg_loss') or 0)
    pf    = abs(avg_w / avg_l) if avg_l else 0

    # ── 실제 총자산: jango_data의 Kiwoom API 직접값 사용 ──────────────
    # total_asset  = opw00018 기준 (예수금 + 총주식평가금액) — 트레이더가 매일 갱신
    # total_evaluation = opw00018 총주식평가금액
    # d2_deposit   = opw00001 D+2 출금가능금액
    # fallback: d2_deposit + present_price×holding_amount 합산
    jango = _fetch(
        "SELECT d2_deposit, total_evaluation, total_asset "
        "FROM jango_data ORDER BY date DESC LIMIT 1"
    )
    if jango:
        j = jango[0]
        d2_deposit       = int(j.get('d2_deposit')       or 0)
        total_evaluation = int(j.get('total_evaluation') or 0)
        jango_total_asset = int(j.get('total_asset')     or 0)
    else:
        d2_deposit = total_evaluation = jango_total_asset = 0

    # 주식 평가금액 (all_item_db fallback용 — present_price × holding_amount)
    val_rows = _fetch(
        "SELECT COALESCE(SUM(present_price * holding_amount), 0) AS tot "
        "FROM all_item_db WHERE sell_date='0'"
    )
    total_value = int(val_rows[0]['tot'] or 0) if val_rows else 0

    # 총자산 결정: Kiwoom API 직접값 우선, 없으면 근사값
    if jango_total_asset > 0:
        total_asset = jango_total_asset                       # opw00018 실측값
    elif d2_deposit > 0:
        stock_val   = total_evaluation if total_evaluation > 0 else total_value
        total_asset = d2_deposit + stock_val                  # 예수금 + 주식평가
    else:
        total_asset = initial_capital + realized + unrealized  # 최후 fallback

    total_ret = (total_asset - initial_capital) / initial_capital * 100 if initial_capital else 0

    # 매수 후보 수
    cand_rows = _fetch("SELECT COUNT(*) AS cnt FROM realtime_daily_buy_list WHERE check_item='0'")
    cand_count = int(cand_rows[0]['cnt']) if cand_rows else 0

    # 트레이더 상태
    sd = _fetch("SELECT today_buy_stop FROM setting_data LIMIT 1")
    buy_stop = (sd[0]['today_buy_stop'] if sd else '0') or '0'
    trader_status = '매수 중지' if buy_stop == _today() else '정상 운영'

    # 투자금
    invest_rows = _fetch("SELECT invest_unit FROM setting_data LIMIT 1")
    invest_unit = int(invest_rows[0]['invest_unit'] or 0) if invest_rows else 0

    return {
        'total_asset': total_asset,
        'total_ret':   total_ret,
        'realized':    realized,
        'unrealized':  unrealized,
        'today_pnl':   today_pnl,
        'open_count':  int(r.get('open_count') or 0),
        'total_trades': n,
        'win_n':       win_n,
        'loss_n':      loss_n,
        'win_rate':    win_n / n * 100 if n else 0,
        'avg_win':     avg_w,
        'avg_loss':    avg_l,
        'pf':          pf,
        'd2_deposit':  d2_deposit,
        'total_value': total_value,
        'cand_count':  cand_count,
        'trader_status': trader_status,
        'buy_stop_val':  buy_stop,
        'invest_unit': invest_unit,
    }


# ── 보유 종목 ─────────────────────────────────────────────────────
def get_positions():
    return _fetch("""
        SELECT a.code, a.code_name,
               a.strategy_type, a.purchase_price, a.present_price,
               a.rate, a.valuation_profit, a.holding_amount,
               a.buy_date, a.composite_score,
               COALESCE(r.highest_price, a.present_price) AS highest_price
        FROM all_item_db a
        LEFT JOIN realtime_position_monitor r ON a.code = r.code
        WHERE a.sell_date = '0'
        ORDER BY a.buy_date ASC
    """)


# ── 매수 후보 ─────────────────────────────────────────────────────
def get_candidates(min_score=0, strategy='전체'):
    """
    realtime_all_scored (전체 스코어 결과) 우선, 없으면 realtime_daily_buy_list fallback.
    """
    # 테이블 존재 여부 확인
    chk = _fetch("SELECT COUNT(*) AS cnt FROM information_schema.tables "
                 "WHERE table_schema=%s AND table_name='realtime_all_scored'",
                 (imi1_db_name,))
    use_all = (chk[0]['cnt'] if chk else 0) > 0

    where = []
    args  = []
    if min_score > 0:
        where.append("composite_score >= %s")
        args.append(min_score)
    if strategy in ('A', 'B'):
        where.append("strategy_type = %s")
        args.append(strategy)
    where_clause = ('WHERE ' + ' AND '.join(where)) if where else ''

    if use_all:
        # "오늘 매수한 종목" 기준: buy_date=오늘 (보유중+당일매도 모두 포함)
        sql = f"""
            SELECT a.code, a.code_name, a.strategy_type,
                   a.composite_score,
                   a.score_a, a.score_b, a.score_c, a.score_d,
                   a.score_e, a.score_f, a.score_g, a.score_h,
                   a.score_penalty, a.vol5, a.vol20, a.rsi14, a.close,
                   a.passed,
                   CASE WHEN bought.code IS NOT NULL THEN '1' ELSE '0' END AS check_item
            FROM realtime_all_scored a
            LEFT JOIN (SELECT DISTINCT code FROM all_item_db
                       WHERE buy_date LIKE '{_today()}%%') bought
                   ON a.code = bought.code
            {where_clause}
            ORDER BY a.composite_score DESC
            LIMIT 50
        """
    else:
        sql = f"""
            SELECT r.code, r.code_name, r.strategy_type,
                   r.composite_score,
                   r.score_a, r.score_b, r.score_c, r.score_d, r.score_e, r.score_f, r.score_g,
                   0 AS score_h, r.score_penalty, r.vol5, r.vol20, r.rsi14, r.close,
                   1 AS passed,
                   CASE WHEN bought.code IS NOT NULL THEN '1' ELSE '0' END AS check_item
            FROM realtime_daily_buy_list r
            LEFT JOIN (SELECT DISTINCT code FROM all_item_db
                       WHERE buy_date LIKE '{_today()}%%') bought
                   ON r.code = bought.code
            {where_clause}
            ORDER BY r.composite_score DESC
            LIMIT 50
        """
    return _fetch(sql, args)


# ── 거래 내역 ─────────────────────────────────────────────────────
def get_history(date_from='', date_to='', strategy='전체', limit=200):
    where = ["sell_date != '0'", "sell_date IS NOT NULL"]
    args  = []
    if date_from:
        where.append("sell_date >= %s")
        args.append(date_from)
    if date_to:
        where.append("sell_date <= %s")
        args.append(date_to + '9')
    if strategy in ('A', 'B'):
        where.append("strategy_type = %s")
        args.append(strategy)
    sql = f"""
        SELECT code, code_name, strategy_type,
               buy_date, sell_date, purchase_price, sell_price,
               sell_rate, realized_profit, holding_amount,
               exit_reason
        FROM all_item_db
        WHERE {' AND '.join(where)}
        ORDER BY sell_date DESC
        LIMIT {int(limit)}
    """
    return _fetch(sql, args)


# ── 수동 주문 내역 ────────────────────────────────────────────────
def get_manual_orders(limit=50):
    return _fetch(f"""
        SELECT id, created_at, order_type, code, code_name,
               quantity, status, executed_at, result_msg
        FROM manual_orders
        ORDER BY id DESC LIMIT {int(limit)}
    """)


def insert_manual_order(order_type, code, code_name, quantity, strategy_type=None):
    return _exec("""
        INSERT INTO manual_orders (order_type, code, code_name, quantity, strategy_type)
        VALUES (%s, %s, %s, %s, %s)
    """, (order_type, code, code_name, int(quantity), strategy_type))


def request_d_scan():
    """트레이더에게 D전략 즉시 스캔 요청 (SCAN_D 커맨드 삽입)."""
    return _exec(
        "INSERT INTO manual_orders (order_type, code, code_name, quantity) "
        "VALUES ('SCAN_D', '', '', 0)"
    )


def reset_manual_orders():
    """PENDING 제외한 완료/실패/취소 주문 내역 삭제."""
    _exec("DELETE FROM manual_orders WHERE status != 'PENDING'")


def cancel_manual_order(order_id):
    _exec("UPDATE manual_orders SET status='CANCELLED' WHERE id=%s AND status='PENDING'",
          (order_id,))


# ── setting_data 읽기/쓰기 ────────────────────────────────────────
def get_setting():
    rows = _fetch("""
        SELECT today_buy_stop, invest_unit, limit_money
        FROM setting_data LIMIT 1
    """)
    return rows[0] if rows else {}


def set_buy_stop(stop: bool):
    val = _today() if stop else '0'
    _exec("UPDATE setting_data SET today_buy_stop=%s", (val,))


def set_invest_unit(amount: int):
    _exec("UPDATE setting_data SET invest_unit=%s, set_invest_unit='0'", (amount,))


def set_limit_money(amount: int):
    _exec("UPDATE setting_data SET limit_money=%s", (amount,))


# ── Strategy D 긴급 후보 ──────────────────────────────────────────
def get_urgent_candidates():
    """
    realtime_urgent_candidates 테이블 조회.
    테이블 없으면 빈 리스트 반환.
    """
    chk = _fetch("SELECT COUNT(*) AS cnt FROM information_schema.tables "
                 "WHERE table_schema=%s AND table_name='realtime_urgent_candidates'",
                 (imi1_db_name,))
    if not (chk and chk[0]['cnt'] > 0):
        return []
    return _fetch("""
        SELECT code, code_name, current_price, change_rate, volume, inst_net_buy, scanned_at
        FROM realtime_urgent_candidates
        ORDER BY inst_net_buy DESC
        LIMIT 50
    """)


def get_d_positions():
    """strategy_type='D'인 현재 보유 종목 조회."""
    return _fetch("""
        SELECT a.code, a.code_name, a.purchase_price, a.present_price,
               a.rate, a.valuation_profit, a.buy_date,
               COALESCE(r.highest_price, a.present_price) AS highest_price
        FROM all_item_db a
        LEFT JOIN realtime_position_monitor r ON a.code = r.code
        WHERE a.sell_date = '0' AND a.strategy_type = 'D'
        ORDER BY a.buy_date DESC
    """)


# ── 종목명 조회 (daily_buy_list DB) ─────────────────────────────
def lookup_code_name(code: str) -> str:
    try:
        rows = _fetch(
            "SELECT code_name FROM stock_item_all WHERE code=%s LIMIT 1",
            (code,), db='daily_buy_list'
        )
        return rows[0]['code_name'] if rows else ''
    except Exception:
        return ''


# ── 누적 P&L 이력 (대시보드 차트용) ─────────────────────────────
def get_pnl_history():
    """매도일별 일간 실현손익 집계 → [(date8, daily_pnl), ...] 오래된 순."""
    rows = _fetch("""
        SELECT SUBSTRING(sell_date, 1, 8) AS d,
               SUM(realized_profit)       AS pnl
        FROM all_item_db
        WHERE sell_date != '0' AND sell_date IS NOT NULL AND sell_date != ''
          AND SUBSTRING(sell_date, 1, 8) REGEXP '^[0-9]{8}$'
        GROUP BY d
        ORDER BY d ASC
    """)
    return [(r['d'], int(r['pnl'] or 0)) for r in rows]


# ── 일별 거래 내역 ────────────────────────────────────────────────
def get_daily_trades(date8: str):
    """특정 날짜에 매수 또는 매도된 모든 거래."""
    return _fetch(f"""
        SELECT code, code_name, strategy_type,
               buy_date, sell_date, purchase_price, sell_price,
               present_price, sell_rate, realized_profit, valuation_profit,
               holding_amount, composite_score, exit_reason,
               CASE
                 WHEN sell_date LIKE '{date8}%%' THEN '매도'
                 ELSE '매수'
               END AS action_type
        FROM all_item_db
        WHERE sell_date LIKE '{date8}%%'
           OR buy_date  LIKE '{date8}%%'
        ORDER BY sell_date DESC, buy_date DESC
    """)


def get_trading_dates(limit=120):
    """거래가 있었던 날짜 목록 (최근 limit일 기준, 내림차순)."""
    rows = _fetch(f"""
        SELECT DISTINCT SUBSTRING(sell_date, 1, 8) AS d
        FROM all_item_db
        WHERE sell_date != '0' AND sell_date IS NOT NULL AND sell_date != ''
          AND SUBSTRING(sell_date, 1, 8) REGEXP '^[0-9]{{8}}$'
        ORDER BY d DESC
        LIMIT {int(limit)}
    """)
    return [r['d'] for r in rows]


# ── 주가 이력 (daily_craw DB) ────────────────────────────────────
def get_price_history(code_name: str, days: int = 90) -> list:
    """
    daily_craw DB에서 종목 가격 이력 조회.
    테이블명 = 한글 종목명 (e.g. `삼성전자`).
    """
    if not code_name:
        return []
    try:
        sql = f"SELECT date, `open`, high, low, close, volume FROM `{code_name}` ORDER BY date DESC LIMIT %s"
        rows = _fetch(sql, (days,), db='daily_craw')
        return list(reversed(rows))   # 오래된 날짜 순으로 정렬
    except Exception:
        return []


# ── 긴급 매매 (D전략) ─────────────────────────────────────────────
def get_urgent_candidates() -> list:
    """실시간 긴급 매수 후보 (realtime_urgent_candidates 테이블, 없으면 빈 리스트)."""
    try:
        return _fetch("""
            SELECT code, code_name, current_price, change_rate,
                   volume, inst_net_buy, scanned_at
            FROM realtime_urgent_candidates
            ORDER BY scanned_at DESC, change_rate DESC
            LIMIT 30
        """)
    except Exception:
        return []


def get_d_positions() -> list:
    """D전략(strategy_type='D') 보유 종목."""
    try:
        return _fetch("""
            SELECT code, code_name, purchase_price, present_price,
                   rate, valuation_profit, buy_date
            FROM all_item_db
            WHERE sell_date = '0' AND strategy_type = 'D'
            ORDER BY buy_date DESC
        """)
    except Exception:
        return []
