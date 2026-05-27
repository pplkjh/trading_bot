# -*- coding: utf-8 -*-
"""
Strategy A/B 최소 스코어 임계값 민감도 분석

Usage:
  python score_sweep.py A           # v4_min_score_a: 80, 90, 100, 110, 120
  python score_sweep.py B           # v4_min_score_b: 70, 80, 90, 100
  python score_sweep.py AB          # A -> B 순서대로
  python score_sweep.py A --from 110  # 110 이상 임계값부터 이어서 실행

각 임계값마다 전체 백테스트(reset)를 실행하고 핵심 지표를 비교한다.
실행 시간: 임계값 1개당 약 30~60분 (3년치 데이터)

결과 저장:
  backtest_report/sweep/sim{N}_score{T}_{YYYYMMDD_HHMM}.csv  — 개별 run
  backtest_report/sweep/sim{N}_summary_{YYYYMMDD_HHMM}.csv   — 전략 전체 요약
"""
import sys
import os
import csv
import pathlib
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

from sqlalchemy import create_engine, text
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
SWEEP_DIR = pathlib.Path(__file__).parent / 'backtest_report' / 'sweep'
# ─────────────────────────────────────────────────────────────────────────


SWEEP_FIELDS = ['strategy', 'threshold', 'total_trades', 'win_rate',
                'avg_profit', 'avg_loss', 'r_ratio', 'avg_hold', 'total_ret', 'sharpe', 'run_at']


def save_run_csv(strategy, threshold, metrics, run_ts):
    """개별 run 결과를 CSV로 저장 — 실패해도 백테스트에 영향 없음"""
    try:
        SWEEP_DIR.mkdir(parents=True, exist_ok=True)
        simul = SIMUL_NUM[strategy]
        fname = SWEEP_DIR / f"sim{simul}_score{threshold}_{run_ts}.csv"
        row = {
            'strategy':     strategy,
            'threshold':    threshold,
            'total_trades': metrics['total_trades'],
            'win_rate':     round(metrics['win_rate'],    2),
            'avg_profit':   round(metrics['avg_profit'],  4),
            'avg_loss':     round(metrics['avg_loss'],    4),
            'r_ratio':      round(metrics['r_ratio'],     4),
            'avg_hold':     round(metrics['avg_hold'],    2),
            'total_ret':    round(metrics['total_ret'],   4),
            'sharpe':       round(metrics['sharpe'],      4),
            'run_at':       run_ts,
        }
        with open(fname, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=SWEEP_FIELDS)
            writer.writeheader()
            writer.writerow(row)
        print(f"  💾 저장: {fname.name}")
    except Exception as e:
        print(f"  ⚠️ CSV 저장 실패 (무시): {e}")


def save_summary_csv(strategy, results, summary_ts):
    """전략 전체 sweep 요약을 CSV로 저장"""
    try:
        SWEEP_DIR.mkdir(parents=True, exist_ok=True)
        simul = SIMUL_NUM[strategy]
        fname = SWEEP_DIR / f"sim{simul}_summary_{summary_ts}.csv"
        with open(fname, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=SWEEP_FIELDS)
            writer.writeheader()
            for r in results:
                writer.writerow({
                    'strategy':     strategy,
                    'threshold':    r['threshold'],
                    'total_trades': r['total_trades'],
                    'win_rate':     round(r['win_rate'],    2),
                    'avg_profit':   round(r['avg_profit'],  4),
                    'avg_loss':     round(r['avg_loss'],    4),
                    'r_ratio':      round(r['r_ratio'],     4),
                    'avg_hold':     round(r['avg_hold'],    2),
                    'total_ret':    round(r['total_ret'],   4),
                    'sharpe':       round(r['sharpe'],      4),
                    'run_at':       summary_ts,
                })
        print(f"  💾 요약 저장: {fname.name}")
    except Exception as e:
        print(f"  ⚠️ 요약 CSV 저장 실패 (무시): {e}")


def get_engine(db_name):
    url = (f"mysql+pymysql://{cf.db_id}:{cf.db_passwd}"
           f"@{cf.db_ip}:{cf.db_port}/{db_name}?charset=utf8")
    return create_engine(url)


def read_metrics(engine, initial_capital):
    """백테스트 완료 후 DB에서 핵심 지표 읽기"""
    try:
        row = engine.execute(text("""
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
        """)).fetchone()

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
    summary_ts = datetime.datetime.now().strftime('%Y%m%d_%H%M')

    for threshold in thresholds:
        run_ts = datetime.datetime.now().strftime('%Y%m%d_%H%M')
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
            # 개별 run 즉시 저장 (프로세스 죽어도 완료된 결과 보존)
            save_run_csv(strategy, threshold, m, run_ts)

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

    # 전략 전체 요약 CSV 저장
    if results:
        save_summary_csv(strategy, results, summary_ts)

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
