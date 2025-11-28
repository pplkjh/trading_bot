
import math
import pymysql
import datetime
from sqlalchemy import create_engine
import pandas as pd
import urllib.request
import urllib.error
from io import StringIO

pymysql.install_as_MySQLdb()
from library import cf
from PyQt5.QtCore import *

# KRX 데이터를 안전하게 가져오는 헬퍼 함수
def safe_read_html(url):
    """HTTPS 리다이렉트 없이 KRX 데이터를 가져옵니다"""
    try:
        # User-Agent 설정
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml',
        }
        req = urllib.request.Request(url, headers=headers)

        # 일반적인 요청으로 데이터 가져오기
        with urllib.request.urlopen(req, timeout=30) as response:
            # 바이트 데이터 읽기
            data = response.read()

            # 인코딩 감지 시도 (EUC-KR 또는 CP949)
            try:
                html = data.decode('euc-kr')
            except UnicodeDecodeError:
                try:
                    html = data.decode('cp949')
                except UnicodeDecodeError:
                    html = data.decode('utf-8', errors='ignore')

            return pd.read_html(StringIO(html), header=0)[0]

    except Exception as e:
        print(f"Error fetching data from {url}: {e}")
        raise


class daily_craw_config():
    def __init__(self, db_name, daily_craw_db_name, daily_buy_list_db_name):
        # db_name 0 인 경우는 simul 일때! 종목 데이터 가져오는 함수만 사용하기위해서
        if db_name != 0:
            self.db_name = db_name
            self.daily_craw_db_name = daily_craw_db_name

            self.daily_buy_list_db_name = daily_buy_list_db_name

            self.engine = create_engine(
                "mysql+mysqldb://" + cf.db_id + ":" + cf.db_passwd + "@" + cf.db_ip + ":" + cf.db_port + "/daily_craw",
                encoding='utf-8')
            self.daily_craw_db_con = self.engine.connect()

            self.get_item()
            # self.date_rows_setting()
            self.variable_setting()
            # print("db name 0아니다!!!!!!!!!!!!!!!!!!!!!!")
        else:
            pass
            # print("db name 0!!!!!!!!!!!!!!!!!!!")

    # 업데이트가 금일 제대로 끝났는지 확인
    def variable_setting(self):

        self.market_start_time = QTime(9, 0, 0)
        # self.market_start_time = QTime(15, 11, 0)
        self.market_end_time = QTime(15, 31, 0)
        # self.market_end_time = QTime(23, 12, 0)

        self.today = datetime.datetime.today().strftime("%Y%m%d")
        self.today_detail = datetime.datetime.today().strftime("%Y%m%d%H%M")
        # self.today_detail_seconds = datetime.datetime.today().strftime("%H / %M / %S")

    def market_time_check(self):
        # print("market_time_check!!!")
        self.current_time = QTime.currentTime()
        if self.current_time > self.market_start_time and self.current_time < self.market_end_time:
            return True
        else:
            print("end!!!")
            return False

    # 불성실공시법인 가져오는 함수
    def get_item_insincerity(self):
        print("get_item_insincerity!!")

        self.code_df_insincerity = safe_read_html('http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=05')
        # print(self.code_df_insincerity)

        # 6자리 만들고 앞에 0을 붙인다.
        self.code_df_insincerity.종목코드 = self.code_df_insincerity.종목코드.astype(str).str.zfill(6)

        # 우리가 필요한 것은 회사명과 종목코드이기 때문에 필요없는 column들은 제외해준다.
        self.code_df_insincerity = self.code_df_insincerity[['회사명', '종목코드']]

        # 한글로된 컬럼명을 영어로 바꿔준다.
        self.code_df_insincerity = self.code_df_insincerity.rename(columns={'회사명': 'code_name', '종목코드': 'code'})

    # 관리 종목을 가져오는 함수
    def get_item_managing(self):
        print("get_item_managing!!")
        self.code_df_managing = safe_read_html('http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=01')  # 종목코드가 6자리이기 때문에 6자리를 맞춰주기 위해 설정해줌

        # 6자리 만들고 앞에 0을 붙인다.strPath --> str(unicode(strPath))
        self.code_df_managing.종목코드 = self.code_df_managing.종목코드.astype(str).str.zfill(6)

        # 우리가 필요한 것은 회사명과 종목코드이기 때문에 필요없는 column들은 제외해준다.
        self.code_df_managing = self.code_df_managing[['회사명', '종목코드']]

        # 한글로된 컬럼명을 영어로 바꿔준다.
        self.code_df_managing = self.code_df_managing.rename(columns={'회사명': 'code_name', '종목코드': 'code'})

    # 코넥스 종목을 가져오는 함수
    def get_item_konex(self):
        print("get_item_konex!!")
        self.code_df_konex = safe_read_html('http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13&marketType=konexMkt')  # 종목코드가 6자리이기 때문에 6자리를 맞춰주기 위해 설정해줌

        # 6자리 만들고 앞에 0을 붙인다.
        self.code_df_konex.종목코드 = self.code_df_konex.종목코드.astype(str).str.zfill(6)

        # 우리가 필요한 것은 회사명과 종목코드이기 때문에 필요없는 column들은 제외해준다.
        self.code_df_konex = self.code_df_konex[['회사명', '종목코드']]

        # 한글로된 컬럼명을 영어로 바꿔준다.
        self.code_df_konex = self.code_df_konex.rename(columns={'회사명': 'code_name', '종목코드': 'code'})

    # 코스피 종목을 가져오는 함수
    def get_item_kospi(self):
        print("get_item_kospi!!")
        self.code_df_kospi = safe_read_html('http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13&marketType=stockMkt')  # 종목코드가 6자리이기 때문에 6자리를 맞춰주기 위해 설정해줌

        # 6자리 만들고 앞에 0을 붙인다.
        self.code_df_kospi.종목코드 = self.code_df_kospi.종목코드.astype(str).str.zfill(6)

        # 우리가 필요한 것은 회사명과 종목코드이기 때문에 필요없는 column들은 제외해준다.
        self.code_df_kospi = self.code_df_kospi[['회사명', '종목코드']]

        # 한글로된 컬럼명을 영어로 바꿔준다.
        self.code_df_kospi = self.code_df_kospi.rename(columns={'회사명': 'code_name', '종목코드': 'code'})

    # 코스닥 종목을 가져오는 함수
    def get_item_kosdaq(self):
        print("get_item_kosdaq!!")
        self.code_df_kosdaq = safe_read_html('http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13&marketType=kosdaqMkt')  # 종목코드가 6자리이기 때문에 6자리를 맞춰주기 위해 설정해줌

        # 6자리 만들고 앞에 0을 붙인다.
        self.code_df_kosdaq.종목코드 = self.code_df_kosdaq.종목코드.astype(str).str.zfill(6)

        # 우리가 필요한 것은 회사명과 종목코드이기 때문에 필요없는 column들은 제외해준다.
        self.code_df_kosdaq = self.code_df_kosdaq[['회사명', '종목코드']]

        # 한글로된 컬럼명을 영어로 바꿔준다.
        self.code_df_kosdaq = self.code_df_kosdaq.rename(columns={'회사명': 'code_name', '종목코드': 'code'})

    # 코스피, 코스닥, 코넥스 모든 정보를 가져오는 함수
    def get_item(self):
        # print("get_item!!")
        self.code_df = safe_read_html('http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13')  # 종목코드가 6자리이기 때문에 6자리를 맞춰주기 위해 설정해줌

        # 6자리 만들고 앞에 0을 붙인다.
        self.code_df.종목코드 = self.code_df.종목코드.astype(str).str.zfill(6)

        # 우리가 필요한 것은 회사명과 종목코드이기 때문에 필요없는 column들은 제외해준다.
        self.code_df = self.code_df[['회사명', '종목코드']]

        # 한글로된 컬럼명을 영어로 바꿔준다.
        self.code_df = self.code_df.rename(columns={'회사명': 'code_name', '종목코드': 'code'})

    def change_format(self, data):
        strip_data = data.replace('.', '')

        return strip_data

if __name__ == "__main__":
    daily_craw_config = daily_craw_config()

