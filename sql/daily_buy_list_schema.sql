-- =============================================================================
-- Daily Buy List Database Schema
-- =============================================================================
-- 파일명: sql/daily_buy_list_schema.sql
-- 설명: 일일 매수 리스트 데이터베이스(daily_buy_list) 스키마
-- 실행 방법:
--   1. mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS daily_buy_list CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
--   2. mysql -u root -p daily_buy_list < sql/daily_buy_list_schema.sql
--   3. mysql -u root -p daily_buy_list < sql/pred_signal.sql
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. pred_signal 테이블 (이미 별도 파일로 존재)
-- 설명: AI 예측 신호 데이터를 저장하는 테이블
-- 주의: 이 테이블은 pred_signal.sql 파일을 통해 생성됩니다
-- -----------------------------------------------------------------------------

-- -----------------------------------------------------------------------------
-- 2. stock_insincerity 테이블
-- 설명: 불성실 공시 종목 정보
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_insincerity (
    `index` BIGINT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(6) NOT NULL COMMENT '종목코드',
    insincerity TEXT NULL COMMENT '불성실 공시 내용',
    KEY ix_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='불성실 공시 종목 정보';

SELECT '✓ stock_insincerity 테이블 생성 완료!' as status;

-- -----------------------------------------------------------------------------
-- 3. stock_managing 테이블
-- 설명: 관리 종목 정보
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_managing (
    `index` BIGINT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(6) NOT NULL COMMENT '종목코드',
    managing TEXT NULL COMMENT '관리 종목 사유',
    KEY ix_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='관리 종목 정보';

SELECT '✓ stock_managing 테이블 생성 완료!' as status;

-- =============================================================================
-- 날짜별 테이블 설명
-- =============================================================================
-- daily_buy_list 데이터베이스에는 위의 고정 테이블 외에도
-- 날짜별로 동적으로 생성되는 테이블들이 있습니다.
--
-- 테이블명 형식: YYYYMMDD (예: 20231215, 20231216 등)
--
-- 날짜별 테이블 구조:
-- CREATE TABLE IF NOT EXISTS `YYYYMMDD` (
--     `index` BIGINT AUTO_INCREMENT PRIMARY KEY,
--     index2 BIGINT NULL,
--     `date` VARCHAR(20) NOT NULL,
--     check_item VARCHAR(20) NULL DEFAULT '0',
--     code VARCHAR(6) NOT NULL,
--     code_name TEXT NULL,
--     d1_diff_rate DOUBLE NULL,
--     `close` DOUBLE NULL,
--     `open` DOUBLE NULL,
--     high DOUBLE NULL,
--     low DOUBLE NULL,
--     volume BIGINT NULL,
--     clo5 DOUBLE NULL,
--     clo10 DOUBLE NULL,
--     clo20 DOUBLE NULL,
--     clo40 DOUBLE NULL,
--     clo60 DOUBLE NULL,
--     clo80 DOUBLE NULL,
--     clo100 DOUBLE NULL,
--     clo120 DOUBLE NULL,
--     clo5_diff_rate DOUBLE NULL,
--     clo10_diff_rate DOUBLE NULL,
--     clo20_diff_rate DOUBLE NULL,
--     clo40_diff_rate DOUBLE NULL,
--     clo60_diff_rate DOUBLE NULL,
--     clo80_diff_rate DOUBLE NULL,
--     clo100_diff_rate DOUBLE NULL,
--     clo120_diff_rate DOUBLE NULL,
--     yes_clo5 DOUBLE NULL,
--     yes_clo10 DOUBLE NULL,
--     yes_clo20 DOUBLE NULL,
--     yes_clo40 DOUBLE NULL,
--     yes_clo60 DOUBLE NULL,
--     yes_clo80 DOUBLE NULL,
--     yes_clo100 DOUBLE NULL,
--     yes_clo120 DOUBLE NULL,
--     vol5 DOUBLE NULL,
--     vol10 DOUBLE NULL,
--     vol20 DOUBLE NULL,
--     vol40 DOUBLE NULL,
--     vol60 DOUBLE NULL,
--     vol80 DOUBLE NULL,
--     vol100 DOUBLE NULL,
--     vol120 DOUBLE NULL,
--     KEY ix_code (code)
-- ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
--
-- 이러한 날짜별 테이블은 library/daily_buy_list.py의 코드에 의해
-- 자동으로 생성되며, cf.py의 start_daily_buy_list 변수(기본값: 20200102)부터
-- 시작하여 일별로 매수 대상 종목 데이터를 저장합니다.
-- =============================================================================

SELECT '
=============================================================================
daily_buy_list 데이터베이스 스키마 생성이 완료되었습니다!

생성된 테이블:
  1. pred_signal         - AI 예측 신호 (pred_signal.sql로 별도 생성 필요)
  2. stock_insincerity   - 불성실 공시 종목 정보
  3. stock_managing      - 관리 종목 정보

동적 테이블:
  - 날짜별 테이블 (YYYYMMDD 형식)은 collector 실행 시 자동 생성됩니다

다음 단계:
  1. sql/pred_signal.sql 파일 실행
  2. collector_v3.py 실행으로 날짜별 테이블 생성
=============================================================================
' as '완료 메시지';
