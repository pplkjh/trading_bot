# -*- coding: utf-8 -*-
"""
rescore_now_v3.py — sim=6 기준 오늘 종가로 매수 후보 재확인 (DB 저장 없음)

사용법:
    python scripts/rescore_now_v3.py             # 최근 영업일 자동 선택
    python scripts/rescore_now_v3.py 20260527    # 날짜 지정

동작:
  - daily_buy_list에서 sim=6 pre-filter (A+B UNION) 로 후보 압축
  - BreakoutStrategyV3 (A) / ReversalStrategyV3 (B) 각각 스코어링
  - Strategy A 결과 + Strategy B 결과 분리 출력
  - DB 쓰기 없음 — 확인용 전용
"""
import sys
import datetime
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import pandas as pd
import pymysql
pymysql.install_as_MySQLdb()
from sqlalchemy import create_engine

from library import cf
from library.hybrid_strategy_v3 import BreakoutStrategyV3, ReversalStrategyV3

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

_url        = f'mysql+mysqldb://{cf.db_id}:{cf.db_passwd}@{cf.db_ip}:{cf.db_port}'
engine_dbl  = create_engine(f'{_url}/daily_buy_list', encoding='utf-8')
engine_craw = create_engine(f'{_url}/daily_craw',     encoding='utf-8')

strat_a = BreakoutStrategyV3()
strat_b = ReversalStrategyV3()

# ── 기준 날짜 ────────────────────────────────────────────────────
if len(sys.argv) > 1:
    target_date = sys.argv[1]
else:
    now = datetime.datetime.now()
    if now.hour > 15 or (now.hour == 15 and now.minute >= 40):
        target_date = now.strftime('%Y%m%d')
    else:
        dt = now - datetime.timedelta(days=1)
        while dt.weekday() >= 5:
            dt -= datetime.timedelta(days=1)
        target_date = dt.strftime('%Y%m%d')

print(f'\n기준 날짜: {target_date}  (DB 저장 없음 — 확인 전용)')
print(f'A커트라인: {cf.v4_min_score_a}pt  /  B커트라인: {cf.v4_min_score_b}pt  (200pt 만점)')

# ── 테이블 존재 확인 ─────────────────────────────────────────────
tbl_exists = engine_dbl.execute(
    f"SELECT COUNT(*) FROM information_schema.TABLES "
    f"WHERE TABLE_SCHEMA='daily_buy_list' AND TABLE_NAME='{target_date}'"
).fetchone()[0]

if not tbl_exists:
    latest = engine_dbl.execute(
        "SELECT TABLE_NAME FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA='daily_buy_list' AND TABLE_NAME REGEXP '^[0-9]{8}$' "
        "ORDER BY TABLE_NAME DESC LIMIT 1"
    ).fetchone()
    print(f'\n❌ daily_buy_list.{target_date} 테이블 없음')
    if latest:
        print(f'   가장 최근 날짜: {latest[0]}  →  python rescore_now_v3.py {latest[0]}')
    engine_dbl.dispose(); engine_craw.dispose()
    sys.exit(0)

# ── pre-filter SQL (sim=6 동일) ──────────────────────────────────
pre_filter_sql = f"""
    (SELECT a.* FROM `{target_date}` a
     WHERE NOT EXISTS (SELECT null FROM stock_konex b WHERE a.code=b.code)
     AND a.close > 0 AND a.close < {cf.invest_unit}
     AND a.volume > 0 AND a.vol20 > 0
     AND a.d1_diff_rate >= 1.5
     AND a.vol5 > a.vol20 * 1.2
     ORDER BY a.d1_diff_rate DESC LIMIT 150)
    UNION
    (SELECT a.* FROM `{target_date}` a
     WHERE NOT EXISTS (SELECT null FROM stock_konex b WHERE a.code=b.code)
     AND a.close > 0 AND a.close < {cf.invest_unit}
     AND a.volume > 0 AND a.vol20 > 0
     AND a.rsi14 <= 54 AND a.rsi14 >= 25
     ORDER BY a.rsi14 ASC LIMIT 150)
"""

candidates = engine_dbl.execute(pre_filter_sql).fetchall()
cnt_a_pre = sum(1 for r in candidates
                if float(r['d1_diff_rate'] or 0) >= 1.5
                and float(r['vol5'] or 0) > float(r['vol20'] or 1) * 1.2)
cnt_b_pre = sum(1 for r in candidates
                if 25 <= float(r['rsi14'] or 0) <= 54)
print(f'\nSQL 사전필터 완료 — {len(candidates)}개 (A후보 {cnt_a_pre} / B후보 {cnt_b_pre})  스코어링 중...')

# ── kospi_index ──────────────────────────────────────────────────
market_data = None
try:
    ki = pd.read_sql(
        f"SELECT close FROM kospi_index WHERE date<='{target_date}' "
        "ORDER BY date DESC LIMIT 20", engine_craw
    )
    if len(ki) >= 20:
        market_data = ki['close'].iloc[::-1].reset_index(drop=True)
except Exception:
    pass

# ── 스코어링 ────────────────────────────────────────────────────
scored_a, scored_b = [], []
errors = 0

for row in candidates:
    code      = str(row['code']).zfill(6)
    code_name = row['code_name']
    row_dict  = dict(row)

    try:
        df_120 = pd.read_sql(
            f"SELECT * FROM `{code_name}` WHERE code='{code}' "
            f"AND date<='{target_date}' ORDER BY date DESC LIMIT 120",
            engine_craw
        )
        if len(df_120) < 5:
            continue
        df_120 = df_120.sort_values('date').reset_index(drop=True)
    except Exception:
        errors += 1
        continue

    base = {
        'code': code, 'code_name': code_name,
        'close':   float(row_dict.get('close')        or 0),
        'd1_diff': float(row_dict.get('d1_diff_rate') or 0),
        'rsi14':   float(row_dict.get('rsi14')        or 0),
        'adx':     float(row_dict.get('adx')          or 0),
        'vol_r':   (float(row_dict.get('vol5') or 0) /
                    max(float(row_dict.get('vol20') or 1), 1)),
    }

    # Strategy A
    res_a = strat_a.calculate_total_score(row_dict, df_120, market_data)
    if not res_a['auto_reject']:
        scored_a.append({**base, **res_a})

    # Strategy B
    res_b = strat_b.calculate_total_score(row_dict, df_120, market_data, fundamental_data=None)
    if not res_b['auto_reject']:
        scored_b.append({**base, **res_b})

scored_a.sort(key=lambda x: x['total'], reverse=True)
scored_b.sort(key=lambda x: x['total'], reverse=True)

print(f'스코어링 완료 — A통과 {len(scored_a)}개 / B통과 {len(scored_b)}개 (오류 {errors}개)')


def _print_table(title, items, min_score, top_n=30):
    passed = [s for s in items if s['total'] >= min_score]
    print(f'\n{"=" * 110}')
    print(f'  {title}  (커트라인 {min_score}pt  |  통과 {len(passed)}개 / 조회 {len(items)}개)')
    print(f'{"=" * 110}')
    if not items:
        print('  (해당 없음)')
        return

    hdr = (f'  {"순위":<4} {"종목코드":<10} {"종목명":<20} {"총점":>6}  '
           f'{"A":>6} {"B":>6} {"C":>6} {"D":>6} {"E":>6} {"패":>6}  '
           f'{"RSI":>5} {"ADX":>5} {"등락":>6} {"거래량비":>7}  {"종가":>10}')
    print(hdr)
    print('  ' + '-' * 105)

    for idx, s in enumerate(items[:top_n], 1):
        flag = '✅' if s['total'] >= min_score else '  '
        print(f'  {idx:<3}{flag} {s["code"]:<10} {s["code_name"]:<20} {s["total"]:>6.1f}'
              f'  {s["score_a"]:>6.1f} {s["score_b"]:>6.1f} {s["score_c"]:>6.1f}'
              f' {s["score_d"]:>6.1f} {s["score_e"]:>6.1f} {s["score_penalty"]:>6.1f}'
              f'  {s["rsi14"]:>5.1f} {s["adx"]:>5.1f} {s["d1_diff"]:>+5.1f}%'
              f' {s["vol_r"]:>6.1f}x'
              f'  {int(s["close"] or 0):>10,}')

    if items:
        all_s = [s['total'] for s in items]
        print(f'\n  점수 범위: {min(all_s):.1f} ~ {max(all_s):.1f}  |  '
              f'평균: {sum(all_s)/len(all_s):.1f}  |  '
              f'커트라인({min_score}pt) 이상: {len(passed)}개')


_print_table('Strategy A  —  돌파 초입 (BreakoutStrategyV3)',
             scored_a, cf.v4_min_score_a)

_print_table('Strategy B  —  RSI 사이클 중장기 (ReversalStrategyV3)',
             scored_b, cf.v4_min_score_b)

# ── A+B 동시 통과 종목 (양쪽 커트라인 초과) ─────────────────────
both = {s['code'] for s in scored_a if s['total'] >= cf.v4_min_score_a} & \
       {s['code'] for s in scored_b if s['total'] >= cf.v4_min_score_b}
if both:
    print(f'\n  ── A+B 동시 통과 {len(both)}개 ──')
    a_map = {s['code']: s['total'] for s in scored_a}
    b_map = {s['code']: s['total'] for s in scored_b}
    name_map = {s['code']: s['code_name'] for s in scored_a + scored_b}
    for code in sorted(both, key=lambda c: max(a_map.get(c, 0), b_map.get(c, 0)), reverse=True):
        print(f'    {code}  {name_map.get(code, ""):<20}  A={a_map.get(code, 0):.1f}pt  B={b_map.get(code, 0):.1f}pt')

print(f'\n{"=" * 110}\n')

engine_dbl.dispose(); engine_craw.dispose()
