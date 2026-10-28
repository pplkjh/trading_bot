-- ================================================
-- 완전 재설치 스크립트 (v1.5.0)
-- ================================================
-- ⚠️⚠️⚠️ 경고: 모든 데이터가 삭제됩니다! ⚠️⚠️⚠️
--
-- 이 스크립트는 다음을 수행합니다:
-- 1. 기존 데이터베이스 완전 삭제
-- 2. 새 데이터베이스 생성
-- 3. 사용자 및 권한 설정
-- 4. 테이블 생성 (v1.5.0 하이브리드 전략 지원)
--
-- 실행 방법: mysql -u root -p --default-character-set=utf8mb4 < reset_and_rebuild.sql
-- ================================================

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

-- ================================================
-- 1단계: 기존 환경 완전 삭제
-- ================================================
SELECT '⚠️  1단계: 기존 데이터베이스 삭제 중...' as status;

DROP DATABASE IF EXISTS daily_craw;
DROP DATABASE IF EXISTS daily_buy_list;
DROP DATABASE IF EXISTS min_craw;
DROP DATABASE IF EXISTS jackbot1_imi1;
DROP DATABASE IF EXISTS jackbot1;

DROP USER IF EXISTS 'bot'@'localhost';

SELECT '✅ 기존 환경 삭제 완료!' as status;

-- ================================================
-- 2단계: 새 데이터베이스 생성
-- ================================================
SELECT '📦 2단계: 새 데이터베이스 생성 중...' as status;

CREATE DATABASE daily_craw CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE daily_buy_list CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE min_craw CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE jackbot1_imi1 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE jackbot1 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

SELECT '✅ 데이터베이스 생성 완료!' as status;

-- ================================================
-- 3단계: 사용자 생성 및 권한 부여
-- ================================================
SELECT '👤 3단계: 사용자 생성 및 권한 설정 중...' as status;

CREATE USER 'bot'@'localhost' IDENTIFIED BY 'qwer1232';
GRANT ALL PRIVILEGES ON daily_craw.* TO 'bot'@'localhost';
GRANT ALL PRIVILEGES ON daily_buy_list.* TO 'bot'@'localhost';
GRANT ALL PRIVILEGES ON min_craw.* TO 'bot'@'localhost';
GRANT ALL PRIVILEGES ON jackbot1_imi1.* TO 'bot'@'localhost';
GRANT ALL PRIVILEGES ON jackbot1.* TO 'bot'@'localhost';
FLUSH PRIVILEGES;

SELECT '✅ 사용자 및 권한 설정 완료!' as status;

-- ================================================
-- 완료 메시지
-- ================================================
SELECT '
========================================
✅ DB 재설치 완료!
========================================

다음 단계:
1. mysql -u bot -p daily_buy_list < sql/stock_item_all_schema.sql
2. mysql -u bot -p jackbot1_imi1 < sql/jackbot_schema.sql
3. python collector_v3.py (약 23시간 소요)

비밀번호: qwer1232
========================================
' as '완료';

-- ================================================
-- 참고:
-- - 이 스크립트는 데이터베이스만 생성합니다
-- - 테이블은 별도 스크립트로 생성하세요
-- - daily_buy_list의 날짜 테이블은 collector가 자동 생성합니다
-- ================================================
