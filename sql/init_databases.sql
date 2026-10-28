-- ================================================
-- 데이터베이스 초기화 스크립트 (v1.6.0)
-- v1.6.0: jackbot3_imi1 추가 (simul_num=3, 250점 HybridStrategyV2)
-- ================================================
-- 실행 방법: mysql -u root -p --default-character-set=utf8mb4 < init_databases.sql
--
-- ⚠️ 주의: 이 스크립트는 기존 데이터베이스를 삭제하고 새로 만듭니다!
--         모든 데이터가 손실되므로 백업 후 실행하세요!
-- ================================================

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

-- 0. 기존 데이터베이스 삭제 (선택사항 - 처음 설치 시 또는 완전 재설치 시)
-- DROP DATABASE IF EXISTS daily_craw;
-- DROP DATABASE IF EXISTS daily_buy_list;
-- DROP DATABASE IF EXISTS min_craw;
-- DROP DATABASE IF EXISTS jackbot1_imi1;
-- DROP DATABASE IF EXISTS jackbot1;
-- DROP DATABASE IF EXISTS jackbot3_imi1;

-- 1. 데이터베이스 생성
CREATE DATABASE IF NOT EXISTS daily_craw CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS daily_buy_list CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS min_craw CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS jackbot1_imi1 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS jackbot1 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS jackbot3_imi1 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS simulator3 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 2. 봇 사용자 생성 및 권한 부여
CREATE USER IF NOT EXISTS 'bot'@'localhost' IDENTIFIED BY 'qwer1232';
GRANT ALL PRIVILEGES ON daily_craw.* TO 'bot'@'localhost';
GRANT ALL PRIVILEGES ON daily_buy_list.* TO 'bot'@'localhost';
GRANT ALL PRIVILEGES ON min_craw.* TO 'bot'@'localhost';
GRANT ALL PRIVILEGES ON jackbot1_imi1.* TO 'bot'@'localhost';
GRANT ALL PRIVILEGES ON jackbot1.* TO 'bot'@'localhost';
GRANT ALL PRIVILEGES ON jackbot3_imi1.* TO 'bot'@'localhost';
GRANT ALL PRIVILEGES ON simulator3.* TO 'bot'@'localhost';
FLUSH PRIVILEGES;

-- 3. 생성 완료 확인
SELECT '✅ 데이터베이스 생성 완료!' as status;
SHOW DATABASES LIKE '%Jack%';
SHOW DATABASES LIKE '%daily%';
SHOW DATABASES LIKE '%min%';

SELECT '✅ 사용자 권한 설정 완료!' as status;
SHOW GRANTS FOR 'bot'@'localhost';

-- ================================================
-- 다음 단계:
-- 1. mysql -u bot -p daily_buy_list < stock_item_all_schema.sql
-- 2. mysql -u bot -p jackbot1_imi1 < jackbot_schema.sql
-- 3. mysql -u bot -p jackbot3_imi1 < jackbot_schema.sql  ← simul_num=3 신규
-- 4. python collector_v3.py 실행 (데이터 수집)
-- 5. python sql/migration_daily_buy_list.py 실행 (v2 지표 컬럼 마이그레이션)
-- ================================================
