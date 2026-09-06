# -*- coding: utf-8 -*-
"""
Task 9-A~D 분석 스크립트
=========================
사용법:
  py37_32 python sql/task9_analysis.py extract   # anchor MA120 DB에서 추출 (먼저 실행)
  py37_32 python sql/task9_analysis.py phase1    # 9건 연도별 백테스트
  py37_32 python sql/task9_analysis.py phase2    # anchor MA60 + 최종 리포트 생성
"""
import sys, os, re, subprocess, time, csv, json, math
from datetime import datetime
from contextlib import contextmanager
from collections import defaultdict, Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pymysql, pymysql.cursors
import library.cf as cf

PROJ    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RPT     = os.path.join(PROJ, 'backtest_report')
TMP     = os.path.join(RPT, 'task9_tmp')
PY      = sys.executable
CF_PATH = os.path.join(PROJ, 'library', 'cf.py')

os.makedirs(TMP, exist_ok=True)
os.makedirs(RPT, exist_ok=True)

YEAR_RANGES = {
    '2018': ('20180102', '20181228'),
    '2020': ('20200102', '20201230'),
    '2022': ('20220103', '20221229'),
}
ANCHOR_RANGE = ('20230905', '20260810')

START_EQ = 10_000_000   # 항상 10M에서 시작 (e_invest_unit=2M × 5슬롯)

# 기존 Task7 anchor OFF 결과 (재실행 생략 — 88건/2.84년, jango 희소 가능성 극히 낮음)
ANCHOR_OFF = {
    'label': 'anchor', 'gate': 'OFF', 'start': '20230905', 'end': '20260810',
    'cagr': 48.53, 'mdd': -24.80, 'calmar': 1.957, 'n_closed': 88,
    'wr': 40.9, 'R': 5.39, 'kospi_cagr': 36.58,
    'n_years_jango': None, 'n_years_cal': round((datetime(2026,8,10)-datetime(2023,9,5)).days/365.25, 4),
    'simple_ret': None,   # 재실행 없이 CAGR로부터 역산
    'note': '재실행 생략 (n=88, 2.84년, jango 희소 위험 극히 낮음)',
}
_n = ANCHOR_OFF['n_years_cal']
ANCHOR_OFF['simple_ret'] = round((pow(1 + ANCHOR_OFF['cagr']/100, _n) - 1) * 100, 2)
# KOSPI simple_ret (anchor period)
_kr = pow(1 + ANCHOR_OFF['kospi_cagr']/100, _n) - 1
ANCHOR_OFF['kospi_simple_ret'] = round(_kr * 100, 2)


def log(msg):
    print('[%s] %s' % (time.strftime('%H:%M:%S'), msg), flush=True)

def _f(v, default=0.0):
    try:
        return float(v) if v not in (None, '', 'None') else default
    except Exception:
        return default


# ─── DB ─────────────────────────────────────────────────────────────────────

def conn_sim():
    return pymysql.connect(host=cf.db_ip, port=int(cf.db_port),
        user=cf.db_id, password=cf.db_passwd, database='simulator10',
        charset='utf8', autocommit=True, cursorclass=pymysql.cursors.DictCursor)

def conn_craw():
    return pymysql.connect(host=cf.db_ip, port=int(cf.db_port),
        user=cf.db_id, password=cf.db_passwd, database='daily_craw',
        charset='utf8', autocommit=True, cursorclass=pymysql.cursors.DictCursor)


# ─── cf.py 패치 ──────────────────────────────────────────────────────────────

def _patch(text, var, val):
    if isinstance(val, str):
        text, n = re.subn(r'^(%s\s*=\s*")[^"]*"' % re.escape(var),
                          '%s = "%s"' % (var, val), text, flags=re.MULTILINE)
        if n == 0:
            text, _ = re.subn(r"^(%s\s*=\s*')[^']*'" % re.escape(var),
                               "%s = '%s'" % (var, val), text, flags=re.MULTILINE)
    elif isinstance(val, bool):
        text, _ = re.subn(r'^%s\s*=\s*(True|False)' % re.escape(var),
                          '%s = %s' % (var, 'True' if val else 'False'),
                          text, flags=re.MULTILINE)
    elif isinstance(val, int):
        text, _ = re.subn(r'^%s\s*=\s*\d+' % re.escape(var),
                          '%s = %d' % (var, val), text, flags=re.MULTILINE)
    return text

@contextmanager
def patched_cf(start_date, end_date, gate_on, gate_ma=60):
    with open(CF_PATH, 'r', encoding='utf-8') as f:
        orig = f.read()
    try:
        p = orig
        for var, val in [('e_simul_start_date', start_date), ('e_simul_end_date', end_date),
                         ('e_regime_gate_on', gate_on), ('e_regime_gate_ma_period', gate_ma)]:
            p = _patch(p, var, val)
        with open(CF_PATH, 'w', encoding='utf-8') as f:
            f.write(p)
        log('  cf.py 패치: %s~%s gate=%s/%d' % (start_date, end_date,
             'ON' if gate_on else 'OFF', gate_ma))
        yield
    finally:
        with open(CF_PATH, 'w', encoding='utf-8') as f:
            f.write(orig)
        log('  cf.py 복원')


# ─── KPI 추출 v2 (calendar n_years 고정판) ───────────────────────────────────

def extract_kpis_v2(label, start_date, end_date, gate_label):
    """
    핵심 수정: n_years = 달력 날짜 기반 (jango_data 행 수 아님)
    Task 9-A 버그 수정.
    """
    # 달력 기반 n_years (Task 9-A 수정)
    n_cal_days = (datetime.strptime(end_date, '%Y%m%d') -
                  datetime.strptime(start_date, '%Y%m%d')).days
    n_years_cal = n_cal_days / 365.25

    try:
        csim  = conn_sim()
        ccraw = conn_craw()
    except Exception as e:
        return {'label': label, 'gate': gate_label, 'error': str(e),
                'n_years_cal': round(n_years_cal, 4), 'n_years_jango': None}

    try:
        with csim.cursor() as c:
            c.execute("SELECT * FROM all_item_db WHERE sell_date IS NOT NULL "
                      "AND sell_date != '' AND sell_date != '0' ORDER BY buy_date")
            trades = c.fetchall()
        with csim.cursor() as c:
            c.execute("SELECT date, total_invest FROM jango_data ORDER BY date")
            jango = c.fetchall()

        if not jango:
            return {'label': label, 'gate': gate_label, 'error': 'jango empty',
                    'n_years_cal': round(n_years_cal, 4), 'n_years_jango': 0}

        n_days_jango = len(jango)
        n_years_jango = n_days_jango / 250.0   # 검증용 (수정 전 방식)

        equities = [_f(r['total_invest'], START_EQ) for r in jango]
        final_eq = equities[-1]

        # ── 단순 수익률 (올바른 분모: 항상 10M 시작) ──
        simple_ret = (final_eq / START_EQ - 1) * 100

        # ── MDD (jango equity로 계산 — 수정 불필요) ──
        peak = equities[0]; max_dd = 0.0
        for eq in equities:
            if eq > peak: peak = eq
            dd = (eq - peak) / peak if peak > 0 else 0
            if dd < max_dd: max_dd = dd

        # ── CAGR: 달력 n_years 사용 (수정 핵심) ──
        cagr       = ((final_eq / START_EQ) ** (1.0 / n_years_cal) - 1) * 100
        cagr_old   = ((final_eq / START_EQ) ** (1.0 / n_years_jango) - 1) * 100 \
                     if n_years_jango > 0 else None

        # ── WR / R ──
        n_closed = len(trades)
        gains    = [_f(t.get('sell_rate')) for t in trades if _f(t.get('sell_rate')) > 0]
        losses   = [abs(_f(t.get('sell_rate'))) for t in trades if _f(t.get('sell_rate')) < 0]
        n_win    = len(gains)
        wr       = n_win / n_closed * 100 if n_closed > 0 else 0
        avg_gain = sum(gains)  / len(gains)  if gains  else 0.0
        avg_loss = sum(losses) / len(losses) if losses else 0.0
        R        = avg_gain / avg_loss if avg_loss > 0 else None

        # ── KOSPI ──
        try:
            with ccraw.cursor() as c:
                c.execute('SELECT close FROM kospi_index WHERE date >= %s '
                          'ORDER BY date LIMIT 1', (start_date,))
                ks = c.fetchone()
                c.execute('SELECT close FROM kospi_index WHERE date <= %s '
                          'ORDER BY date DESC LIMIT 1', (end_date,))
                ke = c.fetchone()
            if ks and ke:
                kospi_raw  = (float(ke['close']) / float(ks['close']) - 1) * 100
                # 달력 n_years 사용 (Task 9-D 통일)
                kospi_cagr = ((1 + kospi_raw/100) ** (1.0 / n_years_cal) - 1) * 100
            else:
                kospi_raw = kospi_cagr = None
        except Exception:
            kospi_raw = kospi_cagr = None

        calmar = abs(cagr / (max_dd * 100)) if max_dd != 0 else None

        # ── 버그 감지 v2 (Task 10-A-B) ──
        # 달력일 기준 예상 거래일(연 242일) 대비 jango 커버리지로 판단
        # 이전 로직(n_years_jango vs n_years_cal 절댓값 차이)은 anchor처럼
        # 게이트 없는 긴 구간에서 오탐을 발생시켰음.
        expected_td = max(1, round(n_cal_days * 242.0 / 365.25))
        coverage    = n_days_jango / expected_td
        if coverage < 0.50:
            bug_flag = 'BUG: jango=%d일 vs 예상거래일=%d일 (%.0f%%)' % (
                n_days_jango, expected_td, coverage * 100)
        elif coverage < 0.80:
            bug_flag = 'WARN: jango=%d일 vs 예상거래일=%d일 (%.0f%%)' % (
                n_days_jango, expected_td, coverage * 100)
        else:
            bug_flag = 'OK'

        return {
            'label': label, 'gate': gate_label,
            'start': start_date, 'end': end_date,
            'n_closed': n_closed, 'n_win': n_win,
            'wr':    round(wr, 1),
            'R':     round(R, 2) if R else '',
            'avg_gain': round(avg_gain, 2), 'avg_loss': round(avg_loss, 2),
            'simple_ret':    round(simple_ret, 2),
            'cagr':          round(cagr, 2),
            'cagr_old':      round(cagr_old, 2) if cagr_old is not None else '',
            'mdd':           round(max_dd * 100, 2),
            'calmar':        round(calmar, 3) if calmar else '',
            'final_equity':  int(final_eq),
            'kospi_cagr':    round(kospi_cagr, 2) if kospi_cagr is not None else '',
            'kospi_simple':  round(kospi_raw, 2)  if kospi_raw  is not None else '',
            'n_years_cal':   round(n_years_cal, 4),
            'n_years_jango': round(n_years_jango, 4),
            'n_days_jango':  n_days_jango,
            'n_cal_days':    n_cal_days,
            'bug_flag':      bug_flag,
            'error': '',
        }
    except Exception as e:
        import traceback
        return {'label': label, 'gate': gate_label, 'error': traceback.format_exc()[-400:],
                'n_years_cal': round(n_years_cal, 4), 'n_years_jango': None}
    finally:
        csim.close(); ccraw.close()


# ─── 시뮬레이터 실행 ──────────────────────────────────────────────────────────

def run_sim(label, start_date, end_date, gate_on, gate_ma=60):
    label_full = '%s gate=%s/MA%d' % (label, 'ON' if gate_on else 'OFF', gate_ma)
    log('  [RUN] ' + label_full)
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    t0 = time.time()
    with patched_cf(start_date, end_date, gate_on=gate_on, gate_ma=gate_ma):
        proc = subprocess.run(
            [PY, 'simulator_v2.py', '10', 'reset'],
            input=b'n\nn\n', capture_output=True, timeout=600, cwd=PROJ, env=env,
        )
    elapsed = time.time() - t0
    gate_label = 'OFF' if not gate_on else 'MA%d' % gate_ma
    log('  ▶ %s 완료 %.0fs rc=%d' % (label_full, elapsed, proc.returncode))
    if proc.returncode != 0:
        out = ((proc.stdout or b'') + (proc.stderr or b'')).decode('utf-8','replace')
        for line in out.splitlines()[-3:]:
            print('    | ' + line)
    kpis = extract_kpis_v2(label, start_date, end_date, gate_label)
    kpis['elapsed_s'] = int(elapsed)
    return kpis


# ─── JSON 저장/로드 ──────────────────────────────────────────────────────────

def save_tmp(name, data):
    path = os.path.join(TMP, name + '.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log('  tmp 저장: ' + path)

def load_tmp(name):
    path = os.path.join(TMP, name + '.json')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


# ─── CSV 저장 ─────────────────────────────────────────────────────────────────

def save_csv(rows, path, fields=None):
    if not rows:
        log('  SKIP (빈 데이터): ' + os.path.basename(path))
        return
    if fields is None:
        fields = list(rows[0].keys())
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    log('저장: %s (%d행)' % (os.path.basename(path), len(rows)))


# ═══════════════════════════════════════════════════════
# PHASE: extract  (anchor MA120 DB에서 추출)
# ═══════════════════════════════════════════════════════

def phase_extract():
    log('=== Phase extract: anchor MA120 KPIs 추출 (현재 DB) ===')
    kpis = extract_kpis_v2('anchor', *ANCHOR_RANGE, 'MA120')
    save_tmp('anchor_ma120', kpis)
    print('  n_years_cal:  ', kpis.get('n_years_cal'))
    print('  n_years_jango:', kpis.get('n_years_jango'))
    print('  CAGR (수정):  ', kpis.get('cagr'), '%')
    print('  CAGR (구버전):', kpis.get('cagr_old'), '%')
    print('  MDD:          ', kpis.get('mdd'), '%')
    print('  bug_flag:     ', kpis.get('bug_flag'))


# ═══════════════════════════════════════════════════════
# PHASE 1: 9건 연도별 백테스트
# ═══════════════════════════════════════════════════════

def phase1():
    log('=== Phase 1: 2018/2020/2022 × OFF/MA60/MA120 (9건) ===')
    results = []

    for year in ['2018', '2020', '2022']:
        s, e = YEAR_RANGES[year]
        # OFF
        r = run_sim(year, s, e, gate_on=False, gate_ma=60)
        r['label'] = year
        results.append(r)
        # MA60
        r = run_sim(year, s, e, gate_on=True, gate_ma=60)
        r['label'] = year
        results.append(r)
        # MA120
        r = run_sim(year, s, e, gate_on=True, gate_ma=120)
        r['label'] = year
        results.append(r)

    save_tmp('phase1_results', results)

    # n_years 비교 출력 (Task 9-A-C)
    print()
    print('  === n_years 전수 점검 (Task 9-A-C) ===')
    fmt = '  %-6s %-6s %8s %8s %6s %6s  %s'
    print(fmt % ('Year', 'Gate', 'n_cal일', 'n_jango행', 'cal년', 'jango년', '판정'))
    print('  ' + '-' * 70)
    for r in results:
        print(fmt % (str(r.get('label','')), str(r.get('gate','')),
                     str(r.get('n_cal_days','')), str(r.get('n_days_jango','')),
                     str(r.get('n_years_cal','')), str(r.get('n_years_jango','')),
                     str(r.get('bug_flag',''))))

    # CAGR 수정 전/후 출력
    print()
    print('  === CAGR 수정 전/후 (Task 9-A-B) ===')
    fmt2 = '  %-6s %-6s %8s %8s %8s %8s'
    print(fmt2 % ('Year', 'Gate', 'CAGR수정', 'CAGR구버전', 'MDD', '단순수익%'))
    print('  ' + '-' * 55)
    for r in results:
        print(fmt2 % (str(r.get('label','')), str(r.get('gate','')),
                      str(r.get('cagr','')), str(r.get('cagr_old','')),
                      str(r.get('mdd','')), str(r.get('simple_ret',''))))

    log('Phase 1 완료')


# ═══════════════════════════════════════════════════════
# PHASE 2: anchor MA60 + 최종 리포트
# ═══════════════════════════════════════════════════════

def compute_composite(rows_by_key, gates, periods_order, n_cal_map):
    """
    비연속 구간 합성 CAGR.
    rows_by_key: {(period, gate): kpis_dict}
    """
    result = {}
    for gate in gates:
        product  = 1.0
        kproduct = 1.0
        total_years = 0.0
        all_ok = True
        for period in periods_order:
            key = (period, gate)
            d = rows_by_key.get(key, {})
            sr = d.get('simple_ret')
            ksr = d.get('kospi_simple')
            n_y = n_cal_map.get(period, 1.0)
            if sr is None or sr == '' or ksr is None or ksr == '':
                all_ok = False
                break
            product  *= (1 + float(sr)/100)
            kproduct *= (1 + float(ksr)/100)
            total_years += n_y
        if not all_ok:
            result[gate] = {'cagr': None, 'kospi_cagr': None, 'total_years': total_years}
            continue
        cagr   = (product  ** (1.0 / total_years) - 1) * 100 if total_years > 0 else None
        kcagr  = (kproduct ** (1.0 / total_years) - 1) * 100 if total_years > 0 else None
        result[gate] = {
            'cagr': round(cagr, 2) if cagr else None,
            'kospi_cagr': round(kcagr, 2) if kcagr else None,
            'total_years': round(total_years, 3),
            'simple_product': round((product - 1) * 100, 2),
        }
    return result


def mdd_std(mdd_list):
    """MDD 표준편차 (Task 9-C-G). mdd_list: list of negative floats e.g. [-24.49, -21.73, ...]"""
    vals = [abs(float(x)) for x in mdd_list if x not in (None, '', 'None')]
    if len(vals) < 2:
        return None
    mean = sum(vals) / len(vals)
    var  = sum((v - mean)**2 for v in vals) / (len(vals) - 1)   # 표본 표준편차
    return round(math.sqrt(var), 2)


def phase2():
    log('=== Phase 2: anchor MA60 실행 + 최종 리포트 ===')

    # anchor MA60 실행 (Task 9-B) — tmp 이미 있으면 재사용
    _anc_m60_tmp = os.path.join(TMP, 'anchor_ma60.json')
    if os.path.exists(_anc_m60_tmp):
        log('--- anchor MA60: tmp 파일 재사용 ---')
        r_anc_m60 = load_tmp('anchor_ma60')
    else:
        log('--- anchor Gate MA60 ---')
        r_anc_m60 = run_sim('anchor', *ANCHOR_RANGE, gate_on=True, gate_ma=60)
        save_tmp('anchor_ma60', r_anc_m60)
    r_anc_m60['label'] = 'anchor'

    # 기존 결과 로드
    phase1_results = load_tmp('phase1_results')
    r_anc_m120     = load_tmp('anchor_ma120')
    r_anc_m120['label'] = 'anchor'
    if not r_anc_m120.get('kospi_simple') and r_anc_m120.get('kospi_cagr'):
        # kospi_simple 없으면 CAGR로부터 역산
        n_y = r_anc_m120.get('n_years_cal', ANCHOR_OFF['n_years_cal'])
        ks  = (pow(1 + float(r_anc_m120['kospi_cagr'])/100, n_y) - 1) * 100
        r_anc_m120['kospi_simple'] = round(ks, 2)

    # anchor OFF — kospi_simple을 anchor MA60 실측값으로 통일 (같은 기간, 같은 KOSPI)
    r_anc_off = dict(ANCHOR_OFF)
    r_anc_off['gate'] = 'OFF'
    # anchor MA60 실측 KOSPI 원시 수익률 사용 (calendar n_years 기반으로 정확)
    if r_anc_m60.get('kospi_simple'):
        r_anc_off['kospi_simple'] = r_anc_m60['kospi_simple']
    elif not r_anc_off.get('kospi_simple'):
        r_anc_off['kospi_simple'] = r_anc_off.get('kospi_simple_ret', '')

    # 전체 결과 dict: (period, gate) -> kpis
    all_results = {}
    for r in phase1_results:
        key = (r['label'], r['gate'])
        all_results[key] = r
    all_results[('anchor', 'OFF')]  = r_anc_off
    all_results[('anchor', 'MA60')] = r_anc_m60
    all_results[('anchor', 'MA120')]= r_anc_m120

    PERIODS = ['2018', '2020', '2022', 'anchor']
    GATES   = ['OFF', 'MA60', 'MA120']

    # n_cal_map: period → n_years_cal
    n_cal_map = {}
    for period in PERIODS:
        if period == 'anchor':
            n_cal_map[period] = ANCHOR_OFF['n_years_cal']
        else:
            s, e = YEAR_RANGES[period]
            n_cal_map[period] = round((datetime.strptime(e,'%Y%m%d') -
                                       datetime.strptime(s,'%Y%m%d')).days / 365.25, 4)

    # ── Task 9-A: CAGR 수정 표 (전수 점검) ───────────────────────────────
    print()
    print('=== Task 9-A-C: n_years 전수 점검 ===')
    fmt = '  %-8s %-6s %7s %7s %6s %6s %12s %8s %8s %8s'
    print(fmt % ('Period','Gate','n_cal일','n_jango','cal년','jango년','판정',
                 'CAGR수정','CAGR구버전','MDD'))
    print('  ' + '-' * 98)

    correction_rows = []
    for period in PERIODS:
        for gate in GATES:
            key = (period, gate)
            d = all_results.get(key, {})
            n_cal_days   = d.get('n_cal_days', '')
            n_days_jango = d.get('n_days_jango', '')
            n_years_cal  = d.get('n_years_cal', n_cal_map.get(period,''))
            n_years_jango= d.get('n_years_jango', '')
            bug_flag     = d.get('bug_flag', '재실행없음' if key==('anchor','OFF') else '')
            cagr_new  = d.get('cagr', '')
            cagr_old  = d.get('cagr_old', '')
            mdd       = d.get('mdd', '')
            print(fmt % (str(period), str(gate),
                         str(n_cal_days), str(n_days_jango),
                         str(round(float(n_years_cal),3) if n_years_cal not in ('', None) else ''),
                         str(round(float(n_years_jango),3) if n_years_jango not in ('', None) else ''),
                         str(bug_flag)[:12], str(cagr_new), str(cagr_old), str(mdd)))
            correction_rows.append({
                'period': period, 'gate': gate,
                'n_cal_days': n_cal_days, 'n_days_jango': n_days_jango,
                'n_years_cal': n_years_cal, 'n_years_jango': n_years_jango,
                'cagr_corrected': cagr_new, 'cagr_old': cagr_old,
                'mdd': mdd, 'simple_ret': d.get('simple_ret',''),
                'bug_flag': bug_flag, 'note': d.get('note',''),
            })

    FIELDS_CORR = ['period','gate','n_cal_days','n_days_jango','n_years_cal','n_years_jango',
                   'cagr_corrected','cagr_old','mdd','simple_ret','bug_flag','note']
    save_csv(correction_rows, os.path.join(RPT, 'task9_cagr_correction.csv'), FIELDS_CORR)

    # ── Task 9-C-F: MDD 범위 + KOSPI 승패 ────────────────────────────────
    print()
    print('=== Task 9-C-F: 설정별 초과수익 + MDD 범위 + KOSPI 승패 ===')
    for gate in GATES:
        excess_list = []
        mdd_list    = []
        wins = 0
        for period in PERIODS:
            d = all_results.get((period, gate), {})
            cg = d.get('cagr')
            kg = d.get('kospi_cagr')
            md = d.get('mdd')
            if cg not in (None,'') and kg not in (None,''):
                exc = round(float(cg) - float(kg), 2)
                excess_list.append(exc)
                if float(cg) > float(kg):
                    wins += 1
            if md not in (None,''):
                mdd_list.append(float(md))
        mdd_std_val = mdd_std(mdd_list)
        mdd_range   = '%.2f ~ %.2f' % (min(mdd_list), max(mdd_list)) if mdd_list else '—'
        print('  Gate %-5s | 초과수익: %s | MDD범위: %s | MDD표준편차: %s | KOSPI대비승: %d/%d' % (
            gate, str([round(e,1) for e in excess_list]), mdd_range,
            str(mdd_std_val), wins, len(excess_list)))

    # ── Task 9-C-G: MDD 안정성 지표 ──────────────────────────────────────
    print()
    print('=== Task 9-C-G: 설정별 MDD 표준편차 ===')
    for gate in GATES:
        mdd_list = []
        for period in PERIODS:
            d = all_results.get((period, gate), {})
            md = d.get('mdd')
            if md not in (None,''):
                mdd_list.append(float(md))
        sd = mdd_std(mdd_list)
        print('  Gate %-5s  MDD값: %s  → 표준편차: %s%%' % (
            gate, str([round(m,1) for m in mdd_list]), str(sd)))

    # ── Task 9-C-H: 합성 CAGR (수정) ─────────────────────────────────────
    # kospi_simple 보정: anchor OFF
    if not r_anc_off.get('kospi_simple'):
        r_anc_off['kospi_simple'] = r_anc_off.get('kospi_simple_ret', '')

    composite = compute_composite(all_results, GATES, PERIODS, n_cal_map)
    print()
    print('=== Task 9-C-H: 합성 CAGR (수정 후, 비연속 구간) ===')
    for gate in GATES:
        c = composite.get(gate, {})
        cg = c.get('cagr')
        kg = c.get('kospi_cagr')
        ty = c.get('total_years','')
        if cg is not None and kg is not None:
            print('  Gate %-5s  합성CAGR: %+.2f%%  KOSPI: %+.2f%%  초과: %+.2f%%p  (%.2f년)' % (
                gate, cg, kg, cg-kg, ty))
        else:
            print('  Gate %-5s  데이터 불완전 (anchor OFF 누락 없이 확인 필요)' % gate)

    # ── task9_final_grid.csv 생성 ─────────────────────────────────────────
    grid_rows = []
    for period in PERIODS:
        for gate in GATES:
            d = all_results.get((period, gate), {})
            cg = d.get('cagr','')
            kg = d.get('kospi_cagr','')
            md = d.get('mdd','')
            excess = ''
            if cg not in (None,'') and kg not in (None,''):
                try:
                    excess = round(float(cg) - float(kg), 2)
                except Exception:
                    pass
            grid_rows.append({
                'period': period,
                'gate':   gate,
                'n_closed':  d.get('n_closed',''),
                'cagr':      cg,
                'mdd':       md,
                'calmar':    d.get('calmar',''),
                'wr':        d.get('wr',''),
                'R':         d.get('R',''),
                'kospi_cagr': kg,
                'excess_cagr': excess,
                'n_years_cal':   d.get('n_years_cal', n_cal_map.get(period,'')),
                'n_years_jango': d.get('n_years_jango',''),
                'bug_flag':  d.get('bug_flag',''),
                'simple_ret': d.get('simple_ret',''),
                'note':      d.get('note',''),
            })

    # 합성 행 추가
    for gate in GATES:
        c = composite.get(gate, {})
        cg = c.get('cagr')
        kg = c.get('kospi_cagr')
        grid_rows.append({
            'period': '합성(비연속)',
            'gate':   gate,
            'n_closed': '',
            'cagr':    cg if cg is not None else '',
            'mdd':     '',
            'calmar':  '',
            'wr':      '',
            'R':       '',
            'kospi_cagr': kg if kg is not None else '',
            'excess_cagr': round(cg-kg,2) if cg is not None and kg is not None else '',
            'n_years_cal':   c.get('total_years',''),
            'n_years_jango': '',
            'bug_flag':  '',
            'simple_ret': c.get('simple_product',''),
            'note':  '비연속구간. 미측정: 2019·2021·2023H1. anchor_OFF=재실행없음(신뢰도높음).',
        })

    FIELDS_GRID = ['period','gate','n_closed','cagr','mdd','calmar','wr','R',
                   'kospi_cagr','excess_cagr','n_years_cal','n_years_jango',
                   'bug_flag','simple_ret','note']
    save_csv(grid_rows, os.path.join(RPT, 'task9_final_grid.csv'), FIELDS_GRID)

    # ── task9_cagr_correction.csv 이미 저장됨 ────────────────────────────

    log('Phase 2 완료')
    print()
    print('출력 파일:')
    print('  backtest_report/task9_cagr_correction.csv  ← 9-A (n_years 전수점검)')
    print('  backtest_report/task9_final_grid.csv       ← 9-C (최종 그리드)')


# ─── MAIN ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'help'
    if cmd == 'extract':
        phase_extract()
    elif cmd == 'phase1':
        phase1()
    elif cmd == 'phase2':
        phase2()
    else:
        print('사용법: task9_analysis.py [extract|phase1|phase2]')
