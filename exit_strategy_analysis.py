"""
매도 전략 사후 분석 스크립트 (Exit Strategy Analysis)

백테스트 완료 후 all_item_db의 매매 기록을 기반으로
daily_craw의 OHLCV 데이터를 이용해 다양한 매도 전략을 시뮬레이션하고 비교한다.

사용법:
    python exit_strategy_analysis.py --db jackbot3_imi1 --days 30
    python exit_strategy_analysis.py --db jackbot4_imi1 --days 20 --simul_num 4

주요 분석:
    1. 매수 후 N일간 일별 가격 경로 재구성
    2. 다양한 매도 전략별 결과 시뮬레이션 비교
    3. "놓친 수익" 분포 분석
    4. 전략별 최적 파라미터 힌트 제공
"""

import argparse
import os
import sys
import pathlib
from datetime import datetime, timedelta
from collections import defaultdict

import pymysql
import pandas as pd
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).parent.absolute()))
from library.cf import db_id, db_passwd, db_ip, db_port


# ─────────────────────────────────────────────
# DB 연결
# ─────────────────────────────────────────────

def get_connection(db_name):
    return pymysql.connect(
        user=db_id,
        passwd=db_passwd,
        host=db_ip,
        db=db_name,
        charset='utf8',
        port=int(db_port),
        cursorclass=pymysql.cursors.DictCursor
    )


# ─────────────────────────────────────────────
# 가격 경로 조회: daily_craw에서 매수일 이후 N일 OHLCV
# ─────────────────────────────────────────────

def get_price_path(con_craw, code_name, buy_date_str, window_days):
    """
    daily_craw DB에서 buy_date 이후 window_days 거래일 OHLCV 반환.
    반환: list of dict {date, open, high, low, close, volume}
    """
    try:
        with con_craw.cursor() as cur:
            sql = (
                f"SELECT date, open, high, low, close, volume "
                f"FROM `{code_name}` "
                f"WHERE date >= '{buy_date_str}' "
                f"ORDER BY date ASC "
                f"LIMIT {window_days + 1}"  # +1: 매수 당일 포함
            )
            cur.execute(sql)
            rows = cur.fetchall()
        return rows
    except Exception:
        return []


# ─────────────────────────────────────────────
# 매도 전략 시뮬레이터
# ─────────────────────────────────────────────

def simulate_fixed_tp_sl(rows, entry_price, tp_pct, sl_pct):
    """고정 TP/SL: 첫 번째로 도달하는 시점 반환"""
    for i, row in enumerate(rows[1:], start=1):  # 매수 당일 제외
        high_pct = (row['high'] / entry_price - 1) * 100
        low_pct  = (row['low']  / entry_price - 1) * 100
        close_pct = (row['close'] / entry_price - 1) * 100

        # 당일 고가로 TP 먼저 체크, 저가로 SL 체크
        if high_pct >= tp_pct:
            return i, tp_pct, 'TP'
        if low_pct <= sl_pct:
            return i, sl_pct, 'SL'
        # 마지막 날이면 종가로 청산
        if i == len(rows) - 1:
            return i, close_pct, 'TIME'
    return len(rows) - 1, (rows[-1]['close'] / entry_price - 1) * 100, 'TIME'


def simulate_trailing_stop(rows, entry_price, activation_pct, trail_pct, floor_pct=0.01):
    """
    트레일링 스톱:
    - activation_pct 이상 수익 시 발동
    - 최고가에서 trail_pct 만큼 하락 시 청산
    - floor = entry * (1 + floor_pct) 보장 (floor 이하로는 청산 안 함)
    """
    peak = entry_price
    activated = False
    floor_price = entry_price * (1 + floor_pct)

    for i, row in enumerate(rows[1:], start=1):
        high_pct = (row['high'] / entry_price - 1) * 100

        if high_pct >= activation_pct:
            activated = True

        if row['high'] > peak:
            peak = row['high']

        if activated:
            trail_stop = max(floor_price, peak * (1 - trail_pct / 100))
            if row['low'] <= trail_stop:
                exit_price = max(trail_stop, row['low'])
                exit_pct = (exit_price / entry_price - 1) * 100
                return i, exit_pct, 'TRAIL'

        if i == len(rows) - 1:
            close_pct = (row['close'] / entry_price - 1) * 100
            return i, close_pct, 'TIME'

    return len(rows) - 1, (rows[-1]['close'] / entry_price - 1) * 100, 'TIME'


def simulate_ma_deadcross(rows, entry_price, ma_short=5, ma_long=20):
    """MA 데드크로스 시 청산 (ma_short < ma_long)"""
    closes = [r['close'] for r in rows]

    for i in range(1, len(rows)):
        if i < ma_long:
            continue
        short_ma = np.mean(closes[i - ma_short + 1: i + 1])
        long_ma  = np.mean(closes[i - ma_long  + 1: i + 1])
        if short_ma < long_ma:
            prev_short = np.mean(closes[i - ma_short: i])
            prev_long  = np.mean(closes[i - ma_long:  i])
            if prev_short >= prev_long:  # 직전엔 golden cross
                close_pct = (rows[i]['close'] / entry_price - 1) * 100
                return i, close_pct, 'MA_DEAD'

    close_pct = (rows[-1]['close'] / entry_price - 1) * 100
    return len(rows) - 1, close_pct, 'TIME'


def simulate_combined(rows, entry_price, tp_pct, sl_pct, trail_activation_pct, trail_pct, floor_pct=0.01):
    """복합 전략: SL + 트레일링 TP (고정 TP 없음)"""
    peak = entry_price
    trail_activated = False
    floor_price = entry_price * (1 + floor_pct)

    for i, row in enumerate(rows[1:], start=1):
        high_pct  = (row['high'] / entry_price - 1) * 100
        low_pct   = (row['low']  / entry_price - 1) * 100

        # SL 먼저
        if low_pct <= sl_pct:
            return i, sl_pct, 'SL'

        if high_pct >= trail_activation_pct:
            trail_activated = True

        if row['high'] > peak:
            peak = row['high']

        if trail_activated:
            trail_stop = max(floor_price, peak * (1 - trail_pct / 100))
            if row['low'] <= trail_stop:
                exit_price = max(trail_stop, row['low'])
                exit_pct = (exit_price / entry_price - 1) * 100
                return i, exit_pct, 'TRAIL'

        if i == len(rows) - 1:
            close_pct = (row['close'] / entry_price - 1) * 100
            return i, close_pct, 'TIME'

    return len(rows) - 1, (rows[-1]['close'] / entry_price - 1) * 100, 'TIME'


def _calc_rsi_list(closes, period=14):
    """EWM 방식 RSI 계산 — list 반환"""
    s = pd.Series(closes, dtype=float)
    delta = s.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float('nan'))
    return (100 - (100 / (1 + rs))).fillna(50).tolist()


def get_price_path_extended(con_craw, code_name, buy_date_str, window_days, pre_days=30):
    """매수일 이전 pre_days + 이후 window_days 데이터 반환 — RSI 초기화용"""
    try:
        with con_craw.cursor() as cur:
            cur.execute(
                f"SELECT date, open, high, low, close, volume FROM `{code_name}` "
                f"WHERE date < '{buy_date_str}' ORDER BY date DESC LIMIT {pre_days}"
            )
            pre_rows = list(reversed(cur.fetchall()))
            cur.execute(
                f"SELECT date, open, high, low, close, volume FROM `{code_name}` "
                f"WHERE date >= '{buy_date_str}' ORDER BY date ASC LIMIT {window_days + 1}"
            )
            post_rows = cur.fetchall()
        return pre_rows, post_rows
    except Exception:
        return [], []


def simulate_rsi_exit(pre_rows, post_rows, entry_price, rsi_threshold, sl_pct, max_days):
    """RSI >= threshold OR SL OR max_days 시간청산"""
    if not post_rows:
        return 0, 0.0, 'TIME'
    all_closes = [r['close'] for r in pre_rows] + [r['close'] for r in post_rows]
    rsi_all = _calc_rsi_list(all_closes)
    pre_len = len(pre_rows)
    limit = min(len(post_rows) - 1, max_days)
    for i in range(1, limit + 1):
        row = post_rows[i]
        rsi_idx = pre_len + i
        rsi_val = rsi_all[rsi_idx] if rsi_idx < len(rsi_all) else 50.0
        low_pct   = (row['low']   / entry_price - 1) * 100
        close_pct = (row['close'] / entry_price - 1) * 100
        if low_pct <= sl_pct:
            return i, sl_pct, 'SL'
        if rsi_val >= rsi_threshold:
            return i, close_pct, f'RSI{rsi_threshold:.0f}'
        if i == limit:
            return i, close_pct, 'TIME'
    close_pct = (post_rows[-1]['close'] / entry_price - 1) * 100
    return len(post_rows) - 1, close_pct, 'TIME'


# ─────────────────────────────────────────────
# 통계 계산
# ─────────────────────────────────────────────

def calc_stats(results):
    """results: list of (days_held, exit_pct, exit_type)"""
    if not results:
        return {}
    pcts = [r[1] for r in results]
    wins  = [p for p in pcts if p > 0]
    loses = [p for p in pcts if p <= 0]
    exit_counts = defaultdict(int)
    for r in results:
        exit_counts[r[2]] += 1

    return {
        'count':       len(pcts),
        'avg_pct':     np.mean(pcts),
        'median_pct':  np.median(pcts),
        'win_rate':    len(wins) / len(pcts) * 100,
        'avg_win':     np.mean(wins)  if wins  else 0,
        'avg_loss':    np.mean(loses) if loses else 0,
        'max_win':     max(pcts),
        'max_loss':    min(pcts),
        'avg_days':    np.mean([r[0] for r in results]),
        'exit_counts': dict(exit_counts),
    }


def pct_above_threshold(values, threshold):
    return sum(1 for v in values if v >= threshold) / len(values) * 100 if values else 0

def pct_below_threshold(values, threshold):
    return sum(1 for v in values if v <= threshold) / len(values) * 100 if values else 0


# ─────────────────────────────────────────────
# 메인 분석
# ─────────────────────────────────────────────

def run_analysis(target_db, window_days, simul_num_filter=None, output_dir=None):
    con_trade = get_connection(target_db)
    con_craw  = get_connection('daily_craw')

    # 컬럼 존재 여부 사전 확인
    with con_trade.cursor() as cur:
        cur.execute("SHOW COLUMNS FROM all_item_db LIKE 'max_high_pct'")
        has_minmax = cur.fetchone() is not None
        cur.execute("SHOW COLUMNS FROM all_item_db LIKE 'strategy_type'")
        has_strategy_type = cur.fetchone() is not None

    minmax_cols = (
        "COALESCE(max_high_pct, 0) as max_high_pct, COALESCE(min_low_pct, 0) as min_low_pct"
        if has_minmax else
        "0 as max_high_pct, 0 as min_low_pct"
    )
    strategy_col = "strategy_type" if has_strategy_type else "'N/A' as strategy_type"
    where_simul  = f"AND simul_num = {simul_num_filter}" if simul_num_filter else ""

    sql = f"""
        SELECT code, code_name, buy_date, purchase_price, sell_date, sell_rate,
               {minmax_cols}, {strategy_col}
        FROM all_item_db
        WHERE sell_date != '0' {where_simul}
        ORDER BY buy_date
    """
    with con_trade.cursor() as cur:
        cur.execute(sql)
        trades = cur.fetchall()

    print(f"총 {len(trades)}건 분석 중 (window={window_days}일)...")

    # 전략 정의
    strategies = {
        'TP+6/SL-3':       lambda rows, ep: simulate_fixed_tp_sl(rows, ep, 6, -3),
        'TP+8/SL-4':       lambda rows, ep: simulate_fixed_tp_sl(rows, ep, 8, -4),
        'TP+10/SL-5':      lambda rows, ep: simulate_fixed_tp_sl(rows, ep, 10, -5),
        'TP+12/SL-5':      lambda rows, ep: simulate_fixed_tp_sl(rows, ep, 12, -5),
        'Trail(3%act,5%trail,1%floor)': lambda rows, ep: simulate_trailing_stop(rows, ep, 3, 5, 1),
        'Trail(5%act,7%trail,1%floor)': lambda rows, ep: simulate_trailing_stop(rows, ep, 5, 7, 1),
        'SL-3+Trail(3%act,5%trail)':    lambda rows, ep: simulate_combined(rows, ep, 99, -3, 3, 5, 0.01),
        'SL-5+Trail(3%act,5%trail)':    lambda rows, ep: simulate_combined(rows, ep, 99, -5, 3, 5, 0.01),
        'MA_DeadCross':    lambda rows, ep: simulate_ma_deadcross(rows, ep),
        f'Hold{window_days}d': lambda rows, ep: (
            len(rows) - 1,
            (rows[-1]['close'] / ep - 1) * 100 if rows else (0, 0, 'TIME'),
            'TIME'
        ),
    }

    # RSI 기반 전략 정의 (pre_rows 필요 — 별도 처리)
    rsi_strategies = {
        'RSI>55+SL-5(20d)': lambda pr, po, ep: simulate_rsi_exit(pr, po, ep, 55, -5, 20),
        'RSI>60+SL-5(20d)': lambda pr, po, ep: simulate_rsi_exit(pr, po, ep, 60, -5, 20),
        'RSI>60+SL-7(30d)': lambda pr, po, ep: simulate_rsi_exit(pr, po, ep, 60, -7, 30),
        'RSI>65+SL-5(30d)': lambda pr, po, ep: simulate_rsi_exit(pr, po, ep, 65, -5, 30),
    }

    # 종목별로 전략 시뮬레이션
    strategy_results = {k: [] for k in strategies}
    rsi_strategy_results = {k: [] for k in rsi_strategies}
    actual_sell_pcts = []
    max_high_pcts    = []
    min_low_pcts     = []
    skipped = 0

    for trade in trades:
        code_name    = trade['code_name']
        buy_date     = str(trade['buy_date'])
        entry_price  = int(trade['purchase_price'])
        actual_pct   = float(trade['sell_rate'])

        rows = get_price_path(con_craw, code_name, buy_date, window_days)
        if len(rows) < 3:
            skipped += 1
            continue

        actual_sell_pcts.append(actual_pct)
        max_high_pcts.append(float(trade['max_high_pct']))
        min_low_pcts.append(float(trade['min_low_pct']))

        for name, fn in strategies.items():
            try:
                result = fn(rows, entry_price)
                strategy_results[name].append(result)
            except Exception:
                pass

        # RSI 전략 — pre_rows 별도 fetch
        try:
            pre_rows, post_rows = get_price_path_extended(con_craw, code_name, buy_date, window_days, pre_days=30)
            if post_rows and len(post_rows) >= 3:
                for name, fn in rsi_strategies.items():
                    try:
                        result = fn(pre_rows, post_rows, entry_price)
                        rsi_strategy_results[name].append(result)
                    except Exception:
                        pass
        except Exception:
            pass

    con_trade.close()
    con_craw.close()

    # ─── 리포트 출력 ───
    now_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_lines = []

    def w(line=''):
        report_lines.append(line)

    w('=' * 90)
    w(f'  매도 전략 사후 분석 리포트')
    w(f'  DB: {target_db}  |  분석기간: 매수 후 {window_days}거래일  |  분석건수: {len(actual_sell_pcts)}건 (스킵: {skipped}건)')
    w(f'  생성: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    w('=' * 90)

    # 실제 매도 결과 요약
    w()
    w('[ 실제 매도 결과 (백테스트 원본) ]')
    w('-' * 60)
    if actual_sell_pcts:
        wins  = [p for p in actual_sell_pcts if p > 0]
        loses = [p for p in actual_sell_pcts if p <= 0]
        w(f'  평균 수익률  : {np.mean(actual_sell_pcts):+.2f}%')
        w(f'  승률        : {len(wins)/len(actual_sell_pcts)*100:.1f}%  (승: {len(wins)}건 / 패: {len(loses)}건)')
        w(f'  평균 익절   : {np.mean(wins):+.2f}%' if wins else '  평균 익절   : N/A')
        w(f'  평균 손절   : {np.mean(loses):+.2f}%' if loses else '  평균 손절   : N/A')

    # 보유 중 최대/최소 분포
    w()
    w(f'[ 보유 기간 중 가격 잠재력 (max_high_pct / min_low_pct) ]')
    w('-' * 60)
    if max_high_pcts:
        w(f'  최대 고가 수익률 평균  : +{np.mean(max_high_pcts):.2f}%')
        w(f'  최대 저가 손실률 평균  : {np.mean(min_low_pcts):.2f}%')
        w()
        w('  max_high_pct 분포 (달성 가능 수익 상한):')
        for thr in [3, 5, 6, 8, 10, 12, 15, 20]:
            pct = pct_above_threshold(max_high_pcts, thr)
            bar = '#' * int(pct / 2)
            w(f'    > +{thr:2d}%  :  {pct:5.1f}%  {bar}')
        w()
        w('  min_low_pct 분포 (최대 역행 손실):')
        for thr in [-2, -3, -4, -5, -7, -10]:
            pct = pct_below_threshold(min_low_pcts, thr)
            bar = '#' * int(pct / 2)
            w(f'    < {thr:3d}%  :  {pct:5.1f}%  {bar}')

    # 전략별 비교
    w()
    w('[ 전략별 시뮬레이션 결과 비교 ]')
    w('-' * 90)
    w(f'  {"전략명":<38} {"평균수익":>8} {"승률":>7} {"평균익절":>9} {"평균손절":>9} {"최대익":>8} {"최대손":>8} {"평균보유일":>9}')
    w('-' * 90)

    for name, results in strategy_results.items():
        s = calc_stats(results)
        if not s:
            continue
        w(f'  {name:<38} {s["avg_pct"]:>+7.2f}% {s["win_rate"]:>6.1f}% '
          f'{s["avg_win"]:>+8.2f}% {s["avg_loss"]:>+8.2f}% '
          f'{s["max_win"]:>+7.2f}% {s["max_loss"]:>+7.2f}% '
          f'{s["avg_days"]:>8.1f}일')

    w('-' * 90)
    w(f'  {"[RSI 기반 전략]":<38}')
    for name, results in rsi_strategy_results.items():
        s = calc_stats(results)
        if not s:
            continue
        w(f'  {name:<38} {s["avg_pct"]:>+7.2f}% {s["win_rate"]:>6.1f}% '
          f'{s["avg_win"]:>+8.2f}% {s["avg_loss"]:>+8.2f}% '
          f'{s["max_win"]:>+7.2f}% {s["max_loss"]:>+7.2f}% '
          f'{s["avg_days"]:>8.1f}일')

    # TP 달성률 상세 (fixed TP 전략 기준)
    w()
    w('[ TP 달성률 vs SL 발동률 상세 ]')
    w('-' * 60)
    for name, results in list(strategy_results.items()) + list(rsi_strategy_results.items()):
        if not results:
            continue
        exit_counts = defaultdict(int)
        for r in results:
            exit_counts[r[2]] += 1
        total = len(results)
        parts = [f'{k}:{v/total*100:.1f}%' for k, v in sorted(exit_counts.items())]
        w(f'  {name:<38}  {" | ".join(parts)}')

    # 추천 파라미터 힌트
    w()
    w('[ 파라미터 힌트 ]')
    w('-' * 60)
    if max_high_pcts and min_low_pcts:
        # SL 힌트: min_low_pct의 특정 백분위수
        p25_low = np.percentile(min_low_pcts, 25)
        p50_low = np.percentile(min_low_pcts, 50)
        w(f'  권장 SL 범위:')
        w(f'    타이트 (하위25% 역행만 컷): {p25_low:.1f}%  → 노이즈 제거 후 재진입 전략에 적합')
        w(f'    넉넉  (중간값 역행까지 허용): {p50_low:.1f}%  → 반등 기다리는 전략에 적합')
        w()
        p75_high = np.percentile(max_high_pcts, 75)
        p50_high = np.percentile(max_high_pcts, 50)
        w(f'  권장 TP/Trail 발동 범위:')
        w(f'    절반 이상 도달하는 수익률 (50th pct): +{p50_high:.1f}%')
        w(f'    상위 25% 종목 수익률 (75th pct): +{p75_high:.1f}%')
        w(f'    → Trail 발동점: +{p50_high*0.5:.1f}~{p50_high*0.7:.1f}% 권장')

    w()
    w('=' * 90)

    report_text = '\n'.join(report_lines)
    print(report_text)

    if output_dir is None:
        output_dir = pathlib.Path(__file__).parent / 'backtest_report'
    else:
        output_dir = pathlib.Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    db_short = target_db.replace('_imi1', '').replace('jackbot', 'algo')
    fname = output_dir / f'exit_analysis_{db_short}_{now_str}.txt'
    with open(fname, 'w', encoding='utf-8') as f:
        f.write(report_text)
    print(f'\n리포트 저장: {fname}')


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='매도 전략 사후 분석')
    parser.add_argument('--db',        default='jackbot3_imi1', help='분석할 DB 이름')
    parser.add_argument('--days',      type=int, default=30,    help='매수 후 추적 거래일 수')
    parser.add_argument('--simul_num', type=int, default=None,  help='simul_num 필터 (없으면 전체)')
    parser.add_argument('--output',    default=None,            help='리포트 저장 디렉토리')
    args = parser.parse_args()

    run_analysis(
        target_db=args.db,
        window_days=args.days,
        simul_num_filter=args.simul_num,
        output_dir=args.output,
    )
