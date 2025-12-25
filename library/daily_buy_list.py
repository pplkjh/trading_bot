ver = "#version 1.5.0 - 하이브리드 전략 지원 (RSI, Bollinger, ATR)"
print(f"daily_buy_list Version: {ver}")

from sqlalchemy import event, String

from library.daily_crawler import *
from library import cf
from pandas import DataFrame
from .open_api import escape_percentage
from library.logging_pack import logger
from library.technical_indicators import calculate_rsi, calculate_bollinger_bands, calculate_atr
import pandas as pd

MARKET_KOSPI = 0
MARKET_KOSDAQ = 10


class daily_buy_list():
    def __init__(self):
        self.variable_setting()

    def variable_setting(self):
        self.today = datetime.datetime.today().strftime("%Y%m%d")
        self.today_detail = datetime.datetime.today().strftime("%Y%m%d%H%M")
        self.start_date = cf.start_daily_buy_list
        self.engine_daily_craw = create_engine(
            "mysql+mysqldb://" + cf.db_id + ":" + cf.db_passwd + "@" + cf.db_ip + ":" + cf.db_port + "/daily_craw",
            encoding='utf-8')
        self.engine_daily_buy_list = create_engine(
            "mysql+mysqldb://" + cf.db_id + ":" + cf.db_passwd + "@" + cf.db_ip + ":" + cf.db_port + "/daily_buy_list",
            encoding='utf-8')

        event.listen(self.engine_daily_craw, 'before_execute', escape_percentage, retval=True)
        event.listen(self.engine_daily_buy_list, 'before_execute', escape_percentage, retval=True)

    def date_rows_setting(self):
        logger.debug("date_rows_setting!!")
        # 날짜 지정
        sql = "select date from `gs글로벌` where date >= '%s' group by date"
        self.date_rows = self.engine_daily_craw.execute(sql % self.start_date).fetchall()

    def is_table_exist_daily_buy_list(self, date):
        sql = "select 1 from information_schema.tables where table_schema ='daily_buy_list' and table_name = '%s'"
        rows = self.engine_daily_buy_list.execute(sql % (date)).fetchall()

        if len(rows) == 1:
            return True
        elif len(rows) == 0:
            return False

    def daily_buy_list(self):
        logger.debug("daily_buy_list!!!")
        self.date_rows_setting()
        self.get_stock_item_all()

        for k in range(len(self.date_rows)):
            # print("self.date_rows !!!!", self.date_rows)
            logger.debug(str(k) + " 번째 : " + datetime.datetime.today().strftime(" ******* %H : %M : %S *******"))

            current_date = self.date_rows[k][0]
            is_today = (current_date == self.today)

            # daily 테이블 존재하는지 확인
            if self.is_table_exist_daily_buy_list(current_date) == True:
                # 데이터가 있는지 확인 (오늘 날짜, 과거 날짜 동일하게 처리)
                empty = not bool(
                    self.engine_daily_buy_list.execute(f"""
                        SELECT 1 FROM `{current_date}`
                    """).fetchall()
                )

                if not empty:
                    # 데이터가 이미 있으면 스킵
                    # (collector_api의 시간 체크로 오후 4시 이후 수집은 이미 필터링됨)
                    logger.debug(current_date + "테이블은 존재한다 !! continue!! ")
                    continue
                else:
                    # to_sql() 도중 콜렉터가 꺼질 시 테이블만 생성하고 데이터를 못 넣는 경우에 대비하여 비어있을 시 테이블을 드랍
                    logger.debug(f"{current_date} 테이블이 비어있어서 다시 생성합니다.")
                    self.engine_daily_buy_list.execute(f"""
                        DROP TABLE `{current_date}`
                    """)

            logger.debug(self.date_rows[k][0] + "테이블은 존재하지 않는다 !!!!!!!!!!! table create !! ")

            multi_list = list()

            for i in range(len(self.stock_item_all)):
                code = self.stock_item_all[i][1]
                code_name = self.stock_item_all[i][0]
                if self.is_table_exist_daily_craw(code, code_name) == False:
                    print("daily_craw db에 " + str(code_name) + " 테이블이 존재하지 않는다 !!")
                    continue

                # 1. 오늘 날짜 데이터 가져오기 (원본 로직 유지)
                sql = "select * from `" + code_name + "` where date = '{}' group by date"
                rows = self.engine_daily_craw.execute(sql.format(self.date_rows[k][0])).fetchall()

                if len(rows) == 0:
                    continue

                # 2. 기술적 지표 계산을 위해 120일 데이터 읽기
                try:
                    sql_120 = f"SELECT * FROM `{code_name}` WHERE code = '{code}' ORDER BY date DESC LIMIT 120"
                    df_120 = pd.read_sql(sql_120, self.engine_daily_craw)

                    if len(df_120) >= 20:
                        # 시간순 정렬 (오래된 것 → 최신 순)
                        df_120 = df_120.sort_values('date').reset_index(drop=True)

                        # 기술적 지표 계산
                        rsi14 = calculate_rsi(df_120['close'], 14)
                        bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(df_120['close'], 20)
                        atr14 = calculate_atr(df_120['high'], df_120['low'], df_120['close'], 14)
                    else:
                        # 데이터 부족 시 기본값
                        rsi14, bb_upper, bb_middle, bb_lower, atr14 = 50.0, 0.0, 0.0, 0.0, 0.0

                except Exception as e:
                    # 에러 발생 시 기본값
                    logger.debug(f"{code_name} 기술적 지표 계산 실패: {e}")
                    rsi14, bb_upper, bb_middle, bb_lower, atr14 = 50.0, 0.0, 0.0, 0.0, 0.0

                # 3. 오늘 데이터에 기술적 지표 추가
                rows_with_indicators = [tuple(row) + (rsi14, bb_upper, bb_middle, bb_lower, atr14) for row in rows]
                multi_list += rows_with_indicators

            if len(multi_list) != 0:
                df_temp = DataFrame(multi_list,
                                    columns=['date', 'check_item', 'code', 'code_name', 'd1_diff_rate',
                                             'close', 'open', 'high', 'low',
                                             'volume', 'clo5', 'clo10', 'clo20', 'clo40', 'clo60', 'clo80',
                                             'clo100', 'clo120', "clo5_diff_rate", "clo10_diff_rate",
                                             "clo20_diff_rate", "clo40_diff_rate", "clo60_diff_rate",
                                             "clo80_diff_rate", "clo100_diff_rate", "clo120_diff_rate",
                                             'yes_clo5', 'yes_clo10', 'yes_clo20', 'yes_clo40', 'yes_clo60',
                                             'yes_clo80',
                                             'yes_clo100', 'yes_clo120',
                                             'vol5', 'vol10', 'vol20', 'vol40', 'vol60', 'vol80',
                                             'vol100', 'vol120',
                                             # 기술적 지표 추가
                                             'rsi14', 'bb_upper', 'bb_middle', 'bb_lower', 'atr14'
                                             ])
                df_temp.to_sql(
                    name=self.date_rows[k][0],
                    con=self.engine_daily_buy_list,
                    if_exists='replace',
                    index=False
                )
                try:
                    self.engine_daily_buy_list.execute(f"""
                        CREATE INDEX ix_{self.date_rows[k][0]}_code
                        ON daily_buy_list.`{self.date_rows[k][0]}` (code(6))
                    """)
                except Exception:
                    pass

    def get_stock_item_all(self):
        logger.debug("get_stock_item_all!!!!!!")
        sql = "select code_name,code from stock_item_all"
        self.stock_item_all = self.engine_daily_buy_list.execute(sql).fetchall()

    def is_table_exist_daily_craw(self, code, code_name):
        sql = "select 1 from information_schema.tables where table_schema ='daily_craw' and table_name = '%s'"
        rows = self.engine_daily_craw.execute(sql % (code_name)).fetchall()

        if len(rows) == 1:
            # print(code + " " + code_name + " 테이블 존재한다!!!")
            return True
        elif len(rows) == 0:
            # print("####################" + code + " " + code_name + " no such table!!!")
            # self.create_new_table(self.cc.code_df.iloc[i][0])
            return False

    def run(self):

        self.transaction_info()

        # print("run end")
        return 0


if __name__ == "__main__":
    daily_buy_list = daily_buy_list()
