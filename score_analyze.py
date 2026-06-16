# -*- coding: utf-8 -*-
"""
Strategy A/B/6/7 스코어 구간별 성과 분석

Usage:
  python score_analyze.py A           # Strategy A 백테스트 + 분석  (simulator4)
  python score_analyze.py B           # Strategy B 백테스트 + 분석  (simulator5)
  python score_analyze.py AB          # 둘 다 백테스트 + 분석
  python score_analyze.py 6           # A+B 혼합 백테스트 + A/B 분리 분석  (simulator6)
  python score_analyze.py 7           # V4+NASDAQ 백테스트 + A/B 분리 분석  (simulator7)
  python score_analyze.py A  --analyze-only   # 기존 DB 결과만 분석 (백테스트 생략)
  python score_analyze.py B  --analyze-only   # 장중 트레이더와 병행 가능
  python score_analyze.py AB --analyze-only   # 가장 빠름 (수초)
  python score_analyze.py 6  --analyze-only   # sim=6 기존 결과만 A/B 분리 분석
  python score_analyze.py 7  --analyze-only   # sim=7 기존 결과만 A/B 분리 분석
  python score_analyze.py 6  --resume         # 중단된 백테스트 이어서 실행
  python score_analyze.py 7  --resume         # sim=7 중단된 백테스트 이어서 실행

동작 방식:
  1. [기본] 최저 임계값으로 백테스트 한 번 실행 → DB에 결과 저장
  2. [--analyze-only] 백테스트 건너뜀 — 기존 DB에 쌓인 결과 그대로 사용
  3. all_item_db에 저장된 composite_score 기준으로 구간별 집계
  4. [6] strategy_type='A'/'B'로 분리해서 각각 분석
  5. 비교 테이블 + min_score 자동 추천 출력

주의:
  백테스트(run_backtest)는 daily_craw를 수백만 쿼리로 읽어 실전 트레이더와 충돌 가능.
  장중에는 반드시 --analyze-only 사용할 것.
"""
import sys
import os
import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# jackbot.log와 분리 (실전 트레이더 로그 오염 방지)
os.environ['JACKBOT_LOG_FILE'] = f"score_analyze_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
os.environ['JACKBOT_LOG_LEVEL'] = 'DEBUG'
os.environ.setdefault('JACKBOT_LOG_NAME', 'simulator')

from sqlalchemy import create_engine
from library import cf

# ── 설정 ─────────────────────────────────────────────────────────
MIN_SCORE = {'A': 60, 'B': 50, '6': 50, '7': 50}   # 백테스트용 최저 임계값

BUCKETS = {
    'A': [60, 70, 80, 90, 100, 110, 120],
    'B': [50, 60, 70, 80, 90, 100, 110],
}

DB_NAME   = {'A': 'simulator4', 'B': 'simulator5', '6': 'simulator6', '7': 'simulator7'}
SIMUL_NUM = {'A': '4',          'B': '5',          '6': '6',          '7': '7'}
INITIAL_CAPITAL = 10_000_000
# ─────────────────────────────────────────────────────────────────


def get_engine(db_name):
    url = (f"mysql+pymysql://{cf.db_id}:{cf.db_passwd}"
           f"@{cf.db_ip}:{cf.db_port}/{db_name}?charset=utf8")
    return create_engine(url)


def run_backtest(strategy, resume=False):
    """최저 임계값으로 풀 백테스트 실행. resume=True이면 중단 지점부터 이어서 실행"""
    simul_num = SIMUL_NUM[strategy]
    mode = 'continue' if resume else 'reset'

    if strategy == '6':
        min_a = MIN_SCORE['A']
        min_b = MIN_SCORE['B']
        print(f"\n{'='*65}")
        print(f"▶  Strategy 6 (A+B 혼합)  백테스트 {'재개' if resume else '시작'}")
        print(f"   min_score_a={min_a}  min_score_b={min_b}  mode={mode}")
        print(f"   시작: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*65}")
        cf.v4_min_score_a = min_a
        cf.v4_min_score_b = min_b
    elif strategy == '7':
        min_a = MIN_SCORE['A']
        min_b = MIN_SCORE['B']
        print(f"\n{'='*65}")
        print(f"▶  Strategy 7 (V4+NASDAQ)  백테스트 {'재개' if resume else '시작'}")
        print(f"   min_score_a={min_a}  min_score_b={min_b}  mode={mode}")
        print(f"   시작: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*65}")
        cf.v5_min_score_a = min_a
        cf.v5_min_score_b = min_b
    else:
        min_score = MIN_SCORE[strategy]
        print(f"\n{'='*65}")
        print(f"▶  Strategy {strategy}  백테스트 {'재개' if resume else '시작'}  (min_score={min_score}, mode={mode})")
        print(f"   시작: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*65}")
        if strategy == 'A':
            cf.v4_min_score_a = min_score
        else:
            cf.v4_min_score_b = min_score

    from library.simulator_func_mysql import simulator_func_mysql
    simulator_func_mysql(simul_num, mode, 0)
    print(f"\n✅ 백테스트 완료: {datetime.datetime.now().strftime('%H:%M:%S')}")


def _bucket_stats(rows, buckets):
    """rows=[(score, rate), ...] 를 buckets 기준으로 구간별 집계 후 출력. cumul_results 반환."""
    hdr = (f"{'구간':>10} | {'거래수':>5} | {'승률':>5} | "
           f"{'평균익절':>6} | {'평균손절':>6} | {'손익비R':>5} | {'평균수익률':>7}")
    print(hdr)
    print("-" * 75)

    for i, lo in enumerate(buckets):
        hi = buckets[i + 1] if i + 1 < len(buckets) else 9999
        subset = [float(r) for s, r in rows if s is not None and lo <= float(s) < hi]
        if not subset:
            label = f"{lo}~{hi-1}" if hi < 9999 else f"{lo}+"
            print(f"{label:>10} | {'(없음)':>5}")
            continue
        wins  = [r for r in subset if r >= 0]
        loses = [r for r in subset if r < 0]
        wr    = len(wins) / len(subset) * 100
        ap    = sum(wins) / len(wins)   if wins  else 0.0
        al    = sum(loses) / len(loses) if loses else 0.0
        rr    = abs(ap / al) if al != 0 else 0.0
        avg   = sum(subset) / len(subset)
        label = f"{lo}~{hi-1}" if hi < 9999 else f"{lo}+"
        print(f"{label:>10} | {len(subset):>5} | {wr:>4.1f}% | "
              f"{ap:>5.2f}% | {al:>5.2f}% | {rr:>5.2f} | {avg:>+6.2f}%")

    print()
    print("  ── 임계값 이상 누적 ──")
    print(hdr)
    print("-" * 75)

    cumul_results = []
    for lo in buckets:
        subset = [float(r) for s, r in rows if s is not None and float(s) >= lo]
        if not subset:
            print(f"{'>='+str(lo):>10} | {'(없음)':>5}")
            continue
        wins  = [r for r in subset if r >= 0]
        loses = [r for r in subset if r < 0]
        wr    = len(wins) / len(subset) * 100
        ap    = sum(wins) / len(wins)   if wins  else 0.0
        al    = sum(loses) / len(loses) if loses else 0.0
        rr    = abs(ap / al) if al != 0 else 0.0
        avg   = sum(subset) / len(subset)
        cumul_results.append({'threshold': lo, 'total': len(subset),
                               'win_rate': wr, 'avg_ret': avg, 'r_ratio': rr})
        print(f"{'>='+str(lo):>10} | {len(subset):>5} | {wr:>4.1f}% | "
              f"{ap:>5.2f}% | {al:>5.2f}% | {rr:>5.2f} | {avg:>+6.2f}%")

    return cumul_results


def _recommend(cumul_results, strategy_label, score_prefix='v4'):
    """min_score 권장값 자동 추론 출력"""
    if len(cumul_results) < 2:
        return
    print()
    print("  ── 📌 min_score 권장값 분석 ──")
    best_ret = max(cumul_results, key=lambda x: x['avg_ret'])
    best_r   = max(cumul_results, key=lambda x: x['r_ratio'])
    mean_ret = sum(x['avg_ret'] for x in cumul_results) / len(cumul_results)
    best_wr  = max(
        (x for x in cumul_results if x['avg_ret'] >= mean_ret),
        key=lambda x: x['win_rate'], default=best_ret
    )
    print(f"  수익률 최고  → min_score = {best_ret['threshold']:>4}  "
          f"(avg {best_ret['avg_ret']:+.2f}%, WR {best_ret['win_rate']:.1f}%, n={best_ret['total']})")
    print(f"  손익비 최고  → min_score = {best_r['threshold']:>4}  "
          f"(R={best_r['r_ratio']:.2f}, avg {best_r['avg_ret']:+.2f}%, n={best_r['total']})")
    print(f"  승률+수익 균형 → min_score = {best_wr['threshold']:>4}  "
          f"(WR {best_wr['win_rate']:.1f}%, avg {best_wr['avg_ret']:+.2f}%, n={best_wr['total']})")
    candidates = sorted(set([best_ret['threshold'], best_r['threshold'], best_wr['threshold']]))
    recommended = candidates[len(candidates) // 2]
    print(f"\n  💡 권장 min_score: {recommended}  → cf.py: {score_prefix}_min_score_{strategy_label} = {recommended}")


def analyze(strategy):
    """DB에서 스코어 구간별 집계 (A 또는 B 단독)"""
    db_name = DB_NAME[strategy]
    buckets = BUCKETS[strategy]
    engine  = get_engine(db_name)

    print(f"\n{'='*80}")
    print(f"  Strategy {strategy}  스코어 구간별 성과 분석  (DB: {db_name})")
    print(f"  백테스트 min_score={MIN_SCORE[strategy]}")
    print(f"{'='*80}")

    try:
        rows = engine.execute("""
            SELECT composite_score, sell_rate FROM all_item_db
            WHERE sell_date != '0' AND sell_date != ''
              AND composite_score IS NOT NULL
        """).fetchall()
    except Exception as e:
        print(f"  ❌ 데이터 읽기 실패: {e}")
        return

    if not rows:
        print("  데이터 없음 (백테스트 실행 후 분석하세요)")
        return

    try:
        jango = engine.execute(
            "SELECT d2_deposit, total_evaluation FROM jango_data ORDER BY date DESC LIMIT 1"
        ).fetchone()
        final_cap = (float(jango[0] or 0) + float(jango[1] or 0)) if jango else INITIAL_CAPITAL
        total_ret_all = (final_cap / INITIAL_CAPITAL - 1) * 100
    except Exception:
        total_ret_all = 0.0

    all_rates = [float(r) for _, r in rows]
    wins_all  = [r for r in all_rates if r >= 0]
    print(f"\n  총 거래: {len(rows)}건  |  승률: {len(wins_all)/len(rows)*100:.1f}%  "
          f"|  평균수익: {sum(all_rates)/len(rows):+.2f}%  "
          f"|  총수익률: {total_ret_all:+.1f}%\n")

    cumul = _bucket_stats(rows, buckets)
    _recommend(cumul, strategy.lower())
    print(f"{'='*80}\n")


def analyze_6():
    """simulator6 DB에서 A/B 분리 분석"""
    engine = get_engine('simulator6')

    print(f"\n{'='*80}")
    print(f"  Strategy 6 (A+B 혼합)  분리 분석  (DB: simulator6)")
    print(f"{'='*80}")

    try:
        rows = engine.execute("""
            SELECT composite_score, sell_rate, strategy_type FROM all_item_db
            WHERE sell_date != '0' AND sell_date != ''
              AND composite_score IS NOT NULL
        """).fetchall()
    except Exception as e:
        print(f"  ❌ 데이터 읽기 실패: {e}")
        return

    if not rows:
        print("  데이터 없음 (백테스트 실행 후 분석하세요)")
        return

    # 전체 통계
    all_rates = [float(r) for _, r, _ in rows]
    wins_all  = [r for r in all_rates if r >= 0]
    rows_a = [(s, r) for s, r, st in rows if str(st) == 'A']
    rows_b = [(s, r) for s, r, st in rows if str(st) == 'B']

    try:
        jango = engine.execute(
            "SELECT d2_deposit, total_evaluation FROM jango_data ORDER BY date DESC LIMIT 1"
        ).fetchone()
        final_cap = (float(jango[0] or 0) + float(jango[1] or 0)) if jango else INITIAL_CAPITAL
        total_ret = (final_cap / INITIAL_CAPITAL - 1) * 100
    except Exception:
        total_ret = 0.0

    print(f"\n  총 거래: {len(rows)}건  (A={len(rows_a)}건 / B={len(rows_b)}건)")
    print(f"  전체 승률: {len(wins_all)/len(rows)*100:.1f}%  "
          f"평균수익: {sum(all_rates)/len(rows):+.2f}%  "
          f"총수익률: {total_ret:+.1f}%")

    # ── Strategy A 분석 ───────────────────────────────────────────
    if rows_a:
        rates_a = [float(r) for _, r in rows_a]
        wins_a  = [r for r in rates_a if r >= 0]
        print(f"\n{'─'*80}")
        print(f"  [Strategy A]  {len(rows_a)}건  "
              f"승률 {len(wins_a)/len(rows_a)*100:.1f}%  "
              f"평균수익 {sum(rates_a)/len(rows_a):+.2f}%")
        print(f"{'─'*80}")
        cumul_a = _bucket_stats(rows_a, BUCKETS['A'])
        _recommend(cumul_a, 'a')
    else:
        print("\n  Strategy A 거래 없음")

    # ── Strategy B 분석 ───────────────────────────────────────────
    if rows_b:
        rates_b = [float(r) for _, r in rows_b]
        wins_b  = [r for r in rates_b if r >= 0]
        print(f"\n{'─'*80}")
        print(f"  [Strategy B]  {len(rows_b)}건  "
              f"승률 {len(wins_b)/len(rows_b)*100:.1f}%  "
              f"평균수익 {sum(rates_b)/len(rows_b):+.2f}%")
        print(f"{'─'*80}")
        cumul_b = _bucket_stats(rows_b, BUCKETS['B'])
        _recommend(cumul_b, 'b')
    else:
        print("\n  Strategy B 거래 없음")

    print(f"\n{'='*80}\n")


def analyze_7():
    """simulator7 DB에서 A/B 분리 분석 (score_h 포함)"""
    engine = get_engine('simulator7')

    print(f"\n{'='*80}")
    print(f"  Strategy 7 (V4+NASDAQ)  분리 분석  (DB: simulator7)")
    print(f"{'='*80}")

    try:
        rows = engine.execute("""
            SELECT composite_score, sell_rate, strategy_type FROM all_item_db
            WHERE sell_date != '0' AND sell_date != ''
              AND composite_score IS NOT NULL
        """).fetchall()
    except Exception as e:
        print(f"  ❌ 데이터 읽기 실패: {e}")
        return

    if not rows:
        print("  데이터 없음 (백테스트 실행 후 분석하세요)")
        return

    all_rates = [float(r) for _, r, _ in rows]
    wins_all  = [r for r in all_rates if r >= 0]
    rows_a = [(s, r) for s, r, st in rows if str(st) == 'A']
    rows_b = [(s, r) for s, r, st in rows if str(st) == 'B']

    try:
        jango = engine.execute(
            "SELECT d2_deposit, total_evaluation FROM jango_data ORDER BY date DESC LIMIT 1"
        ).fetchone()
        final_cap = (float(jango[0] or 0) + float(jango[1] or 0)) if jango else INITIAL_CAPITAL
        total_ret = (final_cap / INITIAL_CAPITAL - 1) * 100
    except Exception:
        total_ret = 0.0

    print(f"\n  총 거래: {len(rows)}건  (A={len(rows_a)}건 / B={len(rows_b)}건)")
    print(f"  전체 승률: {len(wins_all)/len(rows)*100:.1f}%  "
          f"평균수익: {sum(all_rates)/len(rows):+.2f}%  "
          f"총수익률: {total_ret:+.1f}%")

    if rows_a:
        rates_a = [float(r) for _, r in rows_a]
        wins_a  = [r for r in rates_a if r >= 0]
        print(f"\n{'─'*80}")
        print(f"  [Strategy A]  {len(rows_a)}건  "
              f"승률 {len(wins_a)/len(rows_a)*100:.1f}%  "
              f"평균수익 {sum(rates_a)/len(rows_a):+.2f}%")
        print(f"{'─'*80}")
        cumul_a = _bucket_stats(rows_a, BUCKETS['A'])
        _recommend(cumul_a, 'a', 'v5')
    else:
        print("\n  Strategy A 거래 없음")

    if rows_b:
        rates_b = [float(r) for _, r in rows_b]
        wins_b  = [r for r in rates_b if r >= 0]
        print(f"\n{'─'*80}")
        print(f"  [Strategy B]  {len(rows_b)}건  "
              f"승률 {len(wins_b)/len(rows_b)*100:.1f}%  "
              f"평균수익 {sum(rates_b)/len(rows_b):+.2f}%")
        print(f"{'─'*80}")
        cumul_b = _bucket_stats(rows_b, BUCKETS['B'])
        _recommend(cumul_b, 'b', 'v5')
    else:
        print("\n  Strategy B 거래 없음")

    print(f"\n{'='*80}\n")


def main():
    args  = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = [a for a in sys.argv[1:] if a.startswith('--')]

    target = args[0].upper() if args else 'AB'
    if target not in ('A', 'B', 'AB', '6', '7'):
        print(__doc__)
        sys.exit(1)

    analyze_only = '--analyze-only' in flags
    resume       = '--resume' in flags

    if analyze_only:
        print("=" * 65)
        print("  [--analyze-only] 백테스트 생략 — 기존 DB 결과로 분석")
        print("  (장중 트레이더와 병행 가능, 수초 내 완료)")
        print("=" * 65)
    elif resume:
        print("=" * 65)
        print("  [--resume] 중단 지점부터 이어서 백테스트")
        print("  (jango_data 마지막 날짜 이후부터 실행)")
        print("=" * 65)

    start = datetime.datetime.now()

    if target == '6':
        if not analyze_only:
            run_backtest('6', resume=resume)
        analyze_6()
    elif target == '7':
        if not analyze_only:
            run_backtest('7', resume=resume)
        analyze_7()
    else:
        strategies = ['A', 'B'] if target == 'AB' else [target]
        for s in strategies:
            if not analyze_only:
                run_backtest(s, resume=resume)
            analyze(s)

    elapsed = datetime.datetime.now() - start
    print(f"총 소요 시간: {elapsed}")


if __name__ == '__main__':
    main()
