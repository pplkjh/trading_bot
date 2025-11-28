
import pandas as pd
import urllib.request
import urllib.error
from io import StringIO

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

class StockItem():
    def __init__(self):
        # 코스피 종목 가져오기
        self.get_item_kospi()

        # 코스닥 종목 가져오기
        self.get_item_kosdaq()

    # 코스피 종목 리스트를 가져오는 메서드
    def get_item_kospi(self):
        print("get_item_kospi!!")
        self.code_df_kospi = safe_read_html('http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13&marketType=stockMkt')  # 종목코드가 6자리이기 때문에 6자리를 맞춰주기 위해 설정해줌

        # 6자리 만들고 앞에 0을 붙인다.
        self.code_df_kospi.종목코드 = self.code_df_kospi.종목코드.map('{:06d}'.format)

        # 우리가 필요한 것은 회사명과 종목코드이기 때문에 필요없는 column들은 제외해준다.
        self.code_df_kospi = self.code_df_kospi[['회사명', '종목코드']]

        # 한글로된 컬럼명을 영어로 바꿔준다.
        self.code_df_kospi = self.code_df_kospi.rename(columns={'회사명': 'code_name', '종목코드': 'code'})
        return self.code_df_kospi

    # 코스닥 종목 리스트를 가져오는 메서드
    def get_item_kosdaq(self):
        print("get_item_kosdaq!!")
        self.code_df_kosdaq = safe_read_html('http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13&marketType=kosdaqMkt')  # 종목코드가 6자리이기 때문에 6자리를 맞춰주기 위해 설정해줌

        # 6자리 만들고 앞에 0을 붙인다.
        self.code_df_kosdaq.종목코드 = self.code_df_kosdaq.종목코드.map('{:06d}'.format)

        # 우리가 필요한 것은 회사명과 종목코드이기 때문에 필요없는 column들은 제외해준다.
        self.code_df_kosdaq = self.code_df_kosdaq[['회사명', '종목코드']]

        # 한글로된 컬럼명을 영어로 바꿔준다.
        self.code_df_kosdaq = self.code_df_kosdaq.rename(columns={'회사명': 'code_name', '종목코드': 'code'})
        return self.code_df_kosdaq



if __name__ == "__main__":
    s = StockItem()
    print("코스피 종목 수: ", len(s.code_df_kospi))
    print(s.code_df_kospi)
    print(type(s.code_df_kospi))

    print("코스닥 종목 수: ", len(s.code_df_kosdaq))
    print(s.code_df_kosdaq)
    print(type(s.code_df_kospi))




