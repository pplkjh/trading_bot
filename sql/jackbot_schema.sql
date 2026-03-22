-- ================================================
-- JackBot 데이터베이스 스키마 생성 스크립트 (v1.5.0)
-- ================================================
-- 데이터베이스: jackbot1_imi1 (모의투자) 또는 jackbot1 (실전)
-- 용도: 매매 실행, 포지션 관리, 성과 추적
-- ================================================
-- 실행 방법:
--   모의투자: mysql -u bot -p --default-character-set=utf8mb4 jackbot1_imi1 < jackbot_schema.sql
--   실전:     mysql -u bot -p --default-character-set=utf8mb4 jackbot1 < jackbot_schema.sql
--
-- ⚠️ 주의: DROP TABLE IF EXISTS로 기존 테이블을 삭제합니다!
--         기존 매매 데이터가 모두 손실됩니다!
-- ================================================

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

-- 주의: DATABASE 이름을 상황에 맞게 변경하세요!
-- USE jackbot1_imi1;  -- 모의투자
-- USE jackbot1;        -- 실전

-- 기존 테이블 삭제 (완전 재설치 시)
DROP TABLE IF EXISTS realtime_daily_buy_list;
DROP TABLE IF EXISTS possessed_item;
DROP TABLE IF EXISTS all_item_db;
DROP TABLE IF EXISTS jango_data;
DROP TABLE IF EXISTS setting_data;

-- ================================================
-- 1. setting_data: 전체 설정 관리
-- ================================================
CREATE TABLE IF NOT EXISTS setting_data (
    -- 투자 금액 설정
    loan_money INT DEFAULT 0 COMMENT '대출금',
    limit_money INT DEFAULT 0 COMMENT '최소 보유 현금',
    invest_unit INT DEFAULT 0 COMMENT '종목당 투자금액 (자동계산)',
    max_invest_unit INT DEFAULT 0 COMMENT '최대 투자금액',
    min_invest_unit INT DEFAULT 0 COMMENT '최소 투자금액',
    set_invest_unit VARCHAR(20) DEFAULT '0' COMMENT '투자금액 설정 여부',

    -- 실행 상태 플래그 (날짜 저장)
    code_update VARCHAR(20) DEFAULT '0' COMMENT '종목 업데이트 마지막 실행일',
    today_buy_stop VARCHAR(20) DEFAULT '0' COMMENT '당일 매수 중지 여부',
    jango_data_db_check VARCHAR(20) DEFAULT '0' COMMENT 'jango_data 업데이트 마지막 실행일',
    possessed_item VARCHAR(20) DEFAULT '0' COMMENT 'possessed_item 업데이트 마지막 실행일',
    today_profit VARCHAR(20) DEFAULT '0' COMMENT '당일 수익 계산 마지막 실행일',
    final_chegyul_check VARCHAR(20) DEFAULT '0' COMMENT '최종 체결 확인 마지막 실행일',
    db_to_buy_list VARCHAR(20) DEFAULT '0' COMMENT 'buy_list DB 업데이트 마지막 실행일',
    today_buy_list VARCHAR(20) DEFAULT '0' COMMENT '당일 매수리스트 생성 마지막 실행일',
    daily_crawler VARCHAR(20) DEFAULT '0' COMMENT '일봉 수집 마지막 실행일',
    min_crawler VARCHAR(20) DEFAULT '0' COMMENT '분봉 수집 마지막 실행일',
    daily_buy_list VARCHAR(20) DEFAULT '0' COMMENT '매수후보 분석 마지막 실행일'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='전체 시스템 설정 및 실행 상태 관리 (단일 row)';

-- 초기 데이터 삽입 (프로그램이 자동으로 생성하지만 명시적으로)
INSERT INTO setting_data (loan_money, limit_money, invest_unit)
VALUES (0, 0, 0)
ON DUPLICATE KEY UPDATE loan_money=loan_money;

-- ================================================
-- 2. jango_data: 일별 자산 및 성과 추적
-- ================================================
CREATE TABLE IF NOT EXISTS jango_data (
    date VARCHAR(20) PRIMARY KEY COMMENT '날짜 (YYYYMMDD)',

    -- 자산 정보
    total_asset BIGINT DEFAULT 0 COMMENT '총 자산 (예수금 + 보유주식평가금)',
    d2_deposit BIGINT DEFAULT 0 COMMENT 'D+2 예수금 (출금가능금액)',
    total_invest BIGINT DEFAULT 0 COMMENT '총 투자금액',

    -- 일일 수익
    today_profit BIGINT DEFAULT 0 COMMENT '당일 실현+미실현 수익',
    today_earning_rate DECIMAL(10,2) DEFAULT 0 COMMENT '당일 수익률 (%)',

    -- 매수/매도 통계
    today_buy_count INT DEFAULT 0 COMMENT '당일 매수 종목 수',
    today_sell_count INT DEFAULT 0 COMMENT '당일 매도 종목 수',
    today_buy_total_sell_count INT DEFAULT 0 COMMENT '당일 매수한 종목 중 매도된 수',
    today_buy_total_possess_count INT DEFAULT 0 COMMENT '당일 매수한 종목 중 보유 중인 수',

    -- 익절/손절 통계 (당일 매수 → 당일 매도)
    today_buy_today_profitcut_count INT DEFAULT 0 COMMENT '당일 익절 수',
    today_buy_today_profitcut_rate DECIMAL(10,2) DEFAULT 0 COMMENT '당일 익절률 (%)',
    today_buy_today_losscut_count INT DEFAULT 0 COMMENT '당일 손절 수',
    today_buy_today_losscut_rate DECIMAL(10,2) DEFAULT 0 COMMENT '당일 손절률 (%)',

    -- 익절/손절 통계 (당일 매수 → 전체 기간)
    today_buy_total_profitcut_count INT DEFAULT 0 COMMENT '당일 매수 종목의 누적 익절 수',
    today_buy_total_profitcut_rate DECIMAL(10,2) DEFAULT 0 COMMENT '당일 매수 종목의 누적 익절률',
    today_buy_total_losscut_count INT DEFAULT 0 COMMENT '당일 매수 종목의 누적 손절 수',
    today_buy_total_losscut_rate DECIMAL(10,2) DEFAULT 0 COMMENT '당일 매수 종목의 누적 손절률',

    INDEX idx_date (date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='일별 자산 및 매매 성과 추적';

-- ================================================
-- 3. all_item_db: 전체 매매 기록 (보유 + 매도 완료)
-- ================================================
CREATE TABLE IF NOT EXISTS all_item_db (
    `index` INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(10) NOT NULL COMMENT '종목코드',
    code_name VARCHAR(100) NOT NULL COMMENT '종목명',
    chegyul_check VARCHAR(10) DEFAULT '0' COMMENT '체결 확인 (0: 체결완료, 1: 미체결)',

    -- 매수 정보
    buy_date VARCHAR(20) NOT NULL COMMENT '매수일 (YYYYMMDD)',
    buy_time VARCHAR(20) COMMENT '매수시간 (HH:MM:SS)',
    purchase_price INT NOT NULL COMMENT '매수가',
    holding_amount INT NOT NULL COMMENT '보유 수량',

    -- 현재 상태 (보유 중인 경우 실시간 업데이트)
    present_price INT DEFAULT 0 COMMENT '현재가',
    rate DECIMAL(10,2) DEFAULT 0 COMMENT '수익률 (%)',
    valuation_profit BIGINT DEFAULT 0 COMMENT '평가손익',

    -- 매도 정보 (매도 완료 시에만 입력)
    sell_date VARCHAR(20) DEFAULT '0' COMMENT '매도일 (0: 보유중)',
    sell_time VARCHAR(20) COMMENT '매도시간',
    sell_price INT DEFAULT 0 COMMENT '매도가',
    sell_rate DECIMAL(10,2) DEFAULT 0 COMMENT '매도 수익률 (%)',
    realized_profit BIGINT DEFAULT 0 COMMENT '실현손익',

    -- 기술적 지표 (매수 당시)
    d1_diff_rate DECIMAL(10,2) DEFAULT 0 COMMENT 'D-1 대비 변동률',
    yes_close INT DEFAULT 0 COMMENT '전일 종가',
    volume BIGINT DEFAULT 0 COMMENT '거래량',
    today_percent DECIMAL(10,2) DEFAULT 0 COMMENT '당일 변동률',

    -- 이동평균선 (매수 당시)
    ma5 INT DEFAULT 0 COMMENT '5일 이동평균',
    ma10 INT DEFAULT 0 COMMENT '10일 이동평균',
    ma20 INT DEFAULT 0 COMMENT '20일 이동평균',
    ma60 INT DEFAULT 0 COMMENT '60일 이동평균',
    ma120 INT DEFAULT 0 COMMENT '120일 이동평균',

    INDEX idx_code (code),
    INDEX idx_buy_date (buy_date),
    INDEX idx_sell_date (sell_date),
    INDEX idx_code_sell (code, sell_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='전체 매매 기록 (보유 중 + 매도 완료)';

-- ================================================
-- 4. possessed_item: 현재 보유 종목 (키움 계좌 미러링)
-- ================================================
CREATE TABLE IF NOT EXISTS possessed_item (
    `index` INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(10) NOT NULL COMMENT '종목코드',
    code_name VARCHAR(100) NOT NULL COMMENT '종목명',

    -- 보유 정보
    holding_amount INT NOT NULL COMMENT '보유 수량',
    purchase_price INT NOT NULL COMMENT '매수가 (평균)',
    present_price INT NOT NULL COMMENT '현재가',

    -- 수익 정보
    valuation_profit BIGINT DEFAULT 0 COMMENT '평가손익',
    rate DECIMAL(10,2) DEFAULT 0 COMMENT '수익률 (%)',

    -- 매수일
    first_buy_date VARCHAR(20) COMMENT '최초 매수일',

    INDEX idx_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='현재 보유 종목 (키움 계좌와 동기화)';

-- ================================================
-- 5. realtime_daily_buy_list: 내일 매수할 종목 리스트
-- ================================================
CREATE TABLE IF NOT EXISTS realtime_daily_buy_list (
    `index` INT AUTO_INCREMENT PRIMARY KEY,
    date VARCHAR(20) NOT NULL COMMENT '기준일 (YYYYMMDD)',
    code VARCHAR(10) NOT NULL COMMENT '종목코드',
    code_name VARCHAR(100) NOT NULL COMMENT '종목명',

    -- 가격 정보
    d1_diff_rate DECIMAL(10,2) DEFAULT 0 COMMENT 'D-1 대비 변동률',
    close INT NOT NULL COMMENT '종가',
    open INT DEFAULT 0 COMMENT '시가',
    high INT DEFAULT 0 COMMENT '고가',
    low INT DEFAULT 0 COMMENT '저가',
    volume BIGINT DEFAULT 0 COMMENT '거래량',

    -- 이동평균선
    ma5 INT DEFAULT 0 COMMENT '5일 이동평균',
    ma10 INT DEFAULT 0 COMMENT '10일 이동평균',
    ma20 INT DEFAULT 0 COMMENT '20일 이동평균',
    ma40 INT DEFAULT 0 COMMENT '40일 이동평균',
    ma60 INT DEFAULT 0 COMMENT '60일 이동평균',
    ma80 INT DEFAULT 0 COMMENT '80일 이동평균',
    ma100 INT DEFAULT 0 COMMENT '100일 이동평균',
    ma120 INT DEFAULT 0 COMMENT '120일 이동평균',

    -- 하이브리드 전략 (v1.5.0+)
    strategy_type VARCHAR(50) DEFAULT 'basic' COMMENT '전략 타입 (date_based, momentum_breakout, mean_reversion, hybrid)',
    composite_score DECIMAL(10,2) DEFAULT 0 COMMENT '종합 스코어 (0-100)',
    volume_ratio DECIMAL(10,2) DEFAULT 1.0 COMMENT '거래량 비율 (현재/평균)',

    -- 기술적 지표 (v1.5.0+)
    rsi14 DECIMAL(10,2) DEFAULT 50.0 COMMENT 'RSI(14일)',
    bb_upper INT DEFAULT 0 COMMENT '볼린저 밴드 상단',
    bb_middle INT DEFAULT 0 COMMENT '볼린저 밴드 중간 (20일 MA)',
    bb_lower INT DEFAULT 0 COMMENT '볼린저 밴드 하단',
    atr14 INT DEFAULT 0 COMMENT 'ATR(14일) - Average True Range',

    -- 매수 실행 여부
    check_item VARCHAR(20) DEFAULT '0' COMMENT '매수 실행 시간 (0: 미실행)',

    INDEX idx_date (date),
    INDEX idx_code (code),
    INDEX idx_check (check_item),
    INDEX idx_strategy (strategy_type),
    INDEX idx_score (composite_score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='내일 매수할 종목 리스트 (collector가 생성, 하이브리드 전략 지원)';

-- ================================================
-- 완료 메시지
-- ================================================
SELECT '✅ setting_data 테이블 생성 완료!' as status;
SELECT '✅ jango_data 테이블 생성 완료!' as status;
SELECT '✅ all_item_db 테이블 생성 완료!' as status;
SELECT '✅ possessed_item 테이블 생성 완료!' as status;
SELECT '✅ realtime_daily_buy_list 테이블 생성 완료!' as status;

-- 테이블 목록 확인
SHOW TABLES;

-- ================================================
-- 참고:
-- - setting_data: 단일 row만 존재 (시스템 설정)
-- - jango_data: 일별 1 row (자산 추적)
-- - all_item_db: 매매할 때마다 추가 (히스토리)
-- - possessed_item: 키움 계좌 미러링 (실시간 동기화)
-- - realtime_daily_buy_list: collector가 매일 갱신
-- ================================================
