-- ================================================
-- simulator9 스키마
-- simul_num=9: BreakoutStrategyV6 + ReversalStrategyV4
-- All-Required Condition System (A: V5 optional 전부 Required)
--
-- score_a~score_e: 조건 결과 (0=실패, 1=통과) — 전부 1이어야 매수
-- composite_score: 항상 5 (전 조건 통과 시만 매수)
-- B: ReversalV4 scoring (sim=8과 동일)
--
-- 실행:
--   mysql -u root -p -e "CREATE DATABASE simulator9; GRANT ALL PRIVILEGES ON simulator9.* TO 'bot'@'localhost'; FLUSH PRIVILEGES;"
--   mysql -u bot -p --default-character-set=utf8mb4 simulator9 < sql/jackbot9_schema.sql
-- ================================================

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

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

    composite_score INT DEFAULT 0 COMMENT 'A: 항상 5 (전조건 통과) / B: V4 점수',
    score_a DECIMAL(6,2) DEFAULT 0 COMMENT 'A: bb_pos<0.65 / B: RSI신호',
    score_b DECIMAL(6,2) DEFAULT 0 COMMENT 'A: rsi14<55   / B: 펀더멘털',
    score_c DECIMAL(6,2) DEFAULT 0 COMMENT 'A: mfi14>30   / B: 장기추세',
    score_d DECIMAL(6,2) DEFAULT 0 COMMENT 'A: close>kijun / B: BB사이클',
    score_e DECIMAL(6,2) DEFAULT 0 COMMENT 'A: +DI>-DI    / B: 거래량+MACD',
    score_f DECIMAL(6,2) DEFAULT 0,
    score_g DECIMAL(6,2) DEFAULT 0,
    score_h DECIMAL(6,2) DEFAULT 0,
    score_penalty DECIMAL(6,2) DEFAULT 0,
    simul_num INT DEFAULT 9,

    strategy_type VARCHAR(1) DEFAULT 'A' COMMENT 'A: BreakoutV6 / B: ReversalV4',

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
COMMENT='simul_num=9 매매 기록 (All-Required V6)';

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

SELECT 'simulator9 schema created.' AS status;
SHOW TABLES;
