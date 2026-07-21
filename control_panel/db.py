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

TODAY = datetime.now().strftime('%Y%m%d')

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
  id           INT AUTO_INCREMENT PRIMARY KEY,
  created_at   DATETIME DEFAULT NOW(),
  order_type   ENUM('BUY','SELL','PART_SELL','SELL_ALL') NOT NULL,
  code         VARCHAR(10),
  code_name    VARCHAR(100),
  quantity     INT DEFAULT 0,
  status       ENUM('PENDING','EXECUTED','FAILED','CANCELLED') DEFAULT 'PENDING',
  executed_at  DATETIME,
  result_msg   VARCHAR(500)
) CHARACTER SET utf8
"""

def ensure_manual_orders_table():
    _exec(INIT_SQL)


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
    """, (TODAY + '%',))
    today_pnl = int(today_rows[0]['today_pnl']) if today_rows else 0

    realized   = int(r.get('realized') or 0)
    unrealized = int(r.get('unrealized') or 0)
    total_asset = initial_capital + realized + unrealized
    total_ret   = (realized + unrealized) / initial_capital * 100

    n     = int(r.get('total_trades') or 0)
    win_n = int(r.get('win_count') or 0)
    loss_n= int(r.get('loss_count') or 0)
    avg_w = float(r.get('avg_win') or 0)
    avg_l = float(r.get('avg_loss') or 0)
    pf    = abs(avg_w / avg_l) if avg_l else 0

    # 매수 후보 수
    cand_rows = _fetch("SELECT COUNT(*) AS cnt FROM realtime_daily_buy_list WHERE check_item='0'")
    cand_count = int(cand_rows[0]['cnt']) if cand_rows else 0

    # 트레이더 상태
    sd = _fetch("SELECT today_buy_stop FROM setting_data LIMIT 1")
    buy_stop = (sd[0]['today_buy_stop'] if sd else '0') or '0'
    trader_status = '매수 중지' if buy_stop == TODAY else '정상 운영'

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
    where = ["check_item='0'"]
    args  = []
    if min_score > 0:
        where.append("composite_score >= %s")
        args.append(min_score)
    if strategy in ('A', 'B'):
        where.append("strategy_type = %s")
        args.append(strategy)
    sql = f"""
        SELECT code, code_name, strategy_type,
               composite_score,
               score_a, score_b, score_c, score_d, score_e, score_f, score_g,
               score_penalty, volume_ratio, rsi14, close
        FROM realtime_daily_buy_list
        WHERE {' AND '.join(where)}
        ORDER BY composite_score DESC
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


def insert_manual_order(order_type, code, code_name, quantity):
    return _exec("""
        INSERT INTO manual_orders (order_type, code, code_name, quantity)
        VALUES (%s, %s, %s, %s)
    """, (order_type, code, code_name, int(quantity)))


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
    val = TODAY if stop else '0'
    _exec("UPDATE setting_data SET today_buy_stop=%s", (val,))


def set_invest_unit(amount: int):
    _exec("UPDATE setting_data SET invest_unit=%s, set_invest_unit='0'", (amount,))


def set_limit_money(amount: int):
    _exec("UPDATE setting_data SET limit_money=%s", (amount,))


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
