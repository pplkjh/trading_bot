-- ================================================
-- 테이블 재생성 스크립트
-- ================================================
-- 문제: 수동 생성한 테이블과 프로그램이 기대하는 구조가 다름
-- 해결: 테이블 삭제 후 프로그램이 자동 생성하도록 함
-- ================================================
-- 실행: mysql -u bot -p JackBot1_imi1 < reset_tables.sql
-- ================================================

USE JackBot1_imi1;

-- 기존 테이블 삭제 (프로그램이 자동 생성하도록)
DROP TABLE IF EXISTS jango_data;
DROP TABLE IF EXISTS all_item_db;
DROP TABLE IF EXISTS possessed_item;
DROP TABLE IF EXISTS realtime_daily_buy_list;

-- setting_data는 유지 (초기 설정값 포함)
-- DROP TABLE IF EXISTS setting_data;

SELECT '✅ 테이블 초기화 완료!' as status;
SELECT '이제 collector_v3.py를 다시 실행하면 테이블이 자동 생성됩니다.' as next_step;

-- 남은 테이블 확인
SHOW TABLES;
