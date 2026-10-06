import sys
sys.path.insert(0, '.')
from library import cf
from library.hybrid_strategy_v2 import HybridStrategyV2
from library.technical_indicators import calculate_rsi
import pymysql
import pandas as pd

# 20260317 테이블에서 그래디언트 데이터
con = pymysql.connect(user=cf.db_id, passwd=cf.db_passwd, host=cf.db_ip,
                      port=int(cf.db_port), db='daily_buy_list', charset='utf8')
cur = con.cursor(pymysql.cursors.DictCursor)
cur.execute("SELECT * FROM `20260317` WHERE code_name LIKE '%그래디언트%' LIMIT 1")
row = dict(cur.fetchone())
con.close()

# daily_craw 에서 df_120 로드
con2 = pymysql.connect(user=cf.db_id, passwd=cf.db_passwd, host=cf.db_ip,
                       port=int(cf.db_port), db='daily_craw', charset='utf8')
cur2 = con2.cursor()
cur2.execute("SELECT date, open, high, low, close, volume FROM `그래디언트` ORDER BY date DESC LIMIT 120")
rows = cur2.fetchall()
con2.close()

df_120 = pd.DataFrame(rows, columns=['date','open','high','low','close','volume'])
df_120 = df_120.iloc[::-1].reset_index(drop=True)

# RSI 동적 꺽임 계산 — Wilder's EMA, df_120 전체 사용
close_all = df_120['close'].reset_index(drop=True)
delta = close_all.diff()
gain = delta.where(delta > 0, 0.0)
loss = -delta.where(delta < 0, 0.0)
avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
rs = avg_gain / avg_loss.replace(0, float('nan'))
rsi_full = (100 - (100 / (1 + rs))).fillna(50)

recent  = rsi_full.iloc[-16:].reset_index(drop=True)
rsi_now = float(recent.iloc[-1])
search  = recent.iloc[:-1]

peak_idx        = int(search.idxmax())
peak_rsi        = float(search.iloc[peak_idx])
days_since_peak = 15 - peak_idx
fall_from_peak  = rsi_now - peak_rsi

trough_idx        = int(search.idxmin())
trough_rsi        = float(search.iloc[trough_idx])
days_since_trough = 15 - trough_idx
rise_from_trough  = rsi_now - trough_rsi

fall_rate = fall_from_peak / days_since_peak if days_since_peak > 0 else 0
rise_rate = rise_from_trough / days_since_trough if days_since_trough > 0 else 0

print("=" * 65)
print(f"그래디언트 ({row['code']}) — 20260317 기준 점수 분해")
print("=" * 65)

close  = float(row.get('close') or 1)
vol5   = float(row.get('vol5') or 0)
vol20  = float(row.get('vol20') or 0)
adx    = float(row.get('adx') or 0)
pdi    = float(row.get('plus_di') or 0)
mdi    = float(row.get('minus_di') or 0)
macd   = float(row.get('macd') or 0)
macdS  = float(row.get('macd_signal') or 0)
macdH  = float(row.get('macd_histogram') or 0)
cmf    = float(row.get('cmf20') or 0)
atr    = float(row.get('atr14') or 0)
bbu    = float(row.get('bb_upper') or 0)
bbl    = float(row.get('bb_lower') or 0)
bbw    = float(row.get('bb_bandwidth') or 0)
rsi    = float(row.get('rsi14') or 50)
mfi    = float(row.get('mfi14') or 0)
clo5   = float(row.get('clo5') or 0)
clo10  = float(row.get('clo10') or 0)
clo20  = float(row.get('clo20') or 0)
clo40  = float(row.get('clo40') or 0)
clo60  = float(row.get('clo60') or 0)

# ADX 기반 동적 가중치
if adx >= 25:   mom_mult, mr_mult = 1.2, 0.8
elif adx <= 20: mom_mult, mr_mult = 0.8, 1.2
else:           mom_mult, mr_mult = 1.0, 1.0

# A. 모멘텀
a1 = min(20, max(0, (vol5/vol20 - 1.0) * 40)) if vol20 > 0 else 0
ma_vals = [v for v in [clo5,clo10,clo20,clo40,clo60] if v > 0]
pairs_ok = sum(1 for i in range(len(ma_vals)) for j in range(i+1,len(ma_vals)) if ma_vals[i]>ma_vals[j])
total_p  = len(ma_vals)*(len(ma_vals)-1)//2
a2 = (pairs_ok/total_p)*15 if total_p > 0 else 0
a3 = (3 if macd > macdS else 0) + (2 if macdH > 0 else 0)
a_score = (a1+a2+a3) * mom_mult

# B. 평균회귀
b1 = 10 if rsi <= 30 else (10*(40-rsi)/10 if rsi <= 40 else 0)
bb_range = bbu - bbl
pos = (close - bbl)/bb_range if bb_range > 0 else 1
b3 = 10 if pos <= 0.2 else (10*(0.4-pos)/0.2 if pos <= 0.4 else 0)
b_score = (b1+b3) * mr_mult

# C. 추세강도
c1 = 25 if adx>=25 else (25*(adx-20)/5 if adx>=20 else (25*(adx-15)/10*0.5 if adx>=15 else 0))
c2 = 15 if 0<bbw<0.05 else (15*(0.1-bbw)/0.05 if bbw<0.1 else 0)
c3 = min(10, ((pdi-mdi)/max(pdi+mdi,1)*100)*0.5) if pdi>mdi>0 else 0
c_score = c1+c2+c3

# D. CMF만 (OBV, 동조는 df_120 컬럼 구조상 생략)
d2 = 15 if cmf>0.1 else (15*(cmf/0.1) if cmf>0 else 0)

# 패널티
atr_rate = atr/close
p_atr = -20 if atr_rate>0.08 else (-10 if atr_rate>0.05 else 0)
p_mfi = -15 if mfi>90 else (-8 if mfi>80 else 0)

# RSI 동적 꺽임 패널티/보너스
if peak_rsi > 60 and fall_from_peak < 0 and days_since_peak > 0:
    if fall_rate <= -3.0:
        p_rsi = -15
    elif fall_rate <= -1.5:
        p_rsi = -8
    else:
        p_rsi = 0
elif trough_rsi < 40 and rise_from_trough > 0 and days_since_trough > 0:
    if rise_rate >= 2.0:
        p_rsi = 10
    elif rise_rate >= 1.0:
        p_rsi = 5
    else:
        p_rsi = 0
else:
    p_rsi = 0

print(f"\n[원본 지표]")
print(f"  종가={close:.0f}  RSI={rsi:.1f}  MFI={mfi:.1f}  ADX={adx:.1f}")
print(f"  +DI={pdi:.1f}  -DI={mdi:.1f}  CMF={cmf:.4f}  ATR={atr:.0f}({atr_rate*100:.2f}%)")
print(f"  vol5/vol20={vol5:.0f}/{vol20:.0f}={vol5/vol20:.2f}x")
print(f"  MA: {clo5:.0f}/{clo10:.0f}/{clo20:.0f}/{clo40:.0f}/{clo60:.0f}")

print(f"\n[A. 모멘텀 × {mom_mult}]")
print(f"  A1 거래량급증: {a1:.1f}pt  (vol비율 {vol5/vol20:.2f}x)")
print(f"  A2 MA정배열:   {a2:.1f}pt")
print(f"  A3 MACD:       {a3:.1f}pt  (MACD {macd:.0f} >> Signal {macdS:.0f})")
print(f"  소계: ({a1+a2+a3:.1f}) × {mom_mult} = {a_score:.1f}pt")

print(f"\n[B. 평균회귀 × {mr_mult}]")
print(f"  B1 RSI:    {b1:.1f}pt  (RSI={rsi:.1f})")
print(f"  B3 BB하단: {b3:.1f}pt")
print(f"  소계: {b_score:.1f}pt")

print(f"\n[C. 추세강도]")
print(f"  C1 ADX:    {c1:.1f}pt  (ADX={adx:.1f})")
print(f"  C2 BB수렴: {c2:.1f}pt  (BBW={bbw:.3f})")
print(f"  C3 DI방향: {c3:.1f}pt  (+DI {pdi:.0f} vs -DI {mdi:.0f})")
print(f"  소계: {c_score:.1f}pt")

print(f"\n[D. 거래량 — CMF만]")
print(f"  D2 CMF: {d2:.1f}pt  (CMF={cmf:.4f})")

print(f"\n[패널티]")
print(f"  ATR 변동성: {p_atr}pt  (ATR={atr_rate*100:.2f}%)")
print(f"  MFI 과매수: {p_mfi}pt  (MFI={mfi:.1f})")
print(f"  RSI 꺽임:   {p_rsi}pt  (RSI현재={rsi_now:.1f}, "
      f"고점={peak_rsi:.1f}/{days_since_peak}일전 fall={fall_from_peak:.1f}({fall_rate:.2f}/일), "
      f"저점={trough_rsi:.1f}/{days_since_trough}일전 rise={rise_from_trough:.1f}({rise_rate:.2f}/일))")

partial = a_score+b_score+c_score+d2
total_penalty = p_atr+p_mfi+p_rsi
print(f"\n{'=' * 65}")
print(f"부분합 (OBV, D3, E, F 제외): {partial:.1f}pt")
print(f"패널티 합계:                  {total_penalty}pt")
print(f"부분합+패널티:                {partial+total_penalty:.1f}pt")
print(f"실제 composite_score:         134.7pt  (OBV+D3+E+F 포함)")
print(f"=> OBV+D3+E+F 기여:           {134.7-(partial+total_penalty):.1f}pt")
print(f"{'=' * 65}")
