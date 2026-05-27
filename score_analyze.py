# -*- coding: utf-8 -*-
"""
Strategy A/B 스코어 구간별 성과 분석

Usage:
  python score_analyze.py A    # simulator4에서 Strategy A 분석
  python score_analyze.py B    # simulator5에서 Strategy B 분석
  python score_analyze.py AB   # 둘 다

동작 방식:
  1. 최저 임계값(A=70, B=60)으로 백테스트 한 번 실행
  2. all_item_db에 저장된 composite_score 기준으로 구간별 집계
  3. 비교 테이블 출력

기존 score_sweep 대비 장점:
  - 9번 → 2번 실행으로 단축 (~5h vs ~20h)
  - 중간 결과가 DB에 보존됨 (프로세스 죽어도 쿼리로 확인 가능)
"""
import sys
import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from sqlalchemy import create_engine
from library import cf

# ── 설정 ─────────────────────────────────────────────────────────
MIN_SCORE = {'A': 70, 'B': 60}       # 최저 임계값 (이 이상 전부 매수)

# 분석할 스코어 구간 (하한 inclusive)
BUCKETS = {
    'A': [70, 80, 90, 100, 110, 120],
    'B': [60, 70, 80, 90, 100],
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

    for lo in buckets:
        subset = [(score, rate) for score, rate in rows
                  if score is not None and float(score) >= lo]

        if not subset:
            print(f"{'≥'+str(lo):>10} | {'(없음)':>5}")
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

        print(
            f"{'>='+str(lo):>10} | "
            f"{total:>5} | "
            f"{win_rate:>4.1f}% | "
            f"{avg_profit:>5.2f}% | "
            f"{avg_loss:>5.2f}% | "
            f"{r_ratio:>5.2f} | "
            f"{avg_ret:>+6.2f}%"
        )

    print(f"{'='*80}\n")


def main():
    target = sys.argv[1].upper() if len(sys.argv) > 1 else 'AB'
    if target not in ('A', 'B', 'AB'):
        print(__doc__)
        sys.exit(1)

    strategies = ['A', 'B'] if target == 'AB' else [target]

    start = datetime.datetime.now()

    for s in strategies:
        run_backtest(s)
        analyze(s)

    elapsed = datetime.datetime.now() - start
    print(f"총 소요 시간: {elapsed}")


if __name__ == '__main__':
    main()
