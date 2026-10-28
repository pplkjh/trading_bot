# -*- coding: utf-8 -*-
"""
일별 ETL 지표 검증기 — Task F (재발 방지)
==========================================
새 날짜 테이블 생성 후 자동 실행. D-1~D-7 게이트 중 하나라도 위반 시 로그 기록.
실행: python sql/daily_etl_validator.py --date 20260811
실행: python sql/daily_etl_validator.py              (오늘 날짜 자동 감지)

변경 이력:
  2026-08-11  D-6 임계값 8-15% → 15-40% (Step 2-A: 오염된 Phase 0-A 임계값 교정)
  2026-08-11  D-7 check_frozen_values() 호출 연결 + 10거래일 창 / volume>0 필터 /
              len>=8 기준 강화 / 예외 ERROR 분기 (Step 2-B: 게이트 버그 수정)
  2026-08-11  P-2: D-2~D-6 상대 기준으로 재설계.
              |당일값 / 직전60일 평균 - 1| < 0.30 (±30% 이탈 감지)
              + 넓은 절대 안전망 병행.
              게이트 목적: 데이터 손상 탐지 (시장 국면 탐지 아님).
"""
import sys, os, csv, argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pymysql.cursors
import pymysql
import library.cf as cf

OUT_DIR  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'backtest_report')
LOG_FILE = os.path.join(OUT_DIR, 'etl_validation_log.csv')

# D-1 절대 기준 (변경 없음)
# D-2~D-6: 상대 기준 (±30%) + 절대 안전망. 아래는 안전망 범위.
# [P-2] 설계 원칙: 데이터 손상이면 평균과 크게 벗어남. 시장 국면 변화(±30% 이내)는 PASS.
ABS_SAFETY = {
    'adx':     (5,   80),    # 정상 ADX 범위: 거의 0~100 이지만 5~80 이면 충분
    'rsi14':   (5,   95),    # RSI 극단(5 미만/95 초과)은 데이터 오류
    'mfi14':   (5,   95),    # MFI 동일
    'atr_pct': (0.5, 20.0),  # ATR/close(%) 0.5% 미만 or 20% 초과 = 이상
    'bb_bw':   (3.0, 75.0),  # bb_bandwidth(%) 3 미만 or 75 초과 = 이상
}
REL_TOL = 0.30   # ±30% 상대 허용 범위


def make_conn(db):
    return pymysql.connect(
        host=cf.db_ip, port=int(cf.db_port),
        user=cf.db_id, password=cf.db_passwd,
        database=db, charset='utf8', autocommit=True,
        cursorclass=pymysql.cursors.DictCursor
    )


def check_frozen_values(conn, date_str):
    """
    최근 10 거래일 대비 atr14 고정값 종목 탐지.

    [Step 2-B 수정 내역]
    - 조회 창: 6일 → 10거래일 이상 (LIMIT 11 = 현재+이전 10)
    - volume > 0 필터: 거래정지·무거래 종목 제외 (자연스러운 ATR 반복을 오탐 방지)
    - 판정 기준: len >= 3 → len >= 8 (10일 창에서 8일 이상 관측 + 전부 동일값)
    - 예외 시 -1 반환 (호출부에서 ERROR 상태로 분기)

    회귀 테스트: 삼성전자 atr14=2978.57 고정값(재계산 이전 상태 백업 대상)이
    10거래일 창에서 8일 이상 동일값으로 탐지되어야 함.
    """
    try:
        with conn.cursor() as c:
            c.execute(
                "SELECT table_name AS dt FROM information_schema.tables "
                "WHERE table_schema='daily_buy_list' "
                "AND table_name REGEXP '^[0-9]{8}$' "
                f"AND table_name <= '{date_str}' "
                "ORDER BY table_name DESC LIMIT 11"   # 현재 포함 최대 11개 → 10거래일 이전까지
            )
            past_dates = [r['dt'] for r in c.fetchall()]

        if len(past_dates) < 2:
            return 0  # 날짜 부족 → 탐지 불가, PASS

        # 각 날짜에서 atr14 수집 (volume > 0 거래일만)
        atr_history = {}  # {code: [atr14, ...]}
        for dt in past_dates:
            try:
                with conn.cursor() as c:
                    c.execute(
                        f"SELECT code, atr14 FROM `{dt}` "
                        f"WHERE atr14 IS NOT NULL AND volume > 0"
                    )
                    for r in c.fetchall():
                        code = r['code']
                        atr_history.setdefault(code, []).append(round(float(r['atr14']), 2))
            except Exception:
                pass

        # 10일 창에서 8일 이상 관측 + 전부 동일값 → frozen
        return sum(
            1 for v in atr_history.values()
            if len(v) >= 8 and len(set(v)) == 1
        )
    except Exception:
        return -1   # ERROR 상태 (호출부에서 ERROR 분기)


def get_60d_baseline(conn, date_str):
    """
    [P-2] 직전 60 거래일의 지표 평균을 반환.

    각 날짜 테이블에서 per-column 평균을 구한 뒤, 60일 평균의 평균을 계산.
    60일 미만 데이터 (초기 운영)인 경우 None 반환 → 절대 안전망 fallback 적용.

    Returns: dict {metric: 60d_avg} 또는 None (데이터 부족)
    """
    try:
        with conn.cursor() as c:
            c.execute(
                "SELECT table_name AS dt FROM information_schema.tables "
                "WHERE table_schema='daily_buy_list' "
                "AND table_name REGEXP '^[0-9]{8}$' "
                f"AND table_name < '{date_str}' "   # 당일 제외
                "ORDER BY table_name DESC LIMIT 60"
            )
            past_dates = [r['dt'] for r in c.fetchall()]
    except Exception:
        return None

    if len(past_dates) < 10:   # 10일 미만이면 기준선 불안정
        return None

    daily = {'adx': [], 'rsi14': [], 'mfi14': [], 'atr_pct': [], 'bb_bw': []}
    for dt in past_dates:
        try:
            with conn.cursor() as c:
                c.execute(
                    f"SELECT AVG(adx) AS a_adx, AVG(rsi14) AS a_rsi, "
                    f"AVG(mfi14) AS a_mfi, "
                    f"AVG(atr14 / NULLIF(close, 0)) * 100 AS a_atr, "
                    f"AVG(bb_bandwidth) * 100 AS a_bb "
                    f"FROM `{dt}` WHERE close > 0"
                )
                r = c.fetchone()
            if r:
                if r['a_adx'] is not None: daily['adx'].append(float(r['a_adx']))
                if r['a_rsi'] is not None: daily['rsi14'].append(float(r['a_rsi']))
                if r['a_mfi'] is not None: daily['mfi14'].append(float(r['a_mfi']))
                if r['a_atr'] is not None: daily['atr_pct'].append(float(r['a_atr']))
                if r['a_bb']  is not None: daily['bb_bw'].append(float(r['a_bb']))
        except Exception:
            pass

    def davg(lst):
        return sum(lst) / len(lst) if lst else None

    return {k: davg(v) for k, v in daily.items()}


def gate_relative(today_val, baseline_val, metric_key, rel_tol=REL_TOL):
    """
    [P-2] 상대 기준 + 절대 안전망 동시 검사.

    상대 기준:   |today / baseline - 1| < rel_tol
    절대 안전망: abs_lo <= today <= abs_hi
    둘 다 통과해야 PASS.

    today_val 또는 baseline_val이 None이면 None 반환 (체크 불가).
    """
    if today_val is None:
        return None
    abs_lo, abs_hi = ABS_SAFETY.get(metric_key, (None, None))

    # 절대 안전망 (항상 검사)
    if abs_lo is not None and today_val < abs_lo:
        return False
    if abs_hi is not None and today_val > abs_hi:
        return False

    # 상대 기준 (baseline 있을 때만)
    if baseline_val is None or baseline_val == 0:
        return True   # baseline 없으면 절대 안전망만으로 PASS
    return abs(today_val / baseline_val - 1) < rel_tol


def validate_date_table(date_str: str) -> dict:
    """단일 날짜 테이블 D 게이트 검증. Returns dict with gate results."""
    conn = make_conn('daily_buy_list')
    results = {'date': date_str, 'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

    try:
        with conn.cursor() as c:
            c.execute(
                f"SELECT code, adx, rsi14, mfi14, atr14, close, bb_bandwidth "
                f"FROM `{date_str}` WHERE close > 0"
            )
            rows = c.fetchall()

        if not rows:
            results['error'] = f'테이블 없음 또는 행 없음: {date_str}'
            return results

        n_rows = len(rows)
        n_null = 0
        adx_vals = []; rsi_vals = []; mfi_vals = []; atr_pct = []; bw_vals = []

        for r in rows:
            if r.get('atr14') is None or r.get('rsi14') is None or r.get('adx') is None:
                n_null += 1
            if r.get('adx')   is not None: adx_vals.append(float(r['adx']))
            if r.get('rsi14') is not None: rsi_vals.append(float(r['rsi14']))
            if r.get('mfi14') is not None: mfi_vals.append(float(r['mfi14']))
            if r.get('atr14') and r.get('close'):
                atr_pct.append(float(r['atr14']) / float(r['close']) * 100)
            if r.get('bb_bandwidth') is not None:
                bw_vals.append(float(r['bb_bandwidth']) * 100)

        # [Step 2-B] check_frozen_values() 실제 호출
        frozen = check_frozen_values(conn, date_str)

        # [P-2] 60일 기준선 조회
        baseline = get_60d_baseline(conn, date_str)

        def avg(l): return sum(l) / len(l) if l else None

        pct_null  = n_null / n_rows * 100
        avg_adx   = avg(adx_vals)
        avg_rsi   = avg(rsi_vals)
        avg_mfi   = avg(mfi_vals)
        avg_atrt  = avg(atr_pct)    # 이미 * 100
        avg_bw    = avg(bw_vals)    # 이미 * 100

        # ── D-1: NULL 비율 (<1%) ─────────────────────────────────────────
        d1 = pct_null < 1

        # ── D-2~D-6: 상대 기준 (±30%) + 절대 안전망 ─────────────────────
        # [P-2] baseline 있으면 상대 기준 우선, 없으면 절대 안전망 fallback
        b = baseline  # None 가능

        d2_val = gate_relative(avg_adx,  b['adx']     if b else None, 'adx')
        d3_val = gate_relative(avg_rsi,  b['rsi14']   if b else None, 'rsi14')
        d4_val = gate_relative(avg_mfi,  b['mfi14']   if b else None, 'mfi14')
        d5_val = gate_relative(avg_atrt, b['atr_pct'] if b else None, 'atr_pct')
        d6_val = gate_relative(avg_bw,   b['bb_bw']   if b else None, 'bb_bw')

        # None(측정값 없음) → FAIL (보수적)
        d2 = d2_val is not False and d2_val is not None
        d3 = d3_val is not False and d3_val is not None
        d4 = d4_val is not False and d4_val is not None
        d5 = d5_val is not False and d5_val is not None
        d6 = d6_val is not False and d6_val is not None

        # ── D-7: frozen_atr14 = 0 ────────────────────────────────────────
        # [Step 2-B] frozen==-1 은 ERROR(예외), 0은 PASS, >0은 FAIL
        if frozen == -1:
            d7_state = 'ERROR'
            d7 = False
        else:
            d7 = frozen == 0
            d7_state = 'PASS' if d7 else 'FAIL'

        # 60일 기준선 측정값 (로그용)
        b_adx  = round(b['adx'],     2) if b and b['adx']     else None
        b_rsi  = round(b['rsi14'],   2) if b and b['rsi14']   else None
        b_mfi  = round(b['mfi14'],   2) if b and b['mfi14']   else None
        b_atr  = round(b['atr_pct'], 2) if b and b['atr_pct'] else None
        b_bb   = round(b['bb_bw'],   2) if b and b['bb_bw']   else None

        results.update({
            'n_rows':    n_rows,
            'pct_null':  round(pct_null, 2),
            'avg_adx':   round(avg_adx,  2) if avg_adx  else None,
            'avg_rsi14': round(avg_rsi,  2) if avg_rsi  else None,
            'avg_mfi14': round(avg_mfi,  2) if avg_mfi  else None,
            'avg_atr_pct': round(avg_atrt, 2) if avg_atrt else None,
            'avg_bb_bw':   round(avg_bw,   2) if avg_bw   else None,
            'frozen_atr':  frozen,
            'b60_adx':   b_adx,   # 60일 기준선 (로그)
            'b60_rsi14': b_rsi,
            'b60_mfi14': b_mfi,
            'b60_atr_pct': b_atr,
            'b60_bb_bw':   b_bb,
            'D1': 'PASS' if d1 else 'FAIL',
            'D2': 'PASS' if d2 else 'FAIL',
            'D3': 'PASS' if d3 else 'FAIL',
            'D4': 'PASS' if d4 else 'FAIL',
            'D5': 'PASS' if d5 else 'FAIL',
            'D6': 'PASS' if d6 else 'FAIL',
            'D7': d7_state,
            'all_pass': all([d1, d2, d3, d4, d5, d6, d7]),
        })

    except Exception as e:
        results['error'] = str(e)
    finally:
        conn.close()

    return results


def append_log(results: dict):
    """검증 결과를 로그 CSV에 추가"""
    fieldnames = [
        'date', 'ts', 'n_rows', 'pct_null',
        'avg_adx', 'avg_rsi14', 'avg_mfi14', 'avg_atr_pct', 'avg_bb_bw',
        'frozen_atr',
        'b60_adx', 'b60_rsi14', 'b60_mfi14', 'b60_atr_pct', 'b60_bb_bw',
        'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'all_pass', 'error',
    ]
    write_header = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, 'a', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        if write_header:
            w.writeheader()
        w.writerow(results)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', default=None, help='검증할 날짜 (YYYYMMDD). 기본=오늘')
    args = parser.parse_args()

    if args.date:
        date_str = args.date
    else:
        date_str = datetime.now().strftime('%Y%m%d')

    print(f"ETL 검증: {date_str}")
    results = validate_date_table(date_str)
    append_log(results)

    if 'error' in results:
        print(f"  [ERROR] {results['error']}")
        return 1

    all_ok = results.get('all_pass', False)

    # 기준선 있으면 괴리율 표시
    b60_str = ''
    if results.get('b60_adx'):
        def pct_dev(today, b60):
            if today is None or b60 is None or b60 == 0: return '—'
            return f"{(today/b60-1)*100:+.1f}%"
        b60_str = (
            f"\n  60일기준: adx={results.get('b60_adx')} "
            f"rsi14={results.get('b60_rsi14')} mfi14={results.get('b60_mfi14')} "
            f"atr%={results.get('b60_atr_pct')} bb_bw%={results.get('b60_bb_bw')}"
            f"\n  괴리율:   adx={pct_dev(results.get('avg_adx'), results.get('b60_adx'))} "
            f"rsi14={pct_dev(results.get('avg_rsi14'), results.get('b60_rsi14'))} "
            f"mfi14={pct_dev(results.get('avg_mfi14'), results.get('b60_mfi14'))} "
            f"atr%={pct_dev(results.get('avg_atr_pct'), results.get('b60_atr_pct'))} "
            f"bb_bw%={pct_dev(results.get('avg_bb_bw'), results.get('b60_bb_bw'))}"
        )

    print(f"  n_rows={results.get('n_rows')} | "
          f"null={results.get('pct_null')}% | "
          f"adx={results.get('avg_adx')} | rsi14={results.get('avg_rsi14')} | "
          f"mfi14={results.get('avg_mfi14')} | atr%={results.get('avg_atr_pct')} | "
          f"bb_bw%={results.get('avg_bb_bw')} | frozen={results.get('frozen_atr')}"
          f"{b60_str}")
    print(f"  D1:{results.get('D1')} D2:{results.get('D2')} D3:{results.get('D3')} "
          f"D4:{results.get('D4')} D5:{results.get('D5')} D6:{results.get('D6')} "
          f"D7:{results.get('D7')}")
    print(f"  → {'ALL PASS ✅' if all_ok else 'FAIL ❌ — 수동 점검 필요'}")
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
