# -*- coding: utf-8 -*-
"""
NASDAQ / SOX 지수 historical data backfill
daily_craw DB의 nasdaq_index, sox_index 테이블에 저장.

yfinance 불필요 — Yahoo Finance v8 API 직접 호출 (requests + pandas만 사용).

사용법:
    python backfill_nasdaq_data.py
    python backfill_nasdaq_data.py --start 20230101
"""
import sys
import os
import argparse
import datetime
import time
import requests
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from library import cf
from sqlalchemy import create_engine

TICKERS = {
    '^IXIC': 'nasdaq_index',
    '^SOX':  'sox_index',
}

DEFAULT_START = '20230101'
TODAY = datetime.datetime.now().strftime('%Y%m%d')

_YF_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    )
}


def parse_args():
    p = argparse.ArgumentParser(description='NASDAQ/SOX historical backfill')
    p.add_argument('--start', default=DEFAULT_START,
                   help=f'시작일 YYYYMMDD (기본: {DEFAULT_START})')
    return p.parse_args()


def get_engine():
    url = (f"mysql+pymysql://{cf.db_id}:{cf.db_passwd}"
           f"@{cf.db_ip}:{cf.db_port}/{cf.real_daily_craw_db_name}?charset=utf8mb4")
    return create_engine(url)


def yahoo_download(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Yahoo Finance v8 API 직접 호출 (yfinance 미사용)."""
    period1 = int(pd.to_datetime(start_date, format='%Y%m%d').timestamp())
    period2 = int((pd.to_datetime(end_date, format='%Y%m%d')
                   + pd.Timedelta(days=1)).timestamp())

    encoded = ticker.replace('^', '%5E')
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}"
           f"?period1={period1}&period2={period2}&interval=1d")

    resp = requests.get(url, headers=_YF_HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    result = data['chart']['result'][0]
    timestamps = result['timestamp']
    q = result['indicators']['quote'][0]

    df = pd.DataFrame({
        'date':   pd.to_datetime(timestamps, unit='s').strftime('%Y%m%d'),
        'open':   q.get('open'),
        'high':   q.get('high'),
        'low':    q.get('low'),
        'close':  q.get('close'),
        'volume': q.get('volume'),
    })
    return df.dropna(subset=['close'])


def pull_and_store(engine, ticker: str, table_name: str,
                   start_date: str, end_date: str) -> int:
    print(f"  {ticker} → {table_name} 다운로드...", end=' ', flush=True)
    try:
        df = yahoo_download(ticker, start_date, end_date)
    except Exception as e:
        print(f"실패: {e}")
        return 0

    if df.empty:
        print("데이터 없음")
        return 0

    # 이미 존재하는 날짜 제외
    try:
        existing = pd.read_sql(f"SELECT date FROM `{table_name}`", engine)
        existing_dates = set(existing['date'].astype(str).tolist())
        df = df[~df['date'].isin(existing_dates)]
    except Exception:
        pass  # 테이블 없으면 전체 삽입

    if df.empty:
        print("신규 없음 (모두 기존)")
        return 0

    df.to_sql(table_name, engine, if_exists='append', index=False)
    print(f"{len(df)}행 저장 ({df['date'].min()} ~ {df['date'].max()})")
    return len(df)


def main():
    args = parse_args()

    print(f"\n{'='*60}")
    print(f"NASDAQ / SOX 지수 Backfill")
    print(f"  대상: {list(TICKERS.keys())}")
    print(f"  기간: {args.start} ~ {TODAY}")
    print(f"{'='*60}\n")

    engine = get_engine()
    total = 0
    for ticker, table_name in TICKERS.items():
        n = pull_and_store(engine, ticker, table_name, args.start, TODAY)
        total += n
        time.sleep(1)  # Yahoo Finance 속도 제한 방지

    print(f"\n완료: 총 {total}행 저장")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
