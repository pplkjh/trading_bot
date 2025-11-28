-- ================================================
-- stock_item_all 테이블 생성 스크립트
-- ================================================
-- 데이터베이스: daily_buy_list
-- 용도: 전체 종목 리스트 및 수집 상태 관리
-- ================================================
-- 실행 방법: mysql -u root -p daily_buy_list < stock_item_all_schema.sql
-- ================================================

USE daily_buy_list;

-- stock_item_all 테이블 생성
CREATE TABLE IF NOT EXISTS stock_item_all (
    code VARCHAR(10) PRIMARY KEY COMMENT '종목코드 (6자리)',
    code_name VARCHAR(100) NOT NULL COMMENT '종목명',
    check_item TINYINT DEFAULT 0 COMMENT '활성 종목 여부 (0:비활성, 1:활성)',
    check_daily_crawler TINYINT DEFAULT 0 COMMENT '일봉 수집 상태 (0:미수집, 1:완료, 3:과거완료, 4:업데이트필요)',
    check_min_crawler TINYINT DEFAULT 0 COMMENT '분봉 수집 상태 (0:미수집, 1:완료)',

    -- 종목 분류
    market VARCHAR(10) COMMENT '시장 구분 (KOSPI, KOSDAQ, KONEX, ETF)',
    sector VARCHAR(50) COMMENT '업종',

    -- 관리 정보
    is_managing TINYINT DEFAULT 0 COMMENT '관리종목 여부',
    is_insincerity TINYINT DEFAULT 0 COMMENT '불성실법인종목 여부',
    is_suspended TINYINT DEFAULT 0 COMMENT '거래정지 여부',

    -- 시간 정보
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '생성일시',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정일시',

    INDEX idx_check_item (check_item),
    INDEX idx_market (market),
    INDEX idx_check_daily (check_daily_crawler),
    INDEX idx_check_min (check_min_crawler)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='전체 종목 리스트 및 수집 상태 관리';

-- pred_signal 테이블 (AI 예측 시그널) - 기존 파일 내용 통합
CREATE TABLE IF NOT EXISTS pred_signal (
    ref_date DATE NOT NULL COMMENT '기준일',
    code VARCHAR(6) NOT NULL COMMENT '종목코드',
    pred_ret_5 DOUBLE NULL COMMENT '5일 예측 수익률',
    pred_std_5 DOUBLE NULL COMMENT '5일 예측 표준편차',
    pred_ret_15 DOUBLE NULL COMMENT '15일 예측 수익률',
    pred_std_15 DOUBLE NULL COMMENT '15일 예측 표준편차',
    regime VARCHAR(16) NULL COMMENT '시장 국면',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (ref_date, code),
    KEY ix_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='AI 모델 예측 시그널';

-- 완료 메시지
SELECT '✅ stock_item_all 테이블 생성 완료!' as status;
SELECT '✅ pred_signal 테이블 생성 완료!' as status;

-- 테이블 구조 확인
SHOW TABLES;
DESC stock_item_all;
DESC pred_signal;

-- ================================================
-- 참고:
-- - collector_v3.py 실행 시 이 테이블에 종목 정보가 자동 입력됩니다
-- - check_item=1인 종목만 매매 대상입니다
-- - 일봉 데이터는 daily_craw DB에 종목코드별로 테이블 생성됩니다
-- - 예: daily_craw.`005930` (삼성전자)
-- ================================================
