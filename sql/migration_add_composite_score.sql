-- migration_add_composite_score.sql
-- jackbot3_imi1.all_item_db 에 스코어 컬럼 추가 (이미 있는 컬럼은 스킵)
-- 실행: mysql -u bot -p < sql/migration_add_composite_score.sql

-- composite_score
SET @sql = IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA='jackbot3_imi1' AND TABLE_NAME='all_item_db' AND COLUMN_NAME='composite_score') > 0,
    'SELECT "composite_score 이미 존재 — 스킵" AS result',
    'ALTER TABLE jackbot3_imi1.all_item_db ADD COLUMN composite_score INT DEFAULT 0 COMMENT "매수 시점 hybrid_strategy_v2 총점 (0-200)"'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- score_a (모멘텀, 50pt)
SET @sql = IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA='jackbot3_imi1' AND TABLE_NAME='all_item_db' AND COLUMN_NAME='score_a') > 0,
    'SELECT "score_a 이미 존재 — 스킵" AS result',
    'ALTER TABLE jackbot3_imi1.all_item_db ADD COLUMN score_a DECIMAL(6,2) DEFAULT 0 COMMENT "A. 모멘텀 (50pt)"'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- score_b (평균회귀, 20pt)
SET @sql = IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA='jackbot3_imi1' AND TABLE_NAME='all_item_db' AND COLUMN_NAME='score_b') > 0,
    'SELECT "score_b 이미 존재 — 스킵" AS result',
    'ALTER TABLE jackbot3_imi1.all_item_db ADD COLUMN score_b DECIMAL(6,2) DEFAULT 0 COMMENT "B. 평균회귀 (20pt)"'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- score_c (추세강도, 50pt)
SET @sql = IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA='jackbot3_imi1' AND TABLE_NAME='all_item_db' AND COLUMN_NAME='score_c') > 0,
    'SELECT "score_c 이미 존재 — 스킵" AS result',
    'ALTER TABLE jackbot3_imi1.all_item_db ADD COLUMN score_c DECIMAL(6,2) DEFAULT 0 COMMENT "C. 추세강도 (50pt)"'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- score_d (거래량, 40pt)
SET @sql = IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA='jackbot3_imi1' AND TABLE_NAME='all_item_db' AND COLUMN_NAME='score_d') > 0,
    'SELECT "score_d 이미 존재 — 스킵" AS result',
    'ALTER TABLE jackbot3_imi1.all_item_db ADD COLUMN score_d DECIMAL(6,2) DEFAULT 0 COMMENT "D. 거래량 (40pt)"'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- score_e (시장상대강도, 30pt)
SET @sql = IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA='jackbot3_imi1' AND TABLE_NAME='all_item_db' AND COLUMN_NAME='score_e') > 0,
    'SELECT "score_e 이미 존재 — 스킵" AS result',
    'ALTER TABLE jackbot3_imi1.all_item_db ADD COLUMN score_e DECIMAL(6,2) DEFAULT 0 COMMENT "E. 시장상대강도 (30pt)"'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- score_f (다중시간프레임, 10pt)
SET @sql = IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA='jackbot3_imi1' AND TABLE_NAME='all_item_db' AND COLUMN_NAME='score_f') > 0,
    'SELECT "score_f 이미 존재 — 스킵" AS result',
    'ALTER TABLE jackbot3_imi1.all_item_db ADD COLUMN score_f DECIMAL(6,2) DEFAULT 0 COMMENT "F. 다중시간프레임 (10pt)"'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- score_penalty (변동성 패널티)
SET @sql = IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA='jackbot3_imi1' AND TABLE_NAME='all_item_db' AND COLUMN_NAME='score_penalty') > 0,
    'SELECT "score_penalty 이미 존재 — 스킵" AS result',
    'ALTER TABLE jackbot3_imi1.all_item_db ADD COLUMN score_penalty DECIMAL(6,2) DEFAULT 0 COMMENT "변동성 패널티"'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- simul_num (알고리즘 번호)
SET @sql = IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA='jackbot3_imi1' AND TABLE_NAME='all_item_db' AND COLUMN_NAME='simul_num') > 0,
    'SELECT "simul_num 이미 존재 — 스킵" AS result',
    'ALTER TABLE jackbot3_imi1.all_item_db ADD COLUMN simul_num INT DEFAULT 3 COMMENT "알고리즘 번호 (simul_num)"'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT '✅ 마이그레이션 완료' AS result;
