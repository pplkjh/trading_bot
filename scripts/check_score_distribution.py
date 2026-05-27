"""
스코어 분포 측정 스크립트 — 현재 scoring 카테고리별 실효 가중치 분석
"""
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import pymysql
import pandas as pd
import statistics

pymysql.install_as_MySQLdb()
from sqlalchemy import create_engine
from library.cf import db_id, db_passwd, db_ip, db_port, invest_unit
from library.hybrid_strategy_v2 import HybridStrategyV2

_url = f'mysql+mysqldb://{db_id}:{db_passwd}@{db_ip}:{db_port}'
engine_daily = create_engine(f'{_url}/daily_buy_list', encoding='utf-8')
engine_craw  = create_engine(f'{_url}/daily_craw',     encoding='utf-8')

# 최신 날짜 테이블
latest_row = engine_daily.execute("""
    SELECT TABLE_NAME FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = 'daily_buy_list' AND TABLE_NAME REGEXP '^[0-9]{8}$'
    ORDER BY TABLE_NAME DESC LIMIT 1
""").fetchone()

if not latest_row:
    print('daily_buy_list 테이블 없음')
    exit()

tbl = latest_row[0]
print(f'기준일: {tbl}')

# pre-filter + 상위 200개
candidates_sql = """
    SELECT a.* FROM `{tbl}` a
    WHERE NOT EXISTS (SELECT null FROM stock_konex b WHERE a.code=b.code)
    AND a.close > 0 AND a.close < {limit}
    AND a.volume > 0 AND a.vol20 > 0
    ORDER BY (
        (CASE WHEN a.adx > 20 THEN 1 ELSE 0 END) +
        (CASE WHEN a.clo5 > a.clo20 THEN 1 ELSE 0 END) +
        (CASE WHEN a.rsi14 BETWEEN 30 AND 55 THEN 1 ELSE 0 END) +
        (CASE WHEN a.macd > a.macd_signal THEN 1 ELSE 0 END) +
        (CASE WHEN a.cmf20 > 0 THEN 1 ELSE 0 END)
    ) DESC
    LIMIT 200
""".format(tbl=tbl, limit=invest_unit)

rows = engine_daily.execute(candidates_sql).fetchall()
print(f'후보 종목: {len(rows)}개  스코어링 시작...')

# kospi 시장 데이터
market_data = None
try:
    mdf = pd.read_sql("SELECT close FROM kospi_index ORDER BY date DESC LIMIT 20", engine_craw)
    if not mdf.empty:
        market_data = mdf['close'].iloc[::-1].reset_index(drop=True)
except Exception:
    pass

strat = HybridStrategyV2()
results = []
errors = 0

for row in rows:
    try:
        code_name = row[3]
        row_dict = dict(row)
        df_120 = pd.read_sql(
            "SELECT * FROM `{}` ORDER BY date DESC LIMIT 120".format(code_name),
            engine_craw
        ).sort_values('date').reset_index(drop=True)
        s = strat.calculate_total_score(row_dict, df_120, None, market_data)
        s['rsi14'] = float(row_dict.get('rsi14') or 0)
        s['adx']   = float(row_dict.get('adx') or 0)
        s['bb_pos'] = (
            (row_dict.get('close', 0) - row_dict.get('bb_lower', 0))
            / max(row_dict.get('bb_upper', 1) - row_dict.get('bb_lower', 0), 1)
        )
        results.append(s)
    except Exception:
        errors += 1

print(f'완료: {len(results)}개 스코어링 (오류: {errors}개)')
print()

if not results:
    print('결과 없음')
    exit()

# ── 카테고리별 통계 ──────────────────────────────────────────────────────────
keys   = ['total',   'score_a', 'score_b',   'score_c', 'score_d', 'score_e',  'score_f', 'score_penalty']
maxes  = [200,        50,        20,           50,        40,        30,          10,        0]
labels = ['총점',    'A 모멘텀', 'B 진입타이밍', 'C 추세강도', 'D 거래량', 'E 시장강도', 'F 다중시간', '패널티']

print(f"{'카테고리':<14} {'만점':>5} {'평균':>7} {'달성률':>7} {'0점%':>7} {'최소':>7} {'최대':>7}")
print('─' * 65)
avgs = {}
for k, mx, lb in zip(keys, maxes, labels):
    vals = [r[k] for r in results]
    avg  = statistics.mean(vals)
    avgs[k] = avg
    zero_pct = sum(1 for v in vals if v == 0) / len(vals) * 100
    pct = avg / mx * 100 if mx > 0 else 0
    print(f"{lb:<14} {mx:>5} {avg:>7.2f} {pct:>6.1f}% {zero_pct:>6.1f}% {min(vals):>7.2f} {max(vals):>7.2f}")

print()

# ── 실효 가중치 (평균 기여점 / 평균 총점) ────────────────────────────────────
avg_total = avgs['total']
print(f"=== 실효 가중치 (평균 기여점 ÷ 평균 총점 {avg_total:.1f}pt) ===")
cat_keys   = ['score_a','score_b','score_c','score_d','score_e','score_f']
cat_labels = ['A 모멘텀','B 진입타이밍','C 추세강도','D 거래량','E 시장강도','F 다중시간']
cat_maxes  = [50, 20, 50, 40, 30, 10]
nominal    = [50/200, 20/200, 50/200, 40/200, 30/200, 10/200]

print(f"{'카테고리':<14} {'명목비중':>8} {'실효비중':>8} {'차이':>8}")
print('─' * 45)
for k, lb, mx, nom in zip(cat_keys, cat_labels, cat_maxes, nominal):
    eff = avgs[k] / avg_total * 100
    diff = eff - nom * 100
    flag = ' ★ 과소' if diff < -5 else (' ★ 과대' if diff > 5 else '')
    print(f"{lb:<14} {nom*100:>7.1f}% {eff:>7.1f}% {diff:>+7.1f}%{flag}")

print()

# ── RSI / ADX / BB위치 분포 (pre-filter 통과 종목 특성) ──────────────────
rsi_vals = [r['rsi14'] for r in results]
adx_vals = [r['adx']   for r in results]
bb_vals  = [r['bb_pos'] for r in results]

print("=== pre-filter 통과 종목 지표 분포 ===")
print(f"RSI14  - 평균: {statistics.mean(rsi_vals):.1f} | 중앙값: {statistics.median(rsi_vals):.1f} | 범위: {min(rsi_vals):.1f}~{max(rsi_vals):.1f}")
print(f"ADX    - 평균: {statistics.mean(adx_vals):.1f} | 중앙값: {statistics.median(adx_vals):.1f} | 범위: {min(adx_vals):.1f}~{max(adx_vals):.1f}")
print(f"BB위치 - 평균: {statistics.mean(bb_vals):.2f} | 중앙값: {statistics.median(bb_vals):.2f} | 범위: {min(bb_vals):.2f}~{max(bb_vals):.2f}")

# RSI 구간별 비율
b1_target = sum(1 for r in results if 40 <= r['rsi14'] <= 55)
print(f"\nB1 유효 구간(RSI 40~55): {b1_target}/{len(results)} = {b1_target/len(results)*100:.1f}%")

engine_daily.dispose()
engine_craw.dispose()

