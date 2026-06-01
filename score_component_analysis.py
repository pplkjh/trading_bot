# -*- coding: utf-8 -*-
"""
Strategy A/B 스코어 컴포넌트별 수익 상관관계 분석

Usage:
  python score_component_analysis.py A    # simulator4 (Strategy A)
  python score_component_analysis.py B    # simulator5 (Strategy B)
  python score_component_analysis.py AB   # 둘 다

동작:
  - all_item_db에서 매도 완료 종목의 score_a~score_e, composite_score, sell_rate 읽기
  - 각 컴포넌트별 Pearson 상관계수 계산
  - 구간별 승률/평균수익 분포 출력
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
DB_NAME = {'A': 'simulator4', 'B': 'simulator5'}

# Strategy A 컴포넌트 정보 (배점 — v3.1 기준)
COMPONENTS_A = [
    ('score_a', '돌파강도',   50),   # 역U자 수정 (70→50)
    ('score_b', 'BB+단기MA',  60),
    ('score_c', 'ADX방향성',  10),   # 방향성 개선 복원
    ('score_d', 'MACD전환',   30),
    ('score_e', 'RSI50돌파',  30),
    ('score_f', 'BB압축도',   20),   # 신규
]

# Strategy B 컴포넌트 정보 (배점 — v3.2 기준)
COMPONENTS_B = [
    ('score_a', 'RSI신호',    65),   # 80→65
    ('score_b', '펀더멘털',   40),
    ('score_c', '장기추세',   55),   # 40→55
    ('score_d', 'BB사이클',   10),   # 25→15→10 (r=+0.011 무효, 비중 추가 축소)
    ('score_e', '거래량MACD', 15),
    ('score_f', '회복모멘텀', 15),   # 10→15 (r=+0.1316 최고 상관, 비중 상향)
]

COMPONENTS = {'A': COMPONENTS_A, 'B': COMPONENTS_B}
# ─────────────────────────────────────────────────────────────────


def get_engine(db_name):
    url = (f"mysql+pymysql://{cf.db_id}:{cf.db_passwd}"
           f"@{cf.db_ip}:{cf.db_port}/{db_name}?charset=utf8")
    return create_engine(url)


def pearson_r(xs, ys):
    """순수 Python Pearson 상관계수 계산"""
    n = len(xs)
    if n < 3:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy)


def judge_r(r):
    ar = abs(r)
    if ar >= 0.15:
        return '★★★ 유의미'
    elif ar >= 0.08:
        return '★★ 중간 상관'
    elif ar >= 0.04:
        return '★ 약한 상관'
    else:
        return '  없음'


def analyze_component(col_name, label, max_pt, rows, n_buckets=5):
    """단일 컴포넌트 구간별 분포 출력"""
    # 구간 정의
    step = max_pt / n_buckets
    edges = [round(step * i, 1) for i in range(n_buckets + 1)]
    edges[-1] = max_pt + 0.1  # inclusive upper bound

    print(f"\n  [{col_name}] {label} (만점 {max_pt}pt)")
    print(f"  {'구간':>12} | {'n':>5} | {'승률':>5} | {'평균익절':>6} | {'평균손절':>6} | {'R':>5} | {'avg수익':>7}")
    print("  " + "-" * 70)

    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        subset = [(r['sell_rate'],) for r in rows
                  if r[col_name] is not None and lo <= float(r[col_name]) < hi]
        rates = [s[0] for s in subset]
        if not rates:
            label_r = f"{lo:.0f}~{hi-0.1:.0f}"
            print(f"  {label_r:>12} | {'(없음)':>5}")
            continue

        wins = [r for r in rates if r >= 0]
        loses = [r for r in rates if r < 0]
        wr = len(wins) / len(rates) * 100
        ap = sum(wins) / len(wins) if wins else 0.0
        al = sum(loses) / len(loses) if loses else 0.0
        rr = abs(ap / al) if al != 0 else 0.0
        avg = sum(rates) / len(rates)

        label_r = f"{lo:.0f}~{hi-0.1:.0f}" if hi - 0.1 < max_pt else f"{lo:.0f}+"
        print(f"  {label_r:>12} | {len(rates):>5} | {wr:>4.1f}% | "
              f"{ap:>5.2f}% | {al:>5.2f}% | {rr:>5.2f} | {avg:>+6.2f}%")


def analyze(strategy):
    db_name = DB_NAME[strategy]
    comps = COMPONENTS[strategy]
    engine = get_engine(db_name)

    print(f"\n{'='*80}")
    print(f"  Strategy {strategy}  스코어 컴포넌트 × 수익 상관관계 분석")
    print(f"  DB: {db_name}")
    print(f"{'='*80}")

    # 데이터 읽기
    try:
        rows_raw = engine.execute("""
            SELECT sell_rate, composite_score,
                   score_a, score_b, score_c, score_d, score_e, score_f, score_penalty
            FROM all_item_db
            WHERE sell_date != '0' AND sell_date != ''
              AND sell_rate IS NOT NULL
        """).fetchall()
    except Exception as e:
        print(f"  ❌ 데이터 읽기 실패: {e}")
        return

    if not rows_raw:
        print("  데이터 없음 — 백테스트를 먼저 실행하세요")
        return

    # RowProxy → dict
    rows = []
    for r in rows_raw:
        rows.append({
            'sell_rate':       float(r[0] or 0),
            'composite_score': float(r[1] or 0) if r[1] is not None else 0.0,
            'score_a':         float(r[2] or 0) if r[2] is not None else 0.0,
            'score_b':         float(r[3] or 0) if r[3] is not None else 0.0,
            'score_c':         float(r[4] or 0) if r[4] is not None else 0.0,
            'score_d':         float(r[5] or 0) if r[5] is not None else 0.0,
            'score_e':         float(r[6] or 0) if r[6] is not None else 0.0,
            'score_f':         float(r[7] or 0) if r[7] is not None else 0.0,
            'score_penalty':   float(r[8] or 0) if r[8] is not None else 0.0,
        })

    print(f"\n  총 거래: {len(rows)}건")
    rates_all = [r['sell_rate'] for r in rows]
    wins_all = [r for r in rates_all if r >= 0]
    print(f"  전체 승률: {len(wins_all)/len(rows)*100:.1f}%  "
          f"평균수익: {sum(rates_all)/len(rows):+.2f}%")

    # ── 1. Pearson 상관계수 요약 ─────────────────────────────────
    print(f"\n  {'컴포넌트':<14} {'만점':>5}  {'Pearson r':>10}  판정")
    print("  " + "-" * 55)

    sell_rates = [r['sell_rate'] for r in rows]

    for col, lbl, max_pt in comps:
        vals = [r[col] for r in rows]
        r_val = pearson_r(vals, sell_rates)
        print(f"  {lbl+'('+col+')':15} {max_pt:>5}  {r_val:>+10.4f}  {judge_r(r_val)}")

    # 총점
    comp_vals = [r['composite_score'] for r in rows]
    r_total = pearson_r(comp_vals, sell_rates)
    print(f"  {'총점(composite)':15} {'200':>5}  {r_total:>+10.4f}  {judge_r(r_total)}")

    # 패널티
    pen_vals = [r['score_penalty'] for r in rows]
    r_pen = pearson_r(pen_vals, sell_rates)
    print(f"  {'패널티':15} {'-':>5}  {r_pen:>+10.4f}  {judge_r(r_pen)}")

    # ── 2. 각 컴포넌트 구간별 상세 ──────────────────────────────
    print(f"\n\n  ── 컴포넌트별 구간 상세 ──")
    for col, lbl, max_pt in comps:
        analyze_component(col, lbl, max_pt, rows)

    # ── 3. 총점 구간별 ─────────────────────────────────────────
    print(f"\n  [총점] composite_score 구간별 성과")
    print(f"  {'구간':>12} | {'n':>5} | {'승률':>5} | {'평균익절':>6} | {'평균손절':>6} | {'avg수익':>7}")
    print("  " + "-" * 65)
    if strategy == 'A':
        cs_edges = [0, 80, 100, 120, 140, 160, 200]
    else:
        cs_edges = [0, 60, 80, 100, 120, 140, 160]

    for i in range(len(cs_edges) - 1):
        lo, hi = cs_edges[i], cs_edges[i + 1]
        subset_rates = [r['sell_rate'] for r in rows
                        if lo <= r['composite_score'] < hi]
        if not subset_rates:
            continue
        wins_s = [r for r in subset_rates if r >= 0]
        loses_s = [r for r in subset_rates if r < 0]
        wr = len(wins_s) / len(subset_rates) * 100
        ap = sum(wins_s) / len(wins_s) if wins_s else 0.0
        al = sum(loses_s) / len(loses_s) if loses_s else 0.0
        avg = sum(subset_rates) / len(subset_rates)
        lbl_r = f"{lo}~{hi-1}" if hi <= 200 else f"{lo}+"
        print(f"  {lbl_r:>12} | {len(subset_rates):>5} | {wr:>4.1f}% | "
              f"{ap:>5.2f}% | {al:>5.2f}% | {avg:>+6.2f}%")

    print(f"\n{'='*80}\n")


def main():
    target = sys.argv[1].upper() if len(sys.argv) > 1 else 'AB'
    if target not in ('A', 'B', 'AB'):
        print(__doc__)
        sys.exit(1)

    strategies = ['A', 'B'] if target == 'AB' else [target]
    for s in strategies:
        analyze(s)


if __name__ == '__main__':
    main()
