"""
JackBot 실전 대시보드 (sim=6)
실행: streamlit run dashboard.py
"""
import sys, os, time
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pymysql
from sqlalchemy import create_engine

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from library.cf import db_id, db_passwd, db_ip, db_port, imi1_db_name

INITIAL_CAPITAL = 50_000_000
TODAY = datetime.now().strftime('%Y%m%d')

def d8(s):
    """날짜값에서 숫자 8자리만 추출 — '2026-06-29', datetime, int 등 모두 대응"""
    digits = ''.join(c for c in str(s) if c.isdigit())
    return digits[:8] if len(digits) >= 8 else ''

# ──────────────────────────────────────────────────────
st.set_page_config(page_title="JackBot Dashboard", page_icon="📈",
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
/* 라이트모드 기준 — 배경은 자연색, 글씨는 Streamlit 기본 상속 */
.kpi-box {
    border-radius: 8px;
    padding: 14px 18px 10px;
    margin-bottom: 8px;
    border: 1px solid rgba(0,0,0,0.12);
    background: rgba(0,0,0,0.03);
}
.kpi-label {
    font-size: 0.74rem;
    opacity: 0.55;
    letter-spacing: 0.04em;
    margin-bottom: 4px;
}
.kpi-value {
    font-size: 1.50rem;
    font-weight: 700;
    line-height: 1.15;
}
.kpi-sub {
    font-size: 0.82rem;
    margin-top: 4px;
    opacity: 0.7;
}
.up   { color: #c00000; }   /* 수익: 진한 빨강 */
.down { color: #0044bb; }   /* 손실: 진한 파랑 */

.section-title {
    font-size: 0.70rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    opacity: 0.45;
    text-transform: uppercase;
    margin: 16px 0 6px;
    border-bottom: 1px solid rgba(0,0,0,0.12);
    padding-bottom: 3px;
}
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────
# DB 로드
# ──────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def load_data():
    engine = create_engine(
        f"mysql+pymysql://{db_id}:{db_passwd}@{db_ip}:{int(db_port)}/{imi1_db_name}?charset=utf8"
    )
    trades = pd.read_sql("""
        SELECT code, code_name, buy_date, sell_date,
               purchase_price, sell_price, sell_rate,
               realized_profit, holding_amount,
               strategy_type, exit_reason, composite_score
        FROM all_item_db
        WHERE sell_date != '0' AND sell_date IS NOT NULL
        ORDER BY sell_date ASC
    """, engine)
    open_pos = pd.read_sql("""
        SELECT code, code_name, purchase_price, present_price,
               holding_amount, rate, valuation_profit,
               item_total_purchase, strategy_type, buy_date
        FROM all_item_db
        WHERE sell_date = '0'
        ORDER BY buy_date ASC
    """, engine)
    jango = pd.read_sql("""
        SELECT date, d2_deposit, total_invest, today_profit,
               today_earning_rate, today_sell_count, today_buy_count
        FROM jango_data ORDER BY date ASC
    """, engine)
    engine.dispose()
    return trades, open_pos, jango


@st.cache_data(ttl=300)
def load_kospi(start_date8):
    try:
        engine = create_engine(
            f"mysql+pymysql://{db_id}:{db_passwd}@{db_ip}:{int(db_port)}/daily_craw?charset=utf8"
        )
        df = pd.read_sql(
            "SELECT date, close, volume FROM kospi_index ORDER BY date ASC, volume DESC",
            engine)
        engine.dispose()
        df['date']   = df['date'].apply(d8)
        df['close']  = pd.to_numeric(df['close'],  errors='coerce')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0)
        # 날짜당 중복 제거 — volume 내림차순 정렬했으므로 첫 행(최대 volume)이 당일 대표값
        df = df.drop_duplicates('date', keep='first')
        df = df[df['date'] >= start_date8].reset_index(drop=True)
        return df[['date', 'close']]
    except Exception:
        return pd.DataFrame()


# ──────────────────────────────────────────────────────
# 지표 계산
# ──────────────────────────────────────────────────────
def compute_metrics(trades_raw, open_pos, jango):
    trades = trades_raw.copy()
    m = {}

    trades['buy_date_8']    = trades['buy_date'].apply(d8)
    trades['sell_date_8']   = trades['sell_date'].apply(d8)
    jango['date8']          = jango['date'].apply(d8)

    # 숫자 컬럼 조기 변환 — 이후 모든 계산에서 타입 안전 보장
    trades['realized_profit'] = pd.to_numeric(trades['realized_profit'], errors='coerce').fillna(0)
    trades['sell_rate']       = pd.to_numeric(trades['sell_rate'],       errors='coerce').fillna(0)

    m['start'] = trades['buy_date_8'].min()  if len(trades) else TODAY
    m['end']   = trades['sell_date_8'].max() if len(trades) else TODAY
    try:
        m['days'] = max((datetime.strptime(m['end'], '%Y%m%d') -
                         datetime.strptime(m['start'], '%Y%m%d')).days, 1)
    except Exception:
        m['days'] = 1

    m['realized']   = int(trades['realized_profit'].sum())
    m['unrealized'] = int(open_pos['valuation_profit'].sum()) if len(open_pos) else 0

    cash = (int(pd.to_numeric(jango['d2_deposit'].iloc[-1], errors='coerce'))
            if len(jango) and pd.notna(jango['d2_deposit'].iloc[-1])
            else INITIAL_CAPITAL + m['realized'])
    open_val = int((open_pos['present_price'].astype(int) *
                    open_pos['holding_amount'].astype(int)).sum()) if len(open_pos) else 0
    m['cash']    = cash
    m['open_val'] = open_val
    # d2_deposit(T+2 결제 전) + open_val 합산은 매수 금액을 이중계산.
    # 초기자금 + 실현손익 + 미실현손익으로 계산.
    m['total_asset']      = INITIAL_CAPITAL + m['realized'] + m['unrealized']
    m['total_return_pct'] = (m['realized'] + m['unrealized']) / INITIAL_CAPITAL * 100

    # 오늘 손익: 거래내역 탭과 동일하게 trades에서 직접 계산 (jango today_profit은 0으로 초기화돼있을 수 있음)
    today_sells = trades[trades['sell_date_8'] == TODAY]
    m['today_pnl'] = int(pd.to_numeric(today_sells['realized_profit'], errors='coerce').sum())

    n      = len(trades)
    wins   = trades[trades['sell_rate'] > 0]
    losses = trades[trades['sell_rate'] <= 0]
    m['n']        = n
    m['win_n']    = len(wins)
    m['loss_n']   = len(losses)
    m['win_rate'] = len(wins) / n * 100 if n else 0
    m['avg_win']  = float(wins['sell_rate'].mean())   if len(wins)   else 0
    m['avg_loss'] = float(losses['sell_rate'].mean()) if len(losses) else 0
    m['pf']       = abs(m['avg_win'] / m['avg_loss']) if m['avg_loss'] else 0

    def hdays(row):
        try:
            return (datetime.strptime(d8(row['sell_date']), '%Y%m%d') -
                    datetime.strptime(d8(row['buy_date']),  '%Y%m%d')).days
        except: return 0
    trades['hold_days'] = trades.apply(hdays, axis=1)
    m['avg_hold'] = float(trades['hold_days'].mean()) if n else 0

    strat = {}
    for s in ['A', 'B']:
        sub = trades[trades['strategy_type'] == s]
        if not len(sub): continue
        sw = sub[sub['sell_rate'] > 0]
        sl = sub[sub['sell_rate'] <= 0]
        strat[s] = {
            'n': len(sub), 'wr': len(sw)/len(sub)*100,
            'avg_win':  float(sw['sell_rate'].mean())  if len(sw) else 0,
            'avg_loss': float(sl['sell_rate'].mean())  if len(sl) else 0,
            'pnl': int(sub['realized_profit'].sum()),
        }
    m['strat'] = strat

    def cat(r):
        if not r: return '미분류'
        r = str(r)
        if '트레일링' in r: return '트레일링'
        if '하드SL' in r:   return '하드SL'
        if '시간청산' in r: return '시간청산'
        if 'ATR' in r:      return 'ATR'
        return '기타'
    trades['exit_cat'] = trades['exit_reason'].apply(cat)
    exit_s = {}
    for c, grp in trades.groupby('exit_cat'):
        sw = grp[grp['sell_rate'] > 0]
        exit_s[c] = {
            'n': len(grp), 'wr': len(sw)/len(grp)*100,
            'avg': float(grp['sell_rate'].mean()),
            'pnl': int(grp['realized_profit'].sum()),
        }
    m['exit_s'] = exit_s

    # 일별 손익: trades.realized_profit 기준 (거래내역 탭과 동일 소스)
    daily_pnl = (trades.groupby('sell_date_8')['realized_profit']
                 .sum().reset_index()
                 .rename(columns={'sell_date_8': 'date', 'realized_profit': 'pnl'}))
    daily_pnl = daily_pnl[daily_pnl['date'].str.len() == 8].sort_values('date')

    daily_pnl['cum'] = daily_pnl['pnl'].cumsum() + INITIAL_CAPITAL

    full = daily_pnl[['date', 'pnl', 'cum']].copy()
    full['peak'] = full['cum'].cummax()
    full['dd']   = (full['cum'] - full['peak']) / full['peak'] * 100
    full['ret']  = full['pnl'] / INITIAL_CAPITAL

    std = full['ret'].std()
    m['mdd']    = float(full['dd'].min())
    m['sharpe'] = float(full['ret'].mean() / std * np.sqrt(252)) if std > 0 else 0
    m['equity'] = full

    # 디버그용 데이터
    m['_jango_tail']      = jango[['date', 'date8', 'd2_deposit', 'today_profit']].tail(5)
    m['_sell_rate_desc']  = trades['sell_rate'].describe().to_string()
    m['_trades_tail']     = trades[['code_name', 'sell_date_8', 'sell_rate', 'realized_profit']].tail(5)

    return m, trades


# ──────────────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────────────
def kpi(col, label, value_str, sub=None, sub_up=None):
    if sub is None:
        sub_html = ''
    else:
        cls = ('up' if isinstance(sub_up, (int, float)) and sub_up >= 0
               else 'down' if isinstance(sub_up, (int, float))
               else 'neutral')
        sub_html = f'<div class="kpi-sub {cls}">{sub}</div>'
    col.markdown(f"""
<div class="kpi-box">
  <div class="kpi-label">{label}</div>
  <div class="kpi-value">{value_str}</div>
  {sub_html}
</div>""", unsafe_allow_html=True)

def sec(title):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)

def tbl(rows: dict):
    html = ('<div style="border-radius:6px;padding:8px 12px;'
            'border:1px solid #ddd;background:#fafafa;margin-bottom:6px">'
            '<table style="width:100%;border-collapse:collapse;font-size:0.95rem">')
    for k, v in rows.items():
        html += (
            f'<tr style="border-bottom:1px solid #e8e8e8">'
            f'<td style="color:#555;padding:8px 12px 8px 4px;white-space:nowrap;width:44%">{k}</td>'
            f'<td style="color:#111;font-weight:700;font-size:0.97rem;'
            f'padding:8px 4px;text-align:right">{v}</td>'
            f'</tr>'
        )
    html += '</table></div>'
    st.markdown(html, unsafe_allow_html=True)


# ──────────────────────────────────────────────────────
# 탭 1 — 현황
# ──────────────────────────────────────────────────────
def tab_overview(m, open_pos):
    pct = m['total_return_pct']

    c1, c2, c3, c4, c5 = st.columns(5)
    # delta는 방향이 명확한 것만 — 나머지는 delta_color='off' 또는 생략
    c1.metric("추정 총자산",
              f"{m['total_asset']/1e6:.2f}M원",
              delta=f"{pct:+.2f}%",
              delta_color="normal")
    c2.metric("오늘 손익",   f"{m['today_pnl']:+,}원")
    c3.metric("승률",        f"{m['win_rate']:.1f}%")
    c4.metric("손익비 (R)",  f"{m['pf']:.2f}")
    c5.metric("보유 종목",   f"{len(open_pos)}건")

    st.divider()

    col_l, col_r = st.columns(2)
    with col_l:
        sec("거래 통계")
        tbl({
            "전체 거래":   f"{m['n']}건",
            "승 / 패":     f"{m['win_n']}승  /  {m['loss_n']}패",
            "승률":        f"{m['win_rate']:.1f}%",
            "평균 익절":   f"{m['avg_win']:+.2f}%",
            "평균 손절":   f"{m['avg_loss']:+.2f}%",
            "손익비 (R)":  f"{m['pf']:.2f}",
            "평균 보유일": f"{m['avg_hold']:.1f}일",
            "Sharpe (연)": f"{m['sharpe']:.2f}",
            "MDD":         f"{m['mdd']:.2f}%",
        })
    with col_r:
        sec("자산 구성")
        tbl({
            "초기 자금":        f"{INITIAL_CAPITAL:,}원",
            "예수금 (D+2 참고)": f"{m['cash']:,}원",
            "보유 평가금 (참고)": f"{m['open_val']:,}원  ({len(open_pos)}건)",
            "실현 손익":        f"{m['realized']:+,}원",
            "미실현 손익":      f"{m['unrealized']:+,}원",
            "추정 총자산":      f"{m['total_asset']:,}원",
            "총 수익률":        f"{m['total_return_pct']:+.2f}%",
            "운영 기간":        f"{m['days']}일  ({m['start'][:4]}.{m['start'][4:6]}.{m['start'][6:]} ~)",
        })

    # 디버그용 원시 데이터
    with st.expander("🔍 원시 데이터 확인 (데이터 이상할 때 클릭)"):
        st.write(f"**오늘: {TODAY}  |  jango 최근 5행:**")
        st.dataframe(m.get('_jango_tail', pd.DataFrame()), width='stretch')
        st.write(f"**전체 거래 sell_rate 분포:**")
        st.write(m.get('_sell_rate_desc', '데이터 없음'))
        st.write(f"**거래 최근 5건:**")
        st.dataframe(m.get('_trades_tail', pd.DataFrame()), width='stretch')


# ──────────────────────────────────────────────────────
# 탭 2 — 보유 종목
# ──────────────────────────────────────────────────────
def tab_positions(open_pos):
    sec(f"현재 보유  {len(open_pos)}건")
    if not len(open_pos):
        st.info("보유 종목 없음")
        return

    rows = []
    for _, r in open_pos.iterrows():
        rate_raw = float(r['rate'])
        pct = rate_raw - 100 if rate_raw > 10 else rate_raw
        bd8 = d8(r['buy_date'])
        try:
            hold = (datetime.today() - datetime.strptime(bd8, '%Y%m%d')).days
        except: hold = 0
        rows.append({
            '종목명':     str(r['code_name']),
            '전략':       str(r['strategy_type']),
            '매수일':     f"{bd8[:4]}.{bd8[4:6]}.{bd8[6:8]}" if len(bd8) == 8 else bd8,
            '매수가':     int(r['purchase_price']),
            '현재가':     int(r['present_price']),
            '수익률%':    round(pct, 2),
            '미실현손익': int(r['valuation_profit']),
            '수량':       int(r['holding_amount']),
            '보유일':     hold,
        })

    df = pd.DataFrame(rows)
    styled = (df.style
              .map(lambda v: 'color:#cc0000' if v >= 0 else 'color:#0044bb',
                        subset=['수익률%', '미실현손익'])
              .format({'매수가': '{:,}', '현재가': '{:,}',
                       '수익률%': '{:+.2f}%', '미실현손익': '{:+,}원'}))
    st.dataframe(styled, width='stretch', hide_index=True, height=420)


# ──────────────────────────────────────────────────────
# 탭 3 — 거래내역 (날짜 선택)
# ──────────────────────────────────────────────────────
def tab_trades(trades):
    col_d, col_info = st.columns([1, 3])
    with col_d:
        min_d8 = trades['sell_date_8'][trades['sell_date_8'].str.len() == 8].min()
        sel_date = st.date_input(
            "날짜 선택",
            value=datetime.today().date(),
            min_value=datetime.strptime(min_d8, '%Y%m%d').date() if min_d8 else datetime.today().date(),
            max_value=datetime.today().date(),
        )
    sel_str = sel_date.strftime('%Y%m%d')
    day_trades = trades[trades['sell_date_8'] == sel_str].copy()

    with col_info:
        if len(day_trades):
            pnl = int(day_trades['realized_profit'].sum())
            wr  = (day_trades['sell_rate'] > 0).sum()
            cls = 'up' if pnl >= 0 else 'down'
            st.markdown(
                f"<br><span style='font-size:1rem;font-weight:600'>"
                f"{sel_date.strftime('%Y년 %m월 %d일')} — "
                f"{len(day_trades)}건  ({wr}승 {len(day_trades)-wr}패)  |  "
                f"<span class='{cls}'>{pnl:+,}원</span></span>",
                unsafe_allow_html=True)
        else:
            st.markdown(
                f"<br><span style='opacity:0.55'>"
                f"{sel_date.strftime('%Y년 %m월 %d일')} — 거래 없음</span>",
                unsafe_allow_html=True)

    if not len(day_trades):
        return

    st.divider()
    df = day_trades[['code_name','strategy_type','sell_date',
                     'purchase_price','sell_price','sell_rate',
                     'realized_profit','hold_days','exit_reason']].copy()
    df.columns = ['종목명','전략','매도시각','매수가','매도가',
                  '수익률%','실현손익','보유일','매도사유']
    df['매도시각'] = df['매도시각'].apply(
        lambda x: (lambda s: f"{s[8:10]}:{s[10:12]}" if len(s) >= 12 else s)(''.join(c for c in str(x) if c.isdigit())))
    df = df.sort_values('매도시각')

    styled = (df.style
              .map(lambda v: 'color:#cc0000' if v >= 0 else 'color:#0044bb',
                        subset=['수익률%', '실현손익'])
              .format({'매수가': '{:,}', '매도가': '{:,}',
                       '수익률%': '{:+.2f}%', '실현손익': '{:+,}원'}))
    st.dataframe(styled, width='stretch', hide_index=True, height=500)


# ──────────────────────────────────────────────────────
# 탭 4 — 차트 (자산 vs KOSPI + 일별 손익)
# ──────────────────────────────────────────────────────
def tab_charts(m):
    eq    = m['equity']
    dates = pd.to_datetime(eq['date'], format='%Y%m%d', errors='coerce')

    kospi_df = load_kospi(m['start'])
    has_kospi = len(kospi_df) > 0

    # 코스피 수익률 계산 (코스피 자체 날짜 기준)
    kospi_ret = None
    kospi_dates = None
    kospi_norm_vals = None
    if has_kospi and len(kospi_df) >= 2:
        kospi_start = kospi_df['close'].iloc[0]
        if kospi_start > 0:
            kospi_norm_vals = kospi_df['close'] / kospi_start * INITIAL_CAPITAL
            kospi_dates = pd.to_datetime(kospi_df['date'], format='%Y%m%d', errors='coerce')
            kospi_ret = (kospi_norm_vals.iloc[-1] - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100

    # ── 비교 KPI (차트 위)
    c1, c2, c3, c4 = st.columns(4)
    pct = m['total_return_pct']
    kpi(c1, "내 포트폴리오",
        f"{pct:+.2f}%",
        sub=f"{m['start'][:4]}.{m['start'][4:6]}.{m['start'][6:]} ~ 현재",
        sub_up=None)
    if kospi_ret is not None:
        alpha = pct - kospi_ret
        kpi(c2, "코스피 (동기간)",
            f"{kospi_ret:+.2f}%",
            sub=f"초과수익  {alpha:+.2f}%",
            sub_up=alpha)
    else:
        kpi(c2, "코스피", "-")
    kpi(c3, "MDD",         f"{m['mdd']:.2f}%")
    kpi(c4, "Sharpe (연)", f"{m['sharpe']:.2f}")

    st.divider()

    # ── 2패널 차트 (shared_xaxes=True: 두 패널 날짜 동기화)
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.65, 0.35],
        vertical_spacing=0.08,
        subplot_titles=['누적 자산 vs 코스피 (M원)', '일별 실현 손익 (만원)'],
    )

    # ── Y축 zoom: 실제 데이터 범위 기준
    y_vals = eq['cum'].values / 1e6
    if kospi_norm_vals is not None:
        y_vals = np.concatenate([y_vals, kospi_norm_vals.values / 1e6])
    pad = max((y_vals.max() - y_vals.min()) * 0.08, 0.5)
    y_min = y_vals.min() - pad
    y_max = y_vals.max() + pad

    # ── 포트폴리오 곡선 (거래일 기준)
    fig.add_trace(go.Scatter(
        x=dates, y=eq['cum'] / 1e6,
        mode='lines', name='포트폴리오',
        line=dict(color='#1a56db', width=2.5),
        hovertemplate='%{x|%Y-%m-%d}  %{y:.3f}M<extra>포트폴리오</extra>',
    ), row=1, col=1)

    # ── 코스피 비교선 (코스피 자체 전 거래일 기준)
    if kospi_dates is not None:
        fig.add_trace(go.Scatter(
            x=kospi_dates, y=kospi_norm_vals / 1e6,
            mode='lines', name='코스피 (정규화)',
            line=dict(color='#e07b00', width=1.8, dash='dash'),
            hovertemplate='%{x|%Y-%m-%d}  %{y:.3f}M<extra>코스피</extra>',
        ), row=1, col=1)

    # 초기자금 기준선
    fig.add_hline(y=INITIAL_CAPITAL / 1e6,
                  line_dash='dot', line_color='#aaa', line_width=1,
                  row=1, col=1)
    fig.update_yaxes(range=[y_min, y_max], row=1, col=1)

    # ── 일별 손익 바
    bar_colors = ['#cc0000' if v >= 0 else '#0044bb' for v in eq['pnl']]
    fig.add_trace(go.Bar(
        x=dates, y=eq['pnl'] / 1e4,
        name='일손익', marker_color=bar_colors,
        marker_line_width=0, opacity=0.75,
        hovertemplate='%{x|%Y-%m-%d}  %{y:.1f}만원<extra></extra>',
    ), row=2, col=1)
    fig.add_hline(y=0, line_color='#bbb', line_width=1, row=2, col=1)

    # ── 레이아웃 (라이트모드)
    fig.update_layout(
        height=560,
        template='simple_white',
        legend=dict(
            orientation='h', yanchor='bottom', y=1.02,
            xanchor='left', x=0,
            font=dict(size=13),
        ),
        margin=dict(l=70, r=20, t=50, b=40),
        hovermode='x',
        font=dict(size=13),
    )
    for ann in fig['layout']['annotations']:
        ann['font'] = dict(size=13)
        ann['x'] = 0.0
        ann['xanchor'] = 'left'

    ax_style = dict(
        showgrid=True,
        gridcolor='#e8e8e8',
        gridwidth=1,
        linecolor='#ccc',
        tickfont=dict(size=12),
        zeroline=False,
    )
    fig.update_xaxes(**ax_style)
    fig.update_yaxes(**ax_style)
    fig.update_yaxes(ticksuffix='M',  row=1, col=1)
    fig.update_yaxes(ticksuffix='만', row=2, col=1)
    fig.update_xaxes(showticklabels=False, row=1, col=1)
    fig.update_xaxes(tickformat='%m/%d', dtick=7*24*3600000, row=2, col=1)

    st.plotly_chart(fig, width='stretch')

    # 디버그 (데이터 확인용)
    with st.expander("🔍 원시 데이터 확인"):
        st.write("**equity (날짜/손익/자산):**")
        st.dataframe(eq[['date','pnl','cum']].tail(10), width='stretch')
        if has_kospi:
            st.write("**kospi_df 샘플:**")
            st.dataframe(kospi_df.head(5), width='stretch')


# ──────────────────────────────────────────────────────
# 탭 5 — 분석
# ──────────────────────────────────────────────────────
def tab_analysis(m):
    col_l, col_r = st.columns(2)

    with col_l:
        sec("전략별 성과 (A / B)")
        rows = []
        for s in ['A', 'B']:
            if s not in m['strat']: continue
            d = m['strat'][s]
            rows.append({'전략': s, '건수': d['n'], '승률%': d['wr'],
                         '평균익절%': d['avg_win'], '평균손절%': d['avg_loss'],
                         '손익비': abs(d['avg_win']/d['avg_loss']) if d['avg_loss'] else 0,
                         '실현손익': d['pnl']})
        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(
                df.style
                  .map(lambda v: 'color:#cc0000' if v >= 0 else 'color:#0044bb',
                             subset=['실현손익'])
                  .format({'승률%': '{:.1f}%', '평균익절%': '{:+.2f}%',
                           '평균손절%': '{:+.2f}%', '손익비': '{:.2f}',
                           '실현손익': '{:+,}원'}),
                width='stretch', hide_index=True)

    with col_r:
        sec("매도 이유별 분류")
        rows = []
        for c, d in sorted(m['exit_s'].items(), key=lambda x: -x[1]['n']):
            rows.append({'유형': c, '건수': d['n'], '승률%': d['wr'],
                         '평균%': d['avg'], '실현손익': d['pnl']})
        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(
                df.style
                  .map(lambda v: 'color:#cc0000' if v >= 0 else 'color:#0044bb',
                             subset=['실현손익', '평균%'])
                  .format({'승률%': '{:.1f}%', '평균%': '{:+.2f}%',
                           '실현손익': '{:+,}원'}),
                width='stretch', hide_index=True)

    st.divider()
    col_l2, col_r2 = st.columns(2)

    with col_l2:
        sec("매도 이유 건수")
        labels = list(m['exit_s'].keys())
        values = [m['exit_s'][k]['n'] for k in labels]
        colors = ['#1a56db','#cc0000','#e07b00','#16a34a','#7c3aed']
        fig = go.Figure(go.Pie(
            labels=labels, values=values, hole=0.42,
            marker=dict(colors=colors[:len(labels)],
                        line=dict(color='white', width=2)),
            textfont=dict(size=13),
            hovertemplate='%{label}: %{value}건 (%{percent})<extra></extra>',
        ))
        fig.update_layout(template='simple_white', height=280,
                          margin=dict(l=10, r=10, t=10, b=10),
                          font=dict(size=13),
                          legend=dict(font=dict(size=12)))
        st.plotly_chart(fig, width='stretch')

    with col_r2:
        sec("매도 이유별 누적 손익")
        cats  = list(m['exit_s'].keys())
        pnls  = [m['exit_s'][k]['pnl']/1e4 for k in cats]
        colors = ['#cc0000' if v >= 0 else '#0044bb' for v in pnls]
        fig = go.Figure(go.Bar(
            x=cats, y=pnls, marker_color=colors,
            marker_line_width=0, opacity=0.8,
            text=[f"{v:+.0f}만" for v in pnls],
            textposition='outside',
            textfont=dict(size=13),
            hovertemplate='%{x}: %{y:.1f}만원<extra></extra>',
        ))
        fig.update_layout(template='simple_white', height=280,
                          margin=dict(l=10, r=10, t=20, b=10),
                          font=dict(size=13))
        fig.update_yaxes(ticksuffix='만', gridcolor='#e8e8e8')
        fig.update_xaxes(tickfont=dict(size=13))
        st.plotly_chart(fig, width='stretch')


# ──────────────────────────────────────────────────────
# 탭 6 — 전체 거래 내역
# ──────────────────────────────────────────────────────
def tab_history(trades):
    col_a, col_b, _ = st.columns([1, 1, 3])
    with col_a:
        n_show = st.selectbox("표시 건수", [30, 50, 100, 200, 9999], index=1,
                              format_func=lambda x: '전체' if x == 9999 else f'{x}건')
    with col_b:
        strat_filter = st.selectbox("전략 필터", ['전체', 'A', 'B'])

    recent = trades.sort_values('sell_date', ascending=False)
    if strat_filter != '전체':
        recent = recent[recent['strategy_type'] == strat_filter]
    recent = recent.head(n_show)

    sec(f"거래 내역  {len(recent)}건 표시  /  전체 {len(trades)}건")
    df = recent[['code_name','strategy_type','sell_date','buy_date',
                 'purchase_price','sell_price','sell_rate',
                 'realized_profit','hold_days','exit_reason']].copy()
    df.columns = ['종목명','전략','매도일','매수일','매수가','매도가',
                  '수익률%','실현손익','보유일','매도사유']
    for col in ['매도일','매수일']:
        df[col] = df[col].apply(
            lambda x: (lambda s: f"{s[:4]}.{s[4:6]}.{s[6:8]}" if len(s) == 8 else s)(d8(x)))

    styled = (df.style
              .map(lambda v: 'color:#cc0000' if v >= 0 else 'color:#0044bb',
                        subset=['수익률%', '실현손익'])
              .format({'매수가': '{:,}', '매도가': '{:,}',
                       '수익률%': '{:+.2f}%', '실현손익': '{:+,}원'}))
    st.dataframe(styled, width='stretch', hide_index=True, height=580)


# ──────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────
def main():
    with st.sidebar:
        st.title("⚙️ 설정")
        refresh_sec = st.slider("새로고침 간격 (초)", 10, 120, 30)
        if st.button("🔄 지금 새로고침"):
            st.cache_data.clear()
            st.rerun()
        st.divider()
        st.caption(f"DB: {imi1_db_name}")
        st.caption(f"초기자금: {INITIAL_CAPITAL:,}원")

    st.markdown(
        f"## 📈 JackBot 실전 대시보드"
        f"<span style='font-size:0.82rem;opacity:0.45;margin-left:12px'>"
        f"업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>",
        unsafe_allow_html=True)

    with st.spinner("DB 조회 중..."):
        try:
            trades, open_pos, jango = load_data()
        except Exception as e:
            st.error(f"DB 연결 실패: {e}")
            time.sleep(10)
            st.rerun()
            return

    m, trades = compute_metrics(trades, open_pos, jango)

    t1, t2, t3, t4, t5, t6 = st.tabs([
        "📊 현황",
        "📂 보유종목",
        "📋 거래내역",
        "📈 차트",
        "⚡ 분석",
        "📜 전체내역",
    ])

    with t1: tab_overview(m, open_pos)
    with t2: tab_positions(open_pos)
    with t3: tab_trades(trades)
    with t4: tab_charts(m)
    with t5: tab_analysis(m)
    with t6: tab_history(trades)

    st.caption(f"⏱ {refresh_sec}초 후 자동 새로고침")
    time.sleep(refresh_sec)
    st.cache_data.clear()
    st.rerun()


if __name__ == '__main__':
    main()
