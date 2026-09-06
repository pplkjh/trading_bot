-- max_high_pct / min_low_pct 컬럼 추가 migration
-- MySQL 5.x 호환 (ADD COLUMN IF NOT EXISTS 미지원 버전용)
-- 아래 Python 스크립트로 실행 권장:
--   python sql/migration_add_minmax_columns.py
--
-- 직접 SQL 실행 시 컬럼이 이미 있으면 에러 발생. 아래는 참고용 DDL.

ALTER TABLE jackbot3_imi1.all_item_db
    ADD COLUMN max_high_pct DECIMAL(10,4) DEFAULT 0 COMMENT '보유 중 최대 고가 수익률 (%)',
    ADD COLUMN min_low_pct  DECIMAL(10,4) DEFAULT 0 COMMENT '보유 중 최대 저가 손실률 (%)';

ALTER TABLE jackbot4_imi1.all_item_db
    ADD COLUMN max_high_pct DECIMAL(10,4) DEFAULT 0 COMMENT '보유 중 최대 고가 수익률 (%)',
    ADD COLUMN min_low_pct  DECIMAL(10,4) DEFAULT 0 COMMENT '보유 중 최대 저가 손실률 (%)';

ALTER TABLE jackbot5_imi1.all_item_db
    ADD COLUMN max_high_pct DECIMAL(10,4) DEFAULT 0 COMMENT '보유 중 최대 고가 수익률 (%)',
    ADD COLUMN min_low_pct  DECIMAL(10,4) DEFAULT 0 COMMENT '보유 중 최대 저가 손실률 (%)';

ALTER TABLE jackbot6_imi1.all_item_db
    ADD COLUMN max_high_pct DECIMAL(10,4) DEFAULT 0 COMMENT '보유 중 최대 고가 수익률 (%)',
    ADD COLUMN min_low_pct  DECIMAL(10,4) DEFAULT 0 COMMENT '보유 중 최대 저가 손실률 (%)';
