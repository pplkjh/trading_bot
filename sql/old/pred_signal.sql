-- 파일명: sql/pred_signal.sql (한 번만 실행)
CREATE TABLE IF NOT EXISTS daily_buy_list.pred_signal (
ref_date DATE NOT NULL,
code VARCHAR(6) NOT NULL,
pred_ret_5 DOUBLE NULL,
pred_std_5 DOUBLE NULL,
pred_ret_15 DOUBLE NULL,
pred_std_15 DOUBLE NULL,
regime VARCHAR(16) NULL,
updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
PRIMARY KEY (ref_date, code),
KEY ix_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
