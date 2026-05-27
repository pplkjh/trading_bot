# -*- coding: utf-8 -*-
"""
Strategy A/B 최소 스코어 임계값 민감도 분석

Usage:
  python score_sweep.py A     # v4_min_score_a: 80, 90, 100, 110, 120
  python score_sweep.py B     # v4_min_score_b: 70, 80, 90, 100
  python score_sweep.py AB    # A -> B 순서대로

각 임계값마다 전체 백테스트(reset)를 실행하고 핵심 지표를 비교한다.
실행 시간: 임계값 1개당 약 30~60분 (3년치 데이터)
"""
import sys
import os
import datetime

# cp949 콘솔에서 이모지/특수문자 깨짐 방지 (simulator_func_mysql 내부 print 포함)
# reconfigure: 스트림 객체 유지 → shell 리다이렉션/unbuffered(-u) 정상 동작
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# 로그 파일 분리 (백테스트 로그와 겹치지 않도록)
os.environ['JACKBOT_LOG_FILE'] = f"score_sweep_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
os.environ.setdefault('JACKBOT_LOG_NAME', 'simulator')

from sqlalchemy import create_engine
from library import cf

# ─── 설정 ────────────────────────────────────────────────────────────────
THRESHOLDS = {
    'A': [80, 90, 100, 110, 120],
    'B': [70, 80, 90, 100],
}
DB_NAME = {
    'A': 'simulator4',
    'B': 'simulator5',
}
SIMUL_NUM = {
    'A': '4',
    'B': '5',
}
# ─────────────────────────────────────────────────────────────────────────


def get_engine(db_name):
    url = (f"mysql+pymysql://{cf.db_id}:{cf.db_passwd}"
           f"@{cf.db_ip}:{cf.db_port}/{db_name}?charset=utf8")
    return create_engine(url)


def read_metrics(engine, initial_capital):
    """백테스트 완료 후 DB에서 핵심 지표 읽기"""
    try:
        row = engine.execute("""
            SELECT
                COUNT(*)                                                      AS total_trades,
                SUM(CASE WHEN sell_rate >= 0 THEN 1 ELSE 0 END)              AS win_count,
                AVG(CASE WHEN sell_rate >= 0 THEN sell_rate END)             AS avg_profit,
                AVG(CASE WHEN sell_rate  < 0 THEN sell_rate END)             AS avg_loss,
                AVG(DATEDIFF(
                    STR_TO_DATE(sell_date, '%Y%m%d'),
                    STR_TO_DATE(buy_date,  '%Y%m%d')
                ))                                                            AS avg_hold
            FROM all_item_db
            WHERE sell_date != 0 AND sell_date != ''
        """).fetchone()

        total_trades = int(row[0] or 0)
        win_count    = int(row[1] or 0)
        win_rate     = win_count / total_trades * 100 if total_trades > 0 else 0.0
        avg_profit   = float(row[2] or 0)
        avg_loss     = float(row[3] or 0)
        avg_hold     = float(row[4] or 0)
        r_ratio      = abs(avg_profit / avg_loss) if avg_loss != 0 else 0.0

        # 총수익률: 방향성 지표 (jango_data 최종)
        jango = engine.execute(
            "SELECT d2_deposit, total_evaluation FROM jango_data ORDER BY date DESC LIMIT 1"
        ).fetchone()
        if jango:
            d2_dep     = float(jango[0] or 0)
            total_eval = float(jango[1] or 0)
            final_cap  = d2_dep + total_eval
            total_ret  = (final_cap / initial_capital - 1) * 100 if initial_capital > 0 else 0.0
        else:
            total_ret = 0.0

        # Sharpe (일별 sell_rate로 근사)
        try:
            rates = engine.execute("""
                SELECT sell_rate FROM all_item_db
                WHERE sell_date != 0 AND sell_date != ''
            """).fetchall()
            import numpy as np
            arr = np.array([float(r[0]) for r in rates if r[0] is not None])
            if len(arr) > 1:
                sharpe = (arr.mean() / arr.std()) * (252 ** 0.5) if arr.std() > 0 else 0.0
            else:
                sharpe = 0.0
        except Exception:
            sharpe = 0.0

        return {
            'total_trades': total_trades,
            'win_rate':     win_rate,
            'avg_profit':   avg_profit,
            'avg_loss':     avg_loss,
            'r_ratio':      r_ratio,
            'avg_hold':     avg_hold,
            'total_ret':    total_ret,
            'sharpe':       sharpe,
        }
    except Exception as e:
        print(f"  ❌ 메트릭 읽기 실패: {e}")
        return None


def run_sweep(strategy, from_threshold=None):
    thresholds      = THRESHOLDS[strategy]
    if from_threshold is not None:
        thresholds = [t for t in thresholds if t >= from_threshold]
    db_name         = DB_NAME[strategy]
    simul_num       = SIMUL_NUM[strategy]
    initial_capital = 10_000_000   # simulator4/5 기본 초기자본

    engine = get_engine(db_name)
    results = []

    for threshold in thresholds:
        print(f"\n{'='*65}")
        print(f"▶  Strategy {strategy}  |  min_score = {threshold}  |  {datetime.datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*65}")

        # cf 패치 (모듈 레퍼런스이므로 simulator_func_mysql 내부에도 즉시 반영)
        if strategy == 'A':
            cf.v4_min_score_a = threshold
        else:
            cf.v4_min_score_b = threshold

        # 백테스트 실행 (reset = DB 초기화 후 처음부터)
        from library.simulator_func_mysql import simulator_func_mysql
        simulator_func_mysql(simul_num, 'reset', 0)

        # 결과 읽기
        m = read_metrics(engine, initial_capital)
        if m:
            m['threshold'] = threshold
            results.append(m)
            print(f"  → 거래:{m['total_trades']}  승률:{m['win_rate']:.1f}%  "
                  f"R:{m['r_ratio']:.2f}  총수익:{m['total_ret']:.1f}%  Sharpe:{m['sharpe']:.2f}")

    # ── 비교 테이블 출력 ──────────────────────────────────────────
    print(f"\n\n{'='*80}")
    print(f"  Strategy {strategy}  최소 스코어 임계값 민감도 분석 결과")
    print(f"{'='*80}")
    hdr = f"{'임계값':>5} | {'거래수':>5} | {'승률':>5} | {'평균익절':>6} | {'평균손절':>6} | {'손익비R':>5} | {'평균보유':>5} | {'총수익률':>7} | {'Sharpe':>6}"
    print(hdr)
    print("-" * 80)
    for r in results:
        print(
            f"{r['threshold']:>5} | "
            f"{r['total_trades']:>5} | "
            f"{r['win_rate']:>4.1f}% | "
            f"{r['avg_profit']:>5.2f}% | "
            f"{r['avg_loss']:>5.2f}% | "
            f"{r['r_ratio']:>5.2f} | "
            f"{r['avg_hold']:>4.1f}일 | "
            f"{r['total_ret']:>6.1f}% | "
            f"{r['sharpe']:>6.2f}"
        )
    print(f"{'='*80}\n")

    return results


def main():
    target = sys.argv[1].upper() if len(sys.argv) > 1 else 'A'

    if target not in ('A', 'B', 'AB'):
        print(__doc__)
        sys.exit(1)

    # --from N : N 이상인 임계값부터 실행 (이어서 실행 시 사용)
    from_threshold = None
    if '--from' in sys.argv:
        idx = sys.argv.index('--from')
        if idx + 1 < len(sys.argv):
            from_threshold = int(sys.argv[idx + 1])

    start = datetime.datetime.now()
    print(f"\n{'='*65}")
    print(f"  score_sweep.py -- Strategy {target}  시작: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    if from_threshold:
        print(f"  (--from {from_threshold} 이상 임계값만 실행)")
    print(f"{'='*65}")

    if target == 'AB':
        run_sweep('A', from_threshold)
        run_sweep('B')   # B는 항상 전체
    else:
        run_sweep(target, from_threshold)

    elapsed = datetime.datetime.now() - start
    print(f"총 소요 시간: {elapsed}")


if __name__ == '__main__':
    main()
