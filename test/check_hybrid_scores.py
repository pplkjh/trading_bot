"""
하이브리드 전략 스코어 분포 확인
"""
import pymysql
import pandas as pd
from library import cf

print("\n" + "="*100)
print("🔍 하이브리드 전략 스코어 분석")
print("="*100)

con = pymysql.connect(
    user=cf.db_id,
    passwd=cf.db_passwd,
    host=cf.db_ip,
    db='daily_buy_list',
    charset='utf8',
    port=int(cf.db_port)
)

query = """
SELECT
    code, code_name, close, rsi14, volume/vol20 as vol_ratio,
    ROUND((
        (
            CASE
                WHEN volume > vol20 * 2.0 THEN 20
                WHEN volume > vol20 * 1.5 THEN 15
                WHEN volume > vol20 * 1.2 THEN 10
                ELSE 5
            END +
            CASE
                WHEN clo5 > clo20 AND clo20 > clo60 THEN 20
                WHEN clo5 > clo20 THEN 15
                ELSE 5
            END +
            CASE
                WHEN atr14 > 0 AND (high - low) > atr14 * 1.5 THEN 20
                WHEN atr14 > 0 AND (high - low) > atr14 THEN 15
                ELSE 10
            END
        ) * 0.6
        +
        (
            CASE
                WHEN rsi14 <= 30 THEN 15
                WHEN rsi14 <= 40 THEN 10
                WHEN rsi14 <= 50 THEN 5
                ELSE 0
            END +
            CASE
                WHEN bb_lower > 0 AND close <= bb_lower THEN 15
                WHEN bb_lower > 0 AND close <= bb_lower * 1.02 THEN 10
                WHEN bb_middle > 0 AND close < bb_middle THEN 5
                ELSE 0
            END +
            CASE
                WHEN close > clo20 * 0.95 AND close < clo20 * 1.0 THEN 10
                WHEN close > clo60 * 0.95 AND close < clo60 * 1.0 THEN 8
                ELSE 3
            END
        ) * 0.4
    ) * (100.0 / 52.0), 1) as score
FROM `20251224`
WHERE close > 0 AND volume > 0 AND rsi14 > 0 AND bb_lower > 0
    AND (
        (clo5 > clo20 AND volume > vol20 * 1.2)
        OR
        (rsi14 <= 40 AND bb_lower > 0 AND close <= bb_lower * 1.05)
    )
    AND close BETWEEN 1000 AND 500000
ORDER BY score DESC
LIMIT 50
"""

df = pd.read_sql(query, con)
con.close()

print(f"\n📊 하이브리드 조건을 만족하는 종목: {len(df)}개\n")

if df.empty:
    print("❌ 조건을 만족하는 종목이 없습니다!")
    print("\n💡 조건을 완화하거나 min_score를 낮춰야 합니다.")
else:
    print(f"{'='*100}")
    print(f"상위 20개 종목 스코어 분포:")
    print(f"{'='*100}\n")

    for idx, row in df.head(20).iterrows():
        print(f"[{idx+1:2d}] {row['code']} {row['code_name']:<15} "
              f"| 현재가: {int(row['close']):>7,}원 "
              f"| 스코어: {row['score']:>5.1f}점 "
              f"| RSI: {row['rsi14']:>5.1f} "
              f"| 거래량: {row['vol_ratio']:>4.2f}x")

    print(f"\n{'='*100}")
    print("📊 스코어 통계:")
    print(f"{'='*100}")
    print(f"  최고 스코어:  {df['score'].max():.1f}점")
    print(f"  평균 스코어:  {df['score'].mean():.1f}점")
    print(f"  중앙값:       {df['score'].median():.1f}점")
    print(f"  최저 스코어:  {df['score'].min():.1f}점")

    score_ranges = [
        (70, 100, "70점 이상 (현재 설정)"),
        (60, 70, "60-70점"),
        (50, 60, "50-60점"),
        (40, 50, "40-50점"),
        (0, 40, "40점 미만"),
    ]

    print(f"\n{'='*100}")
    print("📊 스코어 구간별 종목 수:")
    print(f"{'='*100}")
    for min_s, max_s, label in score_ranges:
        count = len(df[(df['score'] >= min_s) & (df['score'] < max_s)])
        print(f"  {label:<25}: {count:>3}개")

print(f"\n{'='*100}")
print("💡 권장사항 (100점 스케일 기준):")
print(f"{'='*100}")
if df.empty:
    print("  - 하이브리드 조건 자체가 너무 엄격합니다")
    print("  - clo5 > clo20 AND volume > vol20 * 1.2 조건을 vol20 * 1.0으로 완화")
    print("  - 또는 rsi14 <= 40을 rsi14 <= 50으로 완화")
else:
    max_score = df['score'].max()
    count_70 = len(df[df['score'] >= 70])
    count_65 = len(df[df['score'] >= 65])

    print(f"  - 현재 최고 스코어: {max_score:.1f}점")
    print(f"  - 70점 이상: {count_70}개")
    print(f"  - 65점 이상: {count_65}개 (현재 설정)")

    if count_65 >= 5:
        print(f"  ✅ 현재 설정(min_score_hybrid=65)이 적절합니다")
    elif count_70 > 0:
        print(f"  💡 min_score_hybrid를 70점으로 올리는 것을 고려하세요 ({count_70}개 선정)")
    else:
        recommended = max(60, int(max_score) - 5)
        print(f"  💡 min_score_hybrid를 {recommended}점 정도로 낮추세요")

print(f"{'='*100}\n")
