# -*- coding: utf-8 -*-
"""
Strategy A/B 스코어 구간별 성과 분석

Usage:
  python score_analyze.py A           # Strategy A 백테스트 + 분석
  python score_analyze.py B           # Strategy B 백테스트 + 분석
  python score_analyze.py AB          # 둘 다 백테스트 + 분석
  python score_analyze.py A  --analyze-only   # 기존 DB 결과만 분석 (백테스트 생략)
  python score_analyze.py B  --analyze-only   # 장중 트레이더와 병행 가능
  python score_analyze.py AB --analyze-only   # 가장 빠름 (수초)

동작 방식:
  1. [기본] 최저 임계값(A=70, B=60)으로 백테스트 한 번 실행 → DB에 결과 저장
  2. [--analyze-only] 백테스트 건너뜀 — 기존 DB에 쌓인 sell_rate/composite_score 그대로 사용
  3. all_item_db에 저장된 composite_score 기준으로 구간별 집계
  4. 비교 테이블 + min_score 자동 추천 출력

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
os.environ['JACKBOT_LOG_LEVEL'] = 'DEBUG'   # 백테스트 파일 로그는 DEBUG 전부 기록
os.environ.setdefault('JACKBOT_LOG_NAME', 'simulator')

from sqlalchemy import create_engine
from library import cf

# ── 설정 ─────────────────────────────────────────────────────────
# 스코어링 v3.1 이후: A 최대 200pt(동일), B 최대 200pt(동일, 백테스트 실효 160pt)
# 분포 전체를 보기 위해 하한 임계값을 낮게 설정
MIN_SCORE = {'A': 60, 'B': 50}       # 최저 임계값 (이 이상 전부 매수, 넓은 그물)

# 분석할 스코어 구간 (하한 inclusive) — 재백테스트 후 분포 확인용
BUCKETS = {
    'A': [60, 70, 80, 90, 100, 110, 120],   # A: 역U자 수정으로 하위 분포 확인
    'B': [50, 60, 70, 80, 90, 100, 110],    # B: 컴포넌트 재배분으로 분포 이동 가능
}

DB_NAME  = {'A': 'simulator4', 'B': 'simulator5'}
SIMUL_NUM = {'A': '4', 'B': '5'}
INITIAL_CAPITAL = 10_000_000
# ─────────────────────────────────────────────────────────────────


def get_engine(db_name):
    url = (f"mysql+pymysql://{cf.db_id}:{cf.db_passwd}"
           f"@{cf.db_ip}:{cf.db_port}/{db_name}?charset=utf8")
    return create_engine(url)


def run_backtest(strategy):
    """최저 임계값으로 풀 백테스트 실행"""
    simul_num = SIMUL_NUM[strategy]
    min_score = MIN_SCORE[strategy]

    print(f"\n{'='*65}")
    print(f"▶  Strategy {strategy}  백테스트 시작  (min_score={min_score})")
    print(f"   시작: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*65}")

    if strategy == 'A':
        cf.v4_min_score_a = min_score
    else:
        cf.v4_min_score_b = min_score

    from library.simulator_func_mysql import simulator_func_mysql
    simulator_func_mysql(simul_num, 'reset', 0)

    print(f"\n✅ 백테스트 완료: {datetime.datetime.now().strftime('%H:%M:%S')}")


def analyze(strategy):
    """DB에서 스코어 구간별 집계"""
    db_name  = DB_NAME[strategy]
    buckets  = BUCKETS[strategy]
    engine   = get_engine(db_name)

    print(f"\n{'='*80}")
    print(f"  Strategy {strategy}  스코어 구간별 성과 분석")
    print(f"  (백테스트 min_score={MIN_SCORE[strategy]}, 구간 필터는 오프라인 집계)")
    print(f"{'='*80}")

    # 전체 매도 완료 종목 읽기
    try:
        rows = engine.execute("""
            SELECT composite_score, sell_rate
            FROM all_item_db
            WHERE sell_date != '0' AND sell_date != ''
              AND composite_score IS NOT NULL
        """).fetchall()
    except Exception as e:
        print(f"  ❌ 데이터 읽기 실패: {e}")
        return

    if not rows:
        print("  데이터 없음 (백테스트 실행 후 분석하세요)")
        return

    # jango_data에서 총수익률
    try:
        jango = engine.execute(
            "SELECT d2_deposit, total_evaluation FROM jango_data ORDER BY date DESC LIMIT 1"
        ).fetchone()
        final_cap = (float(jango[0] or 0) + float(jango[1] or 0)) if jango else INITIAL_CAPITAL
        total_ret_all = (final_cap / INITIAL_CAPITAL - 1) * 100
    except Exception:
        total_ret_all = 0.0

    print(f"\n  전체 백테스트 총수익률: {total_ret_all:+.1f}%  "
          f"(min_score={MIN_SCORE[strategy]} 기준)\n")

    hdr = (f"{'구간':>10} | {'거래수':>5} | {'승률':>5} | "
           f"{'평균익절':>6} | {'평균손절':>6} | {'손익비R':>5} | {'평균수익률':>7}")
    print(hdr)
    print("-" * 75)

    for i, lo in enumerate(buckets):
        hi = buckets[i + 1] if i + 1 < len(buckets) else 9999

        subset = [(score, rate) for score, rate in rows
                  if score is not None and lo <= float(score) < hi]

        if not subset:
            label = f"{lo}~{hi-1}" if hi < 9999 else f"{lo}+"
            print(f"{label:>10} | {'(없음)':>5}")
            continue

        rates = [float(r) for _, r in subset]
        wins  = [r for r in rates if r >= 0]
        loses = [r for r in rates if r < 0]

        total     = len(rates)
        win_rate  = len(wins) / total * 100
        avg_profit = sum(wins) / len(wins)   if wins  else 0.0
        avg_loss   = sum(loses) / len(loses) if loses else 0.0
        r_ratio    = abs(avg_profit / avg_loss) if avg_loss != 0 else 0.0
        avg_ret    = sum(rates) / total

        label = f"{lo}~{hi-1}" if hi < 9999 else f"{lo}+"
        print(
            f"{label:>10} | "
            f"{total:>5} | "
            f"{win_rate:>4.1f}% | "
            f"{avg_profit:>5.2f}% | "
            f"{avg_loss:>5.2f}% | "
            f"{r_ratio:>5.2f} | "
            f"{avg_ret:>+6.2f}%"
        )

    # 누적: 특정 임계값 이상 전체
    print()
    print("  ── 임계값 이상 누적 (threshold ≥ X인 모든 거래) ──")
    print(hdr)
    print("-" * 75)

    cumul_results = []   # min_score 권장값 계산용
    for lo in buckets:
        subset = [(score, rate) for score, rate in rows
                  if score is not None and float(score) >= lo]

        if not subset:
            print(f"{'>='+str(lo):>10} | {'(없음)':>5}")
            continue

        rates = [float(r) for _, r in subset]
        wins  = [r for r in rates if r >= 0]
        loses = [r for r in rates if r < 0]

        total      = len(rates)
        win_rate   = len(wins) / total * 100
        avg_profit = sum(wins) / len(wins)   if wins  else 0.0
        avg_loss   = sum(loses) / len(loses) if loses else 0.0
        r_ratio    = abs(avg_profit / avg_loss) if avg_loss != 0 else 0.0
        avg_ret    = sum(rates) / total

        cumul_results.append({
            'threshold': lo, 'total': total,
            'win_rate': win_rate, 'avg_ret': avg_ret, 'r_ratio': r_ratio,
        })

        print(
            f"{'>='+str(lo):>10} | "
            f"{total:>5} | "
            f"{win_rate:>4.1f}% | "
            f"{avg_profit:>5.2f}% | "
            f"{avg_loss:>5.2f}% | "
            f"{r_ratio:>5.2f} | "
            f"{avg_ret:>+6.2f}%"
        )

    # ── min_score 권장값 자동 추론 ─────────────────────────────────
    if len(cumul_results) >= 2:
        print()
        print("  ── 📌 min_score 권장값 분석 ──")

        # 기준 1: avg_ret 최고점 (수익률 기준)
        best_ret  = max(cumul_results, key=lambda x: x['avg_ret'])
        # 기준 2: R_ratio 최고점 (손익비 기준)
        best_r    = max(cumul_results, key=lambda x: x['r_ratio'])
        # 기준 3: 승률 최고 중 avg_ret도 평균 이상인 것
        avg_ret_mean = sum(x['avg_ret'] for x in cumul_results) / len(cumul_results)
        best_wr   = max(
            (x for x in cumul_results if x['avg_ret'] >= avg_ret_mean),
            key=lambda x: x['win_rate'], default=best_ret
        )

        print(f"  수익률 최고  → min_score = {best_ret['threshold']:>4}  "
              f"(avg {best_ret['avg_ret']:+.2f}%, WR {best_ret['win_rate']:.1f}%, n={best_ret['total']})")
        print(f"  손익비 최고  → min_score = {best_r['threshold']:>4}  "
              f"(R={best_r['r_ratio']:.2f}, avg {best_r['avg_ret']:+.2f}%, n={best_r['total']})")
        print(f"  승률+수익 균형 → min_score = {best_wr['threshold']:>4}  "
              f"(WR {best_wr['win_rate']:.1f}%, avg {best_wr['avg_ret']:+.2f}%, n={best_wr['total']})")
        print()
        # 최종 추천: 3개 기준 중 중간값 선택
        candidates = sorted(set([
            best_ret['threshold'], best_r['threshold'], best_wr['threshold']
        ]))
        recommended = candidates[len(candidates) // 2]
        print(f"  💡 권장 min_score (중앙값 기준): {recommended}")
        print(f"     → cf.py: v4_min_score_{strategy.lower()} = {recommended}")

    print(f"{'='*80}\n")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = [a for a in sys.argv[1:] if a.startswith('--')]

    target = args[0].upper() if args else 'AB'
    if target not in ('A', 'B', 'AB'):
        print(__doc__)
        sys.exit(1)

    analyze_only = '--analyze-only' in flags

    if analyze_only:
        print("=" * 65)
        print("  [--analyze-only] 백테스트 생략 — 기존 DB 결과로 분석")
        print("  (장중 트레이더와 병행 가능, 수초 내 완료)")
        print("=" * 65)

    strategies = ['A', 'B'] if target == 'AB' else [target]

    start = datetime.datetime.now()

    for s in strategies:
        if not analyze_only:
            run_backtest(s)
        analyze(s)

    elapsed = datetime.datetime.now() - start
    print(f"총 소요 시간: {elapsed}")


if __name__ == '__main__':
    main()
