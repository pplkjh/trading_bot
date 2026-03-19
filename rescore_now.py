"""
rescore_now.py — 오늘 실제 종가 기준 매수 후보 확인 (DB 변경 없음, 프린트만)

사용법:
    python rescore_now.py            # 오늘 종가 기준 자동 선택
    python rescore_now.py 20260318   # 특정 날짜 지정
"""
import sys
import numpy as np
import pandas as pd
import pymysql
pymysql.install_as_MySQLdb()

from library import cf
from library.hybrid_strategy_v2 import HybridStrategyV2
from library.technical_indicators import (
    calculate_rsi, calculate_atr, calculate_macd, calculate_adx,
    calculate_mfi, calculate_cmf, calculate_obv,
    calculate_bollinger_bands, calculate_bollinger_bandwidth,
    detect_candle_pattern,
)
from sqlalchemy import create_engine

_url        = f"mysql+mysqldb://{cf.db_id}:{cf.db_passwd}@{cf.db_ip}:{cf.db_port}"
engine_dbl  = create_engine(f"{_url}/daily_buy_list", encoding='utf-8')
engine_craw = create_engine(f"{_url}/daily_craw",     encoding='utf-8')

# ── 기준 날짜 ─────────────────────────────────────────────────
target_date = sys.argv[1] if len(sys.argv) > 1 else None
if target_date is None:
    import datetime
    now = datetime.datetime.now()
    if now.hour > 15 or (now.hour == 15 and now.minute >= 40):
        target_date = now.strftime("%Y%m%d")
    else:
        dt = now - datetime.timedelta(days=1)
        while dt.weekday() >= 5:
            dt -= datetime.timedelta(days=1)
        target_date = dt.strftime("%Y%m%d")

print(f"기준 날짜: {target_date}  (오늘 실제 종가 기준 재계산)")

# ── 후보 종목 목록 (stock_item_all 에서 수집 완료 종목) ────────
invest_unit = getattr(cf, 'invest_unit', 1_000_000)
stock_rows = engine_dbl.execute(
    "SELECT code, code_name FROM stock_item_all "
    "WHERE check_daily_crawler IN ('1','3') "
    "AND code NOT IN (SELECT code FROM stock_konex WHERE 1=1)"
).fetchall()
print(f"전체 후보 종목: {len(stock_rows)}개")


def compute_row_from_df(df):
    """df_120 의 마지막 행 기준으로 daily_buy_list 컬럼값을 재계산"""
    if len(df) < 20:
        return None
    t = df.iloc[-1]
    h = df['high'];  l = df['low'];  c = df['close'];  v = df['volume']

    # 기본 OHLCV
    row = {
        'open':   float(t['open']),
        'high':   float(t['high']),
        'low':    float(t['low']),
        'close':  float(t['close']),
        'volume': float(t['volume']),
    }

    # 이동평균 (scoring 에서 clo5/clo20 으로 사용)
    row['clo5']  = float(c.rolling(5).mean().iloc[-1])  if len(df) >= 5  else None
    row['clo20'] = float(c.rolling(20).mean().iloc[-1]) if len(df) >= 20 else None
    row['ma5']   = row['clo5']
    row['ma20']  = row['clo20']

    # 거래량 이평
    row['vol5']  = float(v.rolling(5).mean().iloc[-1])  if len(df) >= 5  else 0
    row['vol20'] = float(v.rolling(20).mean().iloc[-1]) if len(df) >= 20 else 0

    # d1_diff_rate
    if len(df) >= 2 and df['close'].iloc[-2] > 0:
        row['d1_diff_rate'] = (float(t['close']) - float(df['close'].iloc[-2])) \
                              / float(df['close'].iloc[-2]) * 100
    else:
        row['d1_diff_rate'] = 0.0

    # RSI
    row['rsi14'] = calculate_rsi(c, 14)

    # ATR
    row['atr14'] = calculate_atr(h, l, c, 14)

    # MACD
    try:
        macd_val, signal_val, hist_val = calculate_macd(c)
        row['macd']           = macd_val
        row['macd_signal']    = signal_val
        row['macd_histogram'] = hist_val
    except Exception:
        row['macd'] = row['macd_signal'] = row['macd_histogram'] = 0

    # ADX / DI
    try:
        adx_val, plus_di, minus_di = calculate_adx(h, l, c, 14)
        row['adx']      = adx_val
        row['plus_di']  = plus_di
        row['minus_di'] = minus_di
    except Exception:
        row['adx'] = row['plus_di'] = row['minus_di'] = 0

    # MFI
    row['mfi14'] = calculate_mfi(h, l, c, v, 14)

    # CMF
    row['cmf20'] = calculate_cmf(h, l, c, v, 20)

    # OBV
    row['obv'] = calculate_obv(c, v)

    # Bollinger Bands
    try:
        bb_u, bb_m, bb_l = calculate_bollinger_bands(c, 20)
        row['bb_upper']     = bb_u
        row['bb_middle']    = bb_m
        row['bb_lower']     = bb_l
        row['bb_bandwidth'] = calculate_bollinger_bandwidth(bb_u, bb_m, bb_l)
    except Exception:
        row['bb_upper'] = row['bb_middle'] = row['bb_lower'] = row['bb_bandwidth'] = 0

    # 캔들 패턴
    try:
        row['candle_pattern_score'] = detect_candle_pattern(
            float(t['open']), float(t['high']), float(t['low']), float(t['close']),
            float(df['close'].iloc[-2])
        )
    except Exception:
        row['candle_pattern_score'] = 0

    return row


# ── DART 재무 데이터 ──────────────────────────────────────────
fundamental_dict = {}
try:
    _year  = int(target_date[:4])
    _month = int(target_date[4:6])
    _bsns_year = str(_year - 2 if _month <= 3 else _year - 1)
    dart_rows = engine_dbl.execute(
        "SELECT code, account_nm, thstrm_amount FROM dart "
        f"WHERE bsns_year='{_bsns_year}' AND fs_nm='재무제표' "
        "AND account_nm IN ('매출액','수익(매출액)','영업이익','영업이익(손실)',"
        "'당기순이익','당기순이익(손실)','자본총계')"
    ).fetchall()
    for dr in dart_rows:
        _code, _acct = dr[0], dr[1]
        _amt = float(dr[2]) / 1e8 if dr[2] else 0.0
        fd = fundamental_dict.setdefault(_code, {})
        if '매출액' in _acct or '수익' in _acct:
            fd['sales'] = _amt
        elif '영업이익' in _acct:
            fd['operating_profit'] = _amt
        elif '당기순이익' in _acct:
            fd['net_profit'] = _amt
        elif _acct == '자본총계':
            fd['total_equity'] = _amt
    for fd in fundamental_dict.values():
        eq  = fd.get('total_equity', 0)
        np_ = fd.get('net_profit', 0)
        fd['roe'] = (np_ / eq * 100) if eq else 0.0
except Exception as e:
    print(f"DART 로드 실패 (계속 진행): {e}")

# ── 코스피 지수 ───────────────────────────────────────────────
market_data = None
try:
    ki_df = pd.read_sql(
        f"SELECT close FROM kospi_index WHERE date <= '{target_date}' "
        "ORDER BY date DESC LIMIT 20", engine_craw
    )
    if len(ki_df) >= 20:
        market_data = ki_df['close'].iloc[::-1].reset_index(drop=True)
except Exception:
    pass

# ── 스코어링 ──────────────────────────────────────────────────
strategy_v2 = HybridStrategyV2()
scored_list = []
skipped = 0

for code, code_name in stock_rows:
    try:
        df_120 = pd.read_sql(
            f"SELECT date,open,high,low,close,volume FROM `{code_name}` "
            f"WHERE code='{code}' AND date <= '{target_date}' "
            "ORDER BY date DESC LIMIT 120",
            engine_craw
        )
        if len(df_120) < 20:
            skipped += 1
            continue
        df_120 = df_120.sort_values('date').reset_index(drop=True)

        # 오늘 데이터 없으면 스킵
        if str(df_120['date'].iloc[-1]) != target_date:
            skipped += 1
            continue

        # 가격 범위 필터 (저가주/고가주 제외)
        close_now = float(df_120['close'].iloc[-1])
        if close_now <= 0 or close_now >= invest_unit:
            skipped += 1
            continue

        row_dict = compute_row_from_df(df_120)
        if row_dict is None:
            skipped += 1
            continue
        row_dict['code']      = code
        row_dict['code_name'] = code_name

        total_score = strategy_v2.calculate_total_score(row_dict, df_120, None, market_data)

        fd = fundamental_dict.get(code)
        if fd and total_score >= 0:
            roe = fd.get('roe', 0) or 0
            if roe >= 15:
                total_score += 15
            elif roe >= 5:
                total_score += int((roe - 5) / 10 * 15)

        if total_score >= cf.v2_min_score:
            scored_list.append((code_name, code, close_now, total_score))

    except Exception:
        skipped += 1
        continue

scored_list.sort(key=lambda x: x[3], reverse=True)

# ── 결과 출력 (DB 저장 없음) ──────────────────────────────────
print(f"\n{'='*60}")
print(f"오늘 종가({target_date}) 기준 매수 후보  |  커트라인: {cf.v2_min_score}pt")
print(f"{'='*60}")
if scored_list:
    print(f"{'종목명':<20} {'코드':>8} {'종가':>10} {'점수':>8}")
    print('-' * 50)
    for name, code, close, score in scored_list:
        print(f"{name:<20} {code:>8} {close:>10,.0f}원  {score:>6.1f}pt")
    print(f"\n총 {len(scored_list)}개 종목 (검색: {len(stock_rows)}개, 스킵: {skipped}개)")
else:
    print("합격 종목 없음")
    print(f"(검색: {len(stock_rows)}개, 스킵: {skipped}개)")
