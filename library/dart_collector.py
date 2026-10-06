"""
library/dart_collector.py

DART Open API로 상장사 연간 재무 데이터 수집 → jackbot5_imi1.dart_financials 저장.

사용법:
    python library/dart_collector.py              # 2018~현재 전체 수집 (최초 1회)
    python library/dart_collector.py --update     # 현재 연도만 갱신 (분기 업데이트)
    python library/dart_collector.py --years 2023 2024  # 특정 연도만
"""

import argparse
import io
import logging
import os
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime

import pymysql
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from library import cf

# ── 로거 ──────────────────────────────────────────────────────────
os.makedirs('log', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('log/dart_collector.log', encoding='utf-8'),
    ],
)
logger = logging.getLogger(__name__)

# ── 상수 ──────────────────────────────────────────────────────────
DART_KEY      = "cc3e62c424689322f224f18b4f5ab5f6bfdb5497"
BASE_URL      = "https://opendart.fss.or.kr/api"
DB_NAME       = "jackbot5_imi1"
SLEEP_SEC     = 0.15          # API 호출 간격 (초당 ~6건)
REPRT_ANNUAL  = '11011'       # 사업보고서 (연간)
START_YEAR    = 2018

# DART 계정명 → DB 컬럼 (contains 매칭, 선착순)
ACCOUNT_MAP = [
    ('매출액',       'revenue'),
    ('수익(매출액)', 'revenue'),
    ('영업수익',     'revenue'),      # 금융업 일부
    ('영업이익',     'op_profit'),
    ('당기순이익',   'net_income'),
    ('자본총계',     'total_equity'),
    ('부채총계',     'total_debt'),
    ('자산총계',     'total_assets'),
]


# ── DB 연결 ────────────────────────────────────────────────────────
def _conn(db=None):
    return pymysql.connect(
        host=cf.db_ip, port=int(cf.db_port),
        user=cf.db_id, password=cf.db_passwd,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
        database=db or '',
    )


def ensure_db():
    """jackbot5_imi1 DB 및 필요한 테이블 생성."""
    con = _conn()
    try:
        with con.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
                "DEFAULT CHARACTER SET utf8mb4"
            )
            cur.execute(f"USE `{DB_NAME}`")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS dart_corp_map (
                    stock_code  VARCHAR(10)  PRIMARY KEY,
                    corp_code   VARCHAR(10)  NOT NULL,
                    corp_name   VARCHAR(100),
                    updated_at  DATETIME     DEFAULT NOW()
                ) CHARACTER SET utf8mb4
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS dart_financials (
                    id              INT AUTO_INCREMENT PRIMARY KEY,
                    stock_code      VARCHAR(10)  NOT NULL,
                    bsns_year       SMALLINT     NOT NULL,
                    fs_div          VARCHAR(5)   NOT NULL DEFAULT 'CFS',
                    -- 당기 (thstrm)
                    revenue         BIGINT,
                    op_profit       BIGINT,
                    net_income      BIGINT,
                    total_equity    BIGINT,
                    total_debt      BIGINT,
                    total_assets    BIGINT,
                    -- 전기 (frmtrm) — YoY 계산용
                    revenue_py      BIGINT,
                    op_profit_py    BIGINT,
                    net_income_py   BIGINT,
                    total_equity_py BIGINT,
                    -- 계산 비율 (FLOAT: 극단값 허용)
                    roe             FLOAT,
                    op_margin       FLOAT,
                    debt_ratio      FLOAT,
                    revenue_yoy     FLOAT,
                    op_profit_yoy   FLOAT,
                    collected_at    DATETIME DEFAULT NOW(),
                    UNIQUE KEY uq (stock_code, bsns_year, fs_div)
                ) CHARACTER SET utf8mb4
            """)
        con.commit()
        logger.info("DB 준비 완료: %s", DB_NAME)
    finally:
        con.close()


# ── DART API ───────────────────────────────────────────────────────
def get_corp_codes():
    """CORPCODE.xml 다운로드 → {stock_code: {corp_code, corp_name}}."""
    logger.info("DART corp_code 다운로드 중...")
    r = requests.get(
        f"{BASE_URL}/corpCode.xml",
        params={'crtfc_key': DART_KEY},
        timeout=60,
    )
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    root = ET.fromstring(z.read('CORPCODE.xml'))

    result = {}
    for item in root.findall('list'):
        sc = (item.findtext('stock_code') or '').strip()
        cc = (item.findtext('corp_code')  or '').strip()
        nm = (item.findtext('corp_name')  or '').strip()
        if sc and len(sc) == 6 and sc.isdigit():
            result[sc] = {'corp_code': cc, 'corp_name': nm}

    logger.info("상장사 %d개 corp_code 확보", len(result))
    return result


def _dart_request(corp_code, year, fs_div):
    """DART API 단일 호출. 데이터 list 또는 None 반환."""
    for attempt in range(3):
        try:
            r = requests.get(
                f"{BASE_URL}/fnlttSinglAcntAll.json",
                params={
                    'crtfc_key':  DART_KEY,
                    'corp_code':  corp_code,
                    'bsns_year':  str(year),
                    'reprt_code': REPRT_ANNUAL,
                    'fs_div':     fs_div,
                },
                timeout=20,
            )
            data = r.json()
            status = data.get('status', '')
            if status == '000':
                return data.get('list') or []
            if status == '013':    # 데이터 없음 — 정상 케이스
                return []
            if status == '011':    # 사용 횟수 초과
                logger.warning("DART 속도 제한 — 60초 대기")
                time.sleep(60)
                continue
            return []
        except Exception as e:
            logger.debug("DART 요청 오류 (시도 %d): %s", attempt + 1, e)
            time.sleep(1)
    return None


def fetch_financials(corp_code, year):
    """CFS 우선, 없으면 OFS 폴백. (items, fs_div) 반환."""
    items = _dart_request(corp_code, year, 'CFS')
    if items:
        return items, 'CFS'
    time.sleep(SLEEP_SEC)
    items = _dart_request(corp_code, year, 'OFS')
    return (items or []), 'OFS'


# ── 파싱 ──────────────────────────────────────────────────────────
def _to_int(s):
    s = (s or '').replace(',', '').strip()
    if not s or s in ('-', ''):
        return None
    try:
        return int(s)
    except ValueError:
        return None


def parse_accounts(items):
    """
    DART 응답 list → {db_col: (당기값, 전기값)}.
    같은 계정이 여러 번 나오면 첫 번째만 사용.
    """
    result = {}
    for item in items:
        acct = (item.get('account_nm') or '').strip()
        for dart_nm, db_col in ACCOUNT_MAP:
            if dart_nm in acct and db_col not in result:
                result[db_col] = (
                    _to_int(item.get('thstrm_amount')),   # 당기
                    _to_int(item.get('frmtrm_amount')),   # 전기
                )
                break
    return result


def compute_ratios(acc):
    """재무비율 계산. acc = {db_col: (당기, 전기)}"""
    def cur(k):
        v = acc.get(k)
        return v[0] if v else None

    def prv(k):
        v = acc.get(k)
        return v[1] if v else None

    def pct(a, b):
        if a is not None and b and b != 0:
            return round(a / b * 100, 4)
        return None

    def yoy(c, p):
        if c is not None and p and p != 0:
            return round((c - p) / abs(p) * 100, 4)
        return None

    return {
        'roe':           pct(cur('net_income'),  cur('total_equity')),
        'op_margin':     pct(cur('op_profit'),   cur('revenue')),
        'debt_ratio':    pct(cur('total_debt'),  cur('total_equity')),
        'revenue_yoy':   yoy(cur('revenue'),     prv('revenue')),
        'op_profit_yoy': yoy(cur('op_profit'),   prv('op_profit')),
    }


# ── DB 저장 ────────────────────────────────────────────────────────
_UPSERT_SQL = """
    INSERT INTO dart_financials
        (stock_code, bsns_year, fs_div,
         revenue, op_profit, net_income,
         total_equity, total_debt, total_assets,
         revenue_py, op_profit_py, net_income_py, total_equity_py,
         roe, op_margin, debt_ratio, revenue_yoy, op_profit_yoy,
         collected_at)
    VALUES (%s,%s,%s, %s,%s,%s, %s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s,%s, NOW())
    ON DUPLICATE KEY UPDATE
        fs_div=VALUES(fs_div),
        revenue=VALUES(revenue),          op_profit=VALUES(op_profit),
        net_income=VALUES(net_income),    total_equity=VALUES(total_equity),
        total_debt=VALUES(total_debt),    total_assets=VALUES(total_assets),
        revenue_py=VALUES(revenue_py),    op_profit_py=VALUES(op_profit_py),
        net_income_py=VALUES(net_income_py),
        total_equity_py=VALUES(total_equity_py),
        roe=VALUES(roe),                  op_margin=VALUES(op_margin),
        debt_ratio=VALUES(debt_ratio),
        revenue_yoy=VALUES(revenue_yoy),  op_profit_yoy=VALUES(op_profit_yoy),
        collected_at=NOW()
"""

_CORP_MAP_SQL = """
    INSERT INTO dart_corp_map (stock_code, corp_code, corp_name, updated_at)
    VALUES (%s, %s, %s, NOW())
    ON DUPLICATE KEY UPDATE
        corp_code=VALUES(corp_code), corp_name=VALUES(corp_name), updated_at=NOW()
"""


def save_batch(rows, corp_map_rows):
    """수집된 데이터를 DB에 일괄 저장."""
    con = _conn(DB_NAME)
    try:
        with con.cursor() as cur:
            if corp_map_rows:
                cur.executemany(_CORP_MAP_SQL, corp_map_rows)
            if rows:
                cur.executemany(_UPSERT_SQL, rows)
        con.commit()
    finally:
        con.close()


def load_existing(years):
    """이미 수집된 (stock_code, bsns_year) 쌍 반환 — 재실행 시 중복 스킵용."""
    try:
        con = _conn(DB_NAME)
        with con.cursor() as cur:
            placeholders = ','.join(['%s'] * len(years))
            cur.execute(
                f"SELECT stock_code, bsns_year FROM dart_financials "
                f"WHERE bsns_year IN ({placeholders})",
                years,
            )
            rows = cur.fetchall()
        con.close()
        return {(r['stock_code'], r['bsns_year']) for r in rows}
    except Exception:
        return set()


# ── 메인 수집 루프 ────────────────────────────────────────────────
def run_collection(years=None, update_only=False, skip_existing=False):
    """
    Parameters
    ----------
    years         : 수집할 연도 리스트. None이면 DEFAULT_YEARS 사용.
    update_only   : True = 현재 연도만
    skip_existing : True = DB에 이미 있는 (종목, 연도)는 건너뜀
    """
    if years is None:
        years = [datetime.now().year] if update_only else list(range(START_YEAR, datetime.now().year + 1))

    ensure_db()

    corp_map = get_corp_codes()

    existing = load_existing(years) if skip_existing else set()
    if existing:
        logger.info("이미 수집된 레코드 %d건 스킵 예정", len(existing))

    total    = len(corp_map) * len(years)
    done = saved = skipped = errors = 0
    batch_rows    = []
    corp_map_rows = []
    BATCH_SIZE    = 50

    logger.info("수집 시작: %d개 기업 × %d년 = %d건 예정",
                len(corp_map), len(years), total)
    t0 = time.time()

    for stock_code, info in corp_map.items():
        corp_code = info['corp_code']
        corp_map_rows.append((stock_code, corp_code, info['corp_name']))

        for year in years:
            done += 1

            if (stock_code, year) in existing:
                skipped += 1
                continue

            try:
                items, fs_div = fetch_financials(corp_code, year)
                time.sleep(SLEEP_SEC)

                if not items:
                    skipped += 1
                    continue

                acc    = parse_accounts(items)
                ratios = compute_ratios(acc)

                # 핵심 지표가 하나도 없으면 저장 안함
                if not any(acc.get(k, (None,))[0]
                           for k in ('revenue', 'op_profit', 'net_income')):
                    skipped += 1
                    continue

                def c(k):
                    v = acc.get(k); return v[0] if v else None
                def p(k):
                    v = acc.get(k); return v[1] if v else None

                batch_rows.append((
                    stock_code, year, fs_div,
                    c('revenue'), c('op_profit'), c('net_income'),
                    c('total_equity'), c('total_debt'), c('total_assets'),
                    p('revenue'), p('op_profit'), p('net_income'), p('total_equity'),
                    ratios['roe'], ratios['op_margin'], ratios['debt_ratio'],
                    ratios['revenue_yoy'], ratios['op_profit_yoy'],
                ))
                saved += 1

            except Exception as e:
                logger.warning("오류 skip: %s %s — %s", stock_code, year, e)
                errors += 1
                time.sleep(0.5)

        # 배치 저장
        if len(batch_rows) >= BATCH_SIZE:
            save_batch(batch_rows, corp_map_rows)
            batch_rows    = []
            corp_map_rows = []

        if done % 500 == 0:
            elapsed = time.time() - t0
            eta     = elapsed / done * (total - done) if done else 0
            logger.info(
                "진행 %d/%d (%.1f%%) | 저장 %d 스킵 %d 오류 %d | ETA %.0f분",
                done, total, done / total * 100,
                saved, skipped, errors, eta / 60,
            )

    # 잔여 배치
    if batch_rows or corp_map_rows:
        save_batch(batch_rows, corp_map_rows)

    elapsed_min = (time.time() - t0) / 60
    logger.info(
        "수집 완료 — 저장 %d / 스킵 %d / 오류 %d / 소요 %.1f분",
        saved, skipped, errors, elapsed_min,
    )


# ── CLI 진입점 ────────────────────────────────────────────────────
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='DART 재무 데이터 수집')
    parser.add_argument('--update', action='store_true',
                        help='현재 연도만 업데이트 (분기 갱신용)')
    parser.add_argument('--years', nargs='+', type=int,
                        help='수집할 연도 지정 (예: --years 2023 2024)')
    parser.add_argument('--skip-existing', action='store_true',
                        help='DB에 이미 있는 레코드는 건너뜀 (재실행 시 사용)')
    args = parser.parse_args()

    run_collection(
        years=args.years,
        update_only=args.update,
        skip_existing=args.skip_existing,
    )
