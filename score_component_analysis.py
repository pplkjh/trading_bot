# -*- coding: utf-8 -*-
"""
Strategy A/B/6 스코어 컴포넌트별 수익 상관관계 분석

Usage:
  python score_component_analysis.py A    # simulator4 (Strategy A)
  python score_component_analysis.py B    # simulator5 (Strategy B)
  python score_component_analysis.py AB   # 둘 다
  python score_component_analysis.py 6    # simulator6 (A+B 혼합, A/B 분리 분석)
  python score_component_analysis.py 6 --from=20240122  # inst_flow 데이터 있는 구간만

동작:
  - all_item_db에서 매도 완료 종목의 score_a~score_g, composite_score, sell_rate 읽기
  - DB에 존재하는 score_* 컬럼을 자동 감지 — 없는 컬럼은 조용히 스킵
  - 각 컴포넌트별 Pearson 상관계수 계산
  - 구간별 승률/평균수익 분포 출력
  - [6] strategy_type='A'/'B'로 분리해서 각각 분석
"""
import sys
import os
import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

os.environ['JACKBOT_LOG_FILE'] = f"score_corr_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
os.environ['JACKBOT_LOG_LEVEL'] = 'DEBUG'
os.environ.setdefault('JACKBOT_LOG_NAME', 'simulator')

from sqlalchemy import create_engine
from library import cf

# ── 설정 ─────────────────────────────────────────────────────────
DB_NAME = {'A': 'simulator4', 'B': 'simulator5', '6': 'simulator6'}

# Strategy A 컴포넌트 — 추가/변경 시 여기만 수정하면 됨
# DB에 컬럼이 없으면 자동 스킵됨 (score_g = inst_flow, 구버전 DB에 없어도 OK)
COMPONENTS_A = [
    ('score_a', '셋업품질',  50),
    ('score_b', 'BB+단기MA', 60),
    ('score_c', 'ADX방향성', 10),
    ('score_d', 'MACD전환',  30),
    ('score_e', 'RSI50돌파', 30),
    ('score_f', 'BB활성도',  20),
    ('score_g', '기관수급',  20),
]

# Strategy B 컴포넌트
COMPONENTS_B = [
    ('score_a', 'RSI신호',    65),
    ('score_b', '펀더멘털',   40),
    ('score_c', '장기추세',   55),
    ('score_d', 'BB사이클',   10),
    ('score_e', '거래량MACD', 15),
    ('score_f', '회복모멘텀', 15),
    ('score_g', '기관수급',   20),
]

COMPONENTS = {'A': COMPONENTS_A, 'B': COMPONENTS_B}
CS_EDGES   = {'A': [0, 80, 100, 120, 140, 160, 220],
              'B': [0, 60,  80, 100, 120, 140, 220]}
# ─────────────────────────────────────────────────────────────────


def get_engine(db_name):
    url = (f"mysql+pymysql://{cf.db_id}:{cf.db_passwd}"
           f"@{cf.db_ip}:{cf.db_port}/{db_name}?charset=utf8")
    return create_engine(url)


def pearson_r(xs, ys):
    n = len(xs)
    if n < 3:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx  = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy  = sum((y - my) ** 2 for y in ys) ** 0.5
    return (num / (dx * dy)) if dx and dy else 0.0


def judge_r(r):
    a = abs(r)
    if a >= 0.15: return '★★★ 유의미'
    if a >= 0.08: return '★★ 중간 상관'
    if a >= 0.04: return '★ 약한 상관'
    return '  없음'


def _get_score_cols(engine):
    """all_item_db에 실제 존재하는 score_[a-z] 컬럼 목록 반환 (score_penalty 제외)"""
    try:
        rows = engine.execute("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'all_item_db'
              AND COLUMN_NAME LIKE 'score_%%'
              AND COLUMN_NAME != 'score_penalty'
            ORDER BY COLUMN_NAME
        """).fetchall()
        return [r[0] for r in rows]
    except Exception:
        return ['score_a', 'score_b', 'score_c', 'score_d', 'score_e', 'score_f']


def _fetch_rows(engine, where_extra=''):
    """all_item_db에서 분석용 데이터 읽기

    Returns: (rows: list of dict, score_cols: list of str)
    score_cols — DB에서 실제 감지된 score_* 컬럼 목록
    """
    score_cols = _get_score_cols(engine)
    col_select = ', '.join(score_cols)
    sql = f"""
        SELECT sell_rate, composite_score, {col_select}, score_penalty
        FROM all_item_db
        WHERE sell_date != '0' AND sell_date != ''
          AND sell_rate IS NOT NULL
          {where_extra}
    """
    rows_raw = engine.execute(sql).fetchall()
    rows = []
    for r in rows_raw:
        d = {
            'sell_rate':       float(r[0] or 0),
            'composite_score': float(r[1] or 0) if r[1] is not None else 0.0,
            'score_penalty':   float(r[-1] or 0) if r[-1] is not None else 0.0,
        }
        for i, col in enumerate(score_cols):
            d[col] = float(r[2 + i] or 0)
        rows.append(d)
    return rows, score_cols


def analyze_component(col_name, label, max_pt, rows, n_buckets=5):
    """단일 컴포넌트 구간별 분포 출력"""
    step  = max_pt / n_buckets
    edges = [round(step * i, 1) for i in range(n_buckets + 1)]
    edges[-1] = max_pt + 0.1

    print(f"\n  [{col_name}] {label} (만점 {max_pt}pt)")
    print(f"  {'구간':>12} | {'n':>5} | {'승률':>5} | {'평균익절':>6} | {'평균손절':>6} | {'R':>5} | {'avg수익':>7}")
    print("  " + "-" * 70)

    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        rates = [r['sell_rate'] for r in rows
                 if r.get(col_name) is not None and lo <= float(r[col_name]) < hi]
        if not rates:
            lbl_e = f"{lo:.0f}~{hi-0.1:.0f}"
            print(f"  {lbl_e:>12} | {'(없음)':>5}")
            continue
        wins  = [r for r in rates if r >= 0]
        loses = [r for r in rates if r < 0]
        wr  = len(wins) / len(rates) * 100
        ap  = sum(wins)  / len(wins)  if wins  else 0.0
        al  = sum(loses) / len(loses) if loses else 0.0
        rr  = abs(ap / al) if al != 0 else 0.0
        avg = sum(rates) / len(rates)
        lbl = f"{lo:.0f}~{hi-0.1:.0f}" if hi - 0.1 < max_pt else f"{lo:.0f}+"
        print(f"  {lbl:>12} | {len(rates):>5} | {wr:>4.1f}% | "
              f"{ap:>5.2f}% | {al:>5.2f}% | {rr:>5.2f} | {avg:>+6.2f}%")


def _analyze_rows(rows, comps, strategy_label, score_cols=None):
    """rows(list of dict) + comps + 라벨로 상관분석 + 구간별 출력

    score_cols: DB에서 실제 확인된 컬럼 목록.
                None이면 rows[0]의 키에서 추론.
                COMPS 중 score_cols에 없는 항목은 자동 스킵.
    """
    if not rows:
        print("  데이터 없음")
        return

    # DB에 실제 있는 컬럼만 필터
    if score_cols is None:
        score_cols = [k for k in rows[0].keys()
                      if k.startswith('score_') and k != 'score_penalty']
    active_comps = [(col, lbl, mp) for col, lbl, mp in comps if col in score_cols]

    sell_rates = [r['sell_rate'] for r in rows]
    wins_all   = [r for r in sell_rates if r >= 0]
    print(f"\n  총 거래: {len(rows)}건  |  "
          f"승률: {len(wins_all)/len(rows)*100:.1f}%  |  "
          f"평균수익: {sum(sell_rates)/len(rows):+.2f}%")

    # ── Pearson 상관 ─────────────────────────────────────────────
    total_max = sum(mp for _, _, mp in active_comps)
    print(f"\n  {'컴포넌트':<16} {'만점':>5}  {'Pearson r':>10}  판정")
    print("  " + "-" * 55)
    for col, lbl, max_pt in active_comps:
        vals  = [r[col] for r in rows]
        r_val = pearson_r(vals, sell_rates)
        print(f"  {lbl+'('+col+')':17} {max_pt:>5}  {r_val:>+10.4f}  {judge_r(r_val)}")

    cs_vals  = [r['composite_score'] for r in rows]
    pen_vals = [r['score_penalty']   for r in rows]
    print(f"  {'총점(composite)':17} {total_max:>5}  {pearson_r(cs_vals, sell_rates):>+10.4f}  "
          f"{judge_r(pearson_r(cs_vals, sell_rates))}")
    print(f"  {'패널티':17} {'  -':>5}  {pearson_r(pen_vals, sell_rates):>+10.4f}  "
          f"{judge_r(pearson_r(pen_vals, sell_rates))}")

    # ── 컴포넌트별 구간 상세 ─────────────────────────────────────
    print(f"\n  ── 컴포넌트별 구간 상세 ──")
    for col, lbl, max_pt in active_comps:
        analyze_component(col, lbl, max_pt, rows)

    # ── composite_score 구간별 ────────────────────────────────────
    cs_edges = CS_EDGES.get(strategy_label, [0, 80, 100, 120, 140, 160, 220])
    print(f"\n  [총점] composite_score 구간별 성과")
    print(f"  {'구간':>12} | {'n':>5} | {'승률':>5} | {'평균익절':>6} | {'평균손절':>6} | {'avg수익':>7}")
    print("  " + "-" * 65)
    for i in range(len(cs_edges) - 1):
        lo, hi = cs_edges[i], cs_edges[i + 1]
        sub = [r['sell_rate'] for r in rows if lo <= r['composite_score'] < hi]
        if not sub:
            continue
        wins_s  = [r for r in sub if r >= 0]
        loses_s = [r for r in sub if r < 0]
        wr  = len(wins_s) / len(sub) * 100
        ap  = sum(wins_s)  / len(wins_s)  if wins_s  else 0.0
        al  = sum(loses_s) / len(loses_s) if loses_s else 0.0
        avg = sum(sub) / len(sub)
        lbl_r = f"{lo}~{hi-1}" if i < len(cs_edges) - 2 else f"{lo}+"
        print(f"  {lbl_r:>12} | {len(sub):>5} | {wr:>4.1f}% | "
              f"{ap:>5.2f}% | {al:>5.2f}% | {avg:>+6.2f}%")


def _parse_from_flag(flags):
    """--from=YYYYMMDD 또는 --from YYYYMMDD 파싱. 없으면 None 반환"""
    for f in flags:
        if f.startswith('--from='):
            return f.split('=', 1)[1].strip()
        if f == '--from':
            idx = flags.index(f)
            if idx + 1 < len(flags):
                return flags[idx + 1].strip()
    return None


def analyze(strategy, from_date=None):
    """A 또는 B 단독 분석"""
    db_name = DB_NAME[strategy]
    engine  = get_engine(db_name)

    date_filter = f"AND buy_date >= '{from_date}'" if from_date else ''
    date_label  = f"  buy_date >= {from_date}" if from_date else ''

    print(f"\n{'='*80}")
    print(f"  Strategy {strategy}  스코어 컴포넌트 × 수익 상관관계 분석")
    print(f"  DB: {db_name}{date_label}")
    print(f"{'='*80}")

    try:
        rows, score_cols = _fetch_rows(engine, date_filter)
    except Exception as e:
        print(f"  ❌ 데이터 읽기 실패: {e}")
        return

    if not rows:
        print("  데이터 없음 — 백테스트를 먼저 실행하세요")
        return

    print(f"  감지된 score 컬럼: {score_cols}")
    _analyze_rows(rows, COMPONENTS[strategy], strategy, score_cols)
    print(f"\n{'='*80}\n")


def analyze_6(from_date=None):
    """simulator6 A+B 혼합 → strategy_type으로 분리해서 각각 분석"""
    engine = get_engine('simulator6')

    date_filter = f"AND buy_date >= '{from_date}'" if from_date else ''
    date_label  = f"  buy_date >= {from_date}" if from_date else ''

    print(f"\n{'='*80}")
    print(f"  Strategy 6 (A+B 혼합)  컴포넌트 상관관계 분석  (DB: simulator6){date_label}")
    print(f"{'='*80}")

    try:
        rows_a, score_cols = _fetch_rows(engine, f"AND strategy_type = 'A' {date_filter}")
        rows_b, _          = _fetch_rows(engine, f"AND strategy_type = 'B' {date_filter}")
        rows_all, _        = _fetch_rows(engine, date_filter)
    except Exception as e:
        print(f"  ❌ 데이터 읽기 실패: {e}")
        return

    if not rows_all:
        print("  데이터 없음 — python score_analyze.py 6 으로 백테스트 먼저 실행하세요")
        return

    sell_all = [d['sell_rate'] for d in rows_all]
    wins_all = [r for r in sell_all if r >= 0]
    print(f"\n  전체: {len(rows_all)}건 (A={len(rows_a)} / B={len(rows_b)})")
    print(f"  전체 승률: {len(wins_all)/len(rows_all)*100:.1f}%  "
          f"평균수익: {sum(sell_all)/len(rows_all):+.2f}%")
    print(f"  감지된 score 컬럼: {score_cols}")

    # ── Strategy A ────────────────────────────────────────────────
    print(f"\n{'─'*80}")
    print(f"  [Strategy A]  {len(rows_a)}건")
    print(f"{'─'*80}")
    _analyze_rows(rows_a, COMPONENTS_A, 'A', score_cols)

    # ── Strategy B ────────────────────────────────────────────────
    print(f"\n{'─'*80}")
    print(f"  [Strategy B]  {len(rows_b)}건")
    print(f"{'─'*80}")
    _analyze_rows(rows_b, COMPONENTS_B, 'B', score_cols)

    print(f"\n{'='*80}\n")


def main():
    args  = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = [a for a in sys.argv[1:] if a.startswith('--')]

    target = args[0].upper() if args else 'AB'
    if target not in ('A', 'B', 'AB', '6'):
        print(__doc__)
        sys.exit(1)

    from_date = _parse_from_flag(flags)

    if target == '6':
        analyze_6(from_date=from_date)
    else:
        strategies = ['A', 'B'] if target == 'AB' else [target]
        for s in strategies:
            analyze(s, from_date=from_date)


if __name__ == '__main__':
    main()
