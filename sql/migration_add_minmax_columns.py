"""
max_high_pct / min_low_pct 컬럼 추가 migration
컬럼이 이미 있으면 스킵, 없으면 추가.

실행: python sql/migration_add_minmax_columns.py
"""
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.absolute()))

import pymysql
from library.cf import db_id, db_passwd, db_ip, db_port

COLS = [
    ('max_high_pct', 'DECIMAL(10,4) DEFAULT 0 COMMENT "보유 중 최대 고가 수익률 (%)"'),
    ('min_low_pct',  'DECIMAL(10,4) DEFAULT 0 COMMENT "보유 중 최대 저가 손실률 (%)"'),
]
DATABASES = ['jackbot3_imi1', 'jackbot4_imi1', 'jackbot5_imi1', 'jackbot6_imi1']

con = pymysql.connect(user=db_id, passwd=db_passwd, host=db_ip,
                      port=int(db_port), charset='utf8')
cur = con.cursor()

for db in DATABASES:
    cur.execute(f'SHOW DATABASES LIKE "{db}"')
    if not cur.fetchone():
        print(f'{db}: DB 없음 (스킵)')
        continue
    cur.execute(f'SHOW TABLES FROM `{db}` LIKE "all_item_db"')
    if not cur.fetchone():
        print(f'{db}: all_item_db 없음 (스킵)')
        continue
    for col, definition in COLS:
        cur.execute(f'SHOW COLUMNS FROM `{db}`.all_item_db LIKE "{col}"')
        if cur.fetchone():
            print(f'{db}.{col}: 이미 존재 (스킵)')
        else:
            cur.execute(f'ALTER TABLE `{db}`.all_item_db ADD COLUMN `{col}` {definition}')
            con.commit()
            print(f'{db}.{col}: 추가 완료')

con.close()
print('완료')
