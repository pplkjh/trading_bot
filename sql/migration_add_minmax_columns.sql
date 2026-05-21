-- max_high_pct / min_low_pct 컬럼 추가 migration
-- 실행 대상: 백테스트/실전에 사용하는 모든 jackbot*_imi1 DB
-- 실행법: mysql -u bot -p < sql/migration_add_minmax_columns.sql

ALTER TABLE jackbot3_imi1.all_item_db
    ADD COLUMN IF NOT EXISTS max_high_pct DECIMAL(10,4) DEFAULT 0 COMMENT '보유 중 최대 고가 수익률 (%)',
    ADD COLUMN IF NOT EXISTS min_low_pct  DECIMAL(10,4) DEFAULT 0 COMMENT '보유 중 최대 저가 손실률 (%)';

ALTER TABLE jackbot4_imi1.all_item_db
    ADD COLUMN IF NOT EXISTS max_high_pct DECIMAL(10,4) DEFAULT 0 COMMENT '보유 중 최대 고가 수익률 (%)',
    ADD COLUMN IF NOT EXISTS min_low_pct  DECIMAL(10,4) DEFAULT 0 COMMENT '보유 중 최대 저가 손실률 (%)';

ALTER TABLE jackbot5_imi1.all_item_db
    ADD COLUMN IF NOT EXISTS max_high_pct DECIMAL(10,4) DEFAULT 0 COMMENT '보유 중 최대 고가 수익률 (%)',
    ADD COLUMN IF NOT EXISTS min_low_pct  DECIMAL(10,4) DEFAULT 0 COMMENT '보유 중 최대 저가 손실률 (%)';

ALTER TABLE jackbot6_imi1.all_item_db
    ADD COLUMN IF NOT EXISTS max_high_pct DECIMAL(10,4) DEFAULT 0 COMMENT '보유 중 최대 고가 수익률 (%)',
    ADD COLUMN IF NOT EXISTS min_low_pct  DECIMAL(10,4) DEFAULT 0 COMMENT '보유 중 최대 저가 손실률 (%)';
