"""
rsi14 컬럼 추가 migration (B전략 RSI 천장 매도용)
컬럼이 이미 있으면 스킵, 없으면 추가.

실행: python sql/migration_add_rsi14_column.py
"""
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.absolute()))

import pymysql
from library.cf import db_id, db_passwd, db_ip, db_port

COL = ('rsi14', 'DECIMAL(6,2) DEFAULT 0 COMMENT "현재 RSI14 (B전략 RSI 천장 매도용)"')
DATABASES = ['simulator5', 'simulator6', 'jackbot4_imi1']

con = pymysql.connect(user=db_id, passwd=db_passwd, host=db_ip,
                      port=int(db_port), charset='utf8')
cur = con.cursor()

col_name, col_def = COL
for db in DATABASES:
    try:
        cur.execute(f'SHOW COLUMNS FROM `{db}`.all_item_db LIKE "{col_name}"')
        if cur.fetchone():
            print(f'{db}.{col_name}: 이미 존재 (스킵)')
        else:
            cur.execute(f'ALTER TABLE `{db}`.all_item_db ADD COLUMN `{col_name}` {col_def}')
            con.commit()
            print(f'{db}.{col_name}: 추가 완료')
    except Exception as e:
        print(f'{db}.{col_name}: 오류 - {e}')

cur.close()
con.close()
