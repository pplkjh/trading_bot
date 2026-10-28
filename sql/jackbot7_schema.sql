-- ================================================
-- jackbot7_imi1 / simulator7 스키마
-- simul_num=7: BreakoutStrategyV4 + ReversalStrategyV4 + score_h (NASDAQ/SOX)
--
-- sim=6(jackbot4_imi1) 대비 변경:
--   all_item_db.score_h 컬럼 추가 (NASDAQ/SOX 시장환경 최대 20pt)
--   나머지 구조 동일
--
-- 실행:
--   mysql -u bot -p --default-character-set=utf8mb4 simulator7    < sql/jackbot7_schema.sql
--   mysql -u bot -p --default-character-set=utf8mb4 jackbot7_imi1 < sql/jackbot7_schema.sql
-- ================================================

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

-- ================================================
-- 1. setting_data
-- ================================================
CREATE TABLE IF NOT EXISTS setting_data (
    loan_money INT DEFAULT 0,
    limit_money INT DEFAULT 0,
    invest_unit INT DEFAULT 0,
    max_invest_unit INT DEFAULT 0,
    min_invest_unit INT DEFAULT 0,
    set_invest_unit VARCHAR(20) DEFAULT '0',
    code_update VARCHAR(20) DEFAULT '0',
    today_buy_stop VARCHAR(20) DEFAULT '0',
    jango_data_db_check VARCHAR(20) DEFAULT '0',
    possessed_item VARCHAR(20) DEFAULT '0',
    today_profit VARCHAR(20) DEFAULT '0',
    final_chegyul_check VARCHAR(20) DEFAULT '0',
    db_to_buy_list VARCHAR(20) DEFAULT '0',
    today_buy_list VARCHAR(20) DEFAULT '0',
    daily_crawler VARCHAR(20) DEFAULT '0',
    min_crawler VARCHAR(20) DEFAULT '0',
    daily_buy_list VARCHAR(20) DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO setting_data (loan_money, limit_money, invest_unit)
VALUES (0, 0, 0)
ON DUPLICATE KEY UPDATE loan_money=loan_money;

-- ================================================
-- 2. jango_data
-- ================================================
CREATE TABLE IF NOT EXISTS jango_data (
    date VARCHAR(20) PRIMARY KEY,
    total_asset BIGINT DEFAULT 0,
    d2_deposit BIGINT DEFAULT 0,
    total_invest BIGINT DEFAULT 0,
    today_profit BIGINT DEFAULT 0,
    today_earning_rate DECIMAL(10,2) DEFAULT 0,
    today_buy_count INT DEFAULT 0,
    today_sell_count INT DEFAULT 0,
    today_buy_total_sell_count INT DEFAULT 0,
    today_buy_total_possess_count INT DEFAULT 0,
    today_buy_today_profitcut_count INT DEFAULT 0,
    today_buy_today_profitcut_rate DECIMAL(10,2) DEFAULT 0,
    today_buy_today_losscut_count INT DEFAULT 0,
    today_buy_today_losscut_rate DECIMAL(10,2) DEFAULT 0,
    today_buy_total_profitcut_count INT DEFAULT 0,
    today_buy_total_profitcut_rate DECIMAL(10,2) DEFAULT 0,
    today_buy_total_losscut_count INT DEFAULT 0,
    today_buy_total_losscut_rate DECIMAL(10,2) DEFAULT 0,
    INDEX idx_date (date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ================================================
-- 3. all_item_db  (score_h 컬럼 추가 — sim=7 신규)
-- ================================================
CREATE TABLE IF NOT EXISTS all_item_db (
    `index` INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(10) NOT NULL,
    code_name VARCHAR(100) NOT NULL,
    chegyul_check VARCHAR(10) DEFAULT '0',

    buy_date VARCHAR(20) NOT NULL,
    buy_time VARCHAR(20),
    purchase_price INT NOT NULL,
    holding_amount INT NOT NULL,

    present_price INT DEFAULT 0,
    rate DECIMAL(10,2) DEFAULT 0,
    valuation_profit BIGINT DEFAULT 0,

    sell_date VARCHAR(20) DEFAULT '0',
    sell_time VARCHAR(20),
    sell_price INT DEFAULT 0,
    sell_rate DECIMAL(10,2) DEFAULT 0,
    realized_profit BIGINT DEFAULT 0,

    d1_diff_rate DECIMAL(10,2) DEFAULT 0,
    yes_close INT DEFAULT 0,
    volume BIGINT DEFAULT 0,
    today_percent DECIMAL(10,2) DEFAULT 0,

    ma5 INT DEFAULT 0,
    ma10 INT DEFAULT 0,
    ma20 INT DEFAULT 0,
    ma60 INT DEFAULT 0,
    ma120 INT DEFAULT 0,

    item_total_purchase BIGINT DEFAULT 0,
    valuation_price BIGINT DEFAULT 0,

    composite_score INT DEFAULT 0,
    score_a DECIMAL(6,2) DEFAULT 0 COMMENT 'A. 셋업품질',
    score_b DECIMAL(6,2) DEFAULT 0 COMMENT 'B. BB돌파/RSI신호',
    score_c DECIMAL(6,2) DEFAULT 0 COMMENT 'C. ADX/장기추세',
    score_d DECIMAL(6,2) DEFAULT 0 COMMENT 'D. MACD',
    score_e DECIMAL(6,2) DEFAULT 0 COMMENT 'E. RSI50/회복모멘텀',
    score_f DECIMAL(6,2) DEFAULT 0 COMMENT 'F. BB활성도/BB사이클',
    score_g DECIMAL(6,2) DEFAULT 0 COMMENT 'G. 기관/외국인수급',
    score_h DECIMAL(6,2) DEFAULT 0 COMMENT 'H. NASDAQ/SOX 시장환경 (sim=7 신규)',
    score_penalty DECIMAL(6,2) DEFAULT 0,
    simul_num INT DEFAULT 7,

    strategy_type VARCHAR(1) DEFAULT 'A' COMMENT 'A: BreakoutV4 / B: ReversalV4',

    max_high_pct DECIMAL(10,4) DEFAULT 0,
    min_low_pct DECIMAL(10,4) DEFAULT 0,
    rsi14 DECIMAL(6,2) DEFAULT 0,
    rsi_peak DECIMAL(6,2) DEFAULT 0,

    INDEX idx_code (code),
    INDEX idx_buy_date (buy_date),
    INDEX idx_sell_date (sell_date),
    INDEX idx_code_sell (code, sell_date),
    INDEX idx_strategy_type (strategy_type),
    INDEX idx_simul_num (simul_num)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='simul_num=7 매매 기록 (V4 전략 + NASDAQ score_h)';

-- ================================================
-- 4. possessed_item
-- ================================================
CREATE TABLE IF NOT EXISTS possessed_item (
    `index` INT AUTO_INCREMENT PRIMARY KEY,
    date VARCHAR(20),
    code VARCHAR(10) NOT NULL,
    code_name VARCHAR(100) NOT NULL,
    holding_amount INT NOT NULL,
    puchase_price INT NOT NULL,
    present_price INT NOT NULL,
    valuation_profit BIGINT DEFAULT 0,
    rate DECIMAL(10,2) DEFAULT 0,
    INDEX idx_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ================================================
SELECT 'jackbot7_imi1 / simulator7 schema created.' AS status;
SHOW TABLES;
