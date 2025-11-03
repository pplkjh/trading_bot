#!/usr/bin/env python3
"""Generate k=5/15 day signals and upsert into daily_buy_list.pred_signal."""
import argparse
import datetime as dt
import logging
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

from library import cf

DDL_PRED_SIGNAL = """
CREATE TABLE IF NOT EXISTS pred_signal (
  ref_date      DATE        NOT NULL,
  code          VARCHAR(6)  NOT NULL,
  pred_ret_5    DOUBLE      NULL,
  pred_std_5    DOUBLE      NULL,
  pred_ret_15   DOUBLE      NULL,
  pred_std_15   DOUBLE      NULL,
  regime        VARCHAR(16) NULL,
  updated_at    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (ref_date, code),
  KEY ix_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

LOGGER = logging.getLogger("ai_predict")


def build_engine():
    url = (
        f"mysql+pymysql://{cf.db_id}:{cf.db_passwd}@{cf.db_ip}:{cf.db_port}/"
        f"{cf.real_daily_buy_list_db_name}?charset=utf8mb4"
    )
    return create_engine(url, pool_pre_ping=True, future=True)


def ensure_table(engine):
    with engine.begin() as conn:
        conn.execute(text(DDL_PRED_SIGNAL))


def fetch_latest_table(engine, explicit: Optional[str] = None) -> str:
    if explicit:
        if not explicit.isdigit() or len(explicit) != 8:
            raise ValueError("date must be in YYYYMMDD format")
        return explicit

    query = text(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = :schema AND table_name REGEXP '^[0-9]{8}$'
        ORDER BY table_name DESC
        LIMIT 1
        """
    )
    with engine.begin() as conn:
        result = conn.execute(query, {"schema": cf.real_daily_buy_list_db_name}).scalar()
    if not result:
        raise RuntimeError("daily_buy_list에 대상 날짜 테이블이 없습니다.")
    return result


def load_daily_snapshot(engine, table_name: str) -> pd.DataFrame:
    if not table_name.isdigit():
        raise ValueError("table_name must be numeric")
    sql = text(f"SELECT * FROM `{table_name}`")
    return pd.read_sql_query(sql, engine)


def _vol_to_std(series: Optional[pd.Series]) -> pd.Series:
    if series is None:
        return pd.Series(dtype=float)
    arr = pd.to_numeric(series, errors="coerce")
    median = arr.median()
    if pd.isna(median) or median <= 0:
        median = 1.0
    std = (arr / median).abs()
    std = std.replace([np.inf, -np.inf], np.nan).fillna(1.0)
    return std.clip(lower=0.25, upper=4.0)


def compute_predictions(df: pd.DataFrame, ref_date: dt.date) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[
            "ref_date", "code", "pred_ret_5", "pred_std_5", "pred_ret_15", "pred_std_15", "regime"
        ])

    work = df.copy()
    work["code"] = work["code"].astype(str).str.zfill(6)

    ret5 = pd.to_numeric(work.get("clo5_diff_rate"), errors="coerce") / 100.0
    ret15 = pd.to_numeric(work.get("clo20_diff_rate"), errors="coerce") / 100.0

    pred = pd.DataFrame({
        "ref_date": ref_date,
        "code": work["code"],
        "pred_ret_5": ret5.fillna(0.0),
        "pred_ret_15": ret15.fillna(0.0),
        "pred_std_5": _vol_to_std(work.get("vol5")).reindex(work.index).fillna(1.0),
        "pred_std_15": _vol_to_std(work.get("vol20")).reindex(work.index).fillna(1.0),
    })

    def classify(row: pd.Series) -> str:
        if row.pred_ret_5 > 0.02 and row.pred_ret_15 > 0.03:
            return "bull"
        if row.pred_ret_5 < -0.02 and row.pred_ret_15 < -0.03:
            return "bear"
        return "neutral"

    pred["regime"] = pred.apply(classify, axis=1)
    return pred


def upsert_predictions(engine, df: pd.DataFrame, dry_run: bool = False) -> None:
    if df.empty:
        LOGGER.info("예측 결과가 비어 있습니다. upsert를 생략합니다.")
        return

    records = df.to_dict("records")
    sql = text(
        """
        INSERT INTO pred_signal
            (ref_date, code, pred_ret_5, pred_std_5, pred_ret_15, pred_std_15, regime)
        VALUES
            (:ref_date, :code, :pred_ret_5, :pred_std_5, :pred_ret_15, :pred_std_15, :regime)
        ON DUPLICATE KEY UPDATE
            pred_ret_5 = VALUES(pred_ret_5),
            pred_std_5 = VALUES(pred_std_5),
            pred_ret_15 = VALUES(pred_ret_15),
            pred_std_15 = VALUES(pred_std_15),
            regime = VALUES(regime),
            updated_at = CURRENT_TIMESTAMP
        """
    )

    if dry_run:
        LOGGER.info("Dry-run: upsert preview (상위 5개)\n%s", df.head())
        return

    with engine.begin() as conn:
        conn.execute(sql, records)
    LOGGER.info("pred_signal upsert 완료: %s rows", len(records))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update daily_buy_list.pred_signal with k=5/15 predictions")
    parser.add_argument("--date", help="YYYYMMDD 대상 일자 (미지정 시 최신 테이블)")
    parser.add_argument("--dry-run", action="store_true", help="DB 업데이트 없이 결과만 출력")
    return parser.parse_args()


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    args = parse_args()

    engine = build_engine()
    ensure_table(engine)

    table_name = fetch_latest_table(engine, args.date)
    ref_date = dt.datetime.strptime(table_name, "%Y%m%d").date()
    LOGGER.info("대상 일자: %s", ref_date)

    snapshot = load_daily_snapshot(engine, table_name)
    predictions = compute_predictions(snapshot, ref_date)
    upsert_predictions(engine, predictions, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
