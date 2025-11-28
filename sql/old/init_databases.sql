-- ================================================
-- 데이터베이스 초기화 스크립트
-- ================================================
-- 실행 방법: mysql -u root -p < init_databases.sql
--
-- 주의: 이 스크립트는 데이터베이스를 새로 만듭니다.
--      기존 데이터가 있다면 삭제되므로 주의하세요!
-- ================================================

-- 1. 데이터베이스 생성
CREATE DATABASE IF NOT EXISTS daily_craw CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS daily_buy_list CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS min_craw CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS JackBot1_imi1 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS JackBot1 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 2. 봇 사용자 생성 및 권한 부여
CREATE USER IF NOT EXISTS 'root'@'localhost' IDENTIFIED BY 'qwer1234';
GRANT ALL PRIVILEGES ON daily_craw.* TO 'root'@'localhost';
GRANT ALL PRIVILEGES ON daily_buy_list.* TO 'root'@'localhost';
GRANT ALL PRIVILEGES ON min_craw.* TO 'root'@'localhost';
GRANT ALL PRIVILEGES ON JackBot1_imi1.* TO 'root'@'localhost';
GRANT ALL PRIVILEGES ON JackBot1.* TO 'root'@'localhost';
FLUSH PRIVILEGES;

-- 3. 생성 완료 확인
SELECT '✅ 데이터베이스 생성 완료!' as status;
SHOW DATABASES LIKE '%Jack%';
SHOW DATABASES LIKE '%daily%';
SHOW DATABASES LIKE '%min%';

SELECT '✅ 사용자 권한 설정 완료!' as status;
SHOW GRANTS FOR 'root'@'localhost';

-- ================================================
-- 다음 단계:
-- 1. mysql -u root -p daily_buy_list < stock_item_all_schema.sql
-- 2. mysql -u root -p JackBot1_imi1 < jackbot_schema.sql
-- 3. python collector_v3.py 실행 (데이터 수집)
-- ================================================
