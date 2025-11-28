-- ================================================
-- 테이블 초기화 스크립트 (문제 발생시 복구용)
-- ================================================
-- 실행 방법: mysql -u root -p < 03_reset_tables.sql
--
-- 주의: 이 스크립트는 모든 데이터를 삭제합니다!
-- 데이터베이스 구조에 문제가 생겼을 때만 사용하세요.
-- ================================================

-- ================================================
-- 옵션 1: JackBot1_imi1 (모의투자) 테이블만 초기화
-- ================================================
USE JackBot1_imi1;

DROP TABLE IF EXISTS jango_data;
DROP TABLE IF EXISTS all_item_db;
DROP TABLE IF EXISTS possessed_item;
DROP TABLE IF EXISTS realtime_daily_buy_list;
DROP TABLE IF EXISTS today_profit_list;
-- setting_data는 유지 (초기 설정값 포함)

SELECT '✅ JackBot1_imi1 테이블 초기화 완료!' as status;

-- ================================================
-- 옵션 2: JackBot1 (실전) 테이블 초기화 (주석 해제하여 사용)
-- ================================================
-- USE JackBot1;
--
-- DROP TABLE IF EXISTS jango_data;
-- DROP TABLE IF EXISTS all_item_db;
-- DROP TABLE IF EXISTS possessed_item;
-- DROP TABLE IF EXISTS realtime_daily_buy_list;
-- DROP TABLE IF EXISTS today_profit_list;
--
-- SELECT '✅ JackBot1 테이블 초기화 완료!' as status;

-- ================================================
-- 옵션 3: daily_buy_list 초기화 (주석 해제하여 사용)
-- ================================================
-- USE daily_buy_list;
--
-- DROP TABLE IF EXISTS stock_item_all;
-- DROP TABLE IF EXISTS pred_signal;
--
-- SELECT '✅ daily_buy_list 테이블 초기화 완료!' as status;

-- ================================================
-- 옵션 4: KIND 관련 테이블만 초기화 (잘못된 날짜 데이터 삭제)
-- ================================================
USE daily_buy_list;

DROP TABLE IF EXISTS stock_invest_warning;
DROP TABLE IF EXISTS stock_invest_danger;
DROP TABLE IF EXISTS stock_invest_caution;

SELECT '✅ KIND 테이블 초기화 완료 (collector가 자동 재생성)' as status;

-- ================================================
-- 다음 단계
-- ================================================
SELECT '
테이블 초기화 완료!

다음 단계:
1. mysql -u root -p < 01_setup_all.sql  (테이블 재생성)
2. python collector_v3.py               (데이터 수집)

' as '다음 단계';

-- 남은 테이블 확인
SHOW TABLES FROM JackBot1_imi1;
SHOW TABLES FROM daily_buy_list;
