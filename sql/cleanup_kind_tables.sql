-- KIND 테이블 정리 (잘못된 날짜 데이터 삭제)
-- 실행: mysql -u bot -p daily_buy_list < sql/cleanup_kind_tables.sql

USE daily_buy_list;

-- 투자경고/위험/주의 종목 테이블 초기화
DROP TABLE IF EXISTS stock_invest_warning;
DROP TABLE IF EXISTS stock_invest_danger;
DROP TABLE IF EXISTS stock_invest_caution;

-- 테이블은 KIND 크롤러가 자동으로 재생성합니다
SELECT 'KIND 테이블을 초기화했습니다. collector를 실행하면 2023-01-02부터 다시 수집됩니다.' as message;
