-- ================================================
-- MySQL 한글 깨짐 문제 해결 스크립트
-- ================================================
-- 실행 방법: mysql -u root -p < 02_fix_charset.sql
--
-- 문제: 테이블에 한글이 깨져서 이상한 문자로 보임
-- 원인: charset이 utf8mb4가 아닌 latin1 등으로 설정됨
-- 해결: 모든 데이터베이스와 테이블을 utf8mb4로 변환
-- ================================================

-- JackBot1_imi1 데이터베이스
ALTER DATABASE JackBot1_imi1 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE JackBot1_imi1;

ALTER TABLE setting_data CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE jango_data CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE all_item_db CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE possessed_item CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE realtime_daily_buy_list CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE today_profit_list CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- JackBot1 데이터베이스 (실전)
ALTER DATABASE JackBot1 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE JackBot1;

ALTER TABLE setting_data CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE jango_data CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE all_item_db CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE possessed_item CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE realtime_daily_buy_list CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE today_profit_list CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- daily_buy_list 데이터베이스
ALTER DATABASE daily_buy_list CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE daily_buy_list;

ALTER TABLE stock_item_all CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE pred_signal CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- daily_craw 데이터베이스
ALTER DATABASE daily_craw CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- min_craw 데이터베이스
ALTER DATABASE min_craw CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

SELECT '✅ Charset 변환 완료!' as status;

-- 확인
SELECT
    table_schema AS 'Database',
    table_name AS 'Table',
    table_collation AS 'Collation'
FROM information_schema.tables
WHERE table_schema IN ('JackBot1_imi1', 'JackBot1', 'daily_buy_list')
ORDER BY table_schema, table_name;
