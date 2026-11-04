# -*- coding: utf-8 -*-
"""
check_buy_candidates_sim8.py — sim=8 매수 후보 확인
  A: BreakoutStrategyV5 (condition-based, opt>=3)
  B: ReversalStrategyV4 (scoring, min=100)

실행:
    python scripts/check_buy_candidates_sim8.py
"""
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pandas as pd
import pymysql
pymysql.install_as_MySQLdb()
from sqlalchemy import create_engine

from library.cf import db_id, db_passwd, db_ip, db_port, invest_unit, \
    v6_min_opt_a, v6_min_score_b
from library.hybrid_strategy_v5 import BreakoutStrategyV5
from library.hybrid_strategy_v4 import ReversalStrategyV4

_url        = f'mysql+mysqldb://{db_id}:{db_passwd}@{db_ip}:{db_port}'
engine_dbl  = create_engine(f'{_url}/daily_buy_list', encoding='utf-8')
engine_craw = create_engine(f'{_url}/daily_craw',     encoding='utf-8')

strat_a = BreakoutStrategyV5()
strat_b = ReversalStrategyV4()

# ── 최신 daily_buy_list 날짜 ──────────────────────────────────────
latest = engine_dbl.execute(
    "SELECT TABLE_NAME FROM information_schema.TABLES "
    "WHERE TABLE_SCHEMA='daily_buy_list' AND TABLE_NAME REGEXP '^[0-9]{8}$' "
    "ORDER BY TABLE_NAME DESC LIMIT 1"
).fetchone()

if not latest:
    print('❌ daily_buy_list 테이블 없음')
    sys.exit(1)

tbl = latest[0]
print('=' * 110)
print(f'  sim=8 매수 후보 재스코어링  —  기준일: {tbl}')
print(f'  Strategy A (BreakoutV5): optional {v6_min_opt_a}개 이상 필수')
print(f'  Strategy B (ReversalV4): min_score {v6_min_score_b}pt 이상')
print('=' * 110)

# ── pre-filter (sim=8과 동일: A후보+B후보 UNION) ────────────────
pre_sql = f"""
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
    candidates = engine_dbl.execute(pre_sql).fetchall()
except Exception as e:
    print(f'❌ pre-filter 실패: {e}')
    sys.exit(1)

cnt_a_pre = sum(1 for r in candidates
                if float(r['d1_diff_rate'] or 0) >= 1.5
                and float(r['vol5'] or 0) > float(r['vol20'] or 1) * 1.2)
cnt_b_pre = sum(1 for r in candidates
                if 25 <= float(r['rsi14'] or 0) <= 54)
print(f'\n  SQL 사전필터: {len(candidates)}개 (A후보 {cnt_a_pre} / B후보 {cnt_b_pre})  스코어링 중...\n')

# ── 스코어링 ─────────────────────────────────────────────────────
scored_a, scored_b, rejected_a = [], [], []
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
    res_a = strat_a.calculate_total_score(row_dict, df_120)
    res_a['code'] = code; res_a['code_name'] = code_name
    res_a['close']   = float(row_dict.get('close')       or 0)
    res_a['d1_diff'] = float(row_dict.get('d1_diff_rate') or 0)
    res_a['rsi14']   = float(row_dict.get('rsi14')        or 0)
    res_a['vol_r']   = (float(row_dict.get('vol5') or 0) /
                        max(float(row_dict.get('vol20') or 1), 1))
    res_a['bw']      = float(row_dict.get('bb_bandwidth') or 0)

    if not res_a['auto_reject']:
        opt = int(res_a['total'])
        if opt >= v6_min_opt_a:
            scored_a.append(res_a)
        else:
            res_a['reject_reason'] = f'opt {opt}<{v6_min_opt_a}'
            rejected_a.append(res_a)
    else:
        rejected_a.append(res_a)

    # Strategy B
    res_b = strat_b.calculate_total_score(row_dict, df_120, fundamental_data=None)
    res_b['code'] = code; res_b['code_name'] = code_name
    res_b['close']   = float(row_dict.get('close')       or 0)
    res_b['d1_diff'] = float(row_dict.get('d1_diff_rate') or 0)
    res_b['rsi14']   = float(row_dict.get('rsi14')        or 0)
    if not res_b['auto_reject'] and res_b['total'] >= v6_min_score_b:
        scored_b.append(res_b)

scored_a.sort(key=lambda x: x['total'], reverse=True)
scored_b.sort(key=lambda x: x['total'], reverse=True)

print(f'  완료 — A통과 {len(scored_a)}개 / B통과 {len(scored_b)}개 (오류 {errors}개)')

# ═══════════════════════════════════════════════════════════════════
# SECTION 1 — Strategy A 결과
# ═══════════════════════════════════════════════════════════════════
print()
print('=' * 110)
print(f'  ▶ Strategy A (BreakoutV5 Condition)  통과: {len(scored_a)}개  [opt>={v6_min_opt_a}]')
print(f'  Required: vol_ratio>1.5 + atr_rate>0.02 + bb_bandwidth>0.05 + NASDAQ gate')
print(f'  Optional: bb_pos<0.65 / rsi<55 / mfi>30 / close>kijun / +DI>-DI')
print('=' * 110)

if scored_a:
    HDR_A = (f'  {"순":>3} {"종목코드":<10} {"종목명":<18} {"opt":>4}  '
             f'{"bbp":>4} {"rsi":>4} {"mfi":>4} {"kij":>4} {"DI":>4}  '
             f'{"vol_r":>6} {"bw":>6} {"RSI":>5} {"등락":>6}  {"종가":>10}')
    print(HDR_A)
    print('  ' + '-' * 100)
    for i, s in enumerate(scored_a[:30], 1):
        opt_str = (f'{int(s["score_a"])}{int(s["score_b"])}'
                   f'{int(s["score_c"])}{int(s["score_d"])}{int(s["score_e"])}')
        print(f'  {i:>3} {s["code"]:<10} {s["code_name"]:<18} '
              f'{int(s["total"]):>4}  '
              f'  {opt_str}   '
              f'{s["vol_r"]:>6.2f} {s["bw"]:>6.3f} '
              f'{s["rsi14"]:>5.1f} {s["d1_diff"]:>+5.1f}%'
              f'  {int(s["close"]):>10,}')
else:
    print('  (통과 종목 없음)')

# ─── 아슬아슬 탈락 (required 통과했지만 opt 부족) ──────────────
near_miss = [r for r in rejected_a
             if not r['auto_reject'] or 'opt' in str(r.get('reject_reason', ''))][:10]
if near_miss:
    print(f'\n  ── A 아슬아슬 탈락 (opt 부족) ─────────────')
    for s in near_miss:
        opt_str = (f'{int(s["score_a"])}{int(s["score_b"])}'
                   f'{int(s["score_c"])}{int(s["score_d"])}{int(s["score_e"])}')
        print(f'     {s["code"]:<10} {s["code_name"]:<18} '
              f'opt={int(s["total"])}  [{opt_str}]  '
              f'{s["reject_reason"]}')

# ─── NASDAQ 차단 통계 ─────────────────────────────────────────
nasdaq_rej = [r for r in rejected_a if 'NASDAQ' in str(r.get('reject_reason', ''))]
if nasdaq_rej:
    regimes = {}
    for r in nasdaq_rej:
        k = r.get('reject_reason', '')
        regimes[k] = regimes.get(k, 0) + 1
    regime_str = ' / '.join(f'{k}: {v}개' for k, v in regimes.items())
    print(f'\n  ── NASDAQ gate 차단: {len(nasdaq_rej)}개  ({regime_str})')

# ═══════════════════════════════════════════════════════════════════
# SECTION 2 — Strategy B 결과
# ═══════════════════════════════════════════════════════════════════
print()
print('=' * 110)
print(f'  ▶ Strategy B (ReversalV4 Scoring)  통과: {len(scored_b)}개  [>={v6_min_score_b}pt]')
print('=' * 110)

if scored_b:
    HDR_B = (f'  {"순":>3} {"종목코드":<10} {"종목명":<18} {"총점":>6}  '
             f'{"RSI신":>6} {"펀더":>6} {"추세":>6} {"BB사":>6} {"거량":>6} {"회복":>6} {"기관":>6} {"NAS":>6}  '
             f'{"RSI":>5} {"등락":>6}  {"종가":>10}')
    print(HDR_B)
    print('  ' + '-' * 108)
    for i, s in enumerate(scored_b[:25], 1):
        print(f'  {i:>3} {s["code"]:<10} {s["code_name"]:<18} '
              f'{s["total"]:>6.1f}  '
              f'{s["score_a"]:>6.1f} {s["score_b"]:>6.1f} {s["score_c"]:>6.1f} '
              f'{s["score_d"]:>6.1f} {s["score_e"]:>6.1f} {s["score_f"]:>6.1f} '
              f'{s["score_g"]:>6.1f} {s.get("score_h", 0):>6.1f}  '
              f'{s["rsi14"]:>5.1f} {s["d1_diff"]:>+5.1f}%'
              f'  {int(s["close"]):>10,}')
else:
    print('  (통과 종목 없음)')

print()
print('=' * 110)
engine_dbl.dispose(); engine_craw.dispose()
