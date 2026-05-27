# -*- coding: utf-8 -*-
"""
check_buy_candidates_v3.py — Strategy A/B (sim=6) 매수 후보 확인

실행:
    python scripts/check_buy_candidates_v3.py

두 섹션:
  1. realtime_daily_buy_list 현황 (오늘 collector가 저장한 결과)
  2. 전체 시장 재스코어링 (A: BreakoutStrategyV3 / B: ReversalStrategyV3)
     — collector와 동일한 pre-filter SQL 사용 (A최대150 + B최대150 UNION)
"""
import sys
import pathlib
import pandas as pd
import pymysql
pymysql.install_as_MySQLdb()
from sqlalchemy import create_engine
from library.cf import db_id, db_passwd, db_ip, db_port, imi1_db_name, \
    v4_min_score_a, v4_min_score_b, invest_unit
from library.hybrid_strategy_v3 import BreakoutStrategyV3, ReversalStrategyV3

_url        = f'mysql+mysqldb://{db_id}:{db_passwd}@{db_ip}:{db_port}'
engine_jb   = create_engine(f'{_url}/{imi1_db_name}', encoding='utf-8')
engine_dbl  = create_engine(f'{_url}/daily_buy_list', encoding='utf-8')
engine_craw = create_engine(f'{_url}/daily_craw',     encoding='utf-8')

strat_a = BreakoutStrategyV3()
strat_b = ReversalStrategyV3()

# ═══════════════════════════════════════════════════════════════════
# SECTION 1 — realtime_daily_buy_list 현황
# ═══════════════════════════════════════════════════════════════════
print('=' * 110)
print(f'  매수 후보 리스트 — {imi1_db_name}.realtime_daily_buy_list')
print(f'  Strategy A min={v4_min_score_a}pt / Strategy B min={v4_min_score_b}pt  (200pt 만점)')
print('=' * 110)

try:
    rows = engine_jb.execute(
        'SELECT code, code_name, composite_score, strategy_type, check_item, close '
        'FROM realtime_daily_buy_list ORDER BY composite_score DESC'
    ).fetchall()
except Exception as e:
    rows = []
    print(f'  ❌ realtime_daily_buy_list 조회 실패: {e}')

if rows:
    a_rows = [r for r in rows if str(r[3] or '') == 'A']
    b_rows = [r for r in rows if str(r[3] or '') == 'B']

    for label, group, min_s in [('Strategy A (Breakout)', a_rows, v4_min_score_a),
                                  ('Strategy B (Reversal)', b_rows, v4_min_score_b)]:
        print(f'\n  [{label}]  커트라인 {min_s}pt 이상')
        print(f'  {"순위":<4} {"종목코드":<10} {"종목명":<20} {"점수/200":<12} {"매수상태":<10} {"종가":>10}')
        print('  ' + '-' * 70)
        for idx, r in enumerate(group, 1):
            code, name, score, stype, check, close = r
            status = '✅완료' if check == 1 else '⏳대기'
            print(f'  {idx:<4} {code:<10} {name:<20} {float(score or 0):>6.1f}/200    {status:<10} {int(close or 0):>10,}')
        if not group:
            print('  (없음)')

    print(f'\n  합계: A {len(a_rows)}개 / B {len(b_rows)}개 / 총 {len(rows)}개')
else:
    print('\n  ❌ 매수 후보 없음 — collector_v3.py 실행 여부 확인')

# ═══════════════════════════════════════════════════════════════════
# SECTION 2 — 전체 시장 재스코어링 (sim=6 동일 pre-filter)
# ═══════════════════════════════════════════════════════════════════
print()
print('=' * 110)
print('  전체 시장 재스코어링 (collector 동일 로직 — sim=6 A+B UNION)')
print('=' * 110)

# 최신 날짜 테이블
latest_row = engine_dbl.execute(
    "SELECT TABLE_NAME FROM information_schema.TABLES "
    "WHERE TABLE_SCHEMA='daily_buy_list' AND TABLE_NAME REGEXP '^[0-9]{8}$' "
    "ORDER BY TABLE_NAME DESC LIMIT 1"
).fetchone()

if not latest_row:
    print('  ❌ daily_buy_list 테이블 없음')
    engine_jb.dispose(); engine_dbl.dispose(); engine_craw.dispose()
    sys.exit(0)

tbl = latest_row[0]
print(f'  기준일: {tbl}')

# pre-filter SQL (sim=6: A 최대 150 + B 최대 150 UNION)
pre_filter_sql = f"""
    (SELECT a.* FROM `{tbl}` a
     WHERE NOT EXISTS (SELECT null FROM stock_konex b WHERE a.code=b.code)
     AND a.close > 0 AND a.close < {invest_unit}
     AND a.volume > 0 AND a.vol20 > 0
     AND a.d1_diff_rate >= 1.5
     AND a.vol5 > a.vol20 * 1.2
     ORDER BY a.d1_diff_rate DESC LIMIT 150)
    UNION
    (SELECT a.* FROM `{tbl}` a
     WHERE NOT EXISTS (SELECT null FROM stock_konex b WHERE a.code=b.code)
     AND a.close > 0 AND a.close < {invest_unit}
     AND a.volume > 0 AND a.vol20 > 0
     AND a.rsi14 <= 54 AND a.rsi14 >= 25
     ORDER BY a.rsi14 ASC LIMIT 150)
"""

try:
    candidates = engine_dbl.execute(pre_filter_sql).fetchall()
except Exception as e:
    print(f'  ❌ pre-filter 실패: {e}')
    engine_jb.dispose(); engine_dbl.dispose(); engine_craw.dispose()
    sys.exit(0)

cnt_a_pre = sum(1 for r in candidates
                if float(r['d1_diff_rate'] or 0) >= 1.5
                and float(r['vol5'] or 0) > float(r['vol20'] or 1) * 1.2)
cnt_b_pre = sum(1 for r in candidates
                if 25 <= float(r['rsi14'] or 0) <= 54)
print(f'  SQL 사전필터 완료 — {len(candidates)}개 (A후보 {cnt_a_pre}개 / B후보 {cnt_b_pre}개)  스코어링 중...')

# kospi_index 로드
market_data = None
try:
    ki = pd.read_sql('SELECT close FROM kospi_index ORDER BY date DESC LIMIT 20', engine_craw)
    if len(ki) >= 20:
        market_data = ki['close'].iloc[::-1].reset_index(drop=True)
except Exception:
    pass

# 스코어링
scored_a, scored_b = [], []
errors = 0

for row in candidates:
    code      = str(row['code']).zfill(6)
    code_name = row['code_name']
    row_dict  = dict(row)

    try:
        df_120 = pd.read_sql(
            f"SELECT * FROM `{code_name}` WHERE code='{code}' "
            f"AND date<='{tbl}' ORDER BY date DESC LIMIT 120",
            engine_craw
        )
        if len(df_120) < 5:
            continue
        df_120 = df_120.sort_values('date').reset_index(drop=True)
    except Exception:
        errors += 1
        continue

    # Strategy A
    res_a = strat_a.calculate_total_score(row_dict, df_120, market_data)
    if not res_a['auto_reject']:
        res_a['code'] = code; res_a['code_name'] = code_name
        res_a['close'] = row_dict.get('close', 0)
        res_a['d1_diff'] = float(row_dict.get('d1_diff_rate') or 0)
        res_a['rsi14']   = float(row_dict.get('rsi14') or 0)
        res_a['adx']     = float(row_dict.get('adx') or 0)
        scored_a.append(res_a)

    # Strategy B
    res_b = strat_b.calculate_total_score(row_dict, df_120, market_data, fundamental_data=None)
    if not res_b['auto_reject']:
        res_b['code'] = code; res_b['code_name'] = code_name
        res_b['close'] = row_dict.get('close', 0)
        res_b['d1_diff'] = float(row_dict.get('d1_diff_rate') or 0)
        res_b['rsi14']   = float(row_dict.get('rsi14') or 0)
        res_b['adx']     = float(row_dict.get('adx') or 0)
        scored_b.append(res_b)

scored_a.sort(key=lambda x: x['total'], reverse=True)
scored_b.sort(key=lambda x: x['total'], reverse=True)

print(f'  스코어링 완료 — A통과 {len(scored_a)}개 / B통과 {len(scored_b)}개 (오류 {errors}개)\n')

HDR = (f'  {"순위":<4} {"종목코드":<10} {"종목명":<20} {"총점":>6}  '
       f'{"A":>6} {"B":>6} {"C":>6} {"D":>6} {"E":>6} {"패":>6}  '
       f'{"RSI":>5} {"ADX":>5} {"등락":>6}  {"종가":>10}')
SEP = '  ' + '-' * 105

# ── Strategy A ────────────────────────────────────────────────
print(f'  ▶ Strategy A (돌파 초입)  —  커트라인 {v4_min_score_a}pt')
print(HDR); print(SEP)
for idx, s in enumerate(scored_a[:25], 1):
    flag = '✅' if s['total'] >= v4_min_score_a else '  '
    print(f'  {idx:<3}{flag} {s["code"]:<10} {s["code_name"]:<20} {s["total"]:>6.1f}'
          f'  {s["score_a"]:>6.1f} {s["score_b"]:>6.1f} {s["score_c"]:>6.1f}'
          f' {s["score_d"]:>6.1f} {s["score_e"]:>6.1f} {s["score_penalty"]:>6.1f}'
          f'  {s["rsi14"]:>5.1f} {s["adx"]:>5.1f} {s["d1_diff"]:>+5.1f}%'
          f'  {int(s["close"] or 0):>10,}')
if not scored_a:
    print('  (통과 종목 없음)')

print()
passed_a = [s for s in scored_a if s['total'] >= v4_min_score_a]
if scored_a:
    all_s = [s['total'] for s in scored_a]
    print(f'  점수 범위: {min(all_s):.1f} ~ {max(all_s):.1f} | '
          f'평균: {sum(all_s)/len(all_s):.1f} | '
          f'커트라인({v4_min_score_a}pt) 이상: {len(passed_a)}개')

# ── Strategy B ────────────────────────────────────────────────
print()
print(f'  ▶ Strategy B (RSI 사이클)  —  커트라인 {v4_min_score_b}pt')
print(HDR); print(SEP)
for idx, s in enumerate(scored_b[:25], 1):
    flag = '✅' if s['total'] >= v4_min_score_b else '  '
    print(f'  {idx:<3}{flag} {s["code"]:<10} {s["code_name"]:<20} {s["total"]:>6.1f}'
          f'  {s["score_a"]:>6.1f} {s["score_b"]:>6.1f} {s["score_c"]:>6.1f}'
          f' {s["score_d"]:>6.1f} {s["score_e"]:>6.1f} {s["score_penalty"]:>6.1f}'
          f'  {s["rsi14"]:>5.1f} {s["adx"]:>5.1f} {s["d1_diff"]:>+5.1f}%'
          f'  {int(s["close"] or 0):>10,}')
if not scored_b:
    print('  (통과 종목 없음)')

print()
passed_b = [s for s in scored_b if s['total'] >= v4_min_score_b]
if scored_b:
    all_s = [s['total'] for s in scored_b]
    print(f'  점수 범위: {min(all_s):.1f} ~ {max(all_s):.1f} | '
          f'평균: {sum(all_s)/len(all_s):.1f} | '
          f'커트라인({v4_min_score_b}pt) 이상: {len(passed_b)}개')

print()
print('=' * 110)

engine_jb.dispose(); engine_dbl.dispose(); engine_craw.dispose()
