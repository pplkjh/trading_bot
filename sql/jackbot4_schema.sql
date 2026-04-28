-- ================================================
-- jackbot4_imi1 스키마 생성 스크립트
-- simul_num=4 (Strategy A: 돌파초입) / simul_num=5 (Strategy B: 저점반등) / simul_num=6 (A+B)
-- ================================================
-- 실행 방법:
--   mysql -u bot -p --default-character-set=utf8mb4 jackbot4_imi1 < sql/jackbot4_schema.sql
--
-- ⚠️ 주의: jackbot3_imi1 에는 절대 실행하지 말 것!
-- ================================================

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

-- USE jackbot4_imi1;  -- 실행 전 DB 선택 확인

-- ================================================
-- 1. setting_data
-- ================================================
CREATE TABLE IF NOT EXISTS setting_data (
    loan_money INT DEFAULT 0 COMMENT '대출금',
    limit_money INT DEFAULT 0 COMMENT '최소 보유 현금',
    invest_unit INT DEFAULT 0 COMMENT '종목당 투자금액',
    max_invest_unit INT DEFAULT 0 COMMENT '최대 투자금액',
    min_invest_unit INT DEFAULT 0 COMMENT '최소 투자금액',
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
-- 3. all_item_db  ← jackbot3_imi1 컬럼 + strategy_type 포함
-- ================================================
CREATE TABLE IF NOT EXISTS all_item_db (
    `index` INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(10) NOT NULL,
    code_name VARCHAR(100) NOT NULL,
    chegyul_check VARCHAR(10) DEFAULT '0',

    -- 매수 정보
    buy_date VARCHAR(20) NOT NULL,
    buy_time VARCHAR(20),
    purchase_price INT NOT NULL,
    holding_amount INT NOT NULL,

    -- 현재 상태
    present_price INT DEFAULT 0,
    rate DECIMAL(10,2) DEFAULT 0,
    valuation_profit BIGINT DEFAULT 0,

    -- 매도 정보
    sell_date VARCHAR(20) DEFAULT '0',
    sell_time VARCHAR(20),
    sell_price INT DEFAULT 0,
    sell_rate DECIMAL(10,2) DEFAULT 0,
    realized_profit BIGINT DEFAULT 0,

    -- 기술적 지표 (매수 당시)
    d1_diff_rate DECIMAL(10,2) DEFAULT 0,
    yes_close INT DEFAULT 0,
    volume BIGINT DEFAULT 0,
    today_percent DECIMAL(10,2) DEFAULT 0,

    -- 이동평균선 (매수 당시)
    ma5 INT DEFAULT 0,
    ma10 INT DEFAULT 0,
    ma20 INT DEFAULT 0,
    ma60 INT DEFAULT 0,
    ma120 INT DEFAULT 0,

    -- 투자금액
    item_total_purchase BIGINT DEFAULT 0,
    valuation_price BIGINT DEFAULT 0,

    -- 스코어 (jackbot3_imi1 migration 컬럼 — 처음부터 포함)
    composite_score INT DEFAULT 0 COMMENT '매수 시점 총점 (0-200)',
    score_a DECIMAL(6,2) DEFAULT 0 COMMENT 'A. 돌파강도',
    score_b DECIMAL(6,2) DEFAULT 0 COMMENT 'B. 저점반등',
    score_c DECIMAL(6,2) DEFAULT 0 COMMENT 'C. 추세강도',
    score_d DECIMAL(6,2) DEFAULT 0 COMMENT 'D. 거래량',
    score_e DECIMAL(6,2) DEFAULT 0 COMMENT 'E. 시장상대강도',
    score_f DECIMAL(6,2) DEFAULT 0 COMMENT 'F. 다중시간프레임',
    score_penalty DECIMAL(6,2) DEFAULT 0 COMMENT '패널티',
    simul_num INT DEFAULT 4 COMMENT '알고리즘 번호 (4=A전용 / 5=B전용 / 6=A+B)',

    -- ★ simul_num=4 신규: 전략 구분
    strategy_type VARCHAR(1) DEFAULT 'A' COMMENT '전략 유형 (A: 돌파초입, B: 저점반등)',

    INDEX idx_code (code),
    INDEX idx_buy_date (buy_date),
    INDEX idx_sell_date (sell_date),
    INDEX idx_code_sell (code, sell_date),
    INDEX idx_strategy_type (strategy_type),
    INDEX idx_simul_num (simul_num)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='simul_num=4/5/6 매매 기록 (strategy_type으로 A/B 구분)';

-- ================================================
-- 4. possessed_item
-- ================================================
CREATE TABLE IF NOT EXISTS possessed_item (
    `index` INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(10) NOT NULL,
    code_name VARCHAR(100) NOT NULL,
    holding_amount INT NOT NULL,
    purchase_price INT NOT NULL,
    present_price INT NOT NULL,
    valuation_profit BIGINT DEFAULT 0,
    rate DECIMAL(10,2) DEFAULT 0,
    first_buy_date VARCHAR(20),
    INDEX idx_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ================================================
-- 5. realtime_daily_buy_list  ← strategy_type 이미 있음
-- ================================================
CREATE TABLE IF NOT EXISTS realtime_daily_buy_list (
    `index` INT AUTO_INCREMENT PRIMARY KEY,
    date VARCHAR(20) NOT NULL,
    code VARCHAR(10) NOT NULL,
    code_name VARCHAR(100) NOT NULL,
    d1_diff_rate DECIMAL(10,2) DEFAULT 0,
    close INT NOT NULL,
    open INT DEFAULT 0,
    high INT DEFAULT 0,
    low INT DEFAULT 0,
    volume BIGINT DEFAULT 0,
    ma5 INT DEFAULT 0,
    ma10 INT DEFAULT 0,
    ma20 INT DEFAULT 0,
    ma40 INT DEFAULT 0,
    ma60 INT DEFAULT 0,
    ma80 INT DEFAULT 0,
    ma100 INT DEFAULT 0,
    ma120 INT DEFAULT 0,
    strategy_type VARCHAR(50) DEFAULT 'basic' COMMENT '전략 타입 (A: 돌파초입, B: 저점반등)',
    composite_score INT DEFAULT 0,
    score_a DECIMAL(6,2) DEFAULT 0,
    score_b DECIMAL(6,2) DEFAULT 0,
    score_c DECIMAL(6,2) DEFAULT 0,
    score_d DECIMAL(6,2) DEFAULT 0,
    score_e DECIMAL(6,2) DEFAULT 0,
    score_f DECIMAL(6,2) DEFAULT 0,
    score_penalty DECIMAL(6,2) DEFAULT 0,
    simul_num INT DEFAULT 0,
    volume_ratio DECIMAL(10,2) DEFAULT 1.0,
    rsi14 DECIMAL(10,2) DEFAULT 50.0,
    bb_upper INT DEFAULT 0,
    bb_middle INT DEFAULT 0,
    bb_lower INT DEFAULT 0,
    atr14 INT DEFAULT 0,
    check_item VARCHAR(20) DEFAULT '0',
    INDEX idx_date (date),
    INDEX idx_code (code),
    INDEX idx_check (check_item),
    INDEX idx_strategy (strategy_type),
    INDEX idx_score (composite_score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ================================================
-- 6. realtime_position_monitor
-- ================================================
CREATE TABLE IF NOT EXISTS realtime_position_monitor (
    code VARCHAR(10) NOT NULL,
    code_name VARCHAR(50),
    entry_price INT DEFAULT 0,
    entry_date VARCHAR(10),
    current_price INT DEFAULT 0,
    highest_price INT DEFAULT 0,
    last_update DATETIME,
    PRIMARY KEY (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ================================================
SELECT 'jackbot4_imi1 schema created.' AS status;
SHOW TABLES;
