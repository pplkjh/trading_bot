# -*- coding: utf-8 -*-
"""
투자 운용보고서 수동 생성 스크립트

Usage:
  python scripts/generate_report.py          # 기본 DB (cf.imi1_db_name)
  python scripts/generate_report.py --watch  # 60초 간격 자동 갱신 (Ctrl+C 종료)

출력: reports/투자운용보고서.xlsx
"""
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import os
import datetime
import time

os.environ.setdefault('JACKBOT_LOG_FILE',
    f"generate_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
os.environ.setdefault('JACKBOT_LOG_NAME', 'report')

from sqlalchemy import create_engine
from library import cf
from library.investment_report import InvestmentReport


def make_engine(db_name):
    url = (f"mysql+pymysql://{cf.db_id}:{cf.db_passwd}"
           f"@{cf.db_ip}:{cf.db_port}/{db_name}?charset=utf8")
    return create_engine(url)


def run_once(reporter):
    print(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] 보고서 생성 중...")
    saved = reporter.generate()
    if saved:
        print(f"✅ 저장 완료: {saved}")
    else:
        print("❌ 생성 실패 (openpyxl 미설치 또는 DB 오류)")
    return saved


def main():
    watch_mode = '--watch' in sys.argv

    db_name = cf.imi1_db_name
    engine  = make_engine(db_name)

    print(f"{'='*55}")
    print(f"  투자 운용보고서 생성기")
    print(f"  DB  : {db_name}")
    print(f"  파일: reports/투자운용보고서.xlsx")
    if watch_mode:
        print(f"  모드: 자동갱신 (60초 간격, Ctrl+C 종료)")
    print(f"{'='*55}")

    reporter = InvestmentReport(engine)

    # exit_reason 컬럼 마이그레이션 (최초 1회, 이미 있으면 무시)
    reporter.ensure_exit_reason_column()

    if watch_mode:
        try:
            while True:
                run_once(reporter)
                print("  → 60초 후 자동 갱신 (Ctrl+C 종료)")
                time.sleep(60)
        except KeyboardInterrupt:
            print("\n종료")
    else:
        run_once(reporter)

    engine.dispose()


if __name__ == '__main__':
    main()
