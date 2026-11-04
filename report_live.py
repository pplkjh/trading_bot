"""
실전 투자 전체 기간 종합 보고서
jackbot4_imi1 DB 기반 (simul_num=6, A+B 혼합 전략)

실행: python report_live.py [--chart]
"""

import sys
import os
import argparse
from datetime import datetime, timedelta
from collections import defaultdict

import pymysql
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from library.cf import db_id, db_passwd, db_ip, db_port, imi1_db_name


# ─────────────────────────────────────────────────────────
# DB 연결 헬퍼
# ─────────────────────────────────────────────────────────
def connect():
    return pymysql.connect(
        user=db_id, passwd=db_passwd, host=db_ip,
        port=int(db_port), db=imi1_db_name, charset='utf8'
    )


# ─────────────────────────────────────────────────────────
# 데이터 로드
# ─────────────────────────────────────────────────────────
def load_data():
    con = connect()

    # 체결 완료 거래 (매도된 것)
    trades = pd.read_sql("""
        SELECT code, code_name,
               buy_date, sell_date,
               purchase_price, sell_price,
               sell_rate, realized_profit,
               holding_amount,
               strategy_type,
               exit_reason,
               composite_score
        FROM all_item_db
        WHERE sell_date != '0' AND sell_date IS NOT NULL
        ORDER BY sell_date ASC
    """, con)

    # 미결 포지션
    open_pos = pd.read_sql("""
        SELECT code, code_name,
               purchase_price, present_price,
               holding_amount, rate, valuation_profit,
               valuation_price, item_total_purchase,
               strategy_type, buy_date
        FROM all_item_db
        WHERE sell_date = '0'
    """, con)

    # 일별 잔고 스냅샷
    jango = pd.read_sql("""
        SELECT date, d2_deposit, total_invest, today_profit, today_earning_rate,
               today_sell_count, today_buy_count
        FROM jango_data
        ORDER BY date ASC
    """, con)

    con.close()
    return trades, open_pos, jango


# ─────────────────────────────────────────────────────────
# exit_reason 카테고리 분류
# ─────────────────────────────────────────────────────────
def categorize_exit(reason):
    if not reason:
        return '기타(None)'
    r = str(reason)
    if '트레일링' in r or '트레이링' in r or 'trailing' in r.lower() or 'Trailing' in r or '트레일' in r:
        return '트레일링'
    if '하드SL' in r or '하드 SL' in r or '하드sl' in r.lower():
        return '하드SL'
    if '시간청산' in r:
        return '시간청산'
    if 'ATR' in r or 'atr' in r.lower():
        return 'ATR'
    return '기타'


# ─────────────────────────────────────────────────────────
# 핵심 지표 계산
# ─────────────────────────────────────────────────────────
def compute_metrics(trades, open_pos, jango, initial_capital=50_000_000):
    result = {}

    # ── 기간 ──
    if len(trades):
        start_dt = trades['buy_date'].min()[:8]
        end_dt   = trades['sell_date'].max()[:8]
    else:
        start_dt = end_dt = datetime.today().strftime('%Y%m%d')
    result['period_start'] = start_dt
    result['period_end']   = end_dt
    total_days = (datetime.strptime(end_dt, '%Y%m%d') - datetime.strptime(start_dt, '%Y%m%d')).days + 1
    result['total_days'] = total_days

    # ── 실현손익 ──
    realized = int(trades['realized_profit'].sum())
    result['realized_profit'] = realized

    # ── 미실현손익 ──
    unrealized = int(open_pos['valuation_profit'].sum()) if len(open_pos) else 0
    result['unrealized_profit'] = unrealized
    result['open_count'] = len(open_pos)

    # ── 현재 총자산 추정 ──
    # d2_deposit(예수금) + 오픈 포지션 평가금액
    if len(jango) and pd.notna(jango['d2_deposit'].iloc[-1]):
        cash = int(jango['d2_deposit'].iloc[-1])
    else:
        cash = initial_capital + realized  # fallback

    # valuation_price가 0인 경우 present_price * holding_amount로 계산
    if len(open_pos):
        vp = open_pos['valuation_price'].astype(int)
        if vp.sum() == 0:
            vp = open_pos['present_price'].astype(int) * open_pos['holding_amount'].astype(int)
        open_valuation = int(vp.sum())
    else:
        open_valuation = 0
    current_asset = cash + open_valuation
    result['current_asset'] = current_asset
    result['cash'] = cash
    result['open_valuation'] = open_valuation
    result['initial_capital'] = initial_capital

    total_return_pct = (current_asset - initial_capital) / initial_capital * 100
    result['total_return_pct'] = total_return_pct

    # ── 거래 통계 ──
    n = len(trades)
    result['total_trades'] = n

    wins  = trades[trades['sell_rate'] > 0]
    losses = trades[trades['sell_rate'] <= 0]
    result['win_count']   = len(wins)
    result['loss_count']  = len(losses)
    result['win_rate']    = len(wins) / n * 100 if n else 0

    avg_win  = float(wins['sell_rate'].mean())  if len(wins)   else 0
    avg_loss = float(losses['sell_rate'].mean()) if len(losses) else 0
    result['avg_win_pct']  = avg_win
    result['avg_loss_pct'] = avg_loss
    result['profit_factor'] = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

    # 평균 보유일 (buy_date → sell_date, 8자리만 파싱)
    def holding_days(row):
        try:
            b = datetime.strptime(str(row['buy_date'])[:8], '%Y%m%d')
            s = datetime.strptime(str(row['sell_date'])[:8], '%Y%m%d')
            return (s - b).days
        except:
            return 0
    trades['hold_days'] = trades.apply(holding_days, axis=1)
    result['avg_hold_days'] = float(trades['hold_days'].mean()) if n else 0

    # ── 전략별 분석 ──
    strat = {}
    for stype in ['A', 'B']:
        sub = trades[trades['strategy_type'] == stype]
        if len(sub) == 0:
            continue
        sw = sub[sub['sell_rate'] > 0]
        sl = sub[sub['sell_rate'] <= 0]
        strat[stype] = {
            'count':    len(sub),
            'win_rate': len(sw) / len(sub) * 100,
            'avg_win':  float(sw['sell_rate'].mean())  if len(sw) else 0,
            'avg_loss': float(sl['sell_rate'].mean())  if len(sl) else 0,
            'realized': int(sub['realized_profit'].sum()),
        }
    result['strategy'] = strat

    # ── 매도 이유 분류 ──
    trades['exit_cat'] = trades['exit_reason'].apply(categorize_exit)
    exit_summary = {}
    for cat, grp in trades.groupby('exit_cat'):
        sw = grp[grp['sell_rate'] > 0]
        sl = grp[grp['sell_rate'] <= 0]
        exit_summary[cat] = {
            'count':    len(grp),
            'win_rate': len(sw) / len(grp) * 100,
            'avg_rate': float(grp['sell_rate'].mean()),
            'total_profit': int(grp['realized_profit'].sum()),
        }
    result['exit_summary'] = exit_summary

    # ── 일별 누적 손익 (MDD / Sharpe 계산용) ──
    trades['sell_date8'] = trades['sell_date'].str[:8]
    daily_pnl = trades.groupby('sell_date8')['realized_profit'].sum().reset_index()
    daily_pnl.columns = ['date', 'daily_pnl']
    daily_pnl = daily_pnl.sort_values('date')

    # 영업일 전체 날짜 채우기 (거래 없는 날 = 0)
    if len(daily_pnl):
        all_dates = pd.date_range(
            start=datetime.strptime(daily_pnl['date'].min(), '%Y%m%d'),
            end=datetime.today(), freq='B'
        )
        date_str = [d.strftime('%Y%m%d') for d in all_dates]
        full = pd.DataFrame({'date': date_str})
        full = full.merge(daily_pnl, on='date', how='left').fillna(0)
        full['cumulative'] = full['daily_pnl'].cumsum() + initial_capital
        full['peak'] = full['cumulative'].cummax()
        full['drawdown'] = (full['cumulative'] - full['peak']) / full['peak'] * 100
        mdd = float(full['drawdown'].min())

        # Sharpe (일별 수익률 기준, 연환산)
        full['daily_ret'] = full['daily_pnl'] / initial_capital
        daily_ret_nonzero = full['daily_ret']
        annual_factor = np.sqrt(252)
        sharpe = float(daily_ret_nonzero.mean() / daily_ret_nonzero.std() * annual_factor) \
            if daily_ret_nonzero.std() > 0 else 0

        result['mdd'] = mdd
        result['sharpe'] = sharpe
        result['equity_curve'] = full
    else:
        result['mdd'] = 0
        result['sharpe'] = 0
        result['equity_curve'] = pd.DataFrame()

    return result


# ─────────────────────────────────────────────────────────
# 출력
# ─────────────────────────────────────────────────────────
SEP  = '-' * 72
SEP2 = '=' * 72

def fmt_won(v):
    return f"{int(v):+,}원" if v >= 0 else f"{int(v):,}원"

def fmt_pct(v):
    return f"{v:+.2f}%"

def print_report(m, trades, open_pos):
    print()
    print(SEP2)
    print(f"  JackBot 실전 투자 종합 보고서 (sim=6, A+B 혼합)")
    print(f"  기간: {m['period_start'][:4]}-{m['period_start'][4:6]}-{m['period_start'][6:]} "
          f"~ {m['period_end'][:4]}-{m['period_end'][4:6]}-{m['period_end'][6:]} "
          f"({m['total_days']}일)")
    print(f"  생성: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(SEP2)

    # ── 1. 수익률 요약 ──
    print("\n【 1. 전체 수익 현황 】")
    print(SEP)
    print(f"  초기 투자금          :  {m['initial_capital']:>15,}원")
    print(f"  현재 예수금          :  {m['cash']:>15,}원")
    print(f"  오픈 포지션 평가금   :  {m['open_valuation']:>15,}원  ({m['open_count']}건)")
    print(f"  현재 총자산 (추정)   :  {m['current_asset']:>15,}원")
    print(f"  총 수익률            :  {fmt_pct(m['total_return_pct']):>10}")
    print(f"  실현 손익 합계       :  {fmt_won(m['realized_profit']):>15}")
    print(f"  미실현 손익          :  {fmt_won(m['unrealized_profit']):>15}")
    print(f"  MDD (최대낙폭)       :  {m['mdd']:>+10.2f}%")
    print(f"  Sharpe (연환산)      :  {m['sharpe']:>10.2f}")

    # ── 2. 거래 통계 ──
    print(f"\n【 2. 거래 통계 (체결완료 {m['total_trades']}건) 】")
    print(SEP)
    print(f"  승리 / 패배        :  {m['win_count']}승 / {m['loss_count']}패")
    print(f"  승률               :  {m['win_rate']:>10.1f}%")
    print(f"  평균 익절 수익률   :  {fmt_pct(m['avg_win_pct']):>10}")
    print(f"  평균 손절 수익률   :  {fmt_pct(m['avg_loss_pct']):>10}")
    print(f"  손익비 (R)         :  {m['profit_factor']:>10.2f}")
    print(f"  평균 보유일        :  {m['avg_hold_days']:>10.1f}일")

    # ── 3. 전략별 성과 ──
    print(f"\n【 3. 전략별 성과 】")
    print(SEP)
    print(f"  {'전략':<6} {'건수':>6} {'승률':>8} {'평균익절':>10} {'평균손절':>10} {'실현손익':>15}")
    print(f"  {'─'*6} {'─'*6} {'─'*8} {'─'*10} {'─'*10} {'─'*15}")
    for stype in ['A', 'B']:
        if stype not in m['strategy']:
            continue
        s = m['strategy'][stype]
        print(f"  {stype:<6} {s['count']:>6}건 {s['win_rate']:>7.1f}% "
              f"{fmt_pct(s['avg_win']):>10} {fmt_pct(s['avg_loss']):>10} "
              f"{fmt_won(s['realized']):>15}")

    # ── 4. 매도 이유별 분류 ──
    print(f"\n【 4. 매도 이유별 분류 】")
    print(SEP)
    print(f"  {'유형':<10} {'건수':>6} {'승률':>8} {'평균수익률':>12} {'실현손익':>15}")
    print(f"  {'─'*10} {'─'*6} {'─'*8} {'─'*12} {'─'*15}")
    for cat, s in sorted(m['exit_summary'].items(), key=lambda x: -x[1]['count']):
        print(f"  {cat:<10} {s['count']:>6}건 {s['win_rate']:>7.1f}% "
              f"{fmt_pct(s['avg_rate']):>12} {fmt_won(s['total_profit']):>15}")

    # ── 5. 오픈 포지션 ──
    if len(open_pos):
        print(f"\n【 5. 현재 보유 종목 ({len(open_pos)}건) 】")
        print(SEP)
        print(f"  {'종목명':<16} {'전략':>4} {'매수가':>8} {'현재가':>8} {'수익률':>8} {'미실현손익':>12}")
        print(f"  {'─'*16} {'─'*4} {'─'*8} {'─'*8} {'─'*8} {'─'*12}")
        for _, row in open_pos.iterrows():
            pct = float(row['rate']) - 100 if float(row['rate']) > 10 else float(row['rate'])
            print(f"  {str(row['code_name'])[:16]:<16} {str(row['strategy_type']):>4} "
                  f"{int(row['purchase_price']):>8,} {int(row['present_price']):>8,} "
                  f"{fmt_pct(pct):>8} {fmt_won(row['valuation_profit']):>12}")

    # ── 6. 일별 손익 상위/하위 ──
    trades_sorted = trades.sort_values('sell_date')
    print(f"\n【 6. 일별 손익 (최근 10 거래일) 】")
    print(SEP)
    trades['sell_date8'] = trades['sell_date'].str[:8]
    daily = trades.groupby('sell_date8').agg(
        cnt=('code', 'count'),
        pnl=('realized_profit', 'sum'),
        win=('sell_rate', lambda x: (x > 0).sum())
    ).reset_index().sort_values('sell_date8', ascending=False).head(10)

    print(f"  {'날짜':<12} {'거래':>5} {'승/패':>6} {'일손익':>15}")
    print(f"  {'─'*12} {'─'*5} {'─'*6} {'─'*15}")
    for _, row in daily.iterrows():
        d = str(row['sell_date8'])
        d_fmt = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        loss_cnt = int(row['cnt']) - int(row['win'])
        print(f"  {d_fmt:<12} {int(row['cnt']):>5}건 "
              f"{int(row['win']):>2}승{loss_cnt:>2}패 {fmt_won(row['pnl']):>15}")

    print()
    print(SEP2)
    print()


# ─────────────────────────────────────────────────────────
# 차트 (선택)
# ─────────────────────────────────────────────────────────
def draw_chart(m, save_path=None):
    import matplotlib
    matplotlib.use('Agg' if save_path else 'TkAgg')
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker

    eq = m['equity_curve']
    if len(eq) == 0:
        print("차트 데이터 없음")
        return

    # 한글 폰트 (윈도우)
    try:
        from matplotlib import font_manager as fm
        fonts = [f for f in fm.findSystemFonts() if 'malgun' in f.lower() or 'nanum' in f.lower()]
        if fonts:
            plt.rcParams['font.family'] = fm.FontProperties(fname=fonts[0]).get_name()
    except:
        pass
    plt.rcParams['axes.unicode_minus'] = False

    fig, axes = plt.subplots(3, 1, figsize=(14, 10),
                             gridspec_kw={'height_ratios': [3, 1, 1]})
    fig.suptitle(f"JackBot 실전 투자 리포트 (sim=6)  |  "
                 f"{m['period_start'][:4]}-{m['period_start'][4:6]}-{m['period_start'][6:]} ~ "
                 f"{m['period_end'][:4]}-{m['period_end'][4:6]}-{m['period_end'][6:]}",
                 fontsize=13, fontweight='bold')

    dates = pd.to_datetime(eq['date'])

    # 패널 1: 누적 자산 곡선
    ax1 = axes[0]
    ax1.plot(dates, eq['cumulative'] / 1e6, color='steelblue', lw=2, label='총자산(M원)')
    ax1.axhline(m['initial_capital'] / 1e6, color='gray', lw=1, ls='--', label='초기자금')
    ax1.fill_between(dates, eq['cumulative'] / 1e6, m['initial_capital'] / 1e6,
                     where=eq['cumulative'] >= m['initial_capital'],
                     alpha=0.15, color='green')
    ax1.fill_between(dates, eq['cumulative'] / 1e6, m['initial_capital'] / 1e6,
                     where=eq['cumulative'] < m['initial_capital'],
                     alpha=0.15, color='red')
    ax1.set_ylabel('총자산 (백만원)')
    ax1.legend(loc='upper left', fontsize=9)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:.1f}M'))
    ax1.grid(alpha=0.3)

    # 패널 2: DD (낙폭)
    ax2 = axes[1]
    ax2.fill_between(dates, eq['drawdown'], 0, color='red', alpha=0.4)
    ax2.set_ylabel('낙폭 (%)')
    ax2.set_ylim(min(eq['drawdown'].min() * 1.2, -0.5), 0.5)
    ax2.grid(alpha=0.3)

    # 패널 3: 일별 손익
    ax3 = axes[2]
    colors = ['green' if v >= 0 else 'red' for v in eq['daily_pnl']]
    ax3.bar(dates, eq['daily_pnl'] / 1e4, color=colors, width=0.8)
    ax3.set_ylabel('일손익 (만원)')
    ax3.axhline(0, color='black', lw=0.8)
    ax3.grid(alpha=0.3)

    # 오른쪽 상단 텍스트 박스
    info = (f"총수익률: {m['total_return_pct']:+.2f}%\n"
            f"MDD: {m['mdd']:.2f}%\n"
            f"Sharpe: {m['sharpe']:.2f}\n"
            f"승률: {m['win_rate']:.1f}%  ({m['win_count']}승/{m['loss_count']}패)\n"
            f"손익비: {m['profit_factor']:.2f}")
    ax1.text(0.99, 0.98, info, transform=ax1.transAxes,
             fontsize=9, va='top', ha='right',
             bbox=dict(boxstyle='round', fc='white', alpha=0.8))

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"차트 저장: {save_path}")
    else:
        plt.show()


# ─────────────────────────────────────────────────────────
# 진입점
# ─────────────────────────────────────────────────────────
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='실전 투자 종합 보고서')
    parser.add_argument('--chart', action='store_true', help='차트 표시')
    parser.add_argument('--save', type=str, default=None, help='차트 저장 경로 (예: report.png)')
    parser.add_argument('--capital', type=int, default=50_000_000, help='초기자금 (기본 5천만)')
    args = parser.parse_args()

    print("DB 조회 중...")
    trades, open_pos, jango = load_data()
    print(f"  체결완료: {len(trades)}건 / 미결: {len(open_pos)}건 / 잔고스냅샷: {len(jango)}일치")

    m = compute_metrics(trades, open_pos, jango, initial_capital=args.capital)
    print_report(m, trades, open_pos)

    if args.chart or args.save:
        chart_path = args.save or f"backtest_report/live_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        os.makedirs(os.path.dirname(chart_path), exist_ok=True)
        draw_chart(m, save_path=chart_path if args.save else None)
