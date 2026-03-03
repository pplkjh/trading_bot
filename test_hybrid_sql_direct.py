"""
Test the hybrid strategy SQL directly
"""
import pymysql
import pandas as pd
from library import cf

print("\n" + "=" * 80)
print("Testing Hybrid Strategy SQL (with investment warning filter REMOVED)")
print("=" * 80)

con = pymysql.connect(
    user=cf.db_id,
    passwd=cf.db_passwd,
    host=cf.db_ip,
    db='daily_buy_list',
    charset='utf8',
    port=int(cf.db_port)
)

latest_date = '20251224'
min_score = 65.0
top_n = 40

# Check for filter tables
cursor = con.cursor()
cursor.execute("""
    SELECT TABLE_NAME
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = 'daily_buy_list'
    AND TABLE_NAME IN ('stock_konex', 'stock_invest_warning', 'stock_invest_danger')
""")
existing_tables = {row[0] for row in cursor.fetchall()}

print(f"\nExisting filter tables: {existing_tables}")

# Konex exclusion
konex_exclusion = ""
if 'stock_konex' in existing_tables:
    konex_exclusion = "AND code NOT IN (SELECT code FROM stock_konex WHERE 1=1)"
    print("Konex filter: ACTIVE")
else:
    print("Konex filter: NOT FOUND")

# Investment warning filter - DISABLED
warning_exclusion = ""
print("Investment warning filter: DISABLED (matching date_based strategy)")

# Hybrid strategy SQL query
query = f"""
SELECT
    code,
    code_name,
    close,
    d1_diff_rate,
    volume,
    vol5,
    vol20,
    clo5,
    clo10,
    clo20,
    clo40,
    clo60,
    rsi14,
    bb_upper,
    bb_middle,
    bb_lower,
    atr14,

    -- Hybrid score (Momentum 60 + Mean Reversion 40 = 100 max)
    (
        -- Momentum (60 max)
        CASE WHEN volume > vol20 * 2.0 THEN 20 WHEN volume > vol20 * 1.5 THEN 15 WHEN volume > vol20 * 1.2 THEN 10 ELSE 5 END +
        CASE WHEN clo5 > clo20 AND clo20 > clo60 THEN 20 WHEN clo5 > clo20 THEN 15 ELSE 5 END +
        CASE WHEN atr14 > 0 AND (high - low) > atr14 * 1.5 THEN 20 WHEN atr14 > 0 AND (high - low) > atr14 THEN 15 ELSE 10 END +
        -- Mean Reversion (40 max)
        CASE WHEN rsi14 <= 30 THEN 15 WHEN rsi14 <= 40 THEN 10 WHEN rsi14 <= 50 THEN 5 ELSE 0 END +
        CASE WHEN bb_lower > 0 AND close <= bb_lower THEN 15 WHEN bb_lower > 0 AND close <= bb_lower * 1.02 THEN 10 WHEN bb_middle > 0 AND close < bb_middle THEN 5 ELSE 0 END +
        CASE WHEN close > clo20 * 0.95 AND close < clo20 * 1.0 THEN 10 WHEN close > clo60 * 0.95 AND close < clo60 * 1.0 THEN 8 ELSE 3 END
    ) as score,

    -- Strategy type classification
    CASE
        WHEN rsi14 <= 30 AND bb_lower > 0 AND close <= bb_lower * 1.02 THEN 'mean_reversion'
        WHEN volume > vol20 * 1.5 AND clo5 > clo20 THEN 'momentum_breakout'
        ELSE 'hybrid'
    END as strategy_type

FROM `{latest_date}`
WHERE 1=1
    -- Basic filters
    AND close > 0
    AND volume > 0
    AND rsi14 > 0
    AND bb_lower > 0

    {konex_exclusion}

    {warning_exclusion}

    -- Hybrid conditions (Momentum OR Mean Reversion)
    AND (
        -- Momentum condition
        (clo5 > clo20 AND volume > vol20 * 1.2)
        OR
        -- Mean reversion condition
        (rsi14 <= 40 AND bb_lower > 0 AND close <= bb_lower * 1.05)
    )

    -- Price range
    AND close BETWEEN 1000 AND 500000

HAVING score >= {min_score}
ORDER BY score DESC
LIMIT {top_n}
"""

print("\n" + "=" * 80)
print("Executing query...")
print("=" * 80)

df = pd.read_sql(query, con)
con.close()

print(f"\nResults: {len(df)} candidates found")

if df.empty:
    print("\nNO CANDIDATES FOUND!")
else:
    print("\n" + "=" * 80)
    print("Top 20 Hybrid Candidates:")
    print("=" * 80)

    for idx, row in df.head(20).iterrows():
        print(f"[{idx+1:2d}] {row['code']} {row['code_name']:<20} "
              f"| Score: {row['score']:>5.1f} | RSI: {row['rsi14']:>5.1f} "
              f"| Strategy: {row['strategy_type']}")

    print("\n" + "=" * 80)
    print(f"Score range: {df['score'].min():.1f} - {df['score'].max():.1f}")
    print(f"Average score: {df['score'].mean():.1f}")
    print("=" * 80 + "\n")
