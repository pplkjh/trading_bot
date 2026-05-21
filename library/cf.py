# db 계정
db_id='bot' # [mysql ID를 넣어주세요]
# db ip
db_ip='localhost'
# db 패스워드
db_passwd='qwer1232' # [mysql password 를 넣어주세요]

# db port가 3306이 아닌 다른 port를 사용 하시는 분은 아래 변수에 포트에 맞게 수정하셔야합니다.
db_port='3306'

# 모의 투자 계좌번호를 넣는다. 모의 투자 계좌는 3개월에 한번씩 만료 되기 때문에 3개월 이용 후 재신청 하게 되면 계좌 번호가 변경된다.
# 이때 계정이 존재 하지 않는다!!! 는 에러가 뜰텐데 그때 변경 된 계좌번호를 다시 아래 imi1_account 변수에 넣으면 된다.
# 계좌 번호 쉽게 알아보는법:  콘솔창에 보면 상단 부분에 로그로 "계좌번호 :  " 옆에 출력이 된다
imi1_accout = "8120380811" # [모의투자 계좌번호를 넣어주세요. 주의! 10자리 계좌번호입니다. 모의투자는 8자리 계좌번호 뒤에 11, 실전은 10이 붙어 있음]

# imi1_simul_num은 알고리즘의 번호이다. 새로운 알고리즘으로 새롭게 database를 구축해서 운영하고 싶을 경우 번호를 2, 3, 4 ... 순차적으로 올려 주면 된다.
imi1_simul_num=3
imi1_db_name = "jackbot"+str(imi1_simul_num)+"_imi1"


# 아래는 실전 투자 계좌번호를 넣는다.
real_account=""
real_simul_num=1
real_db_name="jackbot"+str(real_simul_num)


real_daily_craw_db_name = "daily_craw"
real_daily_buy_list_db_name = "daily_buy_list"

# daily_buy_list database의 날짜 테이블을 과거 어떤 시점 부터 만들 것인지 설정 하는 변수
start_daily_buy_list='20230102'

# openapi 1회 조회 시 대기 시간(0.2 보다-> 0.3이 안정적)
TR_REQ_TIME_INTERVAL = 0.3

# n회 조회를 1번 발생시킨 경우 대기 시간
TR_REQ_TIME_INTERVAL_LONG = 1

# api를 최대 몇 번까지 호출 하고 봇을 끌지 설정 하는 옵션
# 데이터 수집 시: 99999 (거의 무제한)
# 일반 트레이딩 시: 999 (안전)
max_api_call = 4500

# dart api key (고급클래스에서 소개)
dart_api_key = ''

# etf 사용 여부 (고급클래스에서 소개)
use_etf = False

# 분봉 데이터 수집 여부
# True: 분봉 수집 (백테스팅 정밀도 향상, 시간 오래 걸림)
# False: 분봉 수집 안 함 (스윙 트레이딩은 일봉만으로 충분)
use_min_crawler = False

# dart api key
# dart_api_key = '8c44ace91948ce4d34b8ba27051836c2c8c35257'
dart_api_key = 'cc3e62c424689322f224f18b4f5ab5f6bfdb5497'

# ===== v2 확장 Scoring 설정 (simul_num=3 전용) =====
# 종목당 1회 투자 금액
# - invest_unit_pct > 0 이면 초기 자본의 퍼센트로 계산 (고정값 무시)
#   예) invest_unit_pct = 0.1 → 초기자본 10M × 10% = 1M
# - invest_unit_pct = 0.0 이면 invest_unit 고정값 사용
invest_unit     = 1_000_000   # 고정 금액 모드 (원)
invest_unit_pct = 0.0         # 퍼센트 모드 (0.0 = 고정 금액 사용)
initial_capital = 50_000_000  # 초기 투자 원금 (대시보드 원금 대비 손익 계산용)

# 250점 만점 중 최소 매수 기준점
v2_min_score = 120

# 펀더멘털 사전 필터 사용 여부
v2_fundamental_filter = True

# 펀더멘털 최소 점수 (50점 만점 중)
v2_fundamental_min_score = 15

# 펀더멘털 수집 주기 (일)
v2_fundamental_collect_interval = 1

# 동적 가중치 (ADX 기반)
v2_dynamic_weights = True

# ===== v4 Scoring (simul_num=4/5/6) =====
v4_min_score_a = 100   # BreakoutStrategyV3 minimum buy threshold (200pt max)
v4_min_score_b = 90    # ReversalStrategyV3 minimum buy threshold (200pt max)