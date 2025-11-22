-- =============================================================================
-- JackBot Trading Bot Database Schema
-- =============================================================================
-- 파일명: sql/jackbot_schema.sql
-- 설명: 트레이딩 봇의 메인 데이터베이스(JackBot1_imi1) 스키마
-- 실행 방법: mysql -u root -p JackBot1_imi1 < sql/jackbot_schema.sql
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. setting_data 테이블
-- 설명: 봇의 설정 및 상태 정보를 저장하는 테이블
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS setting_data (
    `index` BIGINT AUTO_INCREMENT PRIMARY KEY,
    loan_money BIGINT NULL DEFAULT 0 COMMENT '대출 금액',
    limit_money BIGINT NULL DEFAULT 0 COMMENT '한도 금액',
    invest_unit BIGINT NULL DEFAULT 0 COMMENT '투자 단위',
    max_invest_unit BIGINT NULL DEFAULT 0 COMMENT '최대 투자 단위',
    min_invest_unit BIGINT NULL DEFAULT 0 COMMENT '최소 투자 단위',
    set_invest_unit VARCHAR(20) NULL DEFAULT '0' COMMENT '설정된 투자 단위',
    code_update VARCHAR(20) NULL DEFAULT '0' COMMENT '종목 업데이트 날짜',
    today_buy_stop VARCHAR(20) NULL DEFAULT '0' COMMENT '오늘 매수 중지 여부',
    jango_data_db_check VARCHAR(20) NULL DEFAULT '0' COMMENT '잔고 데이터 DB 체크 날짜',
    possessed_item VARCHAR(20) NULL DEFAULT '0' COMMENT '보유 종목 업데이트 날짜',
    today_profit VARCHAR(20) NULL DEFAULT '0' COMMENT '오늘 수익 체크 날짜',
    final_chegyul_check VARCHAR(20) NULL DEFAULT '0' COMMENT '최종 체결 체크 날짜',
    db_to_buy_list VARCHAR(20) NULL DEFAULT '0' COMMENT '매수 리스트 DB 반영 날짜',
    today_buy_list VARCHAR(20) NULL DEFAULT '0' COMMENT '오늘 매수 리스트 날짜',
    daily_crawler VARCHAR(20) NULL DEFAULT '0' COMMENT '일봉 크롤러 실행 날짜',
    min_crawler VARCHAR(20) NULL DEFAULT '0' COMMENT '분봉 크롤러 실행 날짜',
    daily_buy_list VARCHAR(20) NULL DEFAULT '0' COMMENT '일일 매수 리스트 날짜'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='봇 설정 및 상태 정보';

-- 초기 데이터 삽입 (존재하지 않을 경우에만)
INSERT INTO setting_data (
    loan_money, limit_money, invest_unit, max_invest_unit, min_invest_unit,
    set_invest_unit, code_update, today_buy_stop, jango_data_db_check,
    possessed_item, today_profit, final_chegyul_check, db_to_buy_list,
    today_buy_list, daily_crawler, min_crawler, daily_buy_list
)
SELECT 0, 0, 0, 0, 0, '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0'
WHERE NOT EXISTS (SELECT 1 FROM setting_data LIMIT 1);

-- Table created: setting_data

-- -----------------------------------------------------------------------------
-- 2. jango_data 테이블
-- 설명: 일별 계좌 잔고 및 거래 통계를 저장하는 테이블
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jango_data (
    `index` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `date` VARCHAR(20) NOT NULL COMMENT '날짜 (YYYYMMDD)',
    today_earning_rate DOUBLE NULL COMMENT '오늘 수익률',
    sum_valuation_profit DOUBLE NULL COMMENT '평가 손익 합계',
    total_profit DOUBLE NULL COMMENT '총 수익',
    today_profit DOUBLE NULL COMMENT '오늘 수익',
    today_profitcut_count BIGINT NULL COMMENT '오늘 익절 건수',
    today_losscut_count BIGINT NULL COMMENT '오늘 손절 건수',
    today_profitcut DOUBLE NULL COMMENT '오늘 익절 금액',
    today_losscut DOUBLE NULL COMMENT '오늘 손절 금액',
    d2_deposit BIGINT NULL COMMENT 'D+2 예수금',
    total_possess_count BIGINT NULL COMMENT '총 보유 종목 수',
    today_buy_count BIGINT NULL COMMENT '오늘 매수 건수',
    today_buy_list_count BIGINT NULL COMMENT '오늘 매수 리스트 건수',
    today_reinvest_count BIGINT NULL COMMENT '오늘 재투자 건수',
    today_cant_reinvest_count BIGINT NULL COMMENT '오늘 재투자 불가 건수',
    total_asset BIGINT NULL COMMENT '총 자산',
    total_invest BIGINT NULL COMMENT '총 투자금',
    sum_item_total_purchase DOUBLE NULL COMMENT '총 매수금액 합계',
    total_evaluation DOUBLE NULL COMMENT '총 평가금액',
    today_rate DOUBLE NULL COMMENT '오늘 수익률',
    today_invest_price DOUBLE NULL COMMENT '오늘 투자금',
    today_reinvest_price DOUBLE NULL COMMENT '오늘 재투자금',
    today_sell_price DOUBLE NULL COMMENT '오늘 매도금액',
    volume_limit BIGINT NULL COMMENT '거래량 제한',
    reinvest_point DOUBLE NULL COMMENT '재투자 포인트',
    sell_point DOUBLE NULL COMMENT '매도 포인트',
    max_reinvest_count BIGINT NULL COMMENT '최대 재투자 횟수',
    invest_limit_rate DOUBLE NULL COMMENT '투자 한도 비율',
    invest_unit BIGINT NULL COMMENT '투자 단위',
    rate_std_sell_point DOUBLE NULL COMMENT '표준 수익률 매도 포인트',
    limit_money BIGINT NULL COMMENT '한도 금액',
    total_profitcut DOUBLE NULL COMMENT '총 익절 금액',
    total_losscut DOUBLE NULL COMMENT '총 손절 금액',
    total_profitcut_count BIGINT NULL COMMENT '총 익절 건수',
    total_losscut_count BIGINT NULL COMMENT '총 손절 건수',
    loan_money BIGINT NULL COMMENT '대출 금액',
    start_kospi_point DOUBLE NULL COMMENT '시작 KOSPI 지수',
    start_kosdaq_point DOUBLE NULL COMMENT '시작 KOSDAQ 지수',
    end_kospi_point DOUBLE NULL COMMENT '종료 KOSPI 지수',
    end_kosdaq_point DOUBLE NULL COMMENT '종료 KOSDAQ 지수',
    today_buy_total_sell_count BIGINT NULL COMMENT '오늘 매수 총 매도 건수',
    today_buy_total_possess_count BIGINT NULL COMMENT '오늘 매수 총 보유 건수',
    today_buy_today_profitcut_count BIGINT NULL COMMENT '오늘 매수 당일 익절 건수',
    today_buy_today_profitcut_rate DOUBLE NULL COMMENT '오늘 매수 당일 익절률',
    today_buy_today_losscut_count BIGINT NULL COMMENT '오늘 매수 당일 손절 건수',
    today_buy_today_losscut_rate DOUBLE NULL COMMENT '오늘 매수 당일 손절률',
    today_buy_total_profitcut_count BIGINT NULL COMMENT '오늘 매수 총 익절 건수',
    today_buy_total_profitcut_rate DOUBLE NULL COMMENT '오늘 매수 총 익절률',
    today_buy_total_losscut_count BIGINT NULL COMMENT '오늘 매수 총 손절 건수',
    today_buy_total_losscut_rate DOUBLE NULL COMMENT '오늘 매수 총 손절률',
    today_buy_reinvest_count0_sell_count BIGINT NULL COMMENT '재투자 0회 매도 건수',
    today_buy_reinvest_count1_sell_count BIGINT NULL COMMENT '재투자 1회 매도 건수',
    today_buy_reinvest_count2_sell_count BIGINT NULL COMMENT '재투자 2회 매도 건수',
    today_buy_reinvest_count3_sell_count BIGINT NULL COMMENT '재투자 3회 매도 건수',
    today_buy_reinvest_count4_sell_count BIGINT NULL COMMENT '재투자 4회 매도 건수',
    today_buy_reinvest_count4_sell_profitcut_count BIGINT NULL COMMENT '재투자 4회 익절 건수',
    today_buy_reinvest_count4_sell_losscut_count BIGINT NULL COMMENT '재투자 4회 손절 건수',
    today_buy_reinvest_count5_sell_count BIGINT NULL COMMENT '재투자 5회 매도 건수',
    today_buy_reinvest_count5_sell_profitcut_count BIGINT NULL COMMENT '재투자 5회 익절 건수',
    today_buy_reinvest_count5_sell_losscut_count BIGINT NULL COMMENT '재투자 5회 손절 건수',
    today_buy_reinvest_count0_remain_count BIGINT NULL COMMENT '재투자 0회 보유 건수',
    today_buy_reinvest_count1_remain_count BIGINT NULL COMMENT '재투자 1회 보유 건수',
    today_buy_reinvest_count2_remain_count BIGINT NULL COMMENT '재투자 2회 보유 건수',
    today_buy_reinvest_count3_remain_count BIGINT NULL COMMENT '재투자 3회 보유 건수',
    today_buy_reinvest_count4_remain_count BIGINT NULL COMMENT '재투자 4회 보유 건수',
    today_buy_reinvest_count5_remain_count BIGINT NULL COMMENT '재투자 5회 보유 건수',
    KEY ix_date (`date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='일별 계좌 잔고 및 거래 통계';

-- Table created: jango_data

-- -----------------------------------------------------------------------------
-- 3. all_item_db 테이블
-- 설명: 모든 매수/매도 거래 내역을 저장하는 테이블
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS all_item_db (
    `index` BIGINT AUTO_INCREMENT PRIMARY KEY,
    id BIGINT NULL COMMENT 'ID',
    order_num VARCHAR(20) NULL COMMENT '주문번호',
    code VARCHAR(6) NOT NULL COMMENT '종목코드',
    code_name TEXT NULL COMMENT '종목명',
    rate DOUBLE NULL COMMENT '수익률',
    purchase_rate DOUBLE NULL COMMENT '매수 시점 수익률',
    purchase_price DOUBLE NULL COMMENT '매수가',
    present_price DOUBLE NULL COMMENT '현재가',
    valuation_price DOUBLE NULL COMMENT '평가금액',
    valuation_profit DOUBLE NULL COMMENT '평가손익',
    holding_amount BIGINT NULL COMMENT '보유수량',
    buy_date VARCHAR(20) NULL COMMENT '매수일시 (YYYYMMDDHHMI)',
    item_total_purchase DOUBLE NULL COMMENT '총 매수금액',
    chegyul_check BIGINT NULL COMMENT '체결 확인',
    reinvest_count BIGINT NULL COMMENT '재투자 횟수',
    reinvest_date TEXT NULL COMMENT '재투자 일시',
    invest_unit BIGINT NULL COMMENT '투자 단위',
    reinvest_unit DOUBLE NULL COMMENT '재투자 단위',
    sell_date VARCHAR(20) NULL DEFAULT '0' COMMENT '매도일시',
    sell_price DOUBLE NULL COMMENT '매도가',
    sell_rate DOUBLE NULL COMMENT '매도 수익률',
    rate_std DOUBLE NULL COMMENT '표준 수익률',
    rate_std_mod_val DOUBLE NULL COMMENT '수정 표준 수익률',
    rate_std_htr DOUBLE NULL COMMENT '보유기간 표준 수익률',
    rate_htr DOUBLE NULL COMMENT '보유기간 수익률',
    rate_std_mod_val_htr DOUBLE NULL COMMENT '보유기간 수정 표준 수익률',
    yes_close DOUBLE NULL COMMENT '전일 종가',
    `close` DOUBLE NULL COMMENT '종가',
    d1_diff_rate DOUBLE NULL COMMENT '1일 등락률',
    d1_diff DOUBLE NULL COMMENT '1일 등락폭',
    `open` DOUBLE NULL COMMENT '시가',
    high DOUBLE NULL COMMENT '고가',
    low DOUBLE NULL COMMENT '저가',
    volume BIGINT NULL COMMENT '거래량',
    clo5 DOUBLE NULL COMMENT '5일 종가',
    clo10 DOUBLE NULL COMMENT '10일 종가',
    clo20 DOUBLE NULL COMMENT '20일 종가',
    clo40 DOUBLE NULL COMMENT '40일 종가',
    clo60 DOUBLE NULL COMMENT '60일 종가',
    clo80 DOUBLE NULL COMMENT '80일 종가',
    clo100 DOUBLE NULL COMMENT '100일 종가',
    clo120 DOUBLE NULL COMMENT '120일 종가',
    clo5_diff_rate DOUBLE NULL COMMENT '5일 종가 대비 등락률',
    clo10_diff_rate DOUBLE NULL COMMENT '10일 종가 대비 등락률',
    clo20_diff_rate DOUBLE NULL COMMENT '20일 종가 대비 등락률',
    clo40_diff_rate DOUBLE NULL COMMENT '40일 종가 대비 등락률',
    clo60_diff_rate DOUBLE NULL COMMENT '60일 종가 대비 등락률',
    clo80_diff_rate DOUBLE NULL COMMENT '80일 종가 대비 등락률',
    clo100_diff_rate DOUBLE NULL COMMENT '100일 종가 대비 등락률',
    clo120_diff_rate DOUBLE NULL COMMENT '120일 종가 대비 등락률',
    KEY ix_code (code),
    KEY ix_buy_date (buy_date),
    KEY ix_sell_date (sell_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='모든 매수/매도 거래 내역';

-- Table created: all_item_db

-- -----------------------------------------------------------------------------
-- 4. possessed_item 테이블
-- 설명: 현재 보유 중인 종목 정보를 저장하는 테이블
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS possessed_item (
    `index` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `date` VARCHAR(20) NOT NULL COMMENT '날짜 (YYYYMMDD)',
    code VARCHAR(6) NOT NULL COMMENT '종목코드',
    code_name TEXT NULL COMMENT '종목명',
    holding_amount BIGINT NULL COMMENT '보유수량',
    puchase_price BIGINT NULL COMMENT '매수가',
    present_price BIGINT NULL COMMENT '현재가',
    valuation_profit BIGINT NULL COMMENT '평가손익',
    rate DOUBLE NULL COMMENT '수익률',
    item_total_purchase BIGINT NULL COMMENT '총 매수금액',
    KEY ix_date (`date`),
    KEY ix_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='현재 보유 종목 정보';

-- Table created: possessed_item

-- -----------------------------------------------------------------------------
-- 5. realtime_daily_buy_list 테이블
-- 설명: 실시간 일일 매수 대상 종목 리스트
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS realtime_daily_buy_list (
    `index` BIGINT AUTO_INCREMENT PRIMARY KEY,
    index2 BIGINT NULL,
    index3 BIGINT NULL,
    `date` VARCHAR(20) NOT NULL COMMENT '날짜 (YYYYMMDD)',
    check_item VARCHAR(20) NULL DEFAULT '0' COMMENT '체크 항목',
    code VARCHAR(6) NOT NULL COMMENT '종목코드',
    code_name TEXT NULL COMMENT '종목명',
    d1_diff_rate DOUBLE NULL COMMENT '1일 등락률',
    `close` DOUBLE NULL COMMENT '종가',
    `open` DOUBLE NULL COMMENT '시가',
    high DOUBLE NULL COMMENT '고가',
    low DOUBLE NULL COMMENT '저가',
    volume BIGINT NULL COMMENT '거래량',
    clo5 DOUBLE NULL COMMENT '5일 종가',
    clo10 DOUBLE NULL COMMENT '10일 종가',
    clo20 DOUBLE NULL COMMENT '20일 종가',
    clo40 DOUBLE NULL COMMENT '40일 종가',
    clo60 DOUBLE NULL COMMENT '60일 종가',
    clo80 DOUBLE NULL COMMENT '80일 종가',
    clo100 DOUBLE NULL COMMENT '100일 종가',
    clo120 DOUBLE NULL COMMENT '120일 종가',
    clo5_diff_rate DOUBLE NULL COMMENT '5일 종가 대비 등락률',
    clo10_diff_rate DOUBLE NULL COMMENT '10일 종가 대비 등락률',
    clo20_diff_rate DOUBLE NULL COMMENT '20일 종가 대비 등락률',
    clo40_diff_rate DOUBLE NULL COMMENT '40일 종가 대비 등락률',
    clo60_diff_rate DOUBLE NULL COMMENT '60일 종가 대비 등락률',
    clo80_diff_rate DOUBLE NULL COMMENT '80일 종가 대비 등락률',
    clo100_diff_rate DOUBLE NULL COMMENT '100일 종가 대비 등락률',
    clo120_diff_rate DOUBLE NULL COMMENT '120일 종가 대비 등락률',
    yes_clo5 DOUBLE NULL COMMENT '전일 5일 종가',
    yes_clo10 DOUBLE NULL COMMENT '전일 10일 종가',
    yes_clo20 DOUBLE NULL COMMENT '전일 20일 종가',
    yes_clo40 DOUBLE NULL COMMENT '전일 40일 종가',
    yes_clo60 DOUBLE NULL COMMENT '전일 60일 종가',
    yes_clo80 DOUBLE NULL COMMENT '전일 80일 종가',
    yes_clo100 DOUBLE NULL COMMENT '전일 100일 종가',
    yes_clo120 DOUBLE NULL COMMENT '전일 120일 종가',
    vol5 DOUBLE NULL COMMENT '5일 평균 거래량',
    vol10 DOUBLE NULL COMMENT '10일 평균 거래량',
    vol20 DOUBLE NULL COMMENT '20일 평균 거래량',
    vol40 DOUBLE NULL COMMENT '40일 평균 거래량',
    vol60 DOUBLE NULL COMMENT '60일 평균 거래량',
    vol80 DOUBLE NULL COMMENT '80일 평균 거래량',
    vol100 DOUBLE NULL COMMENT '100일 평균 거래량',
    vol120 DOUBLE NULL COMMENT '120일 평균 거래량',
    KEY ix_date (`date`),
    KEY ix_code (code),
    KEY ix_check_item (check_item)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='실시간 일일 매수 대상 종목 리스트';

-- Table created: realtime_daily_buy_list

-- -----------------------------------------------------------------------------
-- 6. today_profit_list 테이블
-- 설명: 오늘 수익 종목 리스트
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS today_profit_list (
    `index` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `date` VARCHAR(20) NOT NULL COMMENT '날짜 (YYYYMMDD)',
    code VARCHAR(6) NOT NULL COMMENT '종목코드',
    code_name TEXT NULL COMMENT '종목명',
    rate DOUBLE NULL COMMENT '수익률',
    KEY ix_date (`date`),
    KEY ix_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='오늘 수익 종목 리스트';

-- Table created: today_profit_list

-- =============================================================================
-- Schema Creation Complete
-- =============================================================================
-- JackBot1_imi1 database schema has been created successfully!
--
-- Created tables:
--   1. setting_data              - Bot configuration and state
--   2. jango_data                - Daily account balance and trading stats
--   3. all_item_db               - All buy/sell transaction records
--   4. possessed_item            - Currently held stocks
--   5. realtime_daily_buy_list   - Real-time daily buy target list
--   6. today_profit_list         - Today's profit stocks
--
-- Next steps:
--   1. Create daily_buy_list database and add pred_signal table
--   2. Create daily_craw database
--   3. Verify DB settings in library/cf.py
-- =============================================================================
