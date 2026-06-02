ver = "#version 1.3.10"
print(f"simulator_func_mysql Version: {ver}")
import sys
is_64bits = sys.maxsize > 2**32
if is_64bits:
    print('64bit 환경입니다.')
else:
    print('32bit 환경입니다.')

from sqlalchemy import event

import pymysql.cursors

from library.logging_pack import *
from library import cf
from pandas import DataFrame
import re
import datetime
from sqlalchemy import create_engine
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # GUI 없이 그래프 생성
import os

pymysql.install_as_MySQLdb()


class simulator_func_mysql:
    def __init__(self, simul_num, op, db_name):
        self.simul_num = int(simul_num)

        # scraper할 때 start date 가져오기 위해서
        if self.simul_num == -1:
            self.date_setting()

        # option이 reset일 경우 실행
        elif op == 'reset':
            self.op = 'reset'
            self.simul_reset = True
            self.db_name = db_name
            self.variable_setting()
            self.rotate_date()

        # option이 real일 경우 실행(시뮬레이터와 무관)
        elif op == 'real':
            self.op = 'real'
            self.simul_reset = False
            self.db_name = db_name
            self.variable_setting()

        #  option이 continue 일 경우 실행
        elif op == 'continue':
            self.op = 'continue'
            self.simul_reset = False
            self.db_name = db_name
            self.variable_setting()
            self.rotate_date()
        else:
            print("simul_num or op 어느 것도 만족 하지 못함 simul_num : %s ,op : %s !!", simul_num, op)

    # 마지막으로 구동했던 시뮬레이터의 날짜를 가져온다.
    def get_jango_data_last_date(self):
        sql = "SELECT date from jango_data order by date desc limit 1"
        return self.engine_simulator.execute(sql).fetchall()[0][0]

    # 모든 테이블을 삭제 하는 함수
    def delete_table_data(self):
        logger.info('delete_table_data !!!!')
        if self.is_simul_table_exist(self.db_name, "all_item_db"):
            sql = "drop table all_item_db"
            self.engine_simulator.execute(sql)
            # 만약 jango data 컬럼을 수정하게 되면 테이블을 삭제하고 다시 생성이 자동으로 되는데 이때 삭제했으면 delete가 안먹힌다. 그래서 확인 후 delete

        if self.is_simul_table_exist(self.db_name, "jango_data"):
            sql = "drop table jango_data"
            self.engine_simulator.execute(sql)

        if self.is_simul_table_exist(self.db_name, "realtime_daily_buy_list"):
            sql = "drop table realtime_daily_buy_list"
            self.engine_simulator.execute(sql)

    # realtime_daily_buy_list 테이블의 check_item컬럼에 특정 종목의 매수 시간을 넣는 함수
    def update_realtime_daily_buy_list(self, code, min_date):
        if not self.is_simul_table_exist(self.db_name, "realtime_daily_buy_list"):
            return  # 백테스트 초기 또는 reset 직후 테이블 미생성 시 무시
        sql = "update realtime_daily_buy_list set check_item = '%s' where code = '%s'"
        self.engine_simulator.execute(sql % (min_date, code))

    # cf.invest_unit / invest_unit_pct 기반으로 invest_unit 계산
    @staticmethod
    def _resolve_invest_unit(base_balance):
        """초기 자본(base_balance) 기준으로 실제 invest_unit 반환.
        cf.invest_unit_pct > 0 이면 퍼센트 모드, 0 이면 고정금액 모드."""
        if cf.invest_unit_pct > 0:
            return max(10_000, int(base_balance * cf.invest_unit_pct))
        return cf.invest_unit

    # 시뮬레이션 옵션 설정 함수
    def variable_setting(self):
        # 아래 if문으로 들어가기 전까지의 변수들은 모든 알고리즘에 공통적으로 적용 되는 설정
        # 오늘 날짜를 설정
        self.date_setting()
        # 시뮬레이팅이 끝나는 날짜.
        self.simul_end_date = self.today
        self.start_min = "0900"

        # 아래 3개는 분별시뮬레이션 옵션
        # (use_min, only_nine_buy 변수만 각각의 알고리즘에 붙여 넣기 해서 사용)
        # 분별 시뮬레이션을 사용하고 싶을 경우 아래 옵션을 True로 변경하여 사용
        self.use_min = False
        # 아침 9시에만 매수를 하고 싶은 경우 True, 9시가 아니어도 매수를 하고 싶은 경우 False(분별 시뮬레이션 적용 가능 / 일별 시뮬레이션은 9시에만 매수, 매도)
        self.only_nine_buy = True
        # self.buy_stop옵션은 수정 필요가 없음. self.only_nine_buy 옵션을 True로 하게 되면 시뮬레이터가 9시에 매수 후에 self.buy_stop을 true로 변경해서 당일에는 더이상 매수하지 않도록 설정함
        self.buy_stop = False

        # AI알고리즘 사용 여부 (고급 챕터에서 소개)
        self.use_ai = False  # ai 알고리즘 사용 시 True 사용 안하면 False
        self.ai_filter_num = 1  # ai 알고리즘 선택

        # 실시간 조건 매수 옵션 (고급 챕터에서 소개)
        # self.only_nine_buy 옵션을 반드시 False로 설정해야함
        # self.use_min 옵션이 반드시 True로 설정이 되어야함
        # 실시간 조건 매수 알고리즘 선택 (1,2,3..)
        self.trade_check_num = False

        print("self.simul_num!!! ", self.simul_num)

        ###!@####################################################################################################################
        # 아래 부터는 알고리즘 별로 별도의 설정을 해주는 부분

        # ==================== 새로운 고급 전략 (1-19번) ====================

        if self.simul_num == 1:
            # 🚀 고급 하이브리드 전략: Momentum 60% + Mean Reversion 40%
            # RSI14, Bollinger Bands, ATR14를 활용한 고급 전략
            self.simul_start_date = "20230102"

            # 분별 시뮬레이션 옵션
            self.use_min = False
            self.only_nine_buy = False

            # 알고리즘 선택
            self.db_to_realtime_daily_buy_list_num = 1  # 하이브리드 전략 매수
            self.sell_list_num = 100  # 고급 전략 매도

            # 자본 설정
            self.start_invest_price = 10000000
            self.invest_unit = 1000000  # 기본 단위 (ATR 기반 동적 조정)
            self.limit_money = 2000000

            # 고급 전략 특화 설정
            self.risk_profile = 'aggressive'  # conservative, moderate, aggressive
            self.max_positions = 10  # 최대 포지션 수
            self.atr_multiplier = 2.0  # ATR 손절선 배수
            self.trailing_stop_atr = 1.5  # 트레일링 스톱 ATR 배수

            # 익절/손절은 동적 계산 (고정값 사용 안함)
            self.sell_point = 999  # 사용 안함 (동적 익절)
            self.losscut_point = -999  # 사용 안함 (ATR 기반 손절)

            # 매수 제한
            self.invest_limit_rate = 1.03
            self.invest_min_limit_rate = 0.97

        elif self.simul_num == 2:
            # 🔄 혼합 전략: 날짜 기반 30% + 하이브리드 70%
            # collector와 동일한 전략 (두 전략 점수 합산)
            self.simul_start_date = "20230102"

            # 분별 시뮬레이션 옵션
            self.use_min = False
            self.only_nine_buy = False

            # 알고리즘 선택
            self.db_to_realtime_daily_buy_list_num = 2  # 혼합 전략 매수
            self.sell_list_num = 100  # 고급 전략 매도

            # 자본 설정
            self.start_invest_price = 10000000
            self.invest_unit = 1000000
            self.limit_money = 2000000

            # 고급 전략 특화 설정
            self.risk_profile = 'aggressive'
            self.max_positions = 10
            self.atr_multiplier = 2.0
            self.trailing_stop_atr = 1.5

            # 익절/손절은 동적 계산 (고정값 사용 안함)
            self.sell_point = 999
            self.losscut_point = -999

            # 매수 제한
            self.invest_limit_rate = 1.03
            self.invest_min_limit_rate = 0.97

        elif self.simul_num == 3:
            # v2 확장 Scoring 시스템 (250점 만점, HybridStrategyV2)
            self.simul_start_date = "20230102"
            self.use_min = False
            self.only_nine_buy = False
            self.db_to_realtime_daily_buy_list_num = 21  # HybridStrategyV2 Python 점수 기반
            self.sell_list_num = 20                       # 스윙 익절/손절 + MA 데드크로스
            self.start_invest_price = 10000000
            self.invest_unit = self._resolve_invest_unit(self.start_invest_price)
            self.limit_money = 300000
            self.sell_point = 6          # 빠른 익절 6% (자동매매 장점 활용)
            self.losscut_point = -3      # 타이트 손절 -3% (갭하락 피해 최소화)
            self.max_positions = 999     # 예수금이 허락하는 한 무제한 보유
            self.invest_limit_rate = 1.02
            self.invest_min_limit_rate = 0.97
            self.use_hybrid_v2 = True

        elif self.simul_num == 4:
            # Strategy A: 돌파 초입 (BreakoutStrategyV3) — jackbot4_imi1
            self.simul_start_date = "20230102"
            self.use_min = False
            self.only_nine_buy = False
            self.db_to_realtime_daily_buy_list_num = 22
            self.sell_list_num = 20   # 방향성 검증: 익절+6% / 손절-5% / 시간청산 20일
            self.start_invest_price = 10000000
            self.invest_unit = self._resolve_invest_unit(self.start_invest_price)
            self.limit_money = 300000
            self.sell_point = 6       # 익절 기준 (실전 트레일링 평균 근사)
            self.losscut_point = -5   # 손절 기준 — 실전 하드 SL(-5%)과 일치
            self.time_stop_days = 20  # 시간청산 — 실전 A 시간청산(15일) 근사
            self.max_positions = 999
            self.invest_limit_rate = 1.02
            self.invest_min_limit_rate = 0.97

        elif self.simul_num == 5:
            # Strategy B: 중장기 RSI 사이클 (ReversalStrategyV3) — jackbot4_imi1
            self.simul_start_date = "20230102"
            self.use_min = False
            self.only_nine_buy = False
            self.db_to_realtime_daily_buy_list_num = 22
            self.sell_list_num = 20   # 방향성 검증: 익절+6% / 손절-5% / 시간청산 45일
            self.start_invest_price = 10000000
            self.invest_unit = self._resolve_invest_unit(self.start_invest_price)
            self.limit_money = 300000
            self.sell_point = 6       # 익절 기준
            self.losscut_point = -5   # 손절 기준 — 실전 하드 SL(-5%)과 일치
            self.time_stop_days = 45  # 시간청산 — 실전 B 시간청산(45일)과 일치
            self.max_positions = 999
            self.invest_limit_rate = 1.02
            self.invest_min_limit_rate = 0.97

        elif self.simul_num == 6:
            # Strategy A+B 혼합 — jackbot4_imi1 (실전 운영)
            self.simul_start_date = "20230102"
            self.use_min = False
            self.only_nine_buy = False
            self.db_to_realtime_daily_buy_list_num = 22
            self.sell_list_num = 31   # 실전: get_basic_sell_list A/B 분기 (SL-5%+Trail+시간청산)
            self.start_invest_price = 10000000
            self.invest_unit = self._resolve_invest_unit(self.start_invest_price)
            self.limit_money = 300000
            self.sell_point = 6       # 참고용
            self.losscut_point = -5   # 참고용 (실제는 get_basic_sell_list에서 직접 처리)
            self.max_positions = 999
            self.invest_limit_rate = 1.02
            self.invest_min_limit_rate = 0.97

        # ==================== 기존 전략 (20번대로 이동) ====================

        elif self.simul_num == 21:
            # 시뮬레이팅 시작 일자(분 별 시뮬레이션의 경우 최근 1년 치 데이터만 있기 때문에 start_date 조정 필요)
            self.simul_start_date = "20200102"
            ###
            # # 분별 시뮬레이션을 사용하고 싶을 경우 아래 옵션을 True로 변경하여 사용
            self.use_min = False
            # # 아침 9시에만 매수를 하고 싶은 경우 True, 9시가 아니어도 매수를 하고 싶은 경우 False(분별 시뮬레이션 적용 가능 / 일별 시뮬레이션은 9시에만 매수, 매도)
            self.only_nine_buy = False
            ###
            # ######## 알고리즘 선택 #############
            # 매수 리스트 설정 알고리즘 번호
            self.db_to_realtime_daily_buy_list_num = 1

            # 매도 리스트 설정 알고리즘 번호
            self.sell_list_num = 1
            ###################################

            # 초기 투자자금(시뮬레이션에서의 초기 투자 금액. 모의투자는 신청 당시의 금액이 초기 투자 금액이라고 보시면 됩니다)
            # 주의! start_invest_price 는 모의투자 초기 자본금과 별개. 시뮬레이션에서만 적용.
            # 키움증권 모의투자의 경우 초기에 모의투자 신청 할 때 설정 한 금액으로 자본금이 설정됨
            self.start_invest_price = 10000000

            # 매수 금액
            self.invest_unit = 500000

            # 자산 중 최소로 남겨 둘 금액
            self.limit_money = 3000000

            # 익절 수익률 기준치
            self.sell_point = 5

            # 손절 수익률 기준치
            self.losscut_point = -2

            # 실전/모의 봇 돌릴 때 매수하는 순간 종목의 최신 종가 보다 1% 이상 오른 경우 사지 않도록 하는 설정(변경 가능)
            self.invest_limit_rate = 1.05
            # 실전/모의 봇 돌릴 때 매수하는 순간 종목의 최신 종가 보다 -2% 이하로 떨어진 경우 사지 않도록 하는 설정(변경 가능)
            self.invest_min_limit_rate = 0.96

        elif self.simul_num == 22:
            # 시뮬레이팅 시작 일자
            self.simul_start_date = "20210102"

            # ######## 알고리즘 선택 #############
            # 매수 리스트 설정 알고리즘 번호
            self.db_to_realtime_daily_buy_list_num = 2
            # 매도 리스트 설정 알고리즘 번호
            self.sell_list_num = 2
            ###################################
            # 초기 투자자금
            # 주의! start_invest_price 는 모의투자 초기 자본금과 별개. 시뮬레이션에서만 적용.
            # 키움증권 모의투자의 경우 초기에 모의투자 신청 할 때 설정 한 금액으로 자본금이 설정됨
            self.start_invest_price = 50000000
            # 매수 금액
            self.invest_unit = 1000000

            # 자산 중 최소로 남겨 둘 금액
            self.limit_money = 1000000
            # # 익절 수익률 기준치
            self.sell_point = 8
            # 손절 수익률 기준치
            self.losscut_point = -2
            # 실전/모의 봇 돌릴 때 매수하는 순간 종목의 최신 종가 보다 1% 이상 오른 경우 사지 않도록 하는 설정(변경 가능)
            self.invest_limit_rate = 1.01
            # 실전/모의 봇 돌릴 때 매수하는 순간 종목의 최신 종가 보다 -2% 이하로 떨어진 경우 사지 않도록 하는 설정(변경 가능)
            self.invest_min_limit_rate = 0.98

        elif self.simul_num == 23:

            # 시뮬레이팅 시작 일자

            self.simul_start_date = "20200102"

            # ######## 알고리즘 선택 #############
            # 매수 리스트 설정 알고리즘 번호
            self.db_to_realtime_daily_buy_list_num = 3
            # 매도 리스트 설정 알고리즘 번호
            self.sell_list_num = 2
            ###################################

            # 초기 투자자금
            # 주의! start_invest_price 는 모의투자 초기 자본금과 별개. 시뮬레이션에서만 적용.
            # 키움증권 모의투자의 경우 초기에 모의투자 신청 할 때 설정 한 금액으로 자본금이 설정됨
            self.start_invest_price = 10000000

            # 매수 금액
            self.invest_unit = 3000000

            # 자산 중 최소로 남겨 둘 금액
            self.limit_money = 1000000

            # 익절 수익률 기준치
            self.sell_point = 10

            # 손절 수익률 기준치
            self.losscut_point = -2

            # 실전/모의 봇 돌릴 때 매수하는 순간 종목의 최신 종가 보다 1% 이상 오른 경우 사지 않도록 하는 설정(변경 가능)
            self.invest_limit_rate = 1.01
            # 실전/모의 봇 돌릴 때 매수하는 순간 종목의 최신 종가 보다 -2% 이하로 떨어진 경우 사지 않도록 하는 설정(변경 가능)
            self.invest_min_limit_rate = 0.98

        elif self.simul_num in range(24,37):
            # 시뮬레이팅 시작 일자(분 별 시뮬레이션의 경우 최근 1년 치 데이터만 있기 때문에 start_date 조정 필요)
            self.simul_start_date = "20210102"

            ######### 알고리즘 선택 #############
            # 매수 리스트 설정 알고리즘 번호
            self.db_to_realtime_daily_buy_list_num = 1

            # 매도 리스트 설정 알고리즘 번호
            self.sell_list_num = 1
            ###################################

            # 초기 투자자금
            self.start_invest_price = 10000000

            # 매수 금액
            self.invest_unit = 1000000

            # 자산 중 최소로 남겨 둘 금액
            self.limit_money = 3000000

            # 익절 수익률 기준치
            self.sell_point = 10

            # 손절 수익률 기준치
            self.losscut_point = -2

            # 실전/모의 봇 돌릴 때 매수하는 순간 종목의 최신 종가 보다 1% 이상 오른 경우 사지 않도록 하는 설정(변경 가능)
            self.invest_limit_rate = 1.01
            # 실전/모의 봇 돌릴 때 매수하는 순간 종목의 최신 종가 보다 -2% 이하로 떨어진 경우 사지 않도록 하는 설정(변경 가능)
            self.invest_min_limit_rate = 0.98

            if self.simul_num == 24:
                self.interval_month = 3
                self.invest_unit = 50000

            elif self.simul_num == 25:
                self.total_transaction_price = 10000000000
                self.interval_month = 3
                self.vol_mul = 3
                self.d1_diff = 2
                # self.use_min= True
                # self.only_nine_buy = False

            elif self.simul_num == 31:  # AI알고리즘 사용
                # AI알고리즘 사용 여부 (고급 챕터에서 소개)
                self.use_ai = True  # ai 알고리즘 사용 시 True 사용 안하면 False
                self.ai_filter_num = 1  # ai 알고리즘 선택

            elif self.simul_num == 32:  # 종목 정보 테이블을 활용한 우량주, 고신용 종목 매수 알고리즘
                # audit이 정상이고 거래정지, 관리종목을 제외한 종목 리스트를 매수
                self.db_to_realtime_daily_buy_list_num = 12

            # 실시간 조건 매수
            elif self.simul_num in (33, 34):
                self.simul_start_date = "20220102"
                self.use_min = True
                # 아침 9시에만 매수를 하고 싶은 경우 True, 9시가 아니어도 매수를 하고 싶은 경우 False(분별 시뮬레이션, trader 적용 가능 / 일별 시뮬레이션은 9시에만 매수, 매도)
                self.only_nine_buy = False
                # 실시간 조건 매수 옵션 (고급 챕터에서 소개) self.only_nine_buy 옵션을 반드시 False로 설정해야함
                self.trade_check_num = 1  # 실시간 조건 매수 알고리즘 선택 (1,2,3..)
                # 특정 거래대금 보다 x배 이상 증가 할 경우 매수
                self.volume_up = 2
                #
                if self.simul_num == 33:
                    self.trade_check_num = 2
                    # 매수하는 순간 종목의 최신 종가 보다 1% 이상 오른 경우 사지 않도록 하는 설정(변경 가능)
                    self.invest_limit_rate = 1.01
                    # 매수하는 순간 종목의 최신 종가 보다 -2% 이하로 떨어진 경우 사지 않도록 하는 설정(변경 가능)
                    self.invest_min_limit_rate = 0.98

                # 래리윌리엄스 변동성 돌파 전략
                elif self.simul_num == 34:
                    self.trade_check_num = 3
                    self.rarry_k = 0.5
            ### ETF
            elif self.simul_num == 36:
                self.db_to_realtime_daily_buy_list_num = 11

            # 절대 모멘텀 / 상대 모멘텀
            elif self.simul_num in range(27, 31):
                # 매수 리스트 설정 알고리즘 번호(절대모멘텀 code ver)
                self.db_to_realtime_daily_buy_list_num = self.simul_num
                # 매도 리스트 설정 알고리즘 번호(절대모멘텀 code ver)
                self.sell_list_num = 4
                # 시뮬레이팅 시작 일자(분 별 시뮬레이션의 경우 최근 1년 치 데이터만 있기 때문에 start_date 조정 필요)
                self.simul_start_date = "20200102"
                # n일 전 종가 데이터를 가져올지 설정 (ex. 20 -> 장이 열리는 날 기준 20일 이니까 기간으로 보면 약 한 달, 250일->1년)
                self.day_before = 100 # 단위 일
                # n일 전 종가 대비 현재 종가(현재가)가 몇 프로 증가 했을 때 매수, 몇 프로 떨어졌을 때 매도 할 지 설정(0으로 설정 시 단순히 증가 했을 때 매수, 감소 했을 때 매도)
                self.diff_point = 1 # 단위 %
                # 분별 시뮬레이션 옵션
                # self.use_min = True
                # self.only_nine_buy = True

                if self.simul_num == 28:
                    # 매수 리스트 설정 알고리즘 번호 (절대모멘텀 query ver)
                    self.db_to_realtime_daily_buy_list_num = 8
                    # 매도 리스트 설정 알고리즘 번호 (절대모멘텀 query ver)
                    self.sell_list_num = 5

                elif self.simul_num == 29:
                    # 매수 리스트 설정 알고리즘 번호 (절대모멘텀 query ver)
                    self.db_to_realtime_daily_buy_list_num = 8
                    # 매도 리스트 설정 알고리즘 번호 (절대모멘텀 query ver + losscut point 추가)
                    self.sell_list_num = 6
                    # 손절 수익률 기준치
                    self.losscut_point = -2

                elif self.simul_num == 30:
                    # 매수 리스트 설정 알고리즘 번호 (상대모멘텀 query ver)
                    self.db_to_realtime_daily_buy_list_num = 9
                    # 매도 리스트 설정 알고리즘 번호 (절대모멘텀 query ver + losscut point 추가)
                    self.sell_list_num = 5



        else:
            logger.error(f"입력 하신 {self.simul_num}번 알고리즘에 대한 설정이 없습니다. simulator_func_mysql.py 파일의 variable_setting함수에 알고리즘을 설정해주세요. ")
            sys.exit(1)

        #########################################################################################################################
        self.db_name_setting()

        if self.op != 'real':
            # database, table 초기화 함수
            self.table_setting()

            # 시뮬레이팅 할 날짜를 가져 오는 함수
            self.get_date_for_simul()

            # 매도를 한 종목들 대상 수익
            self.total_valuation_profit = 0

            # 실제 수익 : 매도를 한 종목들 대상 수익 + 현재 보유 중인 종목들의 수익
            self.sum_valuation_profit = 0

            # 전재산 : 투자금액 + 실제 수익(self.sum_valuation_profit)
            self.total_invest_price = self.start_invest_price

            # 현재 총 투자한 금액
            self.total_purchase_price = 0

            # 현재 투자 가능한 금액(예수금) = (초기자본 + 매도한 종목의 수익) - 현재 총 투자 금액
            self.d2_deposit = self.start_invest_price

            # 일별 정산 함수
            self.check_balance()

            # 매수할때 수수료 한번, 매도할때 전체금액에 세금, 수수료
            self.tax_rate = 0.0025
            self.fees_rate = 0.00015

            # 시뮬레이터를 멈춘 지점 부터 다시 돌리기 위해 사용하는 변수(중요X)
            self.simul_reset_lock = False

    # 데이터베이스와 테이블을 세팅하기 위한 함수
    def table_setting(self):
        print("self.simul_reset" + str(self.simul_reset))
        # 시뮬레이터를 초기화 하고 처음부터 구축하기 위한 로직
        if self.simul_reset:
            print("table reset setting !!! ")
            self.init_database()
        # 시뮬레이터를 초기화 하지 않고 마지막으로 끝난 시점 부터 구동하기 위한 로직
        else:
            # self.simul_reset 이 False이고, 시뮬레이터 데이터베이스와, all_item_db 테이블, jango_table이 존재하는 경우 이어서 시뮬레이터 시작
            if self.is_simul_database_exist() and self.is_simul_table_exist(self.db_name,
                                                                            "all_item_db") and self.is_simul_table_exist(
                self.db_name, "jango_data"):
                self.init_df_jango()
                self.init_df_all_item()
                # 마지막으로 구동했던 시뮬레이터의 날짜를 가져온다.
                self.last_simul_date = self.get_jango_data_last_date()
                print("self.last_simul_date: " + str(self.last_simul_date))
            #    초반에 reset 으로 돌다가 멈춰버린 경우 다시 init 해줘야함
            else:
                print("초반에 reset 으로 돌다가 멈춰버린 경우 다시 init 해줘야함 ! ")
                self.init_database()
                self.simul_reset = True

    # 데이터베이스 초기화 함수
    def init_database(self):
        self.drop_database()
        self.create_database()
        self.init_df_jango()
        self.init_df_all_item()

    # 데이터베이스를 생성하는 함수
    def create_database(self):
        if self.is_simul_database_exist() == False:
            sql = 'CREATE DATABASE %s'
            self.db_conn.cursor().execute(sql % (self.db_name))
            self.db_conn.commit()

    # 데이터베이스를 삭제하는 함수
    def drop_database(self):
        if self.is_simul_database_exist():
            print("drop!!!!")
            sql = "drop DATABASE %s"
            self.db_conn.cursor().execute(sql % (self.db_name))
            self.db_conn.commit()

    # 데이터베이스의 존재 유무를 파악하는 함수.
    def is_simul_database_exist(self):
        sql = "SELECT 1 FROM Information_schema.SCHEMATA WHERE SCHEMA_NAME = '%s'"
        rows = self.engine_daily_buy_list.execute(sql % (self.db_name)).fetchall()
        print("rows : ", rows)
        if len(rows):
            return True
        else:
            return False

    # 오늘 날짜를 설정하는 함수
    def date_setting(self):
        self.today = datetime.datetime.today().strftime("%Y%m%d")
        self.today_detail = datetime.datetime.today().strftime("%Y%m%d%H%M")
        self.today_date_form = datetime.datetime.strptime(self.today, "%Y%m%d").date()

    # DB 이름 세팅 함수
    def db_name_setting(self):
        self.engine_simulator = create_engine(
            "mysql+mysqldb://" + cf.db_id + ":" + cf.db_passwd + "@" + cf.db_ip + ":" + cf.db_port + "/" + str(
                self.db_name),
            encoding='utf-8')
        if self.op != "real":
            # db_name을 setting 한다.
            self.db_name = "simulator" + str(self.simul_num)
            self.engine_simulator = create_engine(
                "mysql+mysqldb://" + cf.db_id + ":" + cf.db_passwd + "@" + cf.db_ip + ":" + cf.db_port + "/" + str(
                    self.db_name), encoding='utf-8')


        self.engine_daily_craw = create_engine(
            "mysql+mysqldb://" + cf.db_id + ":" + cf.db_passwd + "@" + cf.db_ip + ":" + cf.db_port + "/daily_craw",
            encoding='utf-8')

        self.engine_craw = create_engine(
            "mysql+mysqldb://" + cf.db_id + ":" + cf.db_passwd + "@" + cf.db_ip + ":" + cf.db_port + "/min_craw",
            encoding='utf-8')
        self.engine_daily_buy_list = create_engine(
            "mysql+mysqldb://" + cf.db_id + ":" + cf.db_passwd + "@" + cf.db_ip + ":" + cf.db_port + "/daily_buy_list",
            encoding='utf-8')

        event.listen(self.engine_simulator, 'before_execute', escape_percentage, retval=True)
        event.listen(self.engine_daily_craw, 'before_execute', escape_percentage, retval=True)
        event.listen(self.engine_craw, 'before_execute', escape_percentage, retval=True)
        event.listen(self.engine_daily_buy_list, 'before_execute', escape_percentage, retval=True)

        # 특정 데이터 베이스가 아닌, mysql 에 접속하는 객체
        self.db_conn = pymysql.connect(host=cf.db_ip, port=int(cf.db_port), user=cf.db_id, password=cf.db_passwd,
                                       charset='utf8')

    # 매수 함수
    def invest_send_order(self, date, code, code_name, price, yes_close, j):
        # print("invest_send_order!!!")
        # 시작가가 투자하려는 금액 보다 작아야 매수가 가능하기 때문에 아래 조건
        if price < self.invest_unit:
            _df = self.df_realtime_daily_buy_list
            _score = int(_df.loc[j, 'composite_score']) if 'composite_score' in _df.columns else 0
            _sa = int(_df.loc[j, 'score_a']) if 'score_a' in _df.columns else 0
            _sb = int(_df.loc[j, 'score_b']) if 'score_b' in _df.columns else 0
            _sc = int(_df.loc[j, 'score_c']) if 'score_c' in _df.columns else 0
            _sd = int(_df.loc[j, 'score_d']) if 'score_d' in _df.columns else 0
            _se = int(_df.loc[j, 'score_e']) if 'score_e' in _df.columns else 0
            print(f"  ✅ 매수: {code_name} ({code}) | 총{_score}pt [A모멘텀:{_sa} B평균회귀:{_sb} C추세:{_sc} D거래량:{_sd} E시장:{_se}]")

            # 매수를 하게 되면 all_item_db 테이블에 반영을 한다.
            self.db_to_all_item(date, self.df_realtime_daily_buy_list, j,
                                code,
                                code_name, price,
                                yes_close)

            # 매수를 성공적으로 했으면 realtime_daily_buy_list 테이블의 check_item 에 매수 시간을 설정
            self.update_realtime_daily_buy_list(code, date)

            # 일별, 분별 정산 함수
            self.check_balance()

    # code명으로 code_name을 가져오는 함수
    def get_name_by_code(self, code):

        sql = "select code_name from stock_item_all where code = '%s'"
        code_name = self.engine_daily_buy_list.execute(sql % (code)).fetchall()
        print(code_name)
        if code_name:
            return code_name[0][0]
        else:
            return False

    # 실제 매수하는 함수
    def auto_trade_stock_realtime(self, min_date, date_rows_today, date_rows_yesterday):
        logger.debug("auto_trade_stock_realtime 함수에 들어왔다!!")
        # self.df_realtime_daily_buy_list 에 있는 모든 종목들을 매수한다
        for j in range(self.len_df_realtime_daily_buy_list):
            if self.jango_check():

                # 종목 코드를 가져온다.
                code = str(self.df_realtime_daily_buy_list.loc[j, 'code']).rjust(6, "0")

                # 종목명을 가져온다.
                code_name = self.df_realtime_daily_buy_list.loc[j, 'code_name']

                # (촬영 후 추가 코드) 매수 들어가기전에 db에 테이블이 존재하는지 확인
                # 분별 시뮬레이팅 인 경우
                if self.use_min:
                    # print("code_name!!", code_name)
                    # min_craw db에 종목이 없으면 매수 하지 않는다.
                    if not self.is_min_craw_table_exist(code_name):
                        continue
                # 일별 시뮬레이팅 인 경우
                else:
                    # daily_craw db에 종목이 없으면 매수 하지 않는다.
                    if not self.is_daily_craw_table_exist(code_name):
                        continue

                # 아래 if else 구문은 영상 촬영 후 수정 하였습니다. open_price 를 가져오는 것을 분별/일별 시뮬레이션 구분하여 설정하였습니다.
                # 분별 시뮬레이션이 아닌 일별 시뮬레이션의 경우
                if not self.use_min:
                    # 매수 당일 시작가를 가져온다.
                    price = self.get_now_open_price_by_date(code, date_rows_today)
                # 분별 시뮬레이션의 경우
                else:
                    # 매수 시점의 가격을 가져온다.
                    price = self.get_now_close_price_by_min(code_name, min_date)

                # 어제 종가를 가져온다.
                yes_close = self.get_yes_close_price_by_date(code, date_rows_yesterday)

                # False는 데이터가 없는것
                if code_name == False or price == 0 or price == False:
                    continue

                # 촬영 후 아래 if 문 추가 (향후 실시간 조건 매수 시 사용) ###################
                if self.use_min and not self.only_nine_buy and self. trade_check_num :
                    # 시작가
                    open = self.get_now_open_price_by_date(code, date_rows_today)
                    # 당일 누적 거래량
                    sum_volume = self.get_now_volume_by_min(code_name, min_date)

                    # open, sum_volume 값이 존재 할 경우
                    if open and sum_volume:
                        # 매수 할 종목에 대한 dataframe row와, 시작가, 현재가, 분별 누적 거래량 정보를 전달
                        if not self.trade_check(self.df_realtime_daily_buy_list.loc[j], open, price, sum_volume):
                            # 실시간 매수 조건에 맞지 않는 경우 pass
                            continue
                ################################################################

                # 매수 주문에 들어간다.
                self.invest_send_order(min_date, code, code_name, price, yes_close, j)
            else:
                break

    # 최근 daily_buy_list의 날짜 테이블에서 code에 해당 하는 row만 가져오는 함수
    def get_daily_buy_list_by_code(self, code, date):
        # print("get_daily_buy_list_by_code 함수에 들어왔습니다!")
        import pandas as pd
        sql = "select * from `%s` where code = '%s' group by code" % (date, code)
        df_daily_buy_list = pd.read_sql(sql, self.engine_daily_buy_list)
        return df_daily_buy_list

    # realtime_daily_buy_list 테이블의 매수 리스트를 가져오는 함수
    def get_realtime_daily_buy_list(self):
        logger.debug("get_realtime_daily_buy_list 함수에 들어왔습니다!")

        # 이 부분은 촬영 후 코드를 간소화 했습니다. 조건문 모두 없앴습니다.
        # check_item = 매수 했을 시 날짜가 찍혀 있다. 매수 하지 않았을 때는 0
        # composite_score 내림차순 정렬: 점수가 높은 종목부터 매수 (실제 트레이더만)
        if self.op == 'real':
            # 실제 트레이더: composite_score로 정렬 (컬럼 없으면 code로 폴백)
            import pandas as pd
            logger.debug("Using database engine: %s", self.engine_simulator.url.database)
            try:
                sql = "select * from realtime_daily_buy_list where check_item = '0' order by composite_score desc, code"
                logger.debug("SQL query: %s", sql)
                self.df_realtime_daily_buy_list = pd.read_sql(sql, self.engine_simulator)
            except Exception:
                sql = "select * from realtime_daily_buy_list where check_item = '0' order by code"
                logger.debug("composite_score 없음, code 정렬로 폴백: %s", sql)
                self.df_realtime_daily_buy_list = pd.read_sql(sql, self.engine_simulator)
            logger.debug("Query returned %d rows", len(self.df_realtime_daily_buy_list))
        elif self.simul_num in (4, 5, 6):
            # simul_num=4/5/6: strategy_type 컬럼 포함 — pd.read_sql로 전체 읽기
            import pandas as pd
            sql = "select * from realtime_daily_buy_list where check_item = '0' order by composite_score desc, code"
            logger.debug("SQL query (sim=4/5/6): %s", sql)
            logger.debug("Using database engine: %s", self.engine_simulator.url.database)
            self.df_realtime_daily_buy_list = pd.read_sql(sql, self.engine_simulator)
            logger.debug("Query returned %d rows", len(self.df_realtime_daily_buy_list))
        else:
            # 시뮬레이터: rsi14, bb_upper, bb_middle, bb_lower, atr14 포함 (47개)
            sql = "select * from realtime_daily_buy_list where check_item = '%s' order by code"
            logger.debug("SQL query: %s", sql % (0))
            logger.debug("Using database engine: %s", self.engine_simulator.url.database)
            realtime_daily_buy_list = self.engine_simulator.execute(sql % (0)).fetchall()
            logger.debug("Query returned %d rows", len(realtime_daily_buy_list))
            self.df_realtime_daily_buy_list = DataFrame(realtime_daily_buy_list,
                                                        columns=['date', 'check_item', 'code', 'code_name',
                                                                 'd1_diff_rate', 'close', 'open', 'high',
                                                                 'low', 'volume',
                                                                 'clo5', 'clo10', 'clo20', 'clo40', 'clo60', 'clo80',
                                                                 'clo100', 'clo120',
                                                                 "clo5_diff_rate", "clo10_diff_rate", "clo20_diff_rate",
                                                                 "clo40_diff_rate", "clo60_diff_rate", "clo80_diff_rate",
                                                                 "clo100_diff_rate", "clo120_diff_rate",
                                                                 'yes_clo5', 'yes_clo10', 'yes_clo20', 'yes_clo40',
                                                                 'yes_clo60', 'yes_clo80', 'yes_clo100', 'yes_clo120',
                                                                 'vol5', 'vol10', 'vol20', 'vol40', 'vol60', 'vol80',
                                                                 'vol100', 'vol120',
                                                                 'rsi14', 'bb_upper', 'bb_middle', 'bb_lower', 'atr14',
                                                                 'composite_score',
                                                                 'score_a', 'score_b', 'score_c', 'score_d',
                                                                 'score_e', 'score_f', 'score_penalty'])

        self.len_df_realtime_daily_buy_list = len(self.df_realtime_daily_buy_list)

    # 가장 최근의 daily_buy_list에 담겨 있는 날짜 테이블 이름을 가져오는 함수
    def get_recent_daily_buy_list_date(self):
        sql = "select TABLE_NAME from information_schema.tables where table_schema = 'daily_buy_list' and TABLE_NAME like '%s' order by table_name desc limit 1"
        row = self.engine_daily_buy_list.execute(sql % ("20%%")).fetchall()

        if len(row) == 0:
            return False
        return row[0][0]

    # 실시간 주가 분석 알고리즘 함수 (느낌표 골뱅이 추가하면 검색 시 편합니다) (고급클래스에서 소개)
    def trade_check(self, df_row, open_price, current_price, current_sum_volume):
        '''
        :param df_row: 매수 종목 리스트(realtime_daily_buy_list)
        :param current_price: (현재가)
        :param current_sum_volume: (현재 누적 거래량)
        :return: True (매수), False(매수 X)
        '''
        code_name = df_row['code_name']
        yes_vol20 = df_row['vol20']
        yes_close = df_row['close']
        yes_high = df_row['high']
        yes_low = df_row['low']
        yes_volume = df_row['volume']

        # 실시간 거래 대금 체크 알고리즘
        if self.trade_check_num == 1:
            # 어제 거래 대금
            yes_total_tr_price = yes_close * yes_volume
            # 현재 거래 대금
            current_total_tr_price = current_price * current_sum_volume
            # 어제 종가 보다 현재가가 증가했고, 거래 대금이 어제 거래대금에 비해서 x배 올라갔을 때 매수
            if current_price > yes_close and current_total_tr_price > yes_total_tr_price * self.volume_up:
                return True
            else:
                return False

        elif self.trade_check_num == 2:
            # 매수 가격 최저 범위
            min_buy_limit = int(yes_close) * self.invest_min_limit_rate
            # 매수 가격 최고 범위
            max_buy_limit = int(yes_close) * self.invest_limit_rate
            # 현재가가 매수 가격 최저 범위와 매수 가격 최고 범위 안에 들어와 있다면 매수 한다.
            if min_buy_limit < current_price < max_buy_limit:
                return True
            else:
                return False

        # 래리 윌리엄스 변동성 돌파 알고리즘(매수)
        elif self.trade_check_num == 3:
            # 변동폭(_range): 전일 고가(yes_high)에서 전일 저가(yes_low)를 뺀 가격
            # 매수시점 : 현재가 > 시작가 + (변동폭 * k)  [k는 0~1 사이 수]
            _range = yes_high - yes_low
            if open_price + _range * self.rarry_k < current_price:
                return True
            else:
                return False

        else:
            logger.debug("trade_check 함수에 self.trade_check_num = {} 에 맞는 알고리즘이 없습니다. ".format(self.trade_check_num))
            exit(1)

    # 여기서 sql문의 date는 반드시 어제 일자여야 한다. -> 어제 일자 기준 반영된 데이터로 종목을 선정해야함.
    ##!@####################################################################################################################################################################################
    # 매수 할 종목의 리스트를 선정 알고리즘
    def db_to_realtime_daily_buy_list(self, date_rows_today, date_rows_yesterday, i):
        # 🚀 전략 1: 하이브리드 전략 (Momentum 60% + Mean Reversion 40%)
        # ✅ collector_api.py의 _hybrid_strategy_sql과 동일한 로직
        # ✅ RSI14, Bollinger Bands, ATR14 활용
        if self.db_to_realtime_daily_buy_list_num == 1:
            sql = '''
                SELECT a.*,
                    -- 하이브리드 스코어 (모멘텀 60점 + 평균회귀 40점 = 100점 만점)
                    (
                        -- 모멘텀 (60점 만점)
                        CASE
                            WHEN a.volume > a.vol20 * 2.0 THEN 20
                            WHEN a.volume > a.vol20 * 1.5 THEN 15
                            WHEN a.volume > a.vol20 * 1.2 THEN 10
                            ELSE 5
                        END +
                        CASE
                            WHEN a.clo5 > a.clo20 AND a.clo20 > a.clo60 THEN 20
                            WHEN a.clo5 > a.clo20 THEN 15
                            ELSE 5
                        END +
                        CASE
                            WHEN a.atr14 > 0 AND (a.high - a.low) > a.atr14 * 1.5 THEN 20
                            WHEN a.atr14 > 0 AND (a.high - a.low) > a.atr14 THEN 15
                            ELSE 10
                        END +
                        -- 평균회귀 (40점 만점)
                        CASE
                            WHEN a.rsi14 <= 30 THEN 15
                            WHEN a.rsi14 <= 40 THEN 10
                            WHEN a.rsi14 <= 50 THEN 5
                            ELSE 0
                        END +
                        CASE
                            WHEN a.bb_lower > 0 AND a.close <= a.bb_lower THEN 15
                            WHEN a.bb_lower > 0 AND a.close <= a.bb_lower * 1.02 THEN 10
                            WHEN a.bb_middle > 0 AND a.close < a.bb_middle THEN 5
                            ELSE 0
                        END +
                        CASE
                            WHEN a.close > a.clo20 * 0.95 AND a.close < a.clo20 * 1.0 THEN 10
                            WHEN a.close > a.clo60 * 0.95 AND a.close < a.clo60 * 1.0 THEN 8
                            ELSE 3
                        END
                    ) AS calculated_score
                FROM `''' + date_rows_yesterday + '''` a
                WHERE
                    -- 기본 필터
                    NOT EXISTS (SELECT null FROM stock_konex b WHERE a.code = b.code)
                    AND a.close > 0
                    AND a.volume > 0
                    AND a.rsi14 > 0  -- RSI 계산 성공한 종목만
                    AND a.bb_lower > 0  -- 볼린저 밴드 계산 성공한 종목만

                    -- 하이브리드 조건 (모멘텀 OR 평균회귀)
                    AND (
                        -- 모멘텀 조건
                        (a.clo5 > a.clo20 AND a.volume > a.vol20 * 1.2)
                        OR
                        -- 평균회귀 조건
                        (a.rsi14 <= 40 AND a.bb_lower > 0 AND a.close <= a.bb_lower * 1.05)
                    )

                    -- 가격 범위
                    AND a.close BETWEEN 1000 AND 500000

                HAVING calculated_score >= 90
                ORDER BY calculated_score DESC
                LIMIT ''' + str(self.max_positions) + '''
            '''
            realtime_daily_buy_list_raw = self.engine_daily_buy_list.execute(sql).fetchall()

            # calculated_score 컬럼 제거 (마지막 컬럼)
            realtime_daily_buy_list = [row[:-1] for row in realtime_daily_buy_list_raw]


        # 🔄 전략 2: 혼합 전략 (날짜 기반 20% + 하이브리드 80%)
        # 두 전략을 가중 합산한 점수가 90점 이상인 종목만 선택
        elif self.db_to_realtime_daily_buy_list_num == 2:
            sql = '''
                SELECT a.*,
                    -- 날짜 기반 스코어 (원본, 100점 스케일)
                    (
                        (a.volume / NULLIF(a.vol5, 0)) *
                        (a.clo5 / NULLIF(a.clo20, 0)) *
                        CASE
                            WHEN a.volume > a.vol20 * 1.5 THEN 1.2
                            ELSE 1.0
                        END
                    ) * 30.0 AS date_score,

                    -- 하이브리드 스코어 (모멘텀 60점 + 평균회귀 40점 = 100점 만점)
                    (
                        CASE
                            WHEN a.volume > a.vol20 * 2.0 THEN 20
                            WHEN a.volume > a.vol20 * 1.5 THEN 15
                            WHEN a.volume > a.vol20 * 1.2 THEN 10
                            ELSE 5
                        END +
                        CASE
                            WHEN a.clo5 > a.clo20 AND a.clo20 > a.clo60 THEN 20
                            WHEN a.clo5 > a.clo20 THEN 15
                            ELSE 5
                        END +
                        CASE
                            WHEN a.atr14 > 0 AND (a.high - a.low) > a.atr14 * 1.5 THEN 20
                            WHEN a.atr14 > 0 AND (a.high - a.low) > a.atr14 THEN 15
                            ELSE 10
                        END +
                        CASE
                            WHEN a.rsi14 <= 30 THEN 15
                            WHEN a.rsi14 <= 40 THEN 10
                            WHEN a.rsi14 <= 50 THEN 5
                            ELSE 0
                        END +
                        CASE
                            WHEN a.bb_lower > 0 AND a.close <= a.bb_lower THEN 15
                            WHEN a.bb_lower > 0 AND a.close <= a.bb_lower * 1.02 THEN 10
                            WHEN a.bb_middle > 0 AND a.close < a.bb_middle THEN 5
                            ELSE 0
                        END +
                        CASE
                            WHEN a.close > a.clo20 * 0.95 AND a.close < a.clo20 * 1.0 THEN 10
                            WHEN a.close > a.clo60 * 0.95 AND a.close < a.clo60 * 1.0 THEN 8
                            ELSE 3
                        END
                    ) AS hybrid_score,

                    -- 최종 혼합 스코어 (날짜 20% + 하이브리드 80% 가중 합산)
                    (
                        -- 날짜 기반 (20%)
                        (
                            (a.volume / NULLIF(a.vol5, 0)) *
                            (a.clo5 / NULLIF(a.clo20, 0)) *
                            CASE
                                WHEN a.volume > a.vol20 * 1.5 THEN 1.2
                                ELSE 1.0
                            END
                        ) * 30.0 * 0.2
                        +
                        -- 하이브리드 (80%)
                        (
                            CASE
                                WHEN a.volume > a.vol20 * 2.0 THEN 20
                                WHEN a.volume > a.vol20 * 1.5 THEN 15
                                WHEN a.volume > a.vol20 * 1.2 THEN 10
                                ELSE 5
                            END +
                            CASE
                                WHEN a.clo5 > a.clo20 AND a.clo20 > a.clo60 THEN 20
                                WHEN a.clo5 > a.clo20 THEN 15
                                ELSE 5
                            END +
                            CASE
                                WHEN a.atr14 > 0 AND (a.high - a.low) > a.atr14 * 1.5 THEN 20
                                WHEN a.atr14 > 0 AND (a.high - a.low) > a.atr14 THEN 15
                                ELSE 10
                            END +
                            CASE
                                WHEN a.rsi14 <= 30 THEN 15
                                WHEN a.rsi14 <= 40 THEN 10
                                WHEN a.rsi14 <= 50 THEN 5
                                ELSE 0
                            END +
                            CASE
                                WHEN a.bb_lower > 0 AND a.close <= a.bb_lower THEN 15
                                WHEN a.bb_lower > 0 AND a.close <= a.bb_lower * 1.02 THEN 10
                                WHEN a.bb_middle > 0 AND a.close < a.bb_middle THEN 5
                                ELSE 0
                            END +
                            CASE
                                WHEN a.close > a.clo20 * 0.95 AND a.close < a.clo20 * 1.0 THEN 10
                                WHEN a.close > a.clo60 * 0.95 AND a.close < a.clo60 * 1.0 THEN 8
                                ELSE 3
                            END
                        ) * 0.8
                    ) AS calculated_score

                FROM `''' + date_rows_yesterday + '''` a
                WHERE
                    -- 기본 필터
                    NOT EXISTS (SELECT null FROM stock_konex b WHERE a.code = b.code)
                    AND a.close > 0
                    AND a.volume > 0

                    -- 날짜 기반 OR 하이브리드 조건
                    AND (
                        -- 날짜 기반 조건
                        (a.volume > a.vol5 * 1.2 AND a.clo5 > a.clo20)
                        OR
                        -- 하이브리드 조건
                        (
                            a.rsi14 > 0 AND a.bb_lower > 0 AND
                            (
                                (a.clo5 > a.clo20 AND a.volume > a.vol20 * 1.2)
                                OR
                                (a.rsi14 <= 40 AND a.close <= a.bb_lower * 1.05)
                            )
                        )
                    )

                    -- 가격 범위
                    AND a.close BETWEEN 1000 AND 500000

                HAVING
                    -- 가중 합산 점수가 90점 이상인 종목만 선택
                    calculated_score >= 90
                ORDER BY calculated_score DESC
                LIMIT ''' + str(self.max_positions) + '''
            '''
            realtime_daily_buy_list_raw = self.engine_daily_buy_list.execute(sql).fetchall()

            # calculated_score, date_score, hybrid_score 컬럼 제거 (마지막 3개 컬럼)
            realtime_daily_buy_list = [row[:-3] for row in realtime_daily_buy_list_raw]


        elif self.db_to_realtime_daily_buy_list_num == 3:
            sql = "select * from `" + date_rows_yesterday + "` a where d1_diff_rate > 1 " \
                                                            "and NOT exists (select null from stock_konex b where a.code=b.code) " \
                                                            "and close < '%s' group by code"
            # 아래 명령을 통해 테이블로 부터 데이터를 가져오면 리스트 형태로 realtime_daily_buy_list 에 담긴다.
            realtime_daily_buy_list = self.engine_daily_buy_list.execute(sql % (self.invest_unit)).fetchall()

        # 시뮬 4번 매수 알고리즘
        elif self.db_to_realtime_daily_buy_list_num == 4:
            sql = "select * from `" + date_rows_yesterday + "` a " \
                                                            "where yes_clo20 > yes_clo5 and clo5 > clo20 " \
                                                            "and NOT exists (select null from stock_konex b where a.code=b.code)" \
                                                            "and NOT exists (select null from stock_managing c where a.code=c.code and c.code_name != '' group by c.code) " \
                                                            "and NOT exists (select null from stock_insincerity d where a.code=d.code and d.code_name !='' group by d.code) " \
                                                            "and NOT exists (select null from stock_invest_caution e where a.code=e.code and DATE_SUB('%s', INTERVAL '%s' MONTH ) < e.post_date and e.post_date < Date('%s') and e.type != '투자경고 지정해제' group by e.code)" \
                                                            "and NOT exists (select null from stock_invest_warning f where a.code=f.code and f.post_date <= DATE('%s') and (f.cleared_date > DATE('%s') or f.cleared_date is null) group by f.code)" \
                                                            "and NOT exists (select null from stock_invest_danger g where a.code=g.code and g.post_date <= DATE('%s') and (g.cleared_date > DATE('%s') or g.cleared_date is null) group by g.code)" \
                                                            "and a.close < '%s'"

            realtime_daily_buy_list = self.engine_daily_buy_list.execute(sql % (
            date_rows_yesterday, self.interval_month, date_rows_yesterday, date_rows_yesterday, date_rows_yesterday,
            date_rows_yesterday, date_rows_yesterday, self.invest_unit)).fetchall()

        ####################
        # 매수함수
        elif self.db_to_realtime_daily_buy_list_num == 5:
            sql = "select * from `" + date_rows_yesterday + "` a " \
                    "where yes_clo20 > yes_clo5 and clo5 > clo20 " \
                    "and volume * close > '%s' " \
                    "and vol20 * '%s' < volume " \
                    "and d1_diff_rate > '%s' " \
                    "and NOT exists (select null from stock_konex b where a.code=b.code)" \
                    "and NOT exists (select null from stock_managing c where a.code=c.code and c.code_name != '' group by c.code) " \
                    "and NOT exists (select null from stock_insincerity d where a.code=d.code and d.code_name !='' group by d.code) " \
                    "and NOT exists (select null from stock_invest_caution e where a.code=e.code and DATE_SUB('%s', INTERVAL '%s' MONTH ) < e.post_date and e.post_date < Date('%s') and e.type != '투자경고 지정해제' group by e.code)"\
                    "and NOT exists (select null from stock_invest_warning f where a.code=f.code and f.post_date <= DATE('%s') and (f.cleared_date > DATE('%s') or f.cleared_date is null) group by f.code)"\
                    "and NOT exists (select null from stock_invest_danger g where a.code=g.code and g.post_date <= DATE('%s') and (g.cleared_date > DATE('%s') or g.cleared_date is null) group by g.code)"\
                    "and a.close < '%s'" \
                    "order by volume * close desc"
            realtime_daily_buy_list = self.engine_daily_buy_list.execute(
                sql % (self.total_transaction_price, self.vol_mul, self.d1_diff ,
                       date_rows_yesterday, self.interval_month, date_rows_yesterday,
                       date_rows_yesterday, date_rows_yesterday, date_rows_yesterday,
                       date_rows_yesterday, self.invest_unit)).fetchall()

        # # 절대 모멘텀 전략 : 특정일 전의 종가 보다 n% 이상 상승한 종목 매수 (code version)
        elif self.db_to_realtime_daily_buy_list_num == 7:
            # 아래에서 필터링 된 매수종목을 append 해주기 위해 비어있는 리스트를 만들어준다.
            realtime_daily_buy_list = []
            if i < self.day_before + 1:
                pass
            else:
                sql = "SELECT * FROM `" + date_rows_yesterday +"` a " \
                       "WHERE NOT exists (SELECT null FROM stock_konex b WHERE a.code=b.code) " \
                       "AND close < '%s' "
                # realtime_daily_buy_list_temp 로 일단 위 조건의 종목을을받는다.
                realtime_daily_buy_list_temp = self.engine_daily_buy_list.execute(sql % (self.invest_unit)).fetchall()
                for row in realtime_daily_buy_list_temp:
                    # 종목코드
                    code = row[4]
                    # 어제 종가
                    yes_close = row[7]
                    # date_rows_yesterday 가 self.date_rows[i-1] 값이다.
                    # 어제 일자 기준 n 일전 날짜
                    date_before = self.date_rows[i-1-self.day_before][0]
                    # 어제 일자 기준 n 일전 종가
                    date_before_close = self.get_now_close_price_by_date(code, date_before)
                    if date_before_close != 0 and date_before_close != False :
                        # 모멘텀 계산 : n일전 종가 대비 수익률
                        diff_point_calc = (yes_close - date_before_close) / date_before_close * 100
                        # 모멘텀(수익률)이 self.diff_point 보다 높을 경우 realtime_daily_buy_list에 append
                        if diff_point_calc > self.diff_point:
                            realtime_daily_buy_list.append(row)


        # 절대 모멘텀 전략 : 특정일 전의 종가 보다 n% 이상 상승한 종목 매수 (query vesrion)
        elif self.db_to_realtime_daily_buy_list_num == 8:
            if i < self.day_before + 1:
                realtime_daily_buy_list = []
                pass
            else:
                date_before = self.date_rows[i - 1 - self.day_before][0]
                sql = "SELECT YES_DAY.* " \
                      "FROM `"+date_before+"` BEFORE_DAY, `" + date_rows_yesterday +"` YES_DAY "\
                        "WHERE BEFORE_DAY.code = YES_DAY.code "\
                        "AND (YES_DAY.close - BEFORE_DAY.close) / BEFORE_DAY.close * 100 > '%s' " \
                        "AND NOT exists (SELECT null FROM stock_konex b WHERE YES_DAY.code=b.code)" \
                        "AND YES_DAY.close < '%s'"

                realtime_daily_buy_list = self.engine_daily_buy_list.execute(sql % (self.diff_point, self.invest_unit)).fetchall()

        # 상대 모멘텀 전략 : 특정일 전의 종가 보다 n% 이상 상승한 종목 중 가장 많이 상승한 종목 순으로 매수 (내림차순) (query version)
        elif self.db_to_realtime_daily_buy_list_num == 9:
            if i < self.day_before + 1:
                realtime_daily_buy_list = []
                pass
            else:
                date_before = self.date_rows[i - 1 - self.day_before][0]
                sql = "SELECT YES_DAY.* " \
                      "FROM `" + date_before + "` BEFORE_DAY, `" + date_rows_yesterday + "` YES_DAY " \
                     "WHERE BEFORE_DAY.code = YES_DAY.code " \
                     "AND (YES_DAY.close - BEFORE_DAY.close) / BEFORE_DAY.close * 100 > '%s' " \
                     "AND NOT exists (SELECT null FROM stock_konex b WHERE YES_DAY.code=b.code)" \
                     "AND YES_DAY.close < '%s'" \
                     "ORDER BY (YES_DAY.close - BEFORE_DAY.close) / BEFORE_DAY.close * 100 DESC"

                realtime_daily_buy_list = self.engine_daily_buy_list.execute(
                    sql % (self.diff_point, self.invest_unit)).fetchall()

        ### ETF
        elif self.db_to_realtime_daily_buy_list_num == 11:
            sql = f"SELECT * from `{date_rows_yesterday}` YES_DAY " \
                  "WHERE yes_clo20 > yes_clo5 and clo5 > clo20 " \
                  "AND EXISTS (SELECT null FROM stock_etf ETF WHERE YES_DAY.code=ETF.code) " \
                  f"AND close < {self.invest_unit} " \
                  "GROUP BY code"
            realtime_daily_buy_list = self.engine_daily_buy_list.execute(sql).fetchall()

        ### 종목 정보 테이블을 활용한 우량주, 고신용 종목 매수 알고리즘
        # audit이 정상이고, 거래정지, 관리종목을 제외한 종목 리스트를 매수
        elif self.db_to_realtime_daily_buy_list_num == 12:
            sql = f'''
                SELECT day.* FROM `{date_rows_yesterday}` day, stock_info info
                WHERE day.code = info.code
                AND info.stock_market IN ("거래소", "코스닥")
                AND info.category0 IN ("우량기업", "신성장기업")
                AND info.audit = '정상'
                AND info.margin <= 40
                AND info.remarks NOT LIKE "%관리종목%"
                AND info.remarks NOT LIKE "%거래정지%"
            '''
            realtime_daily_buy_list = self.engine_daily_buy_list.execute(sql).fetchall()

        # 📈 전략 20: 5/20 골든크로스 (기본 전략)
        # 5일선이 20일선을 상향 돌파한 종목 매수
        elif self.db_to_realtime_daily_buy_list_num == 20:
            sql = "select * from `" + date_rows_yesterday + "` a where yes_clo20 > yes_clo5 and clo5 > clo20 " \
                                                            "and NOT exists (select null from stock_konex b where a.code=b.code) " \
                                                            "and close < '%s' group by code limit 10"

            realtime_daily_buy_list = self.engine_daily_buy_list.execute(sql % (self.invest_unit)).fetchall()

        # 🤖 전략 21: HybridStrategyV2 (250점 만점 Python 점수 기반)
        elif self.db_to_realtime_daily_buy_list_num == 21:
            import pandas as pd
            from library.hybrid_strategy_v2 import HybridStrategyV2
            strategy_v2 = HybridStrategyV2()

            logger.debug(f"[num=21] 매수후보 스코어링 시작 - 기준날짜: {date_rows_today}")

            # SQL 사전 필터: 모멘텀/추세/과매도 신호 기준 상위 200개 종목만 선별
            # (전 종목 df_120 로딩은 너무 느림: 2300개 × 768일)
            try:
                candidates_sql = f"""
                    SELECT a.* FROM `{date_rows_today}` a
                    WHERE NOT EXISTS (SELECT null FROM stock_konex b WHERE a.code=b.code)
                    AND a.close > 0 AND a.close < {self.invest_unit}
                    AND a.volume > 0 AND a.vol20 > 0
                    ORDER BY (
                        (CASE WHEN a.adx > 20 THEN 1 ELSE 0 END) +
                        (CASE WHEN a.clo5 > a.clo20 THEN 1 ELSE 0 END) +
                        (CASE WHEN a.rsi14 BETWEEN 30 AND 55 THEN 1 ELSE 0 END) +
                        (CASE WHEN a.macd > a.macd_signal THEN 1 ELSE 0 END) +
                        (CASE WHEN a.cmf20 > 0 THEN 1 ELSE 0 END)
                    ) DESC
                    LIMIT 200
                """
                candidates = self.engine_daily_buy_list.execute(candidates_sql).fetchall()
                logger.debug(f"[num=21] SQL 사전필터 완료 - 후보: {len(candidates)}개")
            except Exception as e:
                logger.debug(f"[num=21] SQL 사전필터 실패: {e}")
                candidates = []

            # dart 테이블에서 날짜 기준 연도 재무 데이터 로드 (역사적 정확성)
            # 사업보고서 공시: 보통 3~4월 → 1~3월은 전전년도, 4월~ 는 전년도 사용
            fundamental_dict = {}
            try:
                _year = int(date_rows_today[:4])
                _month = int(date_rows_today[4:6])
                _bsns_year = str(_year - 2 if _month <= 3 else _year - 1)
                dart_sql = (
                    "SELECT code, account_nm, thstrm_amount FROM dart "
                    "WHERE bsns_year = '{}' AND fs_nm = '재무제표' "
                    "AND account_nm IN ("
                    "'매출액','수익(매출액)','영업이익','영업이익(손실)',"
                    "'당기순이익','당기순이익(손실)','자본총계')"
                ).format(_bsns_year)
                dart_rows = self.engine_daily_buy_list.execute(dart_sql).fetchall()
                for dr in dart_rows:
                    _code = dr[0]
                    _acct = dr[1]
                    _amt = float(dr[2]) / 1e8 if dr[2] else 0.0  # 억원 단위
                    if _code not in fundamental_dict:
                        fundamental_dict[_code] = {}
                    if '매출액' in _acct or '수익' in _acct:
                        fundamental_dict[_code]['sales'] = _amt
                    elif '영업이익' in _acct:
                        fundamental_dict[_code]['operating_profit'] = _amt
                    elif '당기순이익' in _acct:
                        fundamental_dict[_code]['net_profit'] = _amt
                    elif _acct == '자본총계':
                        fundamental_dict[_code]['total_equity'] = _amt
                # ROE 계산
                for _fd in fundamental_dict.values():
                    _eq = _fd.get('total_equity', 0)
                    _np = _fd.get('net_profit', 0)
                    _fd['roe'] = (_np / _eq * 100) if _eq and _eq != 0 else 0.0
            except Exception as e:
                logger.debug(f"[num=21] DART 재무데이터 로드 실패: {e}")

            logger.debug(f"[num=21] DART 재무데이터 로드 완료 - {len(fundamental_dict)}개 종목")

            # sf_YYYYMMDD 날짜별 테이블에서 수급지표 로드 (외인소진률, 신용비율, 250일 고가비율)
            # 시뮬 날짜 기준 가장 가까운(≤) sf 테이블 사용
            fundamental_extra = {}
            try:
                sf_row = self.engine_daily_buy_list.execute(
                    "SELECT TABLE_NAME FROM information_schema.tables "
                    "WHERE table_schema = 'daily_buy_list' AND TABLE_NAME LIKE 'sf_2%' "
                    f"AND TABLE_NAME <= 'sf_{date_rows_today}' "
                    "ORDER BY TABLE_NAME DESC LIMIT 1"
                ).fetchone()
                if sf_row:
                    sf_table = sf_row[0]
                    fund_df = pd.read_sql(
                        f"SELECT code, foreign_rate, credit_rate, high_250_rate FROM `{sf_table}`",
                        self.engine_daily_buy_list
                    )
                    for _, fr in fund_df.iterrows():
                        fundamental_extra[str(fr['code']).zfill(6)] = {
                            'foreign_rate': fr['foreign_rate'],
                            'credit_rate': fr['credit_rate'],
                            'high_250_rate': fr['high_250_rate'],
                        }
                    logger.debug(f"[num=21] {sf_table} 수급지표 로드 완료 - {len(fundamental_extra)}개")
                else:
                    logger.debug(f"[num=21] sf 테이블 없음 ({date_rows_today} 이전) — 수급지표 미사용")
            except Exception as e:
                logger.debug(f"[num=21] sf 수급지표 로드 실패: {e}")

            # kospi_index 최근 20일 close 로드 (없으면 None)
            market_data = None
            try:
                ki_df = pd.read_sql(
                    "SELECT close FROM kospi_index ORDER BY date DESC LIMIT 20",
                    self.engine_daily_craw
                )
                if len(ki_df) >= 20:
                    market_data = ki_df['close'].iloc[::-1].reset_index(drop=True)
                logger.debug(f"[num=21] kospi_index 로드 완료 - {len(ki_df)}일치")
            except Exception as e:
                logger.debug(f"[num=21] kospi_index 로드 실패: {e}")

            # 종목별 Python 점수 계산
            logger.debug(f"[num=21] 종목별 스코어링 시작 - {len(candidates)}개 후보")
            scored_list = []
            for idx, row in enumerate(candidates):
                code = row['code']
                code_name = row['code_name']
                logger.debug(f"[num=21] 스코어링 {idx+1}/{len(candidates)}: {code_name}({code})")
                try:
                    df_120 = pd.read_sql(
                        f"SELECT * FROM `{code_name}` WHERE code = '{code}'"
                        f" AND date <= '{date_rows_today}' ORDER BY date DESC LIMIT 120",
                        self.engine_daily_craw
                    )
                    if len(df_120) < 2:
                        continue
                    df_120 = df_120.sort_values('date').reset_index(drop=True)
                except Exception as e:
                    logger.debug(f"[num=21] df_120 로드 실패 {code_name}: {e}")
                    continue

                fd = fundamental_dict.get(code)
                row_dict = dict(row)  # RowProxy → dict (.get() 사용 가능)
                # stock_fundamental 수급지표 머지 (foreign_rate, credit_rate, high_250_rate)
                extra = fundamental_extra.get(code, {})
                if extra:
                    row_dict.update(extra)
                # fundamental_data=None으로 넘겨 PER/PBR 기반 필터 우회
                # (dart 데이터는 roe/sales만 있어 PER/PBR 필터 통과 불가)
                score_result = strategy_v2.calculate_total_score(row_dict, df_120, None, market_data)
                total_score = score_result['total']
                # dart ROE 보너스 별도 계산 (펀더멘털 가산점)
                if fd and total_score >= 0:
                    roe = fd.get('roe', 0) or 0
                    if roe >= 15:
                        total_score += 15
                    elif roe >= 5:
                        total_score += int((roe - 5) / 10 * 15)

                if total_score >= cf.v2_min_score:
                    row_dict['composite_score'] = total_score
                    row_dict['score_a']       = score_result['score_a']
                    row_dict['score_b']       = score_result['score_b']
                    row_dict['score_c']       = score_result['score_c']
                    row_dict['score_d']       = score_result['score_d']
                    row_dict['score_e']       = score_result['score_e']
                    row_dict['score_f']       = score_result['score_f']
                    row_dict['score_penalty'] = score_result['score_penalty']
                    scored_list.append((row_dict, total_score))
                    logger.debug(f"[num=21] ✅ 합격: {code_name} {total_score}pt")

            logger.debug(f"[num=21] 스코어링 완료 - 합격: {len(scored_list)}개 / {len(candidates)}개")
            scored_list.sort(key=lambda x: x[1], reverse=True)
            # dict 리스트: DataFrame(list_of_dicts, columns=[...]) 로 45컬럼 처리
            realtime_daily_buy_list = [item[0] for item in scored_list]

        # 🤖 전략 22: BreakoutStrategyV3 / ReversalStrategyV3 (simul_num=4/5/6)
        elif self.db_to_realtime_daily_buy_list_num == 22:
            import pandas as pd
            if self.simul_num == 4:
                from library.hybrid_strategy_v3 import BreakoutStrategyV3
                strategies = [BreakoutStrategyV3()]
                min_score = cf.v4_min_score_a
                logger.debug(f"[num=22] simul_num=4 BreakoutStrategyV3 시작 - 기준날짜: {date_rows_today}")
            elif self.simul_num == 5:
                from library.hybrid_strategy_v3 import ReversalStrategyV3
                strategies = [ReversalStrategyV3()]
                min_score = cf.v4_min_score_b
                logger.debug(f"[num=22] simul_num=5 ReversalStrategyV3 시작 - 기준날짜: {date_rows_today}")
            else:  # simul_num == 6
                from library.hybrid_strategy_v3 import BreakoutStrategyV3, ReversalStrategyV3
                strategies = [BreakoutStrategyV3(), ReversalStrategyV3()]
                min_score = min(cf.v4_min_score_a, cf.v4_min_score_b)
                logger.debug(f"[num=22] simul_num=6 A+B 혼합 시작 - 기준날짜: {date_rows_today}")

            # SQL 사전 필터: 전략별 특성에 맞는 후보 선별
            try:
                if self.simul_num == 4:
                    # Strategy A: 오늘 상승 + 거래량 급증 + BB 상단 근처
                    pre_filter_sql = f"""
                        SELECT a.* FROM `{date_rows_today}` a
                        WHERE NOT EXISTS (SELECT null FROM stock_konex b WHERE a.code=b.code)
                        AND a.close > 0 AND a.close < {self.invest_unit}
                        AND a.volume > 0 AND a.vol20 > 0
                        AND a.d1_diff_rate >= 1.5
                        AND a.vol5 > a.vol20 * 1.2
                        ORDER BY a.d1_diff_rate DESC
                        LIMIT 150
                    """
                elif self.simul_num == 5:
                    # Strategy B: 중장기 사이클 — 진짜 과매도 후 회복 중인 종목
                    pre_filter_sql = f"""
                        SELECT a.* FROM `{date_rows_today}` a
                        WHERE NOT EXISTS (SELECT null FROM stock_konex b WHERE a.code=b.code)
                        AND a.close > 0 AND a.close < {self.invest_unit}
                        AND a.volume > 0 AND a.vol20 > 0
                        AND a.rsi14 <= 54
                        AND a.rsi14 >= 25
                        ORDER BY a.rsi14 ASC
                        LIMIT 150
                    """
                else:  # sim=6
                    # A+B 각각 독립 필터 후 UNION — A 최대 150 + B 최대 150 = 최대 300 (중복 제거)
                    pre_filter_sql = f"""
                        (SELECT a.* FROM `{date_rows_today}` a
                         WHERE NOT EXISTS (SELECT null FROM stock_konex b WHERE a.code=b.code)
                         AND a.close > 0 AND a.close < {self.invest_unit}
                         AND a.volume > 0 AND a.vol20 > 0
                         AND a.d1_diff_rate >= 1.5
                         AND a.vol5 > a.vol20 * 1.2
                         ORDER BY a.d1_diff_rate DESC
                         LIMIT 150)
                        UNION
                        (SELECT a.* FROM `{date_rows_today}` a
                         WHERE NOT EXISTS (SELECT null FROM stock_konex b WHERE a.code=b.code)
                         AND a.close > 0 AND a.close < {self.invest_unit}
                         AND a.volume > 0 AND a.vol20 > 0
                         AND a.rsi14 <= 54
                         AND a.rsi14 >= 25
                         ORDER BY a.rsi14 ASC
                         LIMIT 150)
                    """
                candidates = self.engine_daily_buy_list.execute(pre_filter_sql).fetchall()
                if self.simul_num == 6:
                    cnt_a = sum(1 for r in candidates if r['d1_diff_rate'] >= 1.5 and r['vol5'] > r['vol20'] * 1.2)
                    cnt_b = sum(1 for r in candidates if r['rsi14'] <= 54 and r['rsi14'] >= 25)
                    logger.debug(f"[num=22] SQL 사전필터 완료 - 후보: {len(candidates)}개 (A:{cnt_a} / B:{cnt_b})")
                elif self.simul_num == 4:
                    logger.debug(f"[num=22] SQL 사전필터 완료 - 후보: {len(candidates)}개 (A:{len(candidates)})")
                else:
                    logger.debug(f"[num=22] SQL 사전필터 완료 - 후보: {len(candidates)}개 (B:{len(candidates)})")
            except Exception as e:
                logger.debug(f"[num=22] SQL 사전필터 실패: {e}")
                candidates = []

            # kospi_index 최근 20일 close 로드 (없으면 None)
            market_data = None
            try:
                ki_df = pd.read_sql(
                    "SELECT close FROM kospi_index ORDER BY date DESC LIMIT 20",
                    self.engine_daily_craw
                )
                if len(ki_df) >= 20:
                    market_data = ki_df['close'].iloc[::-1].reset_index(drop=True)
            except Exception as e:
                logger.debug(f"[num=22] kospi_index 로드 실패: {e}")

            # 종목별 스코어링
            scored_list = []
            total_cands = len(candidates)
            if total_cands > 0:
                print(f"  [스코어링] {date_rows_today} 후보 {total_cands}개 처리 중...", flush=True)
            for idx, row in enumerate(candidates):
                code = row['code']
                code_name = row['code_name']
                # 10개마다 진행상황 콘솔 출력 (hang 여부 확인)
                if idx % 10 == 0:
                    print(f"  [스코어링] {idx+1}/{total_cands} {code_name}", end='\r', flush=True)
                logger.debug(f"[num=22] 스코어링 {idx+1}/{total_cands}: {code_name}({code})")
                try:
                    df_120 = pd.read_sql(
                        f"SELECT * FROM `{code_name}` WHERE code = '{code}'"
                        f" AND date <= '{date_rows_today}' ORDER BY date DESC LIMIT 120",
                        self.engine_daily_craw
                    )
                    if len(df_120) < 2:
                        continue
                    df_120 = df_120.sort_values('date').reset_index(drop=True)
                except Exception as e:
                    logger.debug(f"[num=22] df_120 로드 실패 {code_name}: {e}")
                    continue

                row_dict = dict(row)

                if len(strategies) == 1:
                    result = strategies[0].calculate_total_score(row_dict, df_120, market_data)
                    if not result['auto_reject'] and result['total'] >= min_score:
                        row_dict['composite_score'] = int(result['total'])
                        row_dict['score_a']       = result['score_a']
                        row_dict['score_b']       = result['score_b']
                        row_dict['score_c']       = result['score_c']
                        row_dict['score_d']       = result['score_d']
                        row_dict['score_e']       = result['score_e']
                        row_dict['score_f']       = result['score_f']
                        row_dict['score_penalty'] = result['score_penalty']
                        row_dict['strategy_type'] = result['strategy_type']
                        scored_list.append((row_dict, result['total']))
                        logger.debug(f"[num=22] ✅ 합격: {code_name} {result['total']}pt ({result['strategy_type']})")
                else:
                    # sim=6: 두 전략 모두 계산, 높은 점수 선택
                    best_result = None
                    best_score = -9999
                    for strategy in strategies:
                        r = strategy.calculate_total_score(row_dict, df_120, market_data)
                        if not r['auto_reject'] and r['total'] > best_score:
                            best_score = r['total']
                            best_result = r
                    if best_result is not None and best_score >= (cf.v4_min_score_a if best_result['strategy_type'] == 'A' else cf.v4_min_score_b):
                        best_score = best_result['total']
                        row_dict['composite_score'] = int(best_score)
                        row_dict['score_a']       = best_result['score_a']
                        row_dict['score_b']       = best_result['score_b']
                        row_dict['score_c']       = best_result['score_c']
                        row_dict['score_d']       = best_result['score_d']
                        row_dict['score_e']       = best_result['score_e']
                        row_dict['score_f']       = best_result['score_f']
                        row_dict['score_penalty'] = best_result['score_penalty']
                        row_dict['strategy_type'] = best_result['strategy_type']
                        scored_list.append((row_dict, best_score))
                        logger.debug(f"[num=22] ✅ 합격: {code_name} {best_score}pt ({best_result['strategy_type']})")

            count_a = sum(1 for item in scored_list if item[0].get('strategy_type') == 'A')
            count_b = sum(1 for item in scored_list if item[0].get('strategy_type') == 'B')
            logger.debug(f"[num=22] 스코어링 완료 - 합격: {len(scored_list)}개 (A:{count_a} / B:{count_b}) / 후보: {len(candidates)}개")
            scored_list.sort(key=lambda x: x[1], reverse=True)
            realtime_daily_buy_list = [item[0] for item in scored_list]

        # 🔧 전략 100: 심플 프로토타입 전략 (이동평균 기반)
        # 기본 이동평균 + 거래량 조합
        elif self.db_to_realtime_daily_buy_list_num == 100:
            sql = '''
                SELECT a.*
                FROM `''' + date_rows_yesterday + '''` a
                WHERE
                    -- 기본 필터: 코넥스 제외
                    NOT EXISTS (SELECT null FROM stock_konex b WHERE a.code = b.code)

                    -- 거래량 조건: 최소 거래량 확보
                    AND a.volume > a.vol5 * 1.2

                    -- 모멘텀 조건: 상승 추세
                    AND a.clo5 > a.clo20

                    -- 변동성 필터: 급등락 제외
                    AND a.d1_diff_rate BETWEEN -5 AND 5

                    -- 가격 필터: 저가주/고가주 제외 (1000원 ~ 50만원)
                    AND a.close BETWEEN 1000 AND 500000

                    -- NULL 방어
                    AND a.vol5 > 0 AND a.vol20 > 0
                    AND a.clo5 > 0 AND a.clo20 > 0

                ORDER BY
                    -- 🎯 복합 스코어 계산 (정렬용)
                    (
                        -- Date-based Strategy (30% 가중치)
                        -- 거래량 급증 + 상승 추세 스코어
                        (
                            (a.volume / NULLIF(a.vol5, 0)) *        -- 거래량 증가율
                            (a.clo5 / NULLIF(a.clo20, 0)) *         -- 단기/중기 모멘텀
                            CASE
                                WHEN a.volume > a.vol20 * 1.5 THEN 1.2   -- 거래량 급증 보너스
                                ELSE 1.0
                            END
                        ) * 0.3

                        -- Hybrid Strategy - Momentum (42% = 70% * 60%)
                        + (
                            ((a.clo5 - a.clo20) / NULLIF(a.clo20, 0)) *     -- 모멘텀 강도
                            (a.volume / NULLIF(a.vol20, 0))                  -- 거래량 확인
                        ) * 0.42

                        -- Hybrid Strategy - Mean Reversion (28% = 70% * 40%)
                        + (
                            -- 20일선 회귀 점수 (20일선에 가까울수록 높음)
                            (1 - ABS((a.close - a.clo20) / NULLIF(a.clo20, 0))) *
                            -- 과매도 구간 보너스
                            CASE
                                WHEN a.close < a.clo20 * 0.98 THEN 1.3  -- 2% 이상 하락 시 반등 기대
                                WHEN a.close < a.clo20 THEN 1.1         -- 20일선 하회 시 약간 가산
                                ELSE 1.0
                            END
                        ) * 0.28

                    ) DESC

                LIMIT ''' + str(self.max_positions) + '''
            '''
            realtime_daily_buy_list = self.engine_daily_buy_list.execute(sql).fetchall()

        ######################################################################################################################################################################################
        else:
            print(f"{self.simul_num}번 알고리즘에 대한 self.db_to_realtime_daily_buy_list_num 설정이 비었습니다. variable_setting 함수에서 self.db_to_realtime_daily_buy_list_num 을 확인해주세요.")
            sys.exit(1)
        # num=21 실전 모드: 0개여도 테이블을 클리어해 어제 데이터가 남지 않도록 함
        # (트레이더가 date 컬럼으로 collector 실행 여부를 판단하므로 오래된 데이터가 남으면 오동작)
        if self.db_to_realtime_daily_buy_list_num in (21, 22) and self.op == 'real' and len(realtime_daily_buy_list) == 0:
            try:
                if self.is_simul_table_exist(self.db_name, "realtime_daily_buy_list"):
                    self.engine_simulator.execute("DELETE FROM realtime_daily_buy_list")
            except Exception as e:
                print(f"realtime_daily_buy_list 클리어 실패: {e}")

        # realtime_daily_buy_list 에 종목이 하나라도 있다면, 즉 매수할 종목이 하나라도 있다면 아래 로직을 들어간다.
        if len(realtime_daily_buy_list) > 0:
            # realtime_daily_buy_list 라는 리스트를 df_realtime_daily_buy_list 라는 데이터프레임으로 변환하는 과정
            # 차이점은 리스트는 컬럼에 대한 개념이 없는데, 데이터프레임은 컬럼이 있다.

            df_realtime_daily_buy_list = DataFrame(realtime_daily_buy_list,
                                                   columns=['date', 'check_item', 'code', 'code_name',
                                                            'd1_diff_rate', 'close', 'open', 'high',
                                                            'low', 'volume',
                                                            'clo5', 'clo10', 'clo20', 'clo40', 'clo60', 'clo80',
                                                            'clo100', 'clo120',
                                                            "clo5_diff_rate", "clo10_diff_rate", "clo20_diff_rate",
                                                            "clo40_diff_rate", "clo60_diff_rate", "clo80_diff_rate",
                                                            "clo100_diff_rate", "clo120_diff_rate",
                                                            'yes_clo5', 'yes_clo10', 'yes_clo20', 'yes_clo40',
                                                            'yes_clo60', 'yes_clo80', 'yes_clo100', 'yes_clo120',
                                                            'vol5', 'vol10', 'vol20', 'vol40', 'vol60', 'vol80',
                                                            'vol100', 'vol120',
                                                            'rsi14', 'bb_upper', 'bb_middle', 'bb_lower', 'atr14'])

            # 종목코드를 6자리 문자열로 변환 (우선주 코드 'xxxRx' 형태도 처리)
            df_realtime_daily_buy_list['code'] = df_realtime_daily_buy_list['code'].astype(str).str.zfill(6)

            # 섹션별 스코어 컬럼 주입 (num=21/22: row_dict에 이미 저장됨, 나머지: 0)
            score_cols = ['composite_score', 'score_a', 'score_b', 'score_c', 'score_d', 'score_e', 'score_f', 'score_penalty']
            if self.db_to_realtime_daily_buy_list_num in (21, 22) and isinstance(realtime_daily_buy_list[0], dict):
                for col in score_cols:
                    df_realtime_daily_buy_list[col] = [row.get(col, 0) for row in realtime_daily_buy_list]
                if self.db_to_realtime_daily_buy_list_num == 22:
                    df_realtime_daily_buy_list['strategy_type'] = [d.get('strategy_type', 'A') for d in realtime_daily_buy_list]
            else:
                for col in score_cols:
                    df_realtime_daily_buy_list[col] = 0

            # 시뮬레이터의 경우
            if self.op != 'real':
                df_realtime_daily_buy_list['check_item'] = int(0)
                # [to_sql]
                # df_realtime_daily_buy_list 라는 데이터프레임을
                # simulator 데이터베이스의 realtime_daily_buy_list 테이블로 만들어주는 명령
                #
                # ** if_exists 옵션 **
                # # 데이터베이스에 테이블이 존재할 때 수행 동작을 지정한다.
                # 'fail', 'replace', 'append' 중 하나를 사용할 수 있는데 기본값은 'fail'이다.
                # 'fail'은 데이터베이스에 테이블이 있다면 아무 동작도 수행하지 않는다.
                # 'replace'는 테이블이 존재하면 기존 테이블을 삭제하고 새로 테이블을 생성한 후 데이터를 삽입한다.
                # 'append'는 테이블이 존재하면 데이터만을 추가한다.
                df_realtime_daily_buy_list.to_sql('realtime_daily_buy_list', self.engine_simulator, if_exists='replace', index=False)

                # 현재 보유 중인 종목은 매수 리스트(realtime_daily_buy_list) 에서 제거 하는 로직
                if self.is_simul_table_exist(self.db_name, "all_item_db"):
                    sql = "delete from realtime_daily_buy_list where code in (select code from all_item_db where sell_date = '%s' or buy_date = '%s' or sell_date = '%s')"
                    # delete는 리턴 값이 없기 때문에 fetchall 쓰지 않는다.
                    self.engine_simulator.execute(sql % (0, date_rows_today, date_rows_today))

                # 영상 촬영 후 추가 된 코드입니다. AI챕터에서 다룰 예정입니다.
                if self.use_ai:
                    from ai_filter import ai_filter
                    ai_filter(self.ai_filter_num, engine=self.engine_simulator, until=date_rows_yesterday)

                # 최종적으로 realtime_daily_buy_list 테이블에 저장 된 종목들을 가져온다.
                self.get_realtime_daily_buy_list()

            # 모의, 실전 투자 봇 의 경우
            else:
                # check_item 컬럼에 0 으로 setting
                df_realtime_daily_buy_list['check_item'] = int(0)
                # num=21/22: row_dict 기반이므로 모든 컬럼(composite_score, strategy_type 포함) DataFrame으로 저장
                if self.db_to_realtime_daily_buy_list_num in (21, 22):
                    import pandas as pd
                    df_write = pd.DataFrame(realtime_daily_buy_list)
                    df_write['check_item'] = int(0)
                    df_write.to_sql('realtime_daily_buy_list', self.engine_simulator, if_exists='replace', index=False)
                else:
                    df_realtime_daily_buy_list.to_sql('realtime_daily_buy_list', self.engine_simulator, if_exists='replace', index=False)

                # 현재 보유 중인 종목 삭제
                sql = "delete from realtime_daily_buy_list where code in (select code from possessed_item)"
                self.engine_simulator.execute(sql)

                # 오늘 이미 매수한 종목 삭제 (장중 재수집 시 중복 매수 방지)
                # possessed_item은 매도 후 사라지므로, all_item_db의 오늘 매수 이력까지 체크
                import datetime as _dt
                _today = _dt.datetime.now().strftime('%Y%m%d')
                sql_bought = f"delete from realtime_daily_buy_list where code in (select code from all_item_db where LEFT(buy_date, 8) = '{_today}')"
                self.engine_simulator.execute(sql_bought)


        # 매수할 종목이 없으면, df_realtime_daily_buy_list라는 데이터프레임의 길이를 저장하는
        # len_df_realtime_daily_buy_list에 다가 0을 넣는다.
        else:
            self.len_df_realtime_daily_buy_list = 0
            #강의 촬영 후 추가 코드 (매수 조건에 맞는 종목이 하나도 없을 경우 realtime_daily_buy_list 를 비워준다)
            if self.engine_simulator.dialect.has_table(self.engine_simulator, "realtime_daily_buy_list"):
                self.engine_simulator.execute("""
                    DELETE FROM realtime_daily_buy_list 
                """)

    # 현재의 주가를 all_item_db에 있는 보유한 종목들에 대해서 반영 한다.
    def db_to_all_item_present_price_update(self, code_name, d1_diff_rate, close, open, high, low, volume, clo5, clo10, clo20,
                                                         clo40, clo60, clo80, clo100, clo120, option='ALL', rsi14=None):
        # 영상 촬영 후 아래 내용 업데이트 하였습니다.
        if self.op == 'real': # 콜렉터에서 업데이트 할 때는 현재가를 종가로 업데이트(trader에서 실시간으로 present_price 업데이트함)
            present_price = close
        else:
            present_price = open # 시뮬레이터에서는 open가를 현재가로 업데이트

        # option이 ALL이면 모든 데이터 업데이트
        if option == "ALL":
            # 시뮬레이터는 간소화된 스키마: close/open/high/low 없음, clo* → ma*로 매핑
            sql = f"update all_item_db set d1_diff_rate = {d1_diff_rate}, volume = {volume}, present_price = {present_price}, " \
                  f"ma5 = {clo5}, ma10 = {clo10}, ma20 = {clo20}, ma60 = {clo60}, ma120 = {clo120} " \
                  f"where code_name = '{code_name}' and sell_date = {0}"
        # option이 OPEN이면 present_price 만 업데이트
        else:
            sql = f"update all_item_db set present_price = {present_price} where code_name = '{code_name}' and sell_date = {0}"

        self.engine_simulator.execute(sql)

        # max/min 잠재력 추적 (백테스트 분석용)
        if high and low and high > 0 and low > 0:
            sql_minmax = (
                f"UPDATE all_item_db SET "
                f"max_high_pct = GREATEST(COALESCE(max_high_pct, 0), (({high} / purchase_price) - 1) * 100), "
                f"min_low_pct = LEAST(COALESCE(min_low_pct, 0), (({low} / purchase_price) - 1) * 100) "
                f"WHERE code_name = '{code_name}' AND sell_date = 0"
            )
            self.engine_simulator.execute(sql_minmax)

        # RSI 추적 + rsi_peak 갱신 (B전략 Top Failure Swing 매도용)
        if rsi14 is not None and self.simul_num in (5, 6):
            try:
                self.engine_simulator.execute(
                    f"UPDATE all_item_db SET rsi14 = {float(rsi14)}, "
                    f"rsi_peak = GREATEST(COALESCE(rsi_peak, 0), {float(rsi14)}) "
                    f"WHERE code_name = '{code_name}' AND sell_date = 0"
                )
            except Exception:
                pass

    # jango_data 라는 테이블을 만들기 위한 self.jango 데이터프레임을 생성
    def init_df_jango(self):
        jango_temp = {'id': []}

        self.jango = DataFrame(jango_temp,
                               columns=['date', 'today_earning_rate', 'sum_valuation_profit', 'total_profit',
                                        'today_profit',
                                        'today_profitcut_count', 'today_losscut_count', 'today_profitcut',
                                        'today_losscut',
                                        'd2_deposit', 'total_possess_count', 'today_buy_count', 'today_buy_list_count',
                                        'today_reinvest_count',
                                        'today_cant_reinvest_count',
                                        'total_asset',
                                        'total_invest',
                                        'sum_item_total_purchase', 'total_evaluation', 'today_rate',
                                        'today_invest_price', 'today_reinvest_price',
                                        'today_sell_price', 'volume_limit', 'reinvest_point', 'sell_point',
                                        'max_reinvest_count', 'invest_limit_rate', 'invest_unit',
                                        'rate_std_sell_point', 'limit_money', 'total_profitcut', 'total_losscut',
                                        'total_profitcut_count',
                                        'total_losscut_count', 'loan_money', 'start_kospi_point',
                                        'start_kosdaq_point', 'end_kospi_point', 'end_kosdaq_point',
                                        'today_buy_total_sell_count',
                                        'today_buy_total_possess_count', 'today_buy_today_profitcut_count',
                                        'today_buy_today_profitcut_rate', 'today_buy_today_losscut_count',
                                        'today_buy_today_losscut_rate',
                                        'today_buy_total_profitcut_count', 'today_buy_total_profitcut_rate',
                                        'today_buy_total_losscut_count', 'today_buy_total_losscut_rate',
                                        'today_buy_reinvest_count0_sell_count',
                                        'today_buy_reinvest_count1_sell_count', 'today_buy_reinvest_count2_sell_count',
                                        'today_buy_reinvest_count3_sell_count', 'today_buy_reinvest_count4_sell_count',
                                        'today_buy_reinvest_count4_sell_profitcut_count',
                                        'today_buy_reinvest_count4_sell_losscut_count',
                                        'today_buy_reinvest_count5_sell_count',
                                        'today_buy_reinvest_count5_sell_profitcut_count',
                                        'today_buy_reinvest_count5_sell_losscut_count',
                                        'today_buy_reinvest_count0_remain_count',
                                        'today_buy_reinvest_count1_remain_count',
                                        'today_buy_reinvest_count2_remain_count',
                                        'today_buy_reinvest_count3_remain_count',
                                        'today_buy_reinvest_count4_remain_count',
                                        'today_buy_reinvest_count5_remain_count'],
                               index=jango_temp['id'])

    # all_item_db 라는 테이블을 만들기 위한 self.df_all_item 데이터프레임
    def init_df_all_item(self):
        df_all_item_temp = {}

        self.df_all_item = DataFrame(df_all_item_temp,
                                     columns=['code', 'code_name', 'chegyul_check', 'buy_date', 'buy_time',
                                              'purchase_price', 'holding_amount', 'present_price', 'rate',
                                              'valuation_profit', 'sell_date', 'sell_time', 'sell_price',
                                              'sell_rate', 'realized_profit', 'd1_diff_rate', 'yes_close',
                                              'volume', 'today_percent', 'ma5', 'ma10', 'ma20', 'ma60', 'ma120',
                                              'item_total_purchase', 'valuation_price',
                                              'composite_score',
                                              'score_a', 'score_b', 'score_c', 'score_d',
                                              'score_e', 'score_f', 'score_penalty',
                                              'simul_num',
                                              'max_high_pct', 'min_low_pct', 'rsi14', 'rsi_peak'])

    # 가장 초기에 매수 했을 때 all_item_db 에 추가하는 함수
    def db_to_all_item(self, min_date, df, index, code, code_name, purchase_price, yesterday_close):
        self.df_all_item.loc[0, 'code'] = code
        self.df_all_item.loc[0, 'code_name'] = code_name
        # 초기는 반드시 rate가 -0.33 이여야한다. -> 수수료, 세금을 반영함
        self.df_all_item.loc[0, 'rate'] = float(-0.33)

        self.df_all_item.loc[0, 'purchase_price'] = purchase_price
        self.df_all_item.loc[0, 'present_price'] = purchase_price

        # #jackbot("code_name: "+ code_name + "purchase_price: "+ str(purchase_price))
        self.df_all_item.loc[0, 'holding_amount'] = int(self.invest_unit / purchase_price)
        self.df_all_item.loc[0, 'buy_date'] = min_date
        self.df_all_item.loc[0, 'buy_time'] = ''

        # 실시간으로 오늘 투자한 금액 합산
        item_total_purchase = self.df_all_item.loc[0, 'purchase_price'] * self.df_all_item.loc[0, 'holding_amount']
        self.df_all_item.loc[0, 'item_total_purchase'] = item_total_purchase
        self.df_all_item.loc[0, 'valuation_price'] = 0
        self.today_invest_price = self.today_invest_price + item_total_purchase

        self.df_all_item.loc[0, 'chegyul_check'] = '0'
        self.df_all_item.loc[0, 'sell_date'] = '0'
        self.df_all_item.loc[0, 'sell_time'] = ''
        self.df_all_item.loc[0, 'sell_price'] = 0
        self.df_all_item.loc[0, 'sell_rate'] = float(0)
        self.df_all_item.loc[0, 'realized_profit'] = 0
        self.df_all_item.loc[0, 'yes_close'] = yesterday_close if yesterday_close else 0
        self.df_all_item.loc[0, 'volume'] = df.loc[index, 'volume'] if 'volume' in df.columns else 0
        self.df_all_item.loc[0, 'today_percent'] = 0

        if 'd1_diff_rate' in df.columns and df.loc[index, 'd1_diff_rate'] is not None:
            self.df_all_item.loc[0, 'd1_diff_rate'] = float(df.loc[index, 'd1_diff_rate'])
        else:
            self.df_all_item.loc[0, 'd1_diff_rate'] = 0

        # Map clo* columns to ma* columns
        self.df_all_item.loc[0, 'ma5'] = df.loc[index, 'clo5'] if 'clo5' in df.columns else 0
        self.df_all_item.loc[0, 'ma10'] = df.loc[index, 'clo10'] if 'clo10' in df.columns else 0
        self.df_all_item.loc[0, 'ma20'] = df.loc[index, 'clo20'] if 'clo20' in df.columns else 0
        self.df_all_item.loc[0, 'ma60'] = df.loc[index, 'clo60'] if 'clo60' in df.columns else 0
        self.df_all_item.loc[0, 'ma120'] = df.loc[index, 'clo120'] if 'clo120' in df.columns else 0

        self.df_all_item.loc[0, 'valuation_profit'] = int(0)
        for _col in ['composite_score', 'score_a', 'score_b', 'score_c', 'score_d', 'score_e', 'score_f', 'score_penalty']:
            self.df_all_item.loc[0, _col] = df.loc[index, _col] if _col in df.columns else 0
        self.df_all_item.loc[0, 'simul_num'] = self.simul_num
        self.df_all_item.loc[0, 'max_high_pct'] = 0.0
        self.df_all_item.loc[0, 'min_low_pct'] = 0.0
        self.df_all_item.loc[0, 'rsi14'] = 0.0
        self.df_all_item.loc[0, 'rsi_peak'] = 0.0
        if self.simul_num in (4, 5, 6):
            if 'strategy_type' in df.columns:
                self.df_all_item.loc[0, 'strategy_type'] = df.loc[index, 'strategy_type']
            elif self.simul_num == 4:
                self.df_all_item.loc[0, 'strategy_type'] = 'A'
            elif self.simul_num == 5:
                self.df_all_item.loc[0, 'strategy_type'] = 'B'

        # 컬럼 중에 nan 값이 있는 경우 0으로 변경 -> 이렇게 안하면 아래 데이터베이스에 넣을 때
        # AttributeError: 'numpy.int64' object has no attribute 'translate' 에러 발생
        self.df_all_item = self.df_all_item.fillna(0)

        self.df_all_item.to_sql('all_item_db', self.engine_simulator, if_exists='append', index=False)

    # 보유한 종목들을 가져오는 함수
    # sell_date가 0이면 현재 보유 중인 종목이다. 매도를 할 경우 sell_date에 매도 한 날짜가 찍힌다.
    def get_data_from_possessed_item(self):
        sql = "SELECT code_name from all_item_db where sell_date = '%s'"
        return self.engine_simulator.execute(sql % (0)).fetchall()

    # 보유 종복 수 반환 함수
    def get_count_possessed_item(self):
        sql = "SELECT count(*) from all_item_db where sell_date = '%s'"
        return self.engine_simulator.execute(sql % (0)).fetchall()[0][0]

    # 테이블의 존재 여부를 파악하는 함수
    def is_simul_table_exist(self, db_name, table_name):
        sql = "select 1 from information_schema.tables where table_schema = '%s' and table_name = '%s'"
        rows = self.engine_simulator.execute(sql % (db_name, table_name)).fetchall()
        if len(rows) == 1:
            return True
        else:
            return False

    # 일별, 분별 정산 함수
    def check_balance(self):
        # all_item_db가 없으면 check_balance 함수를 나가라
        if self.is_simul_table_exist(self.db_name, "all_item_db") == False:
            return

        # 총 수익 금액 (종목별 평가 금액 합산)
        sql = "SELECT sum(valuation_profit) from all_item_db"
        self.sum_valuation_profit = self.engine_simulator.execute(sql).fetchall()[0][0]
        logger.debug("sum_valuation_profit: " + str(self.sum_valuation_profit))

        # 전재산이라고 보면 된다. 현재 총손익 까지 고려했을 때
        self.total_invest_price = self.start_invest_price + self.sum_valuation_profit

        # 현재 총 투자한 금액 계산
        sql = "select sum(item_total_purchase) from all_item_db where sell_date = '%s'"
        self.total_purchase_price = self.engine_simulator.execute(sql % (0)).fetchall()[0][0]
        if self.total_purchase_price is None:
            self.total_purchase_price = 0

        # 매도를 한 종목들 대상 수익 계산
        sql = "select sum(valuation_profit) from all_item_db where sell_date != '%s'"
        self.total_valuation_profit = self.engine_simulator.execute(sql % (0)).fetchall()[0][0]

        if self.total_valuation_profit is None:
            self.total_valuation_profit = 0

        # 현재 투자 가능한 금액(예수금) = (초기자본 + 매도한 종목의 수익) - 현재 총 투자 금액
        self.d2_deposit = self.start_invest_price + self.total_valuation_profit - self.total_purchase_price

    # 시뮬레이팅 할 날짜를 가져 오는 함수
    # 장이 열렸던 날 들을 self.date_rows 에 담기 위해서 gs글로벌의 date값을 대표적으로 가져온 것
    def get_date_for_simul(self):
        sql = "select date from `gs글로벌` where date >= '%s' and date <= '%s' group by date"
        self.date_rows = self.engine_daily_craw.execute(sql % (self.simul_start_date, self.simul_end_date)).fetchall()

    # daily_buy_list에 일자 테이블이 존재하는지 확인하는 함수
    def is_date_exist(self, date):
        logger.debug("is_date_exist 함수에 들어왔습니다! " + date)
        sql = "select 1 from information_schema.tables where table_schema ='daily_buy_list' and table_name = '%s'"
        rows = self.engine_daily_buy_list.execute(sql % (date)).fetchall()
        if len(rows) == 1:
            return True
        else:
            return False

    # 잔액 체크 함수, 잔고가 있으면 True를 반환, 없으면 False를 반환
    def jango_check(self):
        if int(self.d2_deposit) >= (int(self.limit_money) + int(self.invest_unit)):
            return True
        else:
            logger.debug("돈부족해서 invest 불가!!!!!!!!")
            return False

    # 출력 함수
    def print_info(self, min_date):
        logger.debug("*&*&*&* self.simul_num :" + str(self.simul_num))
        # all_itme_db 테이블이 생성 되어 있으면 보유한 종목 수를 출력
        if self.is_simul_table_exist(self.db_name, "all_item_db"):
            print(f"\n📅 {min_date} | 💼 보유종목: {self.get_count_possessed_item()}개")

    # 특정 종목의 시작가를 가져오는 함수(일별)
    def get_now_open_price_by_date(self, code, date):
        sql = "select open from `" + date + "` where code = '%s' group by code"
        open = self.engine_daily_buy_list.execute(sql % (code)).fetchall()
        if len(open) == 1:
            return open[0][0]
        else:
            print("daily_buy_list db의 " + str(date) + " 테이블에 " + str(code) + " 가 존재하지 않는다!")
            return False
        # 테이블의 존재 여부를 파악하는 함수

    # daily_craw 데이터 베이스에서 특정 종목이 존재하는 여부를 파악하는 함수
    def is_daily_craw_table_exist(self, code_name):
        sql = "select 1 from information_schema.tables where table_schema = 'daily_craw' and table_name = '%s'"
        rows = self.engine_daily_craw.execute(sql % (code_name)).fetchall()
        if len(rows) == 1:
            return True
        else:
            print("daily_craw db 에 " + str(code_name) + " 테이블이 존재하지 않는다. !! ")
            return False

    # min_craw 데이터 베이스에서 특정 종목이 존재하는 여부를 파악하는 함수
    def is_min_craw_table_exist(self, code_name):
        sql = "select 1 from information_schema.tables where table_schema = 'min_craw' and table_name = '%s'"
        rows = self.engine_craw.execute(sql % (code_name)).fetchall()
        if len(rows) == 1:
            return True
        else:
            print("min_craw db 에 " + str(code_name) + " 테이블이 존재하지 않는다. !! ")
            return False

    # 분별 현재 누적 거래량 가져오는 함수
    def get_now_volume_by_min(self, code_name, min_date):
        sql = "select sum_volume from `" + code_name + "` where date = '%s' and open != 0 and volume !=0 order by sum_volume desc limit 1"
        rows = self.engine_craw.execute(sql % (min_date)).fetchall()
        if len(rows) == 1:
            return rows[0][0]
        else:
            return False

    # 분별 현재 종가 가져오는 함수
    # (close가 일별 데이터에서는 일별 종가 이지만, 분별 데이터에서의 close는 각 분별에 대한 종가를 의미
    # 즉, 1분 간격으로 변화하는 시세를 가져오는 함수
    def get_now_close_price_by_min(self, code_name, min_date):
        sql = "select close from `" + code_name + "` where date = '{}' and open != 0 and volume !=0 order by sum_volume desc limit 1"
        rows = self.engine_craw.execute(sql.format(min_date)).fetchall()

        if len(rows) == 1:
            return rows[0][0]
        else:
            return False

    # 특정 종목의 종가를 가져오는 함수
    def get_now_close_price_by_date(self, code, date):
        sql = "select close from `" + date + "` where code = '%s' group by code"
        return_price = self.engine_daily_buy_list.execute(sql % (code)).fetchall()

        if len(return_price) == 1:
            return return_price[0][0]
        else:
            return False

    # 특정 종목의 어제 종가를 가져오는 함수
    def get_yes_close_price_by_date(self, code, date):
        sql = "select close from `" + date + "` where code = '%s' group by code"
        return_price = self.engine_daily_buy_list.execute(sql % (code)).fetchall()

        if len(return_price) == 1:

            return return_price[0][0]
        else:
            return False

    # 종목의 현재 일자에 대한 주가 정보를 가져 오는 함수
    def get_now_price_by_date(self, code_name, date):
        sql = "select d1_diff_rate, close, open, high, low, volume, clo5, clo10, clo20, clo40, clo60, clo80, clo100, clo120, rsi14 from `" + date + "` where code_name = '%s' group by code"
        rows = self.engine_daily_buy_list.execute(sql % (code_name)).fetchall()

        if len(rows) == 1:
            return rows
        else:
            return False

    # all_item_db의 보유한 종목에 현재가를 실시간으로 반영하는 함수
    def db_to_all_item_present_price_update_by_min(self, code_name, now_close_price):
        sql = "update all_item_db set present_price = '%s' where code_name = '%s' and sell_date = 0"
        self.engine_simulator.execute(sql % (now_close_price, code_name))

    # 분 마다 보유한 종목의 시세를 업데이트 하는 함수
    def update_all_db_by_min(self, min_date):
        # 매분마다 possess db 가져와야한다
        possessed_code_name = self.get_data_from_possessed_item()
        for j in range(len(possessed_code_name)):
            # 현재 시간의 close 값을 가져온다.
            now_close_price = self.get_now_close_price_by_min(possessed_code_name[j][0], min_date)
            # print("possessed_code_name: ", possessed_code_name[j][0], "now_close_price: ", now_close_price, "min_date", min_date)
            if now_close_price:
                self.db_to_all_item_present_price_update_by_min(possessed_code_name[j][0], now_close_price)
            else:
                # print(min_date + " / " + str(possessed_code_name[j][0]) + " 의 open_price 가 존재하지 않는다")
                continue

    # 보유 중인 종목들의 주가를 일별로 업데이트 하는 함수
    # all_item_db에서 업데이트를 한다.  option = 'ALL' 의미는 인자값을 date 하나만 줬을 때 option에는 기본값으로 ALL을 준다는 의미
    def update_all_db_by_date(self, date, option='ALL'):
        logger.debug("update_all_db_by_date 함수에 들어왔다!")
        # 현재 보유 중인 종목 들의 code_name 리스트
        possessed_code_name_list = self.get_data_from_possessed_item()
        if len(possessed_code_name_list) == 0:
            logger.debug("현재 보유 중인 종목이 없다 !!!!!")
        for j in range(len(possessed_code_name_list)):
            # 현재 주가를 가져오는 함수
            code_name = possessed_code_name_list[j][0]
            rows = self.get_now_price_by_date(code_name, date)
            if rows == False:
                continue
            d1_diff_rate = rows[0][0]
            close = rows[0][1]
            open = rows[0][2]
            high = rows[0][3]
            low = rows[0][4]
            volume = rows[0][5]
            clo5 = rows[0][6]
            clo10 = rows[0][7]
            clo20 = rows[0][8]
            clo40 = rows[0][9]
            clo60 = rows[0][10]
            clo80 = rows[0][11]
            clo100 = rows[0][12]
            clo120 = rows[0][13]
            rsi14 = rows[0][14] if len(rows[0]) > 14 else None

            # 만약에 open가에 어떤 값이 있으면(True) 현재 주가를 all_item_db에 반영 하기 위해 아래 함수를 들어간다.
            if open:
                self.db_to_all_item_present_price_update(code_name, d1_diff_rate, close, open, high, low, volume, clo5, clo10, clo20,
                                                         clo40, clo60, clo80, clo100, clo120, option, rsi14=rsi14)

                # [시뮬레이터 당일 손절 보정]
                # 실전에서는 장중 손절가 도달 시 즉시 매도하지만, 시뮬레이터는 시가 기준이라
                # 당일 종가가 손절가 이하로 떨어졌을 경우 그 종가로 매도한 것으로 처리.
                if option == 'OPEN' and self.op != 'real' and close:
                    purchase_row = self.engine_simulator.execute(
                        "SELECT purchase_price FROM all_item_db WHERE code_name = '%s' AND sell_date = 0" % code_name
                    ).fetchone()
                    if purchase_row and purchase_row[0]:
                        losscut_price = purchase_row[0] * (1 + self.losscut_point / 100)
                        if close <= losscut_price:
                            self.engine_simulator.execute(
                                "UPDATE all_item_db SET present_price = %d WHERE code_name = '%s' AND sell_date = 0"
                                % (int(close), code_name)
                            )
            else:
                continue

    # 보유 중인 종목들의 주가 이외의 기타 정보들을 업데이트 하는 함수
    def update_all_db_etc(self):
        # valuation_price 업데이트
        sql = f"update all_item_db set valuation_price = round((present_price  * holding_amount) - item_total_purchase * {self.fees_rate} - present_price*holding_amount*{self.fees_rate + self.tax_rate}) where sell_date = '%s'"
        self.engine_simulator.execute(sql % (0))

        # valuation_profit, rate 업데이트
        sql = "update all_item_db set rate= round((valuation_price - item_total_purchase)/item_total_purchase*100,2), valuation_profit =  valuation_price - item_total_purchase where sell_date = '%s';"
        self.engine_simulator.execute(sql % (0))

    # 언제 종목을 팔지(익절, 손절) 결정 하는 알고리즘.
    # !@##############################################################################################################################
    def get_sell_list(self, i):
        logger.debug("get_sell_list!!!")
        # 단순히 현재 보유 종목의 수익률이
        # 익절 기준 수익률(self.sell_point) 이 넘거나,
        # 손절 기준 수익률(self.losscut_point) 보다 떨어지면 파는 알고리즘
        if self.sell_list_num == 1:
            # select 할 컬럼은 항상 코드, 종목명, 수익률, 매도할 종목의 현재가, 수익(손실)금액
            # sql 첫 번째 라인은 항상 고정
            sql = "SELECT code, code_name, rate, present_price, valuation_profit FROM all_item_db WHERE (sell_date = '%s') " \
                  "and (rate>='%s' or rate <= '%s') group by code"
            sell_list = self.engine_simulator.execute(sql % (0, self.sell_point, self.losscut_point)).fetchall()

        # 5 / 20 이동 평균선 데드크로스 이거나, losscut_point(손절 기준 수익률) 이하로 떨어지면 손절하는 알고리즘
        elif self.sell_list_num == 2:
            sql = "SELECT code, code_name, rate, present_price, valuation_profit FROM all_item_db WHERE (sell_date = '%s') " \
                  "and ((ma5 < ma20) or rate <= '%s') group by code"
            sell_list = self.engine_simulator.execute(sql % (0, self.losscut_point)).fetchall()


        # 5 / 40 이동 평균선 데드크로스 이거나, losscut_point(손절 기준 수익률) 이하로 떨어지면 손절하는 알고리즘
        elif self.sell_list_num == 3:
            sql = "SELECT code, code_name, rate, present_price, valuation_profit FROM all_item_db WHERE (sell_date = '%s') " \
                  "and ((ma5 < ma60) or rate <= '%s') group by code"

            sell_list = self.engine_simulator.execute(sql % (0, self.losscut_point)).fetchall()


        # # 절대 모멘텀 전략 (특정일 전 보다 n% 이하로 떨어지면 매도) / code 버전
        elif self.sell_list_num == 4:
           sell_list = []
           sql = "SELECT code, code_name, rate, present_price, valuation_profit FROM all_item_db WHERE sell_date = 0 " \
                 "group by code"
           # realtime_daily_buy_list_temp 로 일단 위 조건의 종목을을받는다.
           sell_list_temp = self.engine_simulator.execute(sql).fetchall()
           for row in sell_list_temp:
               code = row[0]
               # code_name = row[1]
               # rate = row[2]
               present_price = row[3]  # 인덱스 수정 (2 → 3)
               # valuation_profit = row[4]
               # date_rows_yesterday 가 self.date_rows[i-1] 값이다.
               # date_rows_today 가 self.date_rows[i]
               # 오늘 기준 n일 전 날짜
               date_before = self.date_rows[i - self.day_before][0]
               # 오늘 기준 n일 전 종가
               date_before_close = self.get_now_close_price_by_date(code, date_before)
               if date_before_close != 0 and date_before_close != False:
                   diff_point_calc = (present_price - date_before_close) / date_before_close * 100
                   # 현재가(present_price)가 self.day_before 일 전 종가 보다 self.diff_point(0도 가능) 만큼 떨어 지면 매도
                   if diff_point_calc < self.diff_point * (-1):
                       sell_list.append(row)

        # 절대 모멘텀 전략 (특정일 전 보다 n% 이하로 떨어지면 매도) / query 버전
        elif self.sell_list_num == 5:
           date_before = self.date_rows[i - self.day_before][0]
           sql = "SELECT ALLDB.code, ALLDB.code_name, ALLDB.rate, ALLDB.present_price, ALLDB.valuation_profit " \
                 "FROM all_item_db ALLDB, daily_buy_list.`" + date_before + "` BEFORE_DAY "\
                   "WHERE ALLDB.code = BEFORE_DAY.code " \
                   "AND ALLDB.sell_date = 0 "\
                   "AND (ALLDB.present_price - BEFORE_DAY.close) / BEFORE_DAY.close * 100 < '%s' "
           sell_list = self.engine_simulator.execute(sql % (self.diff_point * (-1))).fetchall()

        # 절대 모멘텀 전략 + losscut_point 추가 (특정일 전 보다 n% 이하로 떨어지면 매도) / query 버전
        elif self.sell_list_num == 6:
           date_before = self.date_rows[i - self.day_before][0]
           sql = "SELECT ALLDB.code, ALLDB.code_name, ALLDB.rate, ALLDB.present_price, ALLDB.valuation_profit " \
                 "FROM all_item_db ALLDB, daily_buy_list.`" + date_before + "` BEFORE_DAY " \
                "WHERE ALLDB.code = BEFORE_DAY.code " \
                "AND ALLDB.sell_date = 0 " \
                "AND ((ALLDB.present_price - BEFORE_DAY.close) / BEFORE_DAY.close * 100 < '%s' " \
                "OR ALLDB.rate <= '%s')"
           sell_list = self.engine_simulator.execute(sql % (self.diff_point * (-1), self.losscut_point)).fetchall()

        # 방향성 검증 매도: 익절/손절 + 시간청산 (MA 데드크로스 제거)
        # - 익절: +sell_point% 도달 → 매수 방향 맞음 (WIN)
        # - 손절: losscut_point% 도달 → 매수 방향 틀림 (LOSS)
        # - 시간청산: time_stop_days 초과 보유 → 방향성 미확인 강제 정리
        # - 데드크로스 제거: 익절/손절 중간 애매한 청산 → 승률 해석 오염 방지
        elif self.sell_list_num == 20:
            date_today_str = self.date_rows[i][0]
            td = getattr(self, 'time_stop_days', 20)
            sql = (
                "SELECT code, code_name, rate, present_price, valuation_profit, "
                "CASE WHEN rate >= {sp} THEN '익절(+{sp:.0f}%%)' "
                "     WHEN rate <= {lc} THEN '손절({lc:.0f}%%)' "
                "     ELSE '시간청산({td}일)' END AS sell_reason "
                "FROM all_item_db "
                "WHERE sell_date = '0' "
                "AND ("
                "  (rate >= {sp}) "
                "  OR (rate <= {lc}) "
                "  OR DATEDIFF(STR_TO_DATE('{d}', '%Y%m%d'), STR_TO_DATE(LEFT(buy_date, 8), '%Y%m%d')) >= {td}"
                ") GROUP BY code"
            ).format(sp=self.sell_point, lc=self.losscut_point, d=date_today_str, td=td)
            sell_list = self.engine_simulator.execute(sql).fetchall()

        # MA 데드크로스만으로 청산 (TP/SL 없음) — max/min 잠재력 분석용 백테스트
        elif self.sell_list_num == 30:
            sql = (
                "SELECT code, code_name, rate, present_price, valuation_profit, "
                "'MA데드크로스' AS sell_reason "
                "FROM all_item_db "
                "WHERE sell_date = '0' AND ma5 < ma20 GROUP BY code"
            )
            sell_list = self.engine_simulator.execute(sql).fetchall()

        # Strategy B 과매도 반등 매도 — 하드SL -5% / 트레일링스탑(3%활성화, 5%트레일) / 45일 시간청산
        # 트레일링스탑: max_high_pct >= 3 (고점 3% 달성) 이후
        #              rate <= GREATEST(max_high_pct - 5, 1.0) → 고점 대비 5% 하락, 단 최소 +1% 보장
        #              (예) 고점 +3%: 트리거 = max(-2%, +1%) = +1% → 손실 청산 방지
        #              (예) 고점 +8%: 트리거 = max(+3%, +1%) = +3% → 자연스러운 트레일
        elif self.sell_list_num == 31:
            date_today_str = self.date_rows[i][0]
            sql = (
                "SELECT code, code_name, rate, present_price, valuation_profit, "
                "CASE "
                "  WHEN rate <= -5 THEN '하드SL(-5%)' "
                "  WHEN max_high_pct >= 3 AND rate <= GREATEST(max_high_pct - 5, 1.0) THEN '트레일링스탑' "
                "  ELSE '시간청산(45d)' "
                "END AS sell_reason "
                "FROM all_item_db "
                "WHERE sell_date = '0' "
                "AND ("
                "  rate <= -5 "
                "  OR (max_high_pct >= 3 AND rate <= GREATEST(max_high_pct - 5, 1.0)) "
                "  OR DATEDIFF(STR_TO_DATE('{d}', '%Y%m%d'), STR_TO_DATE(LEFT(buy_date, 8), '%Y%m%d')) >= 45"
                ") GROUP BY code"
            ).format(d=date_today_str)
            sell_list = self.engine_simulator.execute(sql).fetchall()

        # 🚀 고급 통합 전략: exit_strategy.py 사용 (ATR 기반 동적 손절/익절)
        elif self.sell_list_num == 100:
            from library.exit_strategy import get_exit_signals
            from datetime import datetime

            sell_list = []

            # 현재 시뮬레이션 날짜 가져오기 (i로부터 date_rows_today 계산)
            try:
                # 실전 모드 체크: date_rows가 없거나 i가 범위를 벗어나면 실전 모드
                if not hasattr(self, 'date_rows') or not self.date_rows or i >= len(self.date_rows):
                    # 실전 모드: 현재 날짜 사용
                    current_date = datetime.now()
                    logger.debug(f"get_sell_list: 실전 모드 - 현재 날짜 사용 ({current_date.strftime('%Y%m%d')})")
                else:
                    # 시뮬레이션 모드: date_rows에서 날짜 가져오기
                    current_date_str = self.date_rows[i][0]  # YYYYMMDD 형식
                    current_date = datetime.strptime(current_date_str, '%Y%m%d')
                    logger.debug(f"get_sell_list: 시뮬레이션 모드 - 날짜: {current_date_str}")
            except Exception as e:
                # 예외 발생 시 현재 날짜 사용
                logger.warning(f"get_sell_list: 날짜 정보 가져오기 실패, 현재 날짜 사용. 에러: {e}")
                current_date = datetime.now()

            # 보유 중인 종목 조회 (buy_date 추가)
            sql = """
                SELECT code, code_name, rate, present_price, valuation_profit, purchase_price, buy_date
                FROM all_item_db
                WHERE sell_date = 0
                GROUP BY code
            """
            holdings = self.engine_simulator.execute(sql).fetchall()

            # exit_strategy 형식으로 변환
            positions = []
            for holding in holdings:
                code = holding[0]
                code_name = holding[1]
                rate = holding[2]
                present_price = holding[3]
                valuation_profit = holding[4]
                purchase_price = holding[5]
                buy_date = holding[6]

                # highest_price 계산 (현재가와 매수가 중 높은 값)
                highest_price = max(present_price, purchase_price)

                # position 딕셔너리 생성
                # buy_date 파싱 (YYYYMMDD 또는 YYYYMMDDHHMM 형식 대응)
                try:
                    buy_date_str = str(buy_date)[:8]  # 앞 8자리만 사용 (YYYYMMDD)
                    entry_date = datetime.strptime(buy_date_str, '%Y%m%d')
                except:
                    entry_date = current_date

                positions.append({
                    'code': code,
                    'code_name': code_name,
                    'entry_price': purchase_price,
                    'entry_date': entry_date,
                    'shares': 1,  # 시뮬레이터는 비율로 관리
                    'highest_price': highest_price,
                    'current_price': present_price,
                    'rate': rate
                })

            # exit_strategy로 청산 시그널 생성 (current_date 전달)
            exit_signals = get_exit_signals(positions, db_name='daily_buy_list', current_date=current_date)

            # sell_list 형식으로 변환
            for signal in exit_signals:
                code = signal['code']

                # 해당 종목의 holding 정보 찾기
                matching_holding = [h for h in holdings if h[0] == code]
                if matching_holding:
                    holding = matching_holding[0]
                    # sell_list: (code, code_name, rate, present_price, valuation_profit)
                    sell_list.append(holding[:5])

                    # 청산 사유 로깅
                    logger.debug(f"[고급 청산] {code}: {signal['decision']['reason']} (우선순위: {signal['decision']['priority']})")

        ##################################################################################################################################################################################################################
        else:
            print(f"{self.simul_num}번 알고리즘에 대한 self.sell_list_num 설정이 비었습니다. variable_setting 함수에서 self.sell_list_num을 확인해주세요.")
            sys.exit(1)

        return sell_list

    # 실제로 매도를 하는 함수 (매도 한 결과를 all_item_db에 반영)
    def sell_send_order(self, min_date, sell_price, sell_rate, code):
        # print("sell send order")
        sql = "UPDATE all_item_db SET sell_date= '%s', sell_price ='%s' ,sell_rate ='%s' WHERE code='%s' and sell_date = '%s' " \
              "ORDER BY buy_date desc LIMIT 1"
        self.engine_simulator.execute(sql % (min_date, sell_price, sell_rate, code, 0))
        # 매도 후 정산
        self.check_balance()

    # 매도를 하기 위한 함수
    def auto_trade_sell_stock(self, date, _i):
        # 매도 할 리스트를 가져오는 함수
        sell_list = self.get_sell_list(_i)
        for i in range(len(sell_list)):
            # 코드
            get_sell_code = sell_list[i][0]
            # 종목명
            get_sell_code_name = sell_list[i][1]
            # 수익률
            get_sell_rate = sell_list[i][2]
            # 종목의 현재 주가
            get_present_price = sell_list[i][3]
            # 수익(손실) 금액 (종목의 순수익, 순손실 금액)
            valuation_profit = sell_list[i][4]

            sell_reason = sell_list[i][5] if len(sell_list[i]) > 5 else ('손절' if get_sell_rate < 0 else '익절')
            emoji = '💔' if get_sell_rate < 0 else '💰'
            profit_label = '손실' if get_sell_rate < 0 else '수익'
            print(f"  {emoji} {sell_reason}: {get_sell_code_name}({get_sell_code}) | 수익률: {get_sell_rate:.1f}% | {profit_label}: {valuation_profit:,}원")

            # 실제로 매도를 하는 함수 (매도 한 결과를 all_item_db에 반영)
            self.sell_send_order(date, get_present_price, get_sell_rate, get_sell_code)

    # 몇개의 주를 살지 계산해주는 함수
    def buy_num_count(self, invest_unit, present_price):
        # jackbot("******************* buy_num_count!!!")
        return int(int(invest_unit) / int(present_price))

    # 금일 수익 계산 함수
    def get_today_profit(self, date):
        # jackbot("******************* get_today_profit!!!")
        sql = "SELECT sum(valuation_profit) from all_item_db where sell_date like '%s'"
        return self.engine_simulator.execute(sql % ("%%" + date + "%%")).fetchall()[0][0]

    # 총 매입금액 계산 함수
    def get_sum_item_total_purchase(self):

        # jackbot("******************* get_sum_item_total_purchase!!!")
        sql = "SELECT sum(item_total_purchase) from all_item_db where sell_date = '%s'"
        rows = self.engine_simulator.execute(sql % (0)).fetchall()[0][0]
        if rows is not None:
            return rows
        else:
            return 0

    # 총평가금액 계산 함수
    def get_sum_valuation_price(self):
        sql = "SELECT sum(valuation_price) from all_item_db where sell_date = '%s'"
        rows = self.engine_simulator.execute(sql % (0)).fetchall()[0][0]
        if rows is not None:
            return rows
        else:
            return 0

    # 오늘 일자 익절 종목 수
    def get_today_profitcut_count(self, date):
        sql = "SELECT count(code) from all_item_db where sell_date like '%s' and sell_rate>='%s'"
        return self.engine_simulator.execute(sql % ("%%" + date + "%%", 0)).fetchall()[0][0]

    # 오늘 일자 손절 종목 수
    def get_today_losscut_count(self, date):
        sql = "SELECT count(code) from all_item_db where sell_date like '%s' and sell_rate<'%s'"
        return self.engine_simulator.execute(sql % ("%%" + date + "%%", 0)).fetchall()[0][0]

    # 오늘 일자 매도금액
    def get_sum_today_sell_price(self, date):
        sql = "SELECT sum(valuation_price) from all_item_db where sell_date like '%s'"
        return self.engine_simulator.execute(sql % ("%%" + date + "%%")).fetchall()[0][0]

    # 오늘 일자 익절 종목 대상 수익
    def get_sum_today_profitcut(self, date):
        sql = "SELECT sum(valuation_profit) from all_item_db where sell_date like '%s' and valuation_profit >= '%s' "
        return self.engine_simulator.execute(sql % ("%%" + date + "%%", 0)).fetchall()[0][0]

    # 오늘 일자 손절 종목 대상 손실 금액
    def get_sum_today_losscut(self, date):
        sql = "SELECT sum(valuation_profit) from all_item_db where sell_date like '%s' and valuation_profit < '%s' "
        return self.engine_simulator.execute(sql % ("%%" + date + "%%", 0)).fetchall()[0][0]

    # 총 익절 종목 대상 수익
    def get_sum_total_profitcut(self):
        sql = "SELECT sum(valuation_profit) from all_item_db where sell_date != 0 and valuation_profit >= '%s' "
        return self.engine_simulator.execute(sql % (0)).fetchall()[0][0]

    # 총 손절 종목 대상 손실 금액
    def get_sum_total_losscut(self):
        sql = "SELECT sum(valuation_profit) from all_item_db where sell_date != 0 and valuation_profit < '%s' "
        return self.engine_simulator.execute(sql % (0)).fetchall()[0][0]

    # 전체 일자 익절한 종목 수
    def get_sum_total_profitcut_count(self):
        # jackbot("******************* get_sum_total_profitcut_count!!!")
        sql = "select count(code) from all_item_db where sell_date != 0 and valuation_profit >= '%s'"
        return self.engine_simulator.execute(sql % (0)).fetchall()[0][0]

    # 전체 일자 손절한 종목 수
    def get_sum_total_losscut_count(self):
        # jackbot("******************* get_sum_total_losscut_count!!!")
        sql = "select count(code) from all_item_db where sell_date != 0 and valuation_profit < '%s' "
        return self.engine_simulator.execute(sql % (0)).fetchall()[0][0]

    # jango_data의 저장 된 일자 반환 함수
    def get_len_jango_data_date(self):

        sql = "select date from jango_data"
        rows = self.engine_simulator.execute(sql).fetchall()

        return len(rows)

    # 총 보유한 종목 수
    def get_total_possess_count(self):
        # jackbot("******************* get_total_possess_count!!!")
        sql = "select count(code) from all_item_db where sell_date = '%s'"
        return self.engine_simulator.execute(sql % (0)).fetchall()[0][0]

    # jango_data 테이블을 만드는 함수
    def db_to_jango(self, date_rows_today):
        # 정산 함수
        self.check_balance()
        if self.is_simul_table_exist(self.db_name, "all_item_db") == False:
            return

        self.jango.loc[0, 'date'] = date_rows_today

        # self.jango.loc[0, 'total_asset'] = self.total_invest_price - self.loan_money
        self.jango.loc[0, 'today_profit'] = self.get_today_profit(date_rows_today)
        self.jango.loc[0, 'sum_valuation_profit'] = self.sum_valuation_profit
        self.jango.loc[0, 'total_profit'] = self.total_valuation_profit

        self.jango.loc[0, 'total_invest'] = self.total_invest_price
        self.jango.loc[0, 'd2_deposit'] = self.d2_deposit
        # 총매입금액
        self.jango.loc[0, 'sum_item_total_purchase'] = self.get_sum_item_total_purchase()

        # 총평가금액
        self.jango.loc[0, 'total_evaluation'] = self.get_sum_valuation_price()
        self.jango.loc[0, 'today_profitcut_count'] = self.get_today_profitcut_count(date_rows_today)
        self.jango.loc[0, 'today_losscut_count'] = self.get_today_losscut_count(date_rows_today)

        self.jango.loc[0, 'today_invest_price'] = float(self.today_invest_price)

        # self.jango.loc[0, 'today_reinvest_price'] = self.today_reinvest_price
        self.jango.loc[0, 'today_sell_price'] = self.get_sum_today_sell_price(date_rows_today)

        # 오늘 기준 수익률 (키움 잔고 상단에 뜨는 수익률) -0.33 (수수료, 세금)
        try:
            self.jango.loc[0, 'today_rate'] = round(
                (float(self.jango.loc[0, 'total_evaluation']) - float(
                    self.jango.loc[0, 'sum_item_total_purchase'])) / float(
                    self.jango.loc[0, 'sum_item_total_purchase']) * 100 - 0.33, 2)
        except ZeroDivisionError as e:
            pass

        # self.jango.loc[0, 'volume_limit'] = self.volume_limit

        # self.jango.loc[0, 'reinvest_point'] = self.reinvest_point
        self.jango.loc[0, 'sell_point'] = self.sell_point
        # self.jango.loc[0, 'max_reinvest_count'] = self.max_reinvest_count
        self.jango.loc[0, 'invest_limit_rate'] = self.invest_limit_rate
        self.jango.loc[0, 'invest_unit'] = self.invest_unit

        self.jango.loc[0, 'limit_money'] = self.limit_money
        self.jango.loc[0, 'total_possess_count'] = self.get_total_possess_count()
        self.jango.loc[0, 'today_buy_list_count'] = self.len_df_realtime_daily_buy_list
        # self.jango.loc[0, 'today_reinvest_count'] = self.get_today_reinvest_count(date_rows_today)
        # self.jango.loc[0, 'today_cant_reinvest_count'] = self.get_today_cant_reinvest_count()

        # 오늘 익절한 금액
        self.jango.loc[0, 'today_profitcut'] = self.get_sum_today_profitcut(date_rows_today)
        # 오늘 손절한 금액
        self.jango.loc[0, 'today_losscut'] = self.get_sum_today_losscut(date_rows_today)

        # 지금까지 총 익절한 금액
        self.jango.loc[0, 'total_profitcut'] = self.get_sum_total_profitcut()

        # 지금까지 총 손절한 금액
        self.jango.loc[0, 'total_losscut'] = self.get_sum_total_losscut()

        # 지금까지 총 익절한놈들
        self.jango.loc[0, 'total_profitcut_count'] = self.get_sum_total_profitcut_count()

        # 지금까지 총 손절한 놈들

        self.jango.loc[0, 'total_losscut_count'] = self.get_sum_total_losscut_count()

        self.jango.loc[0, 'today_buy_count'] = 0
        self.jango.loc[0, 'today_buy_total_sell_count'] = 0
        self.jango.loc[0, 'today_buy_total_possess_count'] = 0

        self.jango.loc[0, 'today_buy_today_profitcut_count'] = 0

        self.jango.loc[0, 'today_buy_today_losscut_count'] = 0
        self.jango.loc[0, 'today_buy_total_profitcut_count'] = 0

        self.jango.loc[0, 'today_buy_total_losscut_count'] = 0
        # self.jango.loc[0, 'today_buy_reinvest_count0_sell_count'] = 0
        #
        # self.jango.loc[0, 'today_buy_reinvest_count1_sell_count'] = 0
        # self.jango.loc[0, 'today_buy_reinvest_count2_sell_count'] = 0
        # self.jango.loc[0, 'today_buy_reinvest_count3_sell_count'] = 0
        # self.jango.loc[0, 'today_buy_reinvest_count4_sell_count'] = 0
        #
        # self.jango.loc[0, 'today_buy_reinvest_count4_sell_profitcut_count'] = 0
        # self.jango.loc[0, 'today_buy_reinvest_count4_sell_losscut_count'] = 0
        #
        # self.jango.loc[0, 'today_buy_reinvest_count5_sell_count'] = 0
        # self.jango.loc[0, 'today_buy_reinvest_count5_sell_profitcut_count'] = 0
        # self.jango.loc[0, 'today_buy_reinvest_count5_sell_losscut_count'] = 0
        #
        # self.jango.loc[0, 'today_buy_reinvest_count0_remain_count'] = 0
        #
        # self.jango.loc[0, 'today_buy_reinvest_count1_remain_count'] = 0
        # self.jango.loc[0, 'today_buy_reinvest_count2_remain_count'] = 0
        # self.jango.loc[0, 'today_buy_reinvest_count3_remain_count'] = 0
        # self.jango.loc[0, 'today_buy_reinvest_count4_remain_count'] = 0
        # self.jango.loc[0, 'today_buy_reinvest_count4_remain_count'] = 0
        # self.jango.loc[0, 'today_buy_reinvest_count5_remain_count'] = 0

        # # 데이터베이스에 테이블이 존재할 때 수행 동작을 지정한다.
        # 'fail', 'replace', 'append' 중 하나를 사용할 수 있는데 기본값은 'fail'이다.
        # 'fail'은 데이터베이스에 테이블이 있다면 아무 동작도 수행하지 않는다.
        # 'replace'는 테이블이 존재하면 기존 테이블을 삭제하고 새로 테이블을 생성한 후 데이터를 삽입한다.
        # 'append'는 테이블이 존재하면 데이터만을 추가한다.
        self.jango.to_sql('jango_data', self.engine_simulator, if_exists='append')

        #     # today_earning_rate
        sql = "update jango_data set today_earning_rate =round(today_profit / total_invest * '%s',2) WHERE date='%s'"
        # rows[i][0] 하는 이유는 rows[i]는 튜플( )로 나온다 그 튜플의 원소를 꺼내기 위해 rows[i]에 [0]을 추가
        self.engine_simulator.execute(sql % (100, date_rows_today))

    # 시뮬레이션이 다 끝났을 때 마지막 jango_data 정리
    def arrange_jango_data(self):
        if self.engine_simulator.dialect.has_table(self.engine_simulator, 'jango_data'):
            len_date = self.get_len_jango_data_date()
            sql = "select date from jango_data"
            rows = self.engine_simulator.execute(sql).fetchall()

            print(f'\n📊 jango_data 최종 정산 중... (총 {len_date}일)')
            # 위에 전체
            for i in range(len_date):
                # 진행 상황 표시 (10%마다)
                if (i + 1) % max(1, len_date // 10) == 0 or i == len_date - 1:
                    progress = (i + 1) / len_date * 100
                    print(f"  진행 중: {progress:.0f}% ({i+1}/{len_date}일)", end='\r')
                # today_buy_count
                sql = "UPDATE jango_data SET today_buy_count=(select count(*) from (select code from all_item_db where buy_date like '%s') b) WHERE date='%s'"
                # date 하는 이유는 rows[i]는 튜플로 나온다 그 튜플의 원소를 꺼내기 위해 [0]을 추가
                self.engine_simulator.execute(sql % ("%%" + str(rows[i][0]) + "%%", rows[i][0]))

                # today_buy_total_sell_count ( 익절, 손절 포함)
                sql = "UPDATE jango_data SET today_buy_total_sell_count=(select count(*) from (select code from all_item_db a where buy_date like '%s' and (a.sell_date != 0) group by code ) b) WHERE date='%s'"
                self.engine_simulator.execute(sql % ("%%" + rows[i][0] + "%%", rows[i][0]))

                # today_buy_total_possess_count 오늘 사고 계속 가지고 있는것들
                sql = "UPDATE jango_data SET today_buy_total_possess_count=(select count(*) from (select code from all_item_db a where buy_date like '%s' and a.sell_date = '%s' group by code ) b) WHERE date='%s'"
                self.engine_simulator.execute(sql % ("%%" + rows[i][0] + "%%", 0, rows[i][0]))

                sql = "UPDATE jango_data SET today_buy_today_profitcut_count=(select count(*) from (select code from all_item_db where buy_date like '%s' and sell_date like '%s' and (sell_rate >= '%s' ) group by code ) b) WHERE date='%s'"
                self.engine_simulator.execute(sql % ("%%" + rows[i][0] + "%%", "%%" + rows[i][0] + "%%", 0, rows[i][0]))

                sql = "UPDATE jango_data SET today_buy_today_profitcut_rate= CASE WHEN today_buy_count = 0 THEN 0 ELSE round(today_buy_today_profitcut_count /today_buy_count *100,2) END WHERE date = '%s'"
                self.engine_simulator.execute(sql % (rows[i][0]))

                sql = "UPDATE jango_data SET today_buy_today_losscut_count=(select count(*) from (select code from all_item_db where buy_date like '%s' and sell_date like '%s' and sell_rate < '%s'  group by code ) b) WHERE date='%s'"
                self.engine_simulator.execute(sql % ("%%" + rows[i][0] + "%%", "%%" + rows[i][0] + "%%", 0, rows[i][0]))

                sql = "UPDATE jango_data SET today_buy_today_losscut_rate= CASE WHEN today_buy_count = 0 THEN 0 ELSE round(today_buy_today_losscut_count /today_buy_count *100,2) END WHERE date = '%s'"
                self.engine_simulator.execute(sql % (rows[i][0]))

                sql = "UPDATE jango_data SET today_buy_total_profitcut_count=(select count(*) from (select code from all_item_db where buy_date like '%s' and sell_rate >= '%s'  group by code ) b) WHERE date='%s'"
                self.engine_simulator.execute(sql % ("%%" + rows[i][0] + "%%", 0, rows[i][0]))

                sql = "UPDATE jango_data SET today_buy_total_profitcut_rate= CASE WHEN today_buy_count = 0 THEN 0 ELSE round(today_buy_total_profitcut_count /today_buy_count *100,2) END WHERE date = '%s'"
                self.engine_simulator.execute(sql % (rows[i][0]))

                sql = "UPDATE jango_data SET today_buy_total_losscut_count=(select count(*) from (select code from all_item_db where buy_date like '%s' and sell_rate < '%s'  group by code ) b) WHERE date='%s'"
                self.engine_simulator.execute(sql % ("%%" + rows[i][0] + "%%", 0, rows[i][0]))

                sql = "UPDATE jango_data SET today_buy_total_losscut_rate= CASE WHEN today_buy_count = 0 THEN 0 ELSE round(today_buy_total_losscut_count/today_buy_count*100,2) END WHERE date = '%s'"
                self.engine_simulator.execute(sql % (rows[i][0]))

        print('\n\n✅ jango_data 최종 정산 완료')

    def print_simulation_summary(self):
        """
        백테스트 최종 결과 요약 출력
        """
        try:
            # jango_data에서 최종 결과 가져오기
            sql = "SELECT * FROM jango_data ORDER BY date DESC LIMIT 1"
            result = self.engine_simulator.execute(sql)
            final_data = result.fetchone()

            if not final_data:
                print("❌ 시뮬레이션 결과 데이터가 없습니다.")
                return

            # 컬럼명과 값을 딕셔너리로 변환 (안전한 접근)
            column_names = list(result.keys())
            final_dict = dict(zip(column_names, final_data))

            # 안전하게 값 추출하는 함수 (숫자 변환 포함)
            def safe_get(key, default=0):
                value = final_dict.get(key, default)
                if value is None:
                    return default
                # 숫자로 변환 시도
                try:
                    return float(value) if isinstance(value, (str, int, float)) else default
                except (ValueError, TypeError):
                    return default

            # all_item_db에서 거래 통계 가져오기
            sql_trades = """
            SELECT
                COUNT(*) as total_trades,
                COUNT(CASE WHEN sell_rate >= 0 THEN 1 END) as win_count,
                COUNT(CASE WHEN sell_rate < 0 THEN 1 END) as loss_count,
                AVG(CASE WHEN sell_rate >= 0 THEN sell_rate END) as avg_profit_rate,
                AVG(CASE WHEN sell_rate < 0 THEN sell_rate END) as avg_loss_rate,
                AVG(DATEDIFF(
                    STR_TO_DATE(sell_date, '%Y%m%d'),
                    STR_TO_DATE(buy_date, '%Y%m%d')
                )) as avg_holding_days,
                MAX(sell_rate) as max_profit_rate,
                MIN(sell_rate) as max_loss_rate
            FROM all_item_db
            WHERE sell_date != 0 AND sell_date != ''
            """
            trade_stats = self.engine_simulator.execute(sql_trades).fetchone()

            # jango_data에서 필요한 값 추출 (컬럼명으로 안전하게)
            d2_deposit = safe_get('d2_deposit', 0)
            total_profit = safe_get('total_profit', 0)
            total_invest_price = safe_get('total_invest_price', 0)
            total_valuation = safe_get('total_evaluation', 0)  # 컬럼명 수정: total_valuation → total_evaluation

            # 초기 자본
            initial_capital = self.start_invest_price if self.start_invest_price else 10000000

            # 최종 자산 = 예수금 + 총 평가액
            final_capital = d2_deposit + total_valuation

            # 수익률 계산 (0으로 나누기 방지)
            if initial_capital > 0 and final_capital > 0:
                total_return = (final_capital / initial_capital - 1) * 100
            else:
                total_return = 0

            # 거래 통계
            total_trades = trade_stats[0] if trade_stats and trade_stats[0] else 0
            win_count = trade_stats[1] if trade_stats and trade_stats[1] else 0
            loss_count = trade_stats[2] if trade_stats and trade_stats[2] else 0
            avg_profit_rate = trade_stats[3] if trade_stats and trade_stats[3] else 0
            avg_loss_rate = trade_stats[4] if trade_stats and trade_stats[4] else 0
            avg_holding_days = trade_stats[5] if trade_stats and trade_stats[5] else 0
            max_profit_rate = trade_stats[6] if trade_stats and trade_stats[6] else 0
            max_loss_rate = trade_stats[7] if trade_stats and trade_stats[7] else 0

            win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0

            # 결과 출력
            print("\n" + "=" * 70)
            print("📊 백테스트 최종 결과 요약")
            print("=" * 70)

            # 실제 총 손익 계산
            actual_total_profit = final_capital - initial_capital
            unrealized_profit = actual_total_profit - total_profit

            print(f"\n💰 수익 현황:")
            print(f"  초기 자본:             {initial_capital:>15,}원")
            print(f"  현금 (예수금):         {d2_deposit:>15,}원")
            print(f"  보유 주식 평가액:      {total_valuation:>15,}원")
            print(f"  최종 자본:             {final_capital:>15,}원")
            print(f"  총 손익:               {actual_total_profit:>15,}원")
            print(f"    - 실현 손익 (매도):  {total_profit:>15,}원")
            print(f"    - 미실현 손익 (보유):{unrealized_profit:>15,}원")
            print(f"  총 수익률:             {total_return:>14.2f}%")

            print(f"\n📈 거래 통계:")
            print(f"  총 거래 횟수:     {total_trades:>15}회")
            print(f"  익절 횟수:        {win_count:>15}회")
            print(f"  손절 횟수:        {loss_count:>15}회")
            print(f"  승률:             {win_rate:>14.1f}%")

            print(f"\n📊 수익률 분석:")
            print(f"  평균 익절률:      {avg_profit_rate:>14.2f}%")
            print(f"  평균 손절률:      {avg_loss_rate:>14.2f}%")
            print(f"  최대 익절률:      {max_profit_rate:>14.2f}%")
            print(f"  최대 손절률:      {max_loss_rate:>14.2f}%")

            print(f"\n⏱️  보유 기간:")
            print(f"  평균 보유일:      {avg_holding_days:>14.1f}일")

            # 손익비 계산
            profit_loss_ratio = abs(avg_profit_rate / avg_loss_rate) if avg_loss_rate != 0 else 0
            print(f"\n📐 손익비:")
            print(f"  손익비 (R):       {profit_loss_ratio:>14.2f}")

            # 현재 설정값 표시
            print(f"\n⚙️  현재 전략 설정:")
            print(f"  알고리즘 번호:    {self.simul_num:>15}")

            # 익절 기준 (동적/고정 구분)
            if abs(self.sell_point) > 100:
                # 트레일링 스톱 정보 추가
                if hasattr(self, 'trailing_stop_atr'):
                    print(f"  익절 기준:        트레일링 스톱 (ATR × {self.trailing_stop_atr})")
                else:
                    print(f"  익절 기준:        {'ATR 기반 동적 익절':>20}")
            else:
                print(f"  익절 기준:        {self.sell_point:>14.1f}%")

            # 손절 기준 (동적/고정 구분)
            if abs(self.losscut_point) > 100:
                # ATR 배수 정보 추가
                if hasattr(self, 'atr_multiplier'):
                    print(f"  손절 기준:        ATR 기반 동적 손절 (ATR × {self.atr_multiplier})")
                else:
                    print(f"  손절 기준:        {'ATR 기반 동적 손절':>20}")
            else:
                print(f"  손절 기준:        {self.losscut_point:>14.1f}%")

            # 전략 평가 및 제안
            print(f"\n💡 전략 평가 및 제안:")
            print("=" * 70)

            # 1. 수익률 평가
            if total_return > 50:
                print("  ✅ 우수: 높은 수익률을 기록했습니다!")
            elif total_return > 20:
                print("  ✔️  양호: 안정적인 수익을 내고 있습니다.")
            elif total_return > 0:
                print("  ⚠️  보통: 수익은 있으나 개선 여지가 있습니다.")
            else:
                print("  ❌ 주의: 손실이 발생했습니다. 전략 재검토가 필요합니다.")

            # 2. 승률 평가 및 제안
            if win_rate >= 70:
                print(f"  ✅ 승률 우수 ({win_rate:.1f}%)")
            elif win_rate >= 50:
                print(f"  ✔️  승률 양호 ({win_rate:.1f}%)")
                # 고정 손절 사용 시만 제안 (동적 손절이 아닐 때)
                if abs(self.losscut_point) < 100 and abs(avg_loss_rate) > avg_profit_rate * 2:
                    print("     💡 제안: 손절폭이 큽니다. 손절 기준을 더 타이트하게 조정하세요.")
                    print(f"        현재 손절: {self.losscut_point:.1f}% → 추천: {self.losscut_point * 0.7:.1f}%")
            else:
                print(f"  ⚠️  승률 낮음 ({win_rate:.1f}%)")
                print("     💡 제안: 진입 조건을 더 엄격하게 설정하세요.")
                # 고정 손절 사용 시만 제안 (동적 손절이 아닐 때)
                if abs(self.losscut_point) < 100 and self.losscut_point < -5:
                    print(f"        손절 기준이 너무 낮습니다: {self.losscut_point:.1f}% → 추천: -3.0%")

            # 3. 손익비 평가
            if profit_loss_ratio >= 2.0:
                print(f"  ✅ 손익비 우수 (R={profit_loss_ratio:.2f})")
            elif profit_loss_ratio >= 1.5:
                print(f"  ✔️  손익비 양호 (R={profit_loss_ratio:.2f})")
            else:
                print(f"  ⚠️  손익비 낮음 (R={profit_loss_ratio:.2f})")
                print(f"     💡 제안: 익절 목표를 높이거나 손절을 빠르게 하세요.")
                # 고정 익절 사용 시만 제안 (동적 익절이 아닐 때)
                if abs(self.sell_point) < 100 and avg_profit_rate < self.sell_point * 0.7:
                    print(f"        평균 익절률이 목표보다 낮습니다.")
                    print(f"        익절 기준: {self.sell_point:.1f}% → 추천: {self.sell_point * 1.3:.1f}%")

            # 4. 보유 기간 평가
            if avg_holding_days < 3:
                print(f"  ⚠️  평균 보유일 짧음 ({avg_holding_days:.1f}일)")
                print("     💡 제안: 단타 전략입니다. 수수료 영향이 클 수 있습니다.")
            elif avg_holding_days > 10:
                print(f"  ⚠️  평균 보유일 김 ({avg_holding_days:.1f}일)")
                print("     💡 제안: 장기 보유 경향. 시간 기반 청산 조건 추가를 고려하세요.")
            else:
                print(f"  ✔️  평균 보유일 적정 ({avg_holding_days:.1f}일)")

            # 5. 종합 제안
            print(f"\n🎯 종합 제안:")
            if total_return > 20 and win_rate >= 55 and profit_loss_ratio >= 1.5:
                print("  ✅ 현재 전략이 잘 작동하고 있습니다!")
                print("  📌 이 설정을 실전에 적용할 수 있습니다.")
            elif total_return > 0:
                print("  ✔️  전략이 수익을 내고 있으나 개선 가능합니다.")
                print("  📌 위의 제안사항을 참고하여 설정을 조정해보세요.")
            else:
                print("  ❌ 전략 전면 재검토가 필요합니다.")
                print("  📌 진입/청산 조건, 손익 비율을 근본적으로 재설정하세요.")

            # MDD 및 Sharpe Ratio 계산
            print(f"\n📉 리스크 지표:")
            print("=" * 70)

            # jango_data에서 일별 자산 데이터 가져오기
            sql_daily = """
            SELECT
                date,
                d2_deposit,
                total_evaluation,
                total_invest as total_asset
            FROM jango_data
            ORDER BY date ASC
            """
            daily_data = self.engine_simulator.execute(sql_daily).fetchall()

            if daily_data and len(daily_data) > 1:
                # 날짜와 자산 데이터 분리
                dates = [row[0] for row in daily_data]
                total_assets = [float(row[3]) if row[3] else initial_capital for row in daily_data]

                # MDD (Maximum Drawdown) 계산
                peak = total_assets[0]
                max_drawdown = 0
                max_drawdown_pct = 0
                drawdowns = []

                for asset in total_assets:
                    if asset > peak:
                        peak = asset
                    drawdown = (peak - asset) / peak * 100 if peak > 0 else 0
                    drawdowns.append(drawdown)
                    if drawdown > max_drawdown_pct:
                        max_drawdown_pct = drawdown
                        max_drawdown = peak - asset

                # Sharpe Ratio 계산
                daily_returns = []
                for i in range(1, len(total_assets)):
                    if total_assets[i-1] > 0:
                        daily_return = (total_assets[i] / total_assets[i-1] - 1) * 100
                        daily_returns.append(daily_return)

                if len(daily_returns) > 0:
                    avg_daily_return = np.mean(daily_returns)
                    std_daily_return = np.std(daily_returns, ddof=1) if len(daily_returns) > 1 else 0

                    # Sharpe Ratio (무위험 수익률 = 0 가정)
                    sharpe_ratio = avg_daily_return / std_daily_return if std_daily_return > 0 else 0

                    # 연환산 Sharpe Ratio (거래일 기준 252일)
                    annual_sharpe = sharpe_ratio * np.sqrt(252)

                    print(f"  MDD (최대 낙폭):      {max_drawdown_pct:>14.2f}%")
                    print(f"  MDD 금액:             {max_drawdown:>15,}원")
                    print(f"  Sharpe Ratio (일):    {sharpe_ratio:>14.2f}")
                    print(f"  Sharpe Ratio (연):    {annual_sharpe:>14.2f}")
                    print(f"  일평균 수익률:        {avg_daily_return:>14.4f}%")
                    print(f"  일수익률 표준편차:    {std_daily_return:>14.4f}%")

                    # Sharpe Ratio 평가
                    print(f"\n  📊 Sharpe Ratio 평가:")
                    if annual_sharpe > 2.0:
                        print(f"     ✅ 우수 ({annual_sharpe:.2f}) - 위험 대비 수익이 매우 좋습니다!")
                    elif annual_sharpe > 1.0:
                        print(f"     ✔️  양호 ({annual_sharpe:.2f}) - 위험 대비 수익이 준수합니다.")
                    elif annual_sharpe > 0.5:
                        print(f"     ⚠️  보통 ({annual_sharpe:.2f}) - 개선 여지가 있습니다.")
                    else:
                        print(f"     ❌ 낮음 ({annual_sharpe:.2f}) - 리스크가 너무 높습니다.")

                    # MDD 평가
                    print(f"\n  📊 MDD 평가:")
                    if max_drawdown_pct < 10:
                        print(f"     ✅ 우수 ({max_drawdown_pct:.2f}%) - 낙폭이 매우 작습니다!")
                    elif max_drawdown_pct < 20:
                        print(f"     ✔️  양호 ({max_drawdown_pct:.2f}%) - 낙폭이 관리 가능한 수준입니다.")
                    elif max_drawdown_pct < 30:
                        print(f"     ⚠️  보통 ({max_drawdown_pct:.2f}%) - 손절 전략을 개선하세요.")
                    else:
                        print(f"     ❌ 높음 ({max_drawdown_pct:.2f}%) - 리스크 관리가 필요합니다!")

                    # 누적 수익률 그래프 생성
                    try:
                        # log/report 폴더 생성
                        report_dir = os.path.join(os.getcwd(), 'backtest_report')
                        os.makedirs(report_dir, exist_ok=True)

                        # 수익률 계산
                        cumulative_returns = [(asset / initial_capital - 1) * 100 for asset in total_assets]

                        # 그래프 생성
                        plt.figure(figsize=(14, 7))

                        # 한글 폰트 설정 (Windows 기본 폰트 사용)
                        plt.rcParams['font.family'] = 'Malgun Gothic'
                        plt.rcParams['axes.unicode_minus'] = False

                        # 누적 수익률 그래프
                        plt.subplot(2, 1, 1)
                        plt.plot(range(len(cumulative_returns)), cumulative_returns,
                                linewidth=2, color='#2E86AB', label='누적 수익률')
                        plt.axhline(y=0, color='gray', linestyle='--', linewidth=1, alpha=0.5)
                        plt.title(f'백테스트 누적 수익률 (알고리즘 {self.simul_num})', fontsize=14, fontweight='bold')
                        plt.xlabel('거래일', fontsize=11)
                        plt.ylabel('수익률 (%)', fontsize=11)
                        plt.grid(True, alpha=0.3, linestyle=':')
                        plt.legend(loc='best')

                        # 최종 수익률 텍스트 표시
                        final_return = cumulative_returns[-1]
                        color = 'red' if final_return < 0 else 'blue'
                        plt.text(len(cumulative_returns) * 0.02, max(cumulative_returns) * 0.9,
                                f'최종 수익률: {final_return:.2f}%\nMDD: {max_drawdown_pct:.2f}%\nSharpe: {annual_sharpe:.2f}',
                                fontsize=10, bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

                        # Drawdown 그래프
                        plt.subplot(2, 1, 2)
                        plt.fill_between(range(len(drawdowns)), drawdowns, 0,
                                        color='#A23B72', alpha=0.6, label='Drawdown')
                        plt.title('Drawdown', fontsize=14, fontweight='bold')
                        plt.xlabel('거래일', fontsize=11)
                        plt.ylabel('Drawdown (%)', fontsize=11)
                        plt.grid(True, alpha=0.3, linestyle=':')
                        plt.legend(loc='best')
                        plt.gca().invert_yaxis()  # Drawdown은 음수이므로 반전

                        # 레이아웃 조정
                        plt.tight_layout()

                        # 파일명 생성 (타임스탬프 포함)
                        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                        filename = f'backtest_result_algo{self.simul_num}_{timestamp}.png'
                        filepath = os.path.join(report_dir, filename)

                        # 그래프 저장
                        plt.savefig(filepath, dpi=150, bbox_inches='tight')
                        plt.close()

                        print(f"\n📊 그래프 저장 완료:")
                        print(f"  파일 위치: {filepath}")

                    except Exception as e:
                        print(f"\n⚠️  그래프 생성 실패: {e}")
                        import traceback
                        traceback.print_exc()

                else:
                    print("  ⚠️  일별 데이터가 부족하여 지표를 계산할 수 없습니다.")
            else:
                print("  ⚠️  일별 데이터가 부족하여 지표를 계산할 수 없습니다.")

            print("=" * 70)

        except Exception as e:
            print(f"❌ 결과 요약 생성 오류: {e}")
            import traceback
            traceback.print_exc()

    def generate_detailed_analysis_report(self):
        """
        백테스팅 상세 분석 레포트 생성

        Returns:
            tuple: (report_path, csv_path) 저장된 파일 경로
        """
        try:
            print("\n" + "=" * 80)
            print("📊 상세 분석 레포트 생성 중...")
            print("=" * 80)

            # log/report 폴더 생성
            report_dir = os.path.join(os.getcwd(), 'backtest_report')
            os.makedirs(report_dir, exist_ok=True)

            # 타임스탬프
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

            # 1. 전체 거래 내역 조회
            sql_all_trades = """
            SELECT
                code,
                code_name,
                buy_date,
                sell_date,
                purchase_price,
                sell_price,
                sell_rate,
                holding_amount,
                DATEDIFF(
                    STR_TO_DATE(sell_date, '%Y%m%d'),
                    STR_TO_DATE(buy_date, '%Y%m%d')
                ) as holding_days,
                IFNULL(composite_score, 0) as composite_score,
                IFNULL(score_a, 0) as score_a,
                IFNULL(score_b, 0) as score_b,
                IFNULL(score_c, 0) as score_c,
                IFNULL(score_d, 0) as score_d,
                IFNULL(score_e, 0) as score_e,
                IFNULL(score_f, 0) as score_f,
                IFNULL(score_penalty, 0) as score_penalty
            FROM all_item_db
            WHERE sell_date != 0 AND sell_date != ''
            ORDER BY sell_rate DESC
            """

            trades = self.engine_simulator.execute(sql_all_trades).fetchall()

            if not trades or len(trades) == 0:
                print("⚠️  분석할 거래 데이터가 없습니다.")
                return None, None

            # 1.5. summary_stats 계산 (CMD 출력과 동일한 데이터)
            summary_stats = {}
            try:
                daily_rows = self.engine_simulator.execute(
                    "SELECT total_invest FROM jango_data WHERE total_invest > 0 ORDER BY date ASC"
                ).fetchall()
                final_res = self.engine_simulator.execute(
                    "SELECT * FROM jango_data ORDER BY date DESC LIMIT 1"
                )
                final_data = final_res.fetchone()
                col_names  = list(final_res.keys())
                fd = dict(zip(col_names, final_data)) if final_data else {}
                def _sf(k, d=0):
                    v = fd.get(k, d)
                    try: return float(v) if v is not None else d
                    except: return d
                init_cap  = float(self.start_invest_price or 10_000_000)
                d2_dep    = _sf('d2_deposit')
                total_val = _sf('total_evaluation')
                # total_asset 컬럼은 NULL — total_invest(= 초기자본 + 누적손익)를 사용
                final_cap = _sf('total_invest') or (d2_dep + total_val)
                st2 = self.engine_simulator.execute("""
                    SELECT AVG(DATEDIFF(STR_TO_DATE(sell_date,'%%Y%%m%%d'),
                                       STR_TO_DATE(buy_date,'%%Y%%m%%d'))),
                           MAX(sell_rate), MIN(sell_rate)
                    FROM all_item_db WHERE sell_date != 0 AND sell_date != ''
                """).fetchone()
                assets = [float(r[0]) for r in daily_rows if r[0] and float(r[0]) > 0]
                mdd_pct = mdd_amt = sh_d = sh_a = avg_dr = std_dr = 0.0
                if len(assets) > 1:
                    peak = assets[0]
                    for a in assets:
                        if a > peak: peak = a
                        dd = (peak - a) / peak * 100 if peak > 0 else 0
                        if dd > mdd_pct:
                            mdd_pct = dd
                            mdd_amt = peak - a
                    drets = [(assets[i] / assets[i-1] - 1) * 100 for i in range(1, len(assets))]
                    avg_dr = sum(drets) / len(drets)
                    std_dr = float(np.std(drets, ddof=1)) if len(drets) > 1 else 0
                    sh_d = avg_dr / std_dr if std_dr > 0 else 0
                    sh_a = sh_d * np.sqrt(252)
                summary_stats = {
                    'initial_capital':  int(init_cap),
                    'final_capital':    int(final_cap),
                    'd2_deposit':       int(d2_dep),
                    'total_valuation':  int(total_val),
                    'actual_profit':    int(final_cap - init_cap),
                    'total_return':     (final_cap / init_cap - 1) * 100 if init_cap > 0 else 0,
                    'avg_holding_days': float(st2[0]) if st2 and st2[0] else 0,
                    'max_profit_rate':  float(st2[1]) if st2 and st2[1] else 0,
                    'max_loss_rate':    float(st2[2]) if st2 and st2[2] else 0,
                    'mdd_pct':          mdd_pct,
                    'mdd_amt':          int(mdd_amt),
                    'sharpe_daily':     sh_d,
                    'sharpe_annual':    sh_a,
                    'avg_daily_return': avg_dr,
                    'std_daily_return': std_dr,
                }
            except Exception as _e:
                print(f"⚠️  summary_stats 계산 오류: {_e}")

            # 2. Best/Worst 거래 분석
            best_trades, worst_trades = self.analyze_best_worst_trades(trades)

            # 3. 손실 패턴 분석
            loss_patterns = self.analyze_loss_patterns(trades)

            # 4. 개선 제안 생성
            suggestions = self.generate_improvement_suggestions(trades, loss_patterns)

            # 5. 마크다운 레포트 생성
            report_content = self.create_markdown_report(
                trades, best_trades, worst_trades, loss_patterns, suggestions, summary_stats
            )

            # 6. 파일 저장
            report_filename = f'backtest_analysis_algo{self.simul_num}_{timestamp}.md'
            report_path = os.path.join(report_dir, report_filename)

            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report_content)

            # 7. CSV 저장 (전체 거래 내역)
            csv_filename = f'backtest_trades_algo{self.simul_num}_{timestamp}.csv'
            csv_path = os.path.join(report_dir, csv_filename)

            import pandas as pd
            df_trades = pd.DataFrame(trades, columns=[
                'code', 'code_name', 'buy_date', 'sell_date',
                'purchase_price', 'sell_price', 'sell_rate',
                'holding_amount', 'holding_days', 'composite_score',
                'score_a', 'score_b', 'score_c', 'score_d', 'score_e', 'score_f', 'score_penalty'
            ])
            df_trades.to_csv(csv_path, index=False, encoding='utf-8-sig')

            print(f"\n✅ 레포트 생성 완료!")
            print(f"  📄 분석 레포트: {report_path}")
            print(f"  📊 거래 내역 CSV: {csv_path}")
            print("=" * 80)

            return report_path, csv_path

        except Exception as e:
            print(f"❌ 레포트 생성 오류: {e}")
            import traceback
            traceback.print_exc()
            return None, None

    def analyze_best_worst_trades(self, trades):
        """Best 10 / Worst 10 거래 분석"""
        # 수익률 기준 정렬 (이미 DESC로 정렬됨)
        best_trades = trades[:10] if len(trades) >= 10 else trades
        worst_trades = trades[-10:][::-1] if len(trades) >= 10 else []

        return best_trades, worst_trades

    def analyze_loss_patterns(self, trades):
        """손실 패턴 분석"""
        patterns = {
            'total_trades': len(trades),
            'loss_trades': 0,
            'avg_loss_holding_days': 0,
            'loss_by_holding_period': {},
            'loss_count_by_period': {}
        }

        loss_trades = [t for t in trades if t[6] < 0]  # sell_rate < 0
        patterns['loss_trades'] = len(loss_trades)

        if len(loss_trades) > 0:
            # 평균 손실 보유일
            holding_days_list = [t[8] for t in loss_trades if t[8] is not None]
            if holding_days_list:
                patterns['avg_loss_holding_days'] = sum(holding_days_list) / len(holding_days_list)

            # 보유 기간별 손실 분석
            for trade in loss_trades:
                holding_days = trade[8] if trade[8] is not None else 0

                # 기간 구분
                if holding_days <= 3:
                    period = '1-3일'
                elif holding_days <= 7:
                    period = '4-7일'
                elif holding_days <= 15:
                    period = '8-15일'
                else:
                    period = '16일 이상'

                if period not in patterns['loss_by_holding_period']:
                    patterns['loss_by_holding_period'][period] = []
                    patterns['loss_count_by_period'][period] = 0

                patterns['loss_by_holding_period'][period].append(trade[6])
                patterns['loss_count_by_period'][period] += 1

        return patterns

    def generate_improvement_suggestions(self, trades, loss_patterns):
        """개선 제안 생성"""
        suggestions = []

        # 1. 손실 비율 체크
        if loss_patterns['total_trades'] > 0:
            loss_rate = (loss_patterns['loss_trades'] / loss_patterns['total_trades']) * 100

            if loss_rate > 50:
                suggestions.append({
                    'category': '진입 조건',
                    'issue': f'손실 거래 비율이 {loss_rate:.1f}%로 높음',
                    'suggestion': '매수 최소 점수를 95점으로 상향하거나, 추가 필터 조건 적용 권장'
                })

        # 2. 보유 기간별 손실 분석
        if loss_patterns['loss_by_holding_period']:
            for period, losses in loss_patterns['loss_by_holding_period'].items():
                avg_loss = sum(losses) / len(losses)
                count = loss_patterns['loss_count_by_period'][period]

                if avg_loss < -5 and count >= 5:
                    suggestions.append({
                        'category': '보유 기간',
                        'issue': f'{period} 보유 종목의 평균 손실률 {avg_loss:.2f}% ({count}건)',
                        'suggestion': f'시간 기반 손절을 더 타이트하게 조정 권장'
                    })

        # 3. 평균 손실 보유일 분석
        if loss_patterns['avg_loss_holding_days'] > 10:
            suggestions.append({
                'category': '시간 손절',
                'issue': f'손실 거래의 평균 보유일이 {loss_patterns["avg_loss_holding_days"]:.1f}일로 김',
                'suggestion': f'최대 보유 기간을 10일로 단축하거나 시간 경과 시 손절 강화 권장'
            })

        return suggestions

    def create_markdown_report(self, trades, best_trades, worst_trades, loss_patterns, suggestions, summary_stats=None):
        """마크다운 레포트 생성"""

        # 기본 통계
        total_trades = len(trades)
        win_trades = len([t for t in trades if t[6] >= 0])
        loss_trades = len([t for t in trades if t[6] < 0])
        win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0

        avg_profit = sum([t[6] for t in trades if t[6] >= 0]) / win_trades if win_trades > 0 else 0
        avg_loss = sum([t[6] for t in trades if t[6] < 0]) / loss_trades if loss_trades > 0 else 0

        # 수익 현황 + 리스크 지표 섹션
        if summary_stats:
            ss = summary_stats
            mdd_eval = ('✅ 우수 (10% 미만)'   if ss['mdd_pct'] < 10 else
                        '✔️  양호 (20% 미만)'  if ss['mdd_pct'] < 20 else
                        '⚠️  주의 (30% 미만)'  if ss['mdd_pct'] < 30 else
                        '❌ 높음 — 리스크 관리 필요')
            sharpe_eval = ('✅ 우수 (2.0+)'  if ss['sharpe_annual'] > 2.0 else
                           '✔️  양호 (1.0+)' if ss['sharpe_annual'] > 1.0 else
                           '⚠️  보통 (0+)'   if ss['sharpe_annual'] > 0 else
                           '❌ 낮음')
            summary_section = f"""
## 💰 수익 현황

| 항목 | 값 |
|------|----|
| 초기 자본 | {ss['initial_capital']:,}원 |
| 최종 자본 | {ss['final_capital']:,}원 |
| **총 수익률** | **{ss['total_return']:.2f}%** |
| 총 손익 | {ss['actual_profit']:,}원 |
| 예수금 (최종) | {ss['d2_deposit']:,}원 |
| 보유주식 평가액 | {ss['total_valuation']:,}원 |

---

## 📉 리스크 지표

| 항목 | 값 | 평가 |
|------|----|----|
| MDD (최대 낙폭) | {ss['mdd_pct']:.2f}% | {mdd_eval} |
| MDD 금액 | {ss['mdd_amt']:,}원 | |
| Sharpe Ratio (연) | {ss['sharpe_annual']:.2f} | {sharpe_eval} |
| Sharpe Ratio (일) | {ss['sharpe_daily']:.4f} | |
| 일평균 수익률 | {ss['avg_daily_return']:.4f}% | |
| 일수익률 표준편차 | {ss['std_daily_return']:.4f}% | |

---
"""
        else:
            summary_section = ""

        # 매도 이유 분류 (sell_rate vs sell_point / losscut_point)
        sp = getattr(self, 'sell_point', 6)
        lc = getattr(self, 'losscut_point', -3)
        profit_cut_list = [t for t in trades if float(t[6]) >= sp]
        loss_cut_list   = [t for t in trades if float(t[6]) <= lc]
        ma_cross_list   = [t for t in trades if lc < float(t[6]) < sp]
        sell_reason_section = f"""
## 📤 매도 근거 분포

| 매도 유형 | 건수 | 비율 | 평균 수익률 |
|----------|------|------|------------|
| 익절(+{sp:.0f}% 이상) | {len(profit_cut_list)}건 | {len(profit_cut_list)/max(1,total_trades)*100:.1f}% | {sum(float(t[6]) for t in profit_cut_list)/max(1,len(profit_cut_list)):.2f}% |
| 손절({lc:.0f}% 이하) | {len(loss_cut_list)}건 | {len(loss_cut_list)/max(1,total_trades)*100:.1f}% | {sum(float(t[6]) for t in loss_cut_list)/max(1,len(loss_cut_list)):.2f}% |
| MA데드크로스 | {len(ma_cross_list)}건 | {len(ma_cross_list)/max(1,total_trades)*100:.1f}% | {sum(float(t[6]) for t in ma_cross_list)/max(1,len(ma_cross_list)):.2f}% |

---
"""

        # 스코어 통계 (composite_score = index 9, score_a~f = indices 10-15)
        scores = [t[9] for t in trades if t[9] and t[9] > 0]
        min_score = getattr(cf, 'v2_min_score', 120)
        if scores:
            score_avg = sum(scores) / len(scores)
            score_min = min(scores)
            score_max = max(scores)
            win_scores  = [t[9] for t in trades if t[6] >= 0 and t[9] and t[9] > 0]
            loss_scores = [t[9] for t in trades if t[6] <  0 and t[9] and t[9] > 0]
            score_win_avg  = sum(win_scores)  / len(win_scores)  if win_scores  else 0
            score_loss_avg = sum(loss_scores) / len(loss_scores) if loss_scores else 0
            # 구간별 승률 (min_score 기준 동적)
            high_score_trades = [t for t in trades if t[9] and t[9] >= min_score + 30]
            mid_score_trades  = [t for t in trades if t[9] and min_score + 10 <= t[9] < min_score + 30]
            low_score_trades  = [t for t in trades if t[9] and t[9] < min_score + 10]
            def win_rate_of(group):
                if not group: return 0, 0
                wins = len([t for t in group if t[6] >= 0])
                return wins / len(group) * 100, len(group)
            hs_wr, hs_cnt = win_rate_of(high_score_trades)
            ms_wr, ms_cnt = win_rate_of(mid_score_trades)
            ls_wr, ls_cnt = win_rate_of(low_score_trades)
            # 섹션별 스코어 분석 (score_a~f = indices 10-15)
            score_labels = [
                ('A.모멘텀(50pt)',   10),
                ('B.평균회귀(20pt)', 11),
                ('C.추세강도(50pt)', 12),
                ('D.거래량(40pt)',   13),
                ('E.시장강도(30pt)', 14),
                ('F.다중시간(10pt)', 15),
            ]
            section_rows = ""
            for label, idx in score_labels:
                w_vals = [float(t[idx]) for t in trades if t[6] >= 0 and len(t) > idx and t[idx]]
                l_vals = [float(t[idx]) for t in trades if t[6] <  0 and len(t) > idx and t[idx]]
                w_avg = sum(w_vals) / len(w_vals) if w_vals else 0
                l_avg = sum(l_vals) / len(l_vals) if l_vals else 0
                section_rows += f"| {label} | {w_avg:.1f} | {l_avg:.1f} | {w_avg - l_avg:+.1f} |\n"
            score_section = f"""
## 🏆 스코어 분석

| 항목 | 값 |
|------|----|
| 평균 스코어 | {score_avg:.1f}점 |
| 최고 스코어 | {score_max}점 |
| 최저 스코어 | {score_min}점 |
| 수익 거래 평균 스코어 | {score_win_avg:.1f}점 |
| 손실 거래 평균 스코어 | {score_loss_avg:.1f}점 |

### 스코어 구간별 승률

| 구간 | 거래수 | 승률 |
|------|--------|------|
| {min_score + 30}점 이상 | {hs_cnt}건 | {hs_wr:.1f}% |
| {min_score + 10}~{min_score + 29}점 | {ms_cnt}건 | {ms_wr:.1f}% |
| {min_score}~{min_score + 9}점 | {ls_cnt}건 | {ls_wr:.1f}% |

### 섹션별 스코어 — 수익 vs 손실 거래 평균

| 카테고리 | 수익 평균 | 손실 평균 | 차이 |
|---------|---------|---------|------|
{section_rows}
---
"""
        else:
            score_section = ""
            sell_reason_section = ""

        report = f"""# 백테스팅 상세 분석 레포트

**알고리즘 번호**: {self.simul_num}
**생성 일시**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## ⚙️ 전략 파라미터

| 파라미터 | 값 |
|----------|----|
| 투자 단위 (invest_unit) | {getattr(self, 'invest_unit', '-'):,}원 |
| 최소 잔고 (limit_money) | {getattr(self, 'limit_money', '-'):,}원 |
| 익절 기준 (sell_point) | {getattr(self, 'sell_point', '-')}% |
| 손절 기준 (losscut_point) | {getattr(self, 'losscut_point', '-')}% |
| 최소 스코어 (v2_min_score) | {getattr(cf, 'v2_min_score', '-')}점 |
| 매도 전략 번호 (sell_list_num) | {getattr(self, 'sell_list_num', '-')} |

---
{summary_section}
## 📊 기본 통계

| 항목 | 값 |
|------|----|
| 총 거래 횟수 | {total_trades}회 |
| 수익 거래 | {win_trades}회 ({win_rate:.1f}%) |
| 손실 거래 | {loss_trades}회 ({100-win_rate:.1f}%) |
| 평균 익절률 | {avg_profit:.2f}% |
| 평균 손절률 | {avg_loss:.2f}% |
| 최대 익절률 | {summary_stats.get('max_profit_rate', 0) if summary_stats else 0:.2f}% |
| 최대 손절률 | {summary_stats.get('max_loss_rate', 0) if summary_stats else 0:.2f}% |
| 평균 보유일 | {summary_stats.get('avg_holding_days', 0) if summary_stats else 0:.1f}일 |
| 손익비 (R) | {abs(avg_profit / avg_loss) if avg_loss != 0 else 0:.2f} |

---
{sell_reason_section}
{score_section}
## 🎯 최고 수익 거래 Top 10

| 순위 | 종목명 | 매수일 | 매도일 | 수익률 | 보유일 | 스코어 |
|------|--------|--------|--------|--------|--------|--------|
"""

        for idx, trade in enumerate(best_trades, 1):
            code_name = trade[1] if trade[1] else trade[0]
            buy_date = trade[2]
            sell_date = trade[3]
            sell_rate = trade[6]
            holding_days = trade[8] if trade[8] is not None else 0
            score = int(trade[9]) if trade[9] else 0

            report += f"| {idx} | {code_name} | {buy_date} | {sell_date} | **+{sell_rate:.2f}%** | {holding_days}일 | {score}점 |\n"

        report += f"""
---

## 📉 최대 손실 거래 Top 10

| 순위 | 종목명 | 매수일 | 매도일 | 손실률 | 보유일 | 스코어 |
|------|--------|--------|--------|--------|--------|--------|
"""

        for idx, trade in enumerate(worst_trades, 1):
            code_name = trade[1] if trade[1] else trade[0]
            buy_date = trade[2]
            sell_date = trade[3]
            sell_rate = trade[6]
            holding_days = trade[8] if trade[8] is not None else 0
            score = int(trade[9]) if trade[9] else 0

            report += f"| {idx} | {code_name} | {buy_date} | {sell_date} | **{sell_rate:.2f}%** | {holding_days}일 | {score}점 |\n"

        report += f"""
---

## 🔍 손실 패턴 분석

### 보유 기간별 손실 분포

"""

        if loss_patterns['loss_by_holding_period']:
            for period, losses in loss_patterns['loss_by_holding_period'].items():
                avg_loss = sum(losses) / len(losses)
                count = loss_patterns['loss_count_by_period'][period]
                report += f"- **{period}**: {count}건, 평균 손실률 {avg_loss:.2f}%\n"
        else:
            report += "- 손실 거래가 없습니다.\n"

        report += f"""
### 손실 거래 특징

- 평균 손실 보유일: {loss_patterns['avg_loss_holding_days']:.1f}일
- 총 손실 거래: {loss_patterns['loss_trades']}건

---

## 💡 개선 제안

"""

        if suggestions:
            for suggestion in suggestions:
                report += f"""
### {suggestion['category']}

**문제점**: {suggestion['issue']}

**제안사항**: {suggestion['suggestion']}

"""
        else:
            report += "현재 전략이 양호합니다. 큰 개선이 필요하지 않습니다.\n"

        report += """
---

## 📌 다음 단계

1. 위 분석 결과를 바탕으로 전략 파라미터 조정
2. 수정된 전략으로 재 백테스팅
3. 실전 적용 전 소액으로 테스트

---

*이 레포트는 자동 생성되었습니다.*
"""

        return report

    # 분 데이터를 가져오는 함수
    def get_date_min_for_simul(self, simul_start_date):
        # 촬영 후 업데이트 되었습니다
        dt_format = '%Y%m%d%H%M'
        simul_time = datetime.datetime.strptime(simul_start_date + "0900", dt_format)
        min_delta = datetime.timedelta(minutes=1)

        times = []
        while simul_time.hour != 15 or simul_time.minute != 31:
            times.append((datetime.datetime.strftime(simul_time, dt_format),))
            simul_time += min_delta

        self.min_date_rows = times
    # 분별 시뮬레이팅 함수
    # 새로운 종목 매수 및 보유한 종목의 데이터를 업데이트 하는 함수, 매도 함수도 포함
    def trading_by_min(self, date_rows_today, date_rows_yesterday, i):
        self.print_info(date_rows_today)

        # all_item_db가 존재하고, 현재 보유 중인 종목이 있다면 아래 로직을 들어간다.
        if self.is_simul_table_exist(self.db_name, "all_item_db") and len(self.get_data_from_possessed_item()) != 0:
            # 보유 중인 종목들의 주가를 일별로 업데이트 하는 함수(option 이 OPEN 이면 OPEN가만 업데이트)
            self.update_all_db_by_date(date_rows_today, option='OPEN')

        # 분별 시간 데이터를 가져온다.
        self.get_date_min_for_simul(date_rows_today)
        if len(self.min_date_rows) != 0:
            # 분 단위로 for문을 돈다
            for t in range(len(self.min_date_rows)):
                min = self.min_date_rows[t][0]
                # all_item_db가 존재하고 현재 보유 중인 종목이 있는 경우
                if self.is_simul_table_exist(self.db_name,"all_item_db") and len(self.get_data_from_possessed_item()) != 0:
                    self.print_info(min)
                    self.update_all_db_by_min(min)
                    self.update_all_db_etc()
                    # 매도 함수
                    self.auto_trade_sell_stock(min, i)
                    # self.buy_stop 이 False 이고, 보유 자산이 있으면 실제 매수를 한다.
                    if not self.buy_stop and self.jango_check():
                        # 매수 할 종목을 가져온다
                        self.get_realtime_daily_buy_list()

                        if self.len_df_realtime_daily_buy_list > 0:

                            self.auto_trade_stock_realtime(min, date_rows_today, date_rows_yesterday)
                        else:
                            print("realtime_daily_buy_list에 금일 매수 대상 종목이 0개 이다.  ")


                #  여긴 가장 초반에 all_itme_db를 만들어야 할때이거나 매수한 종목이 없을 때 들어가는 로직
                else:
                    if not self.buy_stop and self.jango_check():
                        self.auto_trade_stock_realtime(min, date_rows_today, date_rows_yesterday)

                # 9시에만 매수를 하는 경우는 한번만 9시에 매수 하고 self.buy_stop을 true로 변경하여 이후로 매수하지 않도록 설정
                if not self.buy_stop and self.only_nine_buy:
                    print("9시 매수 끝!!!!!!!!!!")
                    self.buy_stop = True


        else:
            print("min_craw db의 종목 테이블에 " + str(
                date_rows_today) + " 데이터가 존재 하지 않는다! self.simul_start_date 날짜를 변경 하세요! (분별 데이터는 콜렉터에서 최근 1년 데이터만 가져옵니다! ")

    # 새로운 종목 매수 및 보유한 종목의 데이터를 업데이트 하는 함수, 매도 함수도 포함
    def trading_by_date(self, date_rows_today, date_rows_yesterday, i):
        self.print_info(date_rows_today)

        # all_item_db가 존재하고, 현재 보유 중인 종목이 있다면 아래 로직을 들어간다.
        if self.is_simul_table_exist(self.db_name, "all_item_db") and len(self.get_data_from_possessed_item()) != 0:
            # 보유 중인 종목들의 주가를 일별로 업데이트 하는 함수
            self.update_all_db_by_date(date_rows_today, option = 'OPEN')
            # 보유 중인 종목들의 주가 이외의 기타 정보들을 업데이트 하는 함수
            self.update_all_db_etc()
            # 매도 함수
            self.auto_trade_sell_stock(date_rows_today, i)

            # 보유 자산이 있다면, 실제 매수를 한다.
            if self.jango_check():
                # 돈있으면 매수 시작
                self.auto_trade_stock_realtime(str(date_rows_today) + "0900", date_rows_today, date_rows_yesterday)

        #  여긴 가장 초반에 all_itme_db를 만들어야 할때이거나 매수한 종목이 없을 때 들어가는 로직
        else:
            if self.jango_check():
                self.auto_trade_stock_realtime(str(date_rows_today) + "0900", date_rows_today, date_rows_yesterday)

    # 매일 시뮬레이팅 돌기 전 초기화 세팅
    def daily_variable_setting(self):
        self.buy_stop = False
        self.today_invest_price = 0

    # 분별 시뮬레이팅
    def simul_by_min(self, date_rows_today, date_rows_yesterday, i):
        logger.debug("**************************   date: " + date_rows_today)
        # 일별 시뮬레이팅 하며 변수 초기화(분별시뮬레이터의 경우도 하루 단위로 초기화)
        self.daily_variable_setting()
        # daily_buy_list에 시뮬레이팅 할 날짜에 해당하는 테이블과 전 날 테이블이 존재하는지 확인
        if self.is_date_exist(date_rows_today) and self.is_date_exist(date_rows_yesterday):
            # 우선 매수리스트를 가져온다.
            self.db_to_realtime_daily_buy_list(date_rows_today, date_rows_yesterday, i)
            # 분별 시뮬레이팅 시작한다.
            self.trading_by_min(date_rows_today, date_rows_yesterday, i)
            self.db_to_jango(date_rows_today)

            # [추가 코드]all_item_db가 존재하고, 현재 보유 중인 종목이 있다면 아래 로직을 들어간다.
            if self.is_simul_table_exist(self.db_name, "all_item_db") and len(self.get_data_from_possessed_item()) != 0:
                # 보유 중인 종목들의 주가를 일별로 업데이트 하는 함수(분별 종가 업데이트 이외에 clo5, clo20등등의 값을 업데이트)
                self.update_all_db_by_date(date_rows_today, option='ALL')

        else:
            print(date_rows_today + "테이블은 존재하지 않는다!!!")

    # 일별 시뮬레이팅
    def simul_by_date(self, date_rows_today, date_rows_yesterday, i):
        logger.debug("**************************   date: " + date_rows_today)
        # 일별 시뮬레이팅 하며 변수 초기화
        self.daily_variable_setting()
        # daily_buy_list에 시뮬레이팅 할 날짜에 해당하는 테이블과 전 날 테이블이 존재하는지 확인
        if self.is_date_exist(date_rows_today) and self.is_date_exist(date_rows_yesterday):
            # 당일 매수 할 종목들을 realtime_daily_buy_list 테이블에 세팅
            self.db_to_realtime_daily_buy_list(date_rows_today, date_rows_yesterday, i)
            # 트레이딩(매수, 매도) 함수 + 보유 종목의 현재가 업데이트 함수
            self.trading_by_date(date_rows_today, date_rows_yesterday, i)

            # [추가 코드]all_item_db가 존재하고, 현재 보유 중인 종목이 있다면 아래 로직을 들어간다.
            if self.is_simul_table_exist(self.db_name, "all_item_db") and len(self.get_data_from_possessed_item()) != 0:
                # 보유 중인 종목들의 주가를 일별로 업데이트 하는 함수(분별 종가 업데이트 이외에 clo5, clo20등등의 값을 업데이트)
                self.update_all_db_by_date(date_rows_today, option='ALL')

            # 일별 정산
            self.db_to_jango(date_rows_today)

        else:
            print(date_rows_today + "테이블은 존재하지 않는다!!!")

    # 날짜 별 로테이팅 함수
    def rotate_date(self):
        for i in range(1, len(self.date_rows)):
            # print("self.date_rows!!" ,self.date_rows)
            # 시뮬레이팅 할 일자
            date_rows_today = self.date_rows[i][0]
            # 시뮬레이팅 하기 전의 일자
            date_rows_yesterday = self.date_rows[i - 1][0]

            # self.simul_reset 이 False, 즉 시뮬레이터를 멈춘 지점 부터 실행하기 위한 조건
            if not self.simul_reset and not self.simul_reset_lock:
                if int(date_rows_today) <= int(self.last_simul_date):
                    print("**************************   date: " + date_rows_today + "simul jango date exist pass ! ")
                    continue
                else:
                    self.simul_reset_lock = True

            # 분별 시뮬레이팅
            if self.use_min:
                self.simul_by_min(date_rows_today, date_rows_yesterday, i)
            # 일별 시뮬레이팅
            else:
                self.simul_by_date(date_rows_today, date_rows_yesterday, i)

        # 마지막 jango_data 정리
        self.arrange_jango_data()

        # 최종 결과 요약 출력
        self.print_simulation_summary()


# 수업 후 아래 함수 추가 되었습니다
def escape_percentage(conn, clauseelement, multiparams, params):
    # execute로 실행한 sql문이 들어왔을 때 %를 %%로 replace
    if isinstance(clauseelement, str) and '%' in clauseelement and multiparams is not None:
        while True:
            replaced = re.sub(r'([^%])%([^%s])', r'\1%%\2', clauseelement)
            if replaced == clauseelement:
                break
            clauseelement = replaced

    return clauseelement, multiparams, params

if __name__ == '__main__':
    logger.error('simulator.py로 실행해 주시기 바랍니다.')
    sys.exit(1)
