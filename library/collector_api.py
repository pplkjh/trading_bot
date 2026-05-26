from collections import OrderedDict

from sqlalchemy import Integer, Text, String

ver = "#version 1.5.0"
print(f"collector_api Version: {ver}")

import numpy
import pathlib
from library.open_api import *
import os
import time
from PyQt5.QtWidgets import *
from library.daily_buy_list import *
from pandas import DataFrame
from kind_crawling import *

MARKET_KOSPI = 0
MARKET_KOSDAQ = 10


# 콜렉팅에 사용되는 메서드를 모아 놓은 클래스
class collector_api():
    def __init__(self):
        self.open_api = open_api()
        self.engine_JB = self.open_api.engine_JB
        self.variable_setting()
        self.kind = KINDCrawler()

        # 진행률 표시용 변수
        self.current_stock_name = ""
        self.current_stock_code = ""
        self.current_status = ""
        self._progress_lines = 0

    def variable_setting(self):
        self.open_api.py_gubun = "collector"
        self.dc = daily_crawler(self.open_api.cf.real_db_name, self.open_api.cf.real_daily_craw_db_name,
                                self.open_api.cf.real_daily_buy_list_db_name)
        self.dbl = daily_buy_list()

    def print_progress(self, current, total, task_name, start_time=None, stock_name="", stock_code="", status=""):
        """
        진행률 표시 함수 (실시간 업데이트)

        Parameters:
        -----------
        current : int - 현재 진행 수
        total : int - 전체 수
        task_name : str - 작업명
        start_time : float - 시작 시간
        stock_name : str - 현재 처리 중인 종목명
        stock_code : str - 현재 처리 중인 종목코드
        status : str - 현재 상태 메시지
        """
        # 현재 종목 정보 업데이트
        if stock_name:
            self.current_stock_name = stock_name
        if stock_code:
            self.current_stock_code = stock_code
        if status:
            self.current_status = status

        # 0으로 나누기 방지
        if total <= 0:
            total = 1
        percent = (current / total) * 100
        bar_length = 50
        filled = int(bar_length * current / total)
        bar = '█' * filled + '░' * (bar_length - filled)

        # 예상 종료 시간 계산
        eta_str = ""
        if start_time and current > 0:
            elapsed = time.time() - start_time
            if elapsed > 0:
                rate = current / elapsed
                remaining = (total - current) / rate if rate > 0 else 0
                eta_str = f" | ETA: {int(remaining//60)}분 {int(remaining%60)}초"

        # 이전 출력 지우기 (커서를 위로 이동)
        if self._progress_lines > 0:
            print(f"\033[{self._progress_lines}A", end='')

        # 진행률 바
        line1 = f"{task_name}: [{bar}] {percent:>5.1f}% ({current}/{total}){eta_str}"

        # 현재 종목 정보
        stock_info = ""
        if self.current_stock_name:
            stock_info = f"  📌 현재: {self.current_stock_name}"
            if self.current_stock_code:
                stock_info += f" ({self.current_stock_code})"

        # 상태 메시지
        status_info = ""
        if self.current_status:
            # 상태 메시지가 너무 길면 자르기
            max_len = 80
            if len(self.current_status) > max_len:
                status_info = f"  💬 {self.current_status[:max_len]}..."
            else:
                status_info = f"  💬 {self.current_status}"

        # 출력 (각 줄 끝에 공백으로 이전 텍스트 덮어쓰기)
        print(f"\033[K{line1}")
        if stock_info:
            print(f"\033[K{stock_info}")
        if status_info:
            print(f"\033[K{status_info}")

        # 출력한 줄 수 계산
        self._progress_lines = 1
        if stock_info:
            self._progress_lines += 1
        if status_info:
            self._progress_lines += 1

        # 완료 시
        if current == total:
            self._progress_lines = 0
            self.current_stock_name = ""
            self.current_stock_code = ""
            self.current_status = ""
            print()  # 완료 시 줄바꿈

    def update_status(self, status):
        """상태 메시지만 실시간 업데이트 (진행률 표시 중일 때)"""
        self.current_status = status
        if self._progress_lines >= 3:  # 상태 줄이 표시되고 있을 때만
            max_len = 80
            if len(status) > max_len:
                status_info = f"  💬 {status[:max_len]}..."
            else:
                status_info = f"  💬 {status}"
            # 상태 줄로 이동 후 업데이트
            print(f"\033[1A\033[K{status_info}")

    # 콜렉팅을 실행하는 함수
    def code_update_check(self, phase=None):
        # Phase 2 전용: 펀더멘탈 수집만 실행 (rq_count 리셋 활용)
        if phase == 2:
            print("\n" + "="*100)
            print("📊 [Phase 2] 펀더멘탈 수집")
            print("="*100 + "\n")
            overall_start = time.time()
            try:
                self.collect_market_index()
                self.collect_stock_fundamental()
            except Exception as e:
                logger.warning(f"펀더멘탈 수집 실패: {e}")
            total_time = time.time() - overall_start
            print("\n" + "="*100)
            print(f"✅ Phase 2 완료! ({int(total_time//60)}분 {int(total_time%60)}초)")
            print("="*100)
            logger.info("collecting 완료")
            return

        # Phase 3 전용: 스코어링만 실행 (rq_count 리셋 활용)
        if phase == 3:
            print("\n" + "="*100)
            print("📊 [Phase 3] 스코어링 (realtime_daily_buy_list)")
            print("="*100 + "\n")
            overall_start = time.time()
            try:
                self.realtime_daily_buy_list_check()
            except Exception as e:
                logger.warning(f"스코어링 실패: {e}")
            total_time = time.time() - overall_start
            print("\n" + "="*100)
            print(f"✅ Phase 3 완료! ({int(total_time//60)}분 {int(total_time%60)}초)")
            print("="*100)
            logger.info("collecting 완료")
            return

        # Phase 1 또는 전체 실행 (기본)
        if phase == 1:
            print("\n" + "="*100)
            print("📊 [Phase 1] 종가 수집 + 기술지표")
            print("="*100 + "\n")
        else:
            print("\n" + "="*100)
            print("📊 데이터 수집 시작")
            print("="*100 + "\n")

        overall_start = time.time()

        sql = "select code_update,jango_data_db_check, possessed_item, today_profit, final_chegyul_check, db_to_buy_list,today_buy_list, daily_crawler , min_crawler, daily_buy_list from setting_data limit 1"

        rows = self.engine_JB.execute(sql).fetchall()

        # daily_crawler 시간 체크 함수
        def should_collect_daily_craw(daily_crawler_value):
            """
            daily_crawler 재수집 필요 여부 판단

            Returns:
                True: 수집 필요, False: 스킵 가능
            """
            if not daily_crawler_value:
                return True

            # 타임스탬프 형식 체크 (yyyyMMddHHmm = 12자리)
            if len(daily_crawler_value) < 12:
                # 기존 날짜 형식 (yyyyMMdd = 8자리) → 수집 필요
                return daily_crawler_value != self.open_api.today

            # 타임스탬프에서 날짜와 시간 추출
            collected_date = daily_crawler_value[:8]
            collected_time = daily_crawler_value[8:12]  # HHmm

            # 다른 날짜면 수집 필요
            if collected_date != self.open_api.today:
                return True

            # 오늘 날짜인데 오후 4시(1600) 이전에 수집했으면 재수집 필요
            if int(collected_time) < 1600:
                logger.debug(f"오후 4시 이전 수집({collected_time}) → 종가 업데이트 필요")
                return True

            # 오후 4시 이후 수집했으면 스킵
            logger.debug(f"오후 4시 이후 수집({collected_time}) → 이미 종가 반영됨")
            return False

        # daily_buy_list 시간 체크 함수
        def should_collect_daily_buy_list(daily_buy_list_value):
            """daily_buy_list 재수집 필요 여부 판단"""
            if not daily_buy_list_value:
                return True

            if len(daily_buy_list_value) < 12:
                return daily_buy_list_value != self.open_api.today

            collected_date = daily_buy_list_value[:8]
            collected_time = daily_buy_list_value[8:12]

            if collected_date != self.open_api.today:
                return True

            if int(collected_time) < 1600:
                logger.debug(f"오후 4시 이전 수집({collected_time}) → 종가 업데이트 필요")
                return True

            logger.debug(f"오후 4시 이후 수집({collected_time}) → 이미 종가 반영됨")
            return False

        # 전체 작업 수 계산
        total_tasks = 0
        current_task = 0

        # 수집 필요 여부 체크
        need_daily_crawler = should_collect_daily_craw(rows[0][7])
        need_daily_buy_list = should_collect_daily_buy_list(rows[0][9])

        if rows[0][0] != self.open_api.today:
            total_tasks += 1
        if rows[0][1] != self.open_api.today or rows[0][2] != self.open_api.today:
            total_tasks += 3
        if rows[0][2] != self.open_api.today:
            total_tasks += 1
        # daily_crawler와 daily_buy_list는 시간 체크 후 필요시에만 실행
        if need_daily_crawler:
            total_tasks += 1
        if need_daily_buy_list:
            total_tasks += 1
        if rows[0][4] != self.open_api.today:
            total_tasks += 1
        if rows[0][6] != self.open_api.today:
            total_tasks += 1
        if self.open_api.cf.use_min_crawler and rows[0][8] != self.open_api.today:
            total_tasks += 1
        total_tasks += 1  # kind.craw()

        if total_tasks == 0:
            print("✅ 모든 데이터가 최신 상태입니다. 수집할 항목이 없습니다.\n")
            return

        # stock_item_all(kospi,kosdaq,konex)
        # kospi(stock_kospi), kosdaq(stock_kosdaq), konex(stock_konex)
        # 관리종목(stock_managing), 불성실법인종목(stock_insincerity) 업데이트
        if rows[0][0] != self.open_api.today:
            current_task += 1
            print(f"\n[{current_task}/{total_tasks}] 📋 종목 코드 업데이트 중...")
            task_start = time.time()
            self.get_code_list()
            print(f"✅ 완료 ({time.time() - task_start:.1f}초)")


        # 촬영 후 콜렉팅 순서가 일부 업데이트 되었습니다.
        # 잔고 및 보유종목 현황 db setting  & 당일 종목별 실현 손익
        if rows[0][1] != self.open_api.today or rows[0][2] != self.open_api.today:
            current_task += 1
            print(f"\n[{current_task}/{total_tasks}] 💰 투자 단위 설정 중...")
            task_start = time.time()
            self.open_api.set_invest_unit()
            # 결과 출력
            print(f"✅ 완료 ({time.time() - task_start:.1f}초)")
            print(f"    📊 투자 단위: {self.open_api.change_format(str(self.open_api.invest_unit))}원")
            print(f"    💵 예수금(D+2): {self.open_api.change_format(str(self.open_api.d2_deposit_before_format))}원")
            print(f"    💰 총 투자금: {self.open_api.change_format(str(self.open_api.total_invest))}원")

            current_task += 1
            print(f"\n[{current_task}/{total_tasks}] 📊 당일 손익 리스트 업데이트 중...")
            task_start = time.time()
            self.db_to_today_profit_list()
            self.py_check_balance()
            print(f"✅ 완료 ({time.time() - task_start:.1f}초)")
            # 결과 출력 (테이블이 없을 수 있음)
            try:
                profit_sql = "SELECT COUNT(*) FROM today_profit WHERE date = '%s'"
                profit_count = self.engine_JB.execute(profit_sql % self.open_api.today).fetchone()[0]
                print(f"    📈 당일 손익 종목 수: {profit_count}개")
            except Exception:
                pass  # 테이블이 아직 없거나 데이터가 없는 경우

            current_task += 1
            print(f"\n[{current_task}/{total_tasks}] 💼 잔고 데이터 업데이트 중...")
            task_start = time.time()
            self.db_to_jango()
            print(f"✅ 완료 ({time.time() - task_start:.1f}초)")
            # 결과 출력 (테이블이 없을 수 있음)
            try:
                jango_sql = "SELECT total_asset, d2_deposit, today_profit, today_earning_rate FROM jango_data WHERE date = '%s' LIMIT 1"
                jango_result = self.engine_JB.execute(jango_sql % self.open_api.today).fetchone()
                if jango_result:
                    # None 값 처리 (기본값 0)
                    total_asset = jango_result[0] if jango_result[0] is not None else 0
                    d2_deposit = jango_result[1] if jango_result[1] is not None else 0
                    today_profit = jango_result[2] if jango_result[2] is not None else 0
                    today_rate = jango_result[3] if jango_result[3] is not None else 0.0

                    print(f"    💼 총 자산: {self.open_api.change_format(str(total_asset))}원")
                    print(f"    💵 예수금: {self.open_api.change_format(str(d2_deposit))}원")
                    print(f"    {'📈' if today_profit >= 0 else '📉'} 당일 손익: {self.open_api.change_format(str(today_profit))}원 ({today_rate:.2f}%)")
            except Exception:
                pass  # 테이블이 아직 없거나 데이터가 없는 경우

        # possessed_item(현재 보유종목) 테이블 업데이트
        if rows[0][2] != self.open_api.today:
            current_task += 1
            print(f"\n[{current_task}/{total_tasks}] 📌 보유 종목 업데이트 중...")
            task_start = time.time()
            self.open_api.db_to_possesed_item()
            self.open_api.setting_data_possesed_item()
            print(f"✅ 완료 ({time.time() - task_start:.1f}초)")
            # 결과 출력 (테이블이 없을 수 있음)
            try:
                possessed_sql = "SELECT COUNT(*), SUM(hold_quantity * current_price) FROM possessed_item WHERE sell_date IS NULL"
                possessed_result = self.engine_JB.execute(possessed_sql).fetchone()
                if possessed_result and possessed_result[0]:
                    print(f"    📌 보유 종목 수: {possessed_result[0]}개")
                    print(f"    💰 보유 종목 평가액: {self.open_api.change_format(str(int(possessed_result[1] or 0)))}원")
                else:
                    print(f"    📌 보유 종목: 없음")
            except Exception:
                pass  # 테이블이 아직 없거나 데이터가 없는 경우

        # daily_craw db 업데이터 (시간 체크 후 필요시에만 실행)
        if need_daily_crawler:
            current_task += 1
            if rows[0][7] and len(rows[0][7]) >= 8 and rows[0][7][:8] == self.open_api.today:
                print(f"\n[{current_task}/{total_tasks}] 📈 일봉 데이터 재수집 중 (종가 업데이트)...")
                # 오늘 이미 수집했지만 재수집이 필요한 경우(장후 종가 반영 등) check_daily_crawler 리셋
                try:
                    self.open_api.engine_daily_buy_list.execute(
                        "UPDATE stock_item_all SET check_daily_crawler='0' WHERE check_daily_crawler='1'"
                    )
                    logger.debug("check_daily_crawler 리셋 완료 (1→0) for 종가 재수집")
                except Exception as e:
                    logger.warning(f"check_daily_crawler 리셋 실패: {e}")
            else:
                print(f"\n[{current_task}/{total_tasks}] 📈 일봉 데이터 수집 중...")
            task_start = time.time()
            self.daily_crawler_check()
            print(f"✅ 완료 ({time.time() - task_start:.1f}초)")
            # 결과 출력 (테이블이 없을 수 있음)
            try:
                collected_sql = "SELECT COUNT(*) FROM stock_item_all WHERE check_daily_crawler IN ('1', '3')"
                total_sql = "SELECT COUNT(*) FROM stock_item_all"
                collected_count = self.open_api.engine_daily_buy_list.execute(collected_sql).fetchone()[0]
                total_count = self.open_api.engine_daily_buy_list.execute(total_sql).fetchone()[0]
                print(f"    📈 수집 완료 종목: {collected_count}/{total_count}개")
            except Exception:
                pass  # 테이블이 아직 없는 경우
        else:
            logger.debug("daily_crawler 스킵 (이미 종가 수집 완료)")

        # daily_buy_list db 업데이트 (시간 체크 후 필요시에만 실행)
        if need_daily_buy_list:
            current_task += 1
            if rows[0][9] and len(rows[0][9]) >= 8 and rows[0][9][:8] == self.open_api.today:
                print(f"\n[{current_task}/{total_tasks}] 🎯 매수 후보 재분석 중 (종가 업데이트)...")
            else:
                print(f"\n[{current_task}/{total_tasks}] 🎯 매수 후보 분석 중...")
            task_start = time.time()
            logger.debug("[collector] daily_buy_list_check 시작")
            self.daily_buy_list_check()
            logger.debug("[collector] daily_buy_list_check 완료")
            # 결과 출력
            try:
                from library.utils import get_latest_complete_date
                _target = get_latest_complete_date()
                buy_list_sql = f"SELECT COUNT(*) FROM daily_buy_list.`{_target}`"
                buy_list_count = self.open_api.engine_daily_buy_list.execute(buy_list_sql).fetchone()[0]
                logger.debug(f"[collector] daily_buy_list 종목수: {buy_list_count}")
                print(f"✅ 완료 ({time.time() - task_start:.1f}초)")
                print(f"    🎯 매수 후보 종목: {buy_list_count}개")
                print(f"    📊 기술적 지표 분석 완료 (RSI, Bollinger Bands, ATR)")
            except Exception:
                print(f"✅ 완료 ({time.time() - task_start:.1f}초)")
        else:
            logger.debug("daily_buy_list 스킵 (이미 종가 수집 완료)")

        # daily_buy_list db업데이트 이 후에 들어가야함
        if rows[0][4] != self.open_api.today:
            current_task += 1
            print(f"\n[{current_task}/{total_tasks}] 🔍 체결 확인 및 업데이트 중...")
            logger.debug("[collector] chegyul_check 시작")
            task_start = time.time()
            self.open_api.chegyul_check()
            logger.debug("[collector] chegyul_check 완료 → final_chegyul_check 시작")
            self.open_api.final_chegyul_check()
            logger.debug("[collector] final_chegyul_check 완료")
            print(f"✅ 완료 ({time.time() - task_start:.1f}초)")

        # 내일 매수 종목 업데이트 (realtime_daily_buy_list) — phase=1이면 스킵 (phase 3에서 처리)
        if phase == 1:
            logger.debug("[Phase 1] 스코어링 스킵 → Phase 3에서 처리")
        elif rows[0][6] != self.open_api.today or need_daily_buy_list:
            current_task += 1
            print(f"\n[{current_task}/{total_tasks}] 🚀 실시간 매수 리스트 생성 중...")
            logger.debug(f"[collector] realtime_daily_buy_list_check 시작")
            task_start = time.time()
            self.realtime_daily_buy_list_check()
            logger.debug(f"[collector] realtime_daily_buy_list_check 완료")
            # 결과 출력
            try:
                realtime_sql = "SELECT COUNT(*) FROM realtime_daily_buy_list"
                realtime_count = self.engine_JB.execute(realtime_sql).fetchone()[0]
                print(f"✅ 완료 ({time.time() - task_start:.1f}초)")
                print(f"    🚀 실시간 매수 대기 종목: {realtime_count}개")
            except Exception:
                print(f"✅ 완료 ({time.time() - task_start:.1f}초)")

        # min_craw db (분별 데이터) 업데이트
        # cf.use_min_crawler = True일 때만 실행
        if self.open_api.cf.use_min_crawler and rows[0][8] != self.open_api.today:
            current_task += 1
            print(f"\n[{current_task}/{total_tasks}] ⏱️  분봉 데이터 수집 중...")
            task_start = time.time()
            self.min_crawler_check()
            print(f"✅ 완료 ({time.time() - task_start:.1f}초)")

        current_task += 1
        print(f"\n[{current_task}/{total_tasks}] 🌐 KIND 데이터 크롤링 중...")
        task_start = time.time()
        try:
            self.kind.craw()
            print(f"✅ 완료 ({time.time() - task_start:.1f}초)")
        except Exception as e:
            print(f"⚠️  KIND 크롤링 실패 (무시하고 계속 진행)")
            print(f"    사유: {str(e)[:100]}")
            logger.warning(f"KIND 크롤링 실패: {e}")

        # v2 확장 데이터 수집 — phase 없는 레거시 전체 실행 모드에서만 수행
        # phase=1: 종가 수집 전용 (펀더멘탈은 phase 2에서 처리)
        # phase=2,3: 각자 early return으로 이미 처리됨
        if phase is None:
            try:
                self.collect_market_index()
                self.collect_stock_fundamental()
            except Exception as e:
                logger.warning(f"v2 확장 데이터 수집 실패 (무시하고 계속): {e}")

        # 전체 완료
        total_time = time.time() - overall_start
        print("\n" + "="*100)
        print(f"✅ 모든 데이터 수집 완료! (총 소요 시간: {int(total_time//60)}분 {int(total_time%60)}초)")
        print("="*100)

        logger.info("collecting 완료")

        # cmd 콘솔창 종료 - 주석 처리 (collector_v3.py의 60초 대기를 방해함)
        # os.system("@taskkill /f /im cmd.exe")

        # # AI 알고리즘 적용
        if self.open_api.sf.use_ai:
            path = pathlib.Path(__file__).parent.parent.absolute() / 'bat' / 'ai_filter.bat'
            os.system(f"start {path} {self.open_api.db_name} {self.open_api.simul_num}")

    # ── v2 확장 데이터 수집 메서드 ──────────────────────────────────────────

    def collect_market_index(self):
        """OPT20006 (업종일봉차트조회)으로 코스피/코스닥 지수 일봉 수집
        → daily_craw DB의 kospi_index, kosdaq_index 테이블에 저장
        오늘 데이터가 이미 있으면 스킵.
        """
        today = self.open_api.today
        engine_craw = self.open_api.engine_daily_craw

        for index_code, table_name in [("001", "kospi_index"), ("101", "kosdaq_index")]:
            # 오늘 데이터 이미 있으면 스킵
            try:
                check_sql = f"SELECT 1 FROM `{table_name}` WHERE date = '{today}' LIMIT 1"
                if engine_craw.execute(check_sql).fetchone():
                    logger.debug(f"{table_name} 오늘 데이터 존재, 스킵")
                    continue
            except Exception:
                pass  # 테이블 없으면 계속 진행

            # OPT20006 호출
            self.open_api.ohlcv = defaultdict(list)
            self.open_api.set_input_value("업종코드", index_code)
            self.open_api.set_input_value("기준일자", today)
            self.open_api.set_input_value("수정주가구분", 1)
            self.open_api.comm_rq_data("opt20006_req", "opt20006", 0, "0102")
            time.sleep(cf.TR_REQ_TIME_INTERVAL)

            if not self.open_api.ohlcv or not self.open_api.ohlcv.get('date'):
                continue

            df = DataFrame(
                self.open_api.ohlcv,
                columns=['date', 'open', 'high', 'low', 'close', 'volume']
            )
            df = df[df['date'].str.strip() != '']
            if len(df) == 0:
                continue

            df.to_sql(table_name, engine_craw, if_exists='append', index=False)
            logger.debug(f"{table_name} {len(df)}행 저장 완료")

    def collect_stock_fundamental(self):
        """OPT10001 (주식기본정보요청)으로 전 종목 펀더멘털 수집
        → daily_buy_list DB의 sf_YYYYMMDD 날짜별 테이블에 저장
        cf.v2_fundamental_collect_interval일 미경과 시 스킵.
        """
        import datetime as _dt
        import pandas as pd
        today = self.open_api.today
        table_name = f'sf_{today}'  # e.g. sf_20260406
        engine_buy = self.open_api.engine_daily_buy_list

        # 주기 미경과 + 오늘 완전 수집 완료 시 스킵
        try:
            # 가장 최근 sf_YYYYMMDD 테이블 찾기
            rows = engine_buy.execute(
                "SELECT TABLE_NAME FROM information_schema.tables "
                "WHERE table_schema = 'daily_buy_list' AND TABLE_NAME LIKE 'sf_2%' "
                "ORDER BY TABLE_NAME DESC LIMIT 1"
            ).fetchone()
            if rows:
                last_date = rows[0].replace('sf_', '')  # 'sf_20260406' → '20260406'
                today_dt = _dt.datetime.strptime(today, "%Y%m%d")
                last_dt = _dt.datetime.strptime(last_date, "%Y%m%d")
                days_since = (today_dt - last_dt).days
                if days_since < cf.v2_fundamental_collect_interval:
                    if last_date == today:
                        # 오늘 테이블 있음 — 건수 검증 (체크포인트 부분 저장이면 재수집)
                        today_count = engine_buy.execute(
                            f"SELECT COUNT(*) FROM `{table_name}`"
                        ).scalar()
                        total_count = engine_buy.execute(
                            "SELECT COUNT(*) FROM stock_item_all"
                        ).scalar()
                        if total_count and today_count >= total_count * 0.95:
                            logger.debug(f"펀더멘털 수집 스킵 (오늘 완료: {today_count}/{total_count})")
                            return
                        logger.info(f"펀더멘털 수집 재개 (오늘 저장 {today_count}/{total_count}, 미완료)")
                    else:
                        logger.debug(f"펀더멘털 수집 스킵 (주기 미경과, 마지막: {last_date})")
                        return
        except Exception:
            pass  # 테이블 없으면 진행

        # 전 종목 코드 조회
        stocks = engine_buy.execute(
            "SELECT code_name, code FROM stock_item_all"
        ).fetchall()
        total = len(stocks)

        # 재시작 재개: 오늘 테이블에 이미 수집된 코드 조회 → 건너뜀
        already_done = set()
        try:
            rows = engine_buy.execute(f"SELECT code FROM `{table_name}`").fetchall()
            already_done = {r[0] for r in rows}
        except Exception:
            pass  # 오늘 테이블 없으면 처음부터

        if already_done:
            logger.info(f"펀더멘털 재개 모드: {len(already_done)}/{total} 이미 수집 → 나머지 {total - len(already_done)}개 수집")
            print(f"[펀더멘털] 재개: {len(already_done)}개 완료, 나머지 {total - len(already_done)}개 수집", flush=True)
        else:
            eta_min = total * cf.TR_REQ_TIME_INTERVAL / 60
            logger.info(f"펀더멘털 수집 시작 - {total}개 종목 (약 {eta_min:.0f}분 소요 예상) → {table_name}")
            print(f"[펀더멘털] 수집 시작 - {total}개 종목 (약 {eta_min:.0f}분)", flush=True)

        done_count = len(already_done)
        records = []
        empty_streak = 0  # 연속 빈 응답 카운터 (서버 스로틀 감지용)
        for i, (code_name, code) in enumerate(stocks):
            if code in already_done:
                continue

            collected = done_count + len(records)
            if len(records) > 0 and len(records) % 100 == 0:
                pct = collected / total * 100
                remain_min = (total - collected) * cf.TR_REQ_TIME_INTERVAL / 60
                logger.info(f"펀더멘털 수집 {collected}/{total} ({pct:.0f}%) - 남은시간 약 {remain_min:.0f}분")
                print(f"[펀더멘털] {collected}/{total} ({pct:.0f}%) 완료 — 남은시간 약 {remain_min:.0f}분", flush=True)
                # 100건마다 체크포인트 저장 (append — 기존 데이터 보존)
                df_partial = pd.DataFrame(records)
                df_partial.to_sql(table_name, engine_buy, if_exists='append', index=False)
                done_count += len(records)
                records = []

            fd = {}
            for retry in range(3):  # 최대 3회 시도 (서버 스로틀 대응)
                try:
                    self.open_api.fundamental_data = {}
                    self.open_api.set_input_value("종목코드", code)
                    self.open_api.comm_rq_data("opt10001_req", "opt10001", 0, "0103")
                    time.sleep(cf.TR_REQ_TIME_INTERVAL)
                    fd = self.open_api.fundamental_data
                    if fd:
                        empty_streak = 0
                        break
                    else:
                        empty_streak += 1
                        if empty_streak >= 5:
                            logger.warning(f"[펀더멘털] 빈 응답 {empty_streak}연속 — 5초 대기 후 재시도")
                            print(f"[펀더멘털] 서버 응답 없음 {empty_streak}연속, 5초 대기...", flush=True)
                            time.sleep(5)
                        elif retry < 2:
                            time.sleep(1)
                except Exception as e:
                    logger.debug(f"{code} 펀더멘털 수집 실패 (retry {retry}): {e}")
                    time.sleep(1)

            if fd:
                fd['code'] = code
                fd['code_name'] = code_name
                records.append(fd)

        if records:
            df = pd.DataFrame(records)
            df.to_sql(table_name, engine_buy, if_exists='append', index=False)

        try:
            final_count = engine_buy.execute(f"SELECT COUNT(*) FROM `{table_name}`").scalar()
        except Exception:
            final_count = done_count + len(records)
        logger.info(f"펀더멘털 저장 완료: {table_name} {final_count}개")
        print(f"[펀더멘털] 저장 완료 - {final_count}개 종목 ({table_name})", flush=True)

    # 실전 봇, 모의 봇 매수 종목 세팅 + all_item_db 업데이트 함수
    # 고급 전략 통합 버전 (date_based_strategy 사용)
    def realtime_daily_buy_list_check(self):
        # simul_num=3: HybridStrategyV2 Python 점수 기반 선정
        # (simulator_func_mysql.db_to_realtime_daily_buy_list_num=21 분기에서 처리)
        if self.open_api.simul_num == 3:
            from library.utils import get_latest_complete_date
            self.open_api.sf.get_date_for_simul()
            target_date = get_latest_complete_date(self.open_api.sf.date_rows)
            logger.debug(f"[simul_num=3] 스코어링 기준날짜: {target_date}")
            self.open_api.sf.db_to_realtime_daily_buy_list(
                target_date, target_date, len(self.open_api.sf.date_rows)
            )
            # check_collector_done.py가 확인하는 값 — 오늘 날짜로 업데이트 (스코어링 완료 표시)
            sql = "UPDATE setting_data SET today_buy_list='%s' limit 1"
            self.engine_JB.execute(sql % (self.open_api.today))
            return

        # simul_num=4/5/6: BreakoutStrategyV3 / ReversalStrategyV3 (num=22)
        # simulator_func_mysql.db_to_realtime_daily_buy_list_num=22 분기에서 처리
        if self.open_api.simul_num in (4, 5, 6):
            from library.utils import get_latest_complete_date
            label = {4: 'Strategy A (Breakout)', 5: 'Strategy B (Reversal)', 6: 'Strategy A+B (sim=6)'}
            print(f"\n🚀 [{label.get(self.open_api.simul_num, str(self.open_api.simul_num))}] 스코어링 시작")
            self.open_api.sf.get_date_for_simul()
            target_date = get_latest_complete_date(self.open_api.sf.date_rows)
            logger.debug(f"[simul_num={self.open_api.simul_num}] 스코어링 기준날짜: {target_date}")
            self.open_api.sf.db_to_realtime_daily_buy_list(
                target_date, target_date, len(self.open_api.sf.date_rows)
            )
            sql = "UPDATE setting_data SET today_buy_list='%s' limit 1"
            self.engine_JB.execute(sql % (self.open_api.today))
            print(f"✅ [simul_num={self.open_api.simul_num}] 스코어링 완료")
            return

        # 최근 영업일 테이블 찾기 (simul_num=1,2 기존 전략)
        from library.date_based_strategy import get_latest_date_table

        latest_date = get_latest_date_table('daily_buy_list')

        if latest_date:
            logger.info("realtime_daily_buy_list 생성 시작 (기준: %s)", latest_date)

            try:
                # 고급 전략으로 매수 후보 종목 스캔
                from library.date_based_strategy import generate_buy_signals as date_based_signals
                from library.hybrid_strategy import get_buy_candidates as hybrid_signals
                import pymysql

                print("\n🚀 고급 전략으로 매수 후보 스캔 중...")
                print(f"📅 기준 날짜: {latest_date}")

                # 포트폴리오 가치 및 설정
                portfolio_value = self.open_api.sf.start_invest_price if hasattr(self.open_api.sf, 'start_invest_price') else 10000000
                top_n = 20  # 최대 20개 종목
                min_hybrid_score = 90.0  # 하이브리드 전략 최소 90점

                # 🚀 하이브리드 전략: Momentum 60% + Mean Reversion 40%
                print("  🚀 하이브리드 전략 스캔 (Momentum 60% + Mean Reversion 40%)...")
                buy_signals = self._hybrid_strategy_sql(latest_date, min_hybrid_score, top_n)

                print(f"  🎯 최종 선정: {len(buy_signals)}개 종목 (하이브리드 점수 {min_hybrid_score}점 이상)")

                if buy_signals.empty:
                    print("⚠️  매수 조건을 만족하는 종목이 없습니다.")

                    # 빈 DataFrame을 전략 컬럼 구조와 함께 생성
                    empty_columns = {
                        'code': pd.Series(dtype='str'),
                        'code_name': pd.Series(dtype='str'),
                        'date': pd.Series(dtype='str'),
                        'check_item': pd.Series(dtype='int'),
                        'd1_diff_rate': pd.Series(dtype='float'),
                        'close': pd.Series(dtype='float'),
                        'open': pd.Series(dtype='float'),
                        'high': pd.Series(dtype='float'),
                        'low': pd.Series(dtype='float'),
                        'volume': pd.Series(dtype='float'),
                        'clo5': pd.Series(dtype='float'),
                        'clo10': pd.Series(dtype='float'),
                        'clo20': pd.Series(dtype='float'),
                        'clo40': pd.Series(dtype='float'),
                        'clo60': pd.Series(dtype='float'),
                        'clo80': pd.Series(dtype='float'),
                        'clo100': pd.Series(dtype='float'),
                        'clo120': pd.Series(dtype='float'),
                        'clo5_diff_rate': pd.Series(dtype='float'),
                        'clo10_diff_rate': pd.Series(dtype='float'),
                        'clo20_diff_rate': pd.Series(dtype='float'),
                        'clo40_diff_rate': pd.Series(dtype='float'),
                        'clo60_diff_rate': pd.Series(dtype='float'),
                        'clo80_diff_rate': pd.Series(dtype='float'),
                        'clo100_diff_rate': pd.Series(dtype='float'),
                        'clo120_diff_rate': pd.Series(dtype='float'),
                        'yes_clo5': pd.Series(dtype='float'),
                        'yes_clo10': pd.Series(dtype='float'),
                        'yes_clo20': pd.Series(dtype='float'),
                        'yes_clo40': pd.Series(dtype='float'),
                        'yes_clo60': pd.Series(dtype='float'),
                        'yes_clo80': pd.Series(dtype='float'),
                        'yes_clo100': pd.Series(dtype='float'),
                        'yes_clo120': pd.Series(dtype='float'),
                        'vol5': pd.Series(dtype='float'),
                        'vol10': pd.Series(dtype='float'),
                        'vol20': pd.Series(dtype='float'),
                        'vol40': pd.Series(dtype='float'),
                        'vol60': pd.Series(dtype='float'),
                        'vol80': pd.Series(dtype='float'),
                        'vol100': pd.Series(dtype='float'),
                        'vol120': pd.Series(dtype='float'),
                        'strategy_type': pd.Series(dtype='str'),
                        'composite_score': pd.Series(dtype='float'),
                        'volume_ratio': pd.Series(dtype='float')
                    }
                    df_realtime_daily_buy_list = pd.DataFrame(empty_columns)

                    # 빈 테이블 생성 (컬럼 구조 유지)
                    df_realtime_daily_buy_list.to_sql('realtime_daily_buy_list', self.engine_JB, if_exists='replace', index=False)
                    print("✅ realtime_daily_buy_list 테이블 생성 완료 (0개 종목)")

                else:
                    print(f"✅ 고급 전략으로 {len(buy_signals)}개 종목 선정 완료")

                    # 선정된 종목 코드 리스트
                    selected_codes = buy_signals['code'].tolist()

                    # 날짜 테이블에서 전체 데이터 가져오기
                    con = pymysql.connect(
                        user=self.open_api.cf.db_id,
                        passwd=self.open_api.cf.db_passwd,
                        host=self.open_api.cf.db_ip,
                        db='daily_buy_list',
                        charset='utf8',
                        port=int(self.open_api.cf.db_port)
                    )

                    # IN 절을 위한 코드 리스트 문자열 생성
                    codes_str = "','".join(selected_codes)

                    query = f"""
                    SELECT
                        code, code_name, date, check_item,
                        d1_diff_rate, close, open, high, low, volume,
                        clo5, clo10, clo20, clo40, clo60, clo80, clo100, clo120,
                        clo5_diff_rate, clo10_diff_rate, clo20_diff_rate, clo40_diff_rate,
                        clo60_diff_rate, clo80_diff_rate, clo100_diff_rate, clo120_diff_rate,
                        yes_clo5, yes_clo10, yes_clo20, yes_clo40, yes_clo60, yes_clo80, yes_clo100, yes_clo120,
                        vol5, vol10, vol20, vol40, vol60, vol80, vol100, vol120
                    FROM `{latest_date}`
                    WHERE code IN ('{codes_str}')
                    """

                    df_realtime_daily_buy_list = pd.read_sql(query, con)
                    con.close()

                    # 디버그: 컬럼명 확인
                    logger.debug(f"  읽어온 컬럼: {list(df_realtime_daily_buy_list.columns)}")

                    # 잘못된 인덱스가 컬럼으로 추가되었는지 확인 및 제거
                    unwanted_cols = ['level_0', 'index', 'Unnamed: 0']
                    for col in unwanted_cols:
                        if col in df_realtime_daily_buy_list.columns:
                            logger.debug(f"  🗑️  불필요한 컬럼 제거: {col}")
                            df_realtime_daily_buy_list = df_realtime_daily_buy_list.drop(columns=[col])

                    # check_item 설정
                    df_realtime_daily_buy_list['check_item'] = 0

                    # 종목코드를 6자리 문자열로 변환
                    df_realtime_daily_buy_list['code'] = df_realtime_daily_buy_list['code'].astype(str).str.zfill(6)

                    # 전략 정보 추가 (buy_signals와 조인)
                    strategy_info = buy_signals[['code', 'strategy_type', 'composite_score', 'volume_ratio']].copy()
                    strategy_info['code'] = strategy_info['code'].astype(str).str.zfill(6)

                    # 전략 정보 병합
                    df_realtime_daily_buy_list = df_realtime_daily_buy_list.merge(
                        strategy_info,
                        on='code',
                        how='left'
                    )

                    # 전략 타입이 없는 경우 기본값 설정
                    df_realtime_daily_buy_list['strategy_type'] = df_realtime_daily_buy_list['strategy_type'].fillna('basic')
                    df_realtime_daily_buy_list['composite_score'] = df_realtime_daily_buy_list['composite_score'].fillna(0)
                    df_realtime_daily_buy_list['volume_ratio'] = df_realtime_daily_buy_list['volume_ratio'].fillna(1.0)

                    # 불필요한 인덱스 컬럼 제거 (index, index2, index3, level_0 등)
                    drop_columns = [col for col in df_realtime_daily_buy_list.columns
                                   if col.startswith('index') or col.startswith('level_') or col == 'Unnamed: 0']
                    if drop_columns:
                        print(f"  🗑️  불필요한 컬럼 제거: {drop_columns}")
                        df_realtime_daily_buy_list = df_realtime_daily_buy_list.drop(columns=drop_columns)

                    # 인덱스 리셋 (중요: merge 후 인덱스가 컬럼으로 변환될 수 있음)
                    df_realtime_daily_buy_list = df_realtime_daily_buy_list.reset_index(drop=True)

                    # realtime_daily_buy_list 테이블에 저장
                    df_realtime_daily_buy_list.to_sql('realtime_daily_buy_list', self.engine_JB, if_exists='replace', index=False)

                    # 현재 보유 중인 종목은 매수 리스트에서 제거
                    sql = "DELETE FROM realtime_daily_buy_list WHERE code IN (SELECT code FROM possessed_item)"
                    self.engine_JB.execute(sql)

                    print(f"✅ realtime_daily_buy_list 테이블 생성 완료 ({len(df_realtime_daily_buy_list)}개 종목)")

                    # 선정된 종목 간략 출력
                    for idx, row in buy_signals.head(5).iterrows():
                        print(f"  [{idx+1}] {row['code']} {row['code_name']}: {row['composite_score']:.1f}점 ({row['strategy_type']})")
                    if len(buy_signals) > 5:
                        print(f"  ... 외 {len(buy_signals) - 5}개 종목")

            except Exception as e:
                logger.error(f"고급 전략 실행 오류: {e}")
                import traceback
                traceback.print_exc()
                print("\n⚠️  고급 전략 실행 실패. 기본 전략으로 폴백합니다.")
                # 기본 전략 실행
                from library.utils import get_latest_complete_date
                self.open_api.sf.get_date_for_simul()
                _fallback_date = get_latest_complete_date(self.open_api.sf.date_rows)
                self.open_api.sf.db_to_realtime_daily_buy_list(_fallback_date, _fallback_date, len(self.open_api.sf.date_rows))

            # all_item_db에서 open, clo5~120, volume 등을 최근 영업일 데이터로 업데이트 한다.
            self.open_api.sf.update_all_db_by_date(latest_date)
            self.open_api.rate_check()
            # realtime_daily_buy_list(매수 리스트) 테이블 세팅을 완료 했으면 아래 쿼리를 통해 setting_data의 today_buy_list에 오늘 날짜를 찍는다.
            sql = "UPDATE setting_data SET today_buy_list='%s' limit 1"
            self.engine_JB.execute(sql % (self.open_api.today))
        else:
            logger.warning("realtime_daily_buy_list 생성 불가: daily_buy_list에 %s 테이블 없음", self.open_api.today)

    def _hybrid_strategy_sql(self, latest_date: str, min_score: float, top_n: int) -> pd.DataFrame:
        """
        하이브리드 전략 SQL 구현 (모멘텀 60% + 평균회귀 40%)

        Parameters:
        -----------
        latest_date : str
            스캔할 날짜 테이블명
        min_score : float
            최소 스코어
        top_n : int
            선정할 종목 수

        Returns:
        --------
        pd.DataFrame : 하이브리드 전략 매수 후보
        """
        try:
            # 필터링 테이블 존재 여부 체크
            con = pymysql.connect(
                user=cf.db_id,
                passwd=cf.db_passwd,
                host=cf.db_ip,
                db='daily_buy_list',
                charset='utf8',
                port=int(cf.db_port)
            )
            cursor = con.cursor()
            cursor.execute("""
                SELECT TABLE_NAME
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = 'daily_buy_list'
                AND TABLE_NAME IN ('stock_konex', 'stock_invest_warning', 'stock_invest_danger')
            """)
            existing_tables = {row[0] for row in cursor.fetchall()}

            # 코넥스 제외 쿼리
            konex_exclusion = ""
            if 'stock_konex' in existing_tables:
                konex_exclusion = "AND code NOT IN (SELECT code FROM stock_konex WHERE 1=1)"

            # 투자위험 종목 필터 제거 (더 많은 후보 허용)
            # 날짜 기반 전략과 동일하게 investment warning/danger 필터 비활성화
            warning_exclusion = ""

            # 하이브리드 전략 SQL 쿼리
            query = f"""
            SELECT
                code,
                code_name,
                close,
                d1_diff_rate,
                volume,
                vol5,
                vol20,
                clo5,
                clo10,
                clo20,
                clo40,
                clo60,
                rsi14,
                bb_upper,
                bb_middle,
                bb_lower,
                atr14,

                -- 하이브리드 스코어 (모멘텀 60점 + 평균회귀 40점 = 100점 만점)
                (
                    -- === 모멘텀 (60점 만점) ===
                    -- 거래량 조건 (20점)
                    CASE
                        WHEN volume > vol20 * 2.0 THEN 20
                        WHEN volume > vol20 * 1.5 THEN 15
                        WHEN volume > vol20 * 1.2 THEN 10
                        ELSE 5
                    END +
                    -- 모멘텀 조건 (20점)
                    CASE
                        WHEN clo5 > clo20 AND clo20 > clo60 THEN 20
                        WHEN clo5 > clo20 THEN 15
                        ELSE 5
                    END +
                    -- ATR 기반 변동성 돌파 (20점)
                    CASE
                        WHEN atr14 > 0 AND (high - low) > atr14 * 1.5 THEN 20
                        WHEN atr14 > 0 AND (high - low) > atr14 THEN 15
                        ELSE 10
                    END +

                    -- === 평균회귀 (40점 만점) ===
                    -- RSI 과매도 (15점)
                    CASE
                        WHEN rsi14 <= 30 THEN 15
                        WHEN rsi14 <= 40 THEN 10
                        WHEN rsi14 <= 50 THEN 5
                        ELSE 0
                    END +
                    -- 볼린저 밴드 하단 근처 (15점)
                    CASE
                        WHEN bb_lower > 0 AND close <= bb_lower THEN 15
                        WHEN bb_lower > 0 AND close <= bb_lower * 1.02 THEN 10
                        WHEN bb_middle > 0 AND close < bb_middle THEN 5
                        ELSE 0
                    END +
                    -- 지지선 반등 (10점)
                    CASE
                        WHEN close > clo20 * 0.95 AND close < clo20 * 1.0 THEN 10
                        WHEN close > clo60 * 0.95 AND close < clo60 * 1.0 THEN 8
                        ELSE 3
                    END
                ) as score,

                'hybrid' as strategy_type

            FROM `{latest_date}`
            WHERE 1=1
                -- 기본 필터
                AND close > 0
                AND volume > 0
                AND rsi14 > 0  -- RSI 계산 성공한 종목만
                AND bb_lower > 0  -- 볼린저 밴드 계산 성공한 종목만

                {konex_exclusion}

                {warning_exclusion}

                -- 하이브리드 조건 (모멘텀 OR 평균회귀)
                AND (
                    -- 모멘텀 조건
                    (clo5 > clo20 AND volume > vol20 * 1.2)
                    OR
                    -- 평균회귀 조건
                    (rsi14 <= 40 AND bb_lower > 0 AND close <= bb_lower * 1.05)
                )

                -- 가격 범위
                AND close BETWEEN 1000 AND 500000

            HAVING score >= {min_score}
            ORDER BY score DESC
            LIMIT {top_n}
            """

            df = pd.read_sql(query, con)
            con.close()

            if df.empty:
                return pd.DataFrame()

            # 추가 계산 (volume_ratio 등)
            df['volume_ratio'] = df['volume'] / df['vol20']
            df['composite_score'] = df['score']  # 호환성을 위해

            return df

        except Exception as e:
            print(f"하이브리드 전략 SQL 실행 오류: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()

    def _combined_strategy_sql(self, latest_date: str, min_combined_score: float, top_n: int) -> pd.DataFrame:
        """
        혼합 전략 SQL 구현 (날짜 기반 20% + 하이브리드 80%)

        두 전략을 가중 합산한 점수가 min_combined_score 이상인 종목만 선택

        Parameters:
        -----------
        latest_date : str
            스캔할 날짜 테이블명
        min_combined_score : float
            최소 합산 스코어 (기본 90점)
        top_n : int
            선정할 종목 수

        Returns:
        --------
        pd.DataFrame : 혼합 전략 매수 후보
        """
        try:
            # 필터링 테이블 존재 여부 체크
            con = pymysql.connect(
                user=cf.db_id,
                passwd=cf.db_passwd,
                host=cf.db_ip,
                db='daily_buy_list',
                charset='utf8',
                port=int(cf.db_port)
            )
            cursor = con.cursor()
            cursor.execute("""
                SELECT TABLE_NAME
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = 'daily_buy_list'
                AND TABLE_NAME IN ('stock_konex', 'stock_invest_warning', 'stock_invest_danger')
            """)
            existing_tables = {row[0] for row in cursor.fetchall()}

            # 코넥스 제외 쿼리
            konex_exclusion = ""
            if 'stock_konex' in existing_tables:
                konex_exclusion = "AND code NOT IN (SELECT code FROM stock_konex WHERE 1=1)"

            # 혼합 전략 SQL 쿼리
            query = f"""
            SELECT
                code,
                code_name,
                close,
                d1_diff_rate,
                volume,
                vol5,
                vol20,
                clo5,
                clo10,
                clo20,
                clo40,
                clo60,
                rsi14,
                bb_upper,
                bb_middle,
                bb_lower,
                atr14,
                date_score,
                hybrid_score,
                combined_score as score,
                'hybrid_combined' as strategy_type

            FROM (
                SELECT
                    *,
                    -- 날짜 기반 스코어 (100점 스케일)
                    (
                        (volume / NULLIF(vol5, 0)) *
                        (clo5 / NULLIF(clo20, 0)) *
                        CASE
                            WHEN volume > vol20 * 1.5 THEN 1.2
                            ELSE 1.0
                        END
                    ) * 30.0 AS date_score,

                    -- 하이브리드 스코어 (모멘텀 60점 + 평균회귀 40점 = 100점 만점)
                    (
                        -- 모멘텀 (60점 만점)
                        CASE
                            WHEN volume > vol20 * 2.0 THEN 20
                            WHEN volume > vol20 * 1.5 THEN 15
                            WHEN volume > vol20 * 1.2 THEN 10
                            ELSE 5
                        END +
                        CASE
                            WHEN clo5 > clo20 AND clo20 > clo60 THEN 20
                            WHEN clo5 > clo20 THEN 15
                            ELSE 5
                        END +
                        CASE
                            WHEN atr14 > 0 AND (high - low) > atr14 * 1.5 THEN 20
                            WHEN atr14 > 0 AND (high - low) > atr14 THEN 15
                            ELSE 10
                        END +
                        -- 평균회귀 (40점 만점)
                        CASE
                            WHEN rsi14 <= 30 THEN 15
                            WHEN rsi14 <= 40 THEN 10
                            WHEN rsi14 <= 50 THEN 5
                            ELSE 0
                        END +
                        CASE
                            WHEN bb_lower > 0 AND close <= bb_lower THEN 15
                            WHEN bb_lower > 0 AND close <= bb_lower * 1.02 THEN 10
                            WHEN bb_middle > 0 AND close < bb_middle THEN 5
                            ELSE 0
                        END +
                        CASE
                            WHEN close > clo20 * 0.95 AND close < clo20 * 1.0 THEN 10
                            WHEN close > clo60 * 0.95 AND close < clo60 * 1.0 THEN 8
                            ELSE 3
                        END
                    ) AS hybrid_score,

                    -- 최종 혼합 스코어 (날짜 20% + 하이브리드 80% 가중 합산)
                    (
                        -- 날짜 기반 (20%)
                        (
                            (volume / NULLIF(vol5, 0)) *
                            (clo5 / NULLIF(clo20, 0)) *
                            CASE
                                WHEN volume > vol20 * 1.5 THEN 1.2
                                ELSE 1.0
                            END
                        ) * 30.0 * 0.2
                        +
                        -- 하이브리드 (80%)
                        (
                            CASE
                                WHEN volume > vol20 * 2.0 THEN 20
                                WHEN volume > vol20 * 1.5 THEN 15
                                WHEN volume > vol20 * 1.2 THEN 10
                                ELSE 5
                            END +
                            CASE
                                WHEN clo5 > clo20 AND clo20 > clo60 THEN 20
                                WHEN clo5 > clo20 THEN 15
                                ELSE 5
                            END +
                            CASE
                                WHEN atr14 > 0 AND (high - low) > atr14 * 1.5 THEN 20
                                WHEN atr14 > 0 AND (high - low) > atr14 THEN 15
                                ELSE 10
                            END +
                            CASE
                                WHEN rsi14 <= 30 THEN 15
                                WHEN rsi14 <= 40 THEN 10
                                WHEN rsi14 <= 50 THEN 5
                                ELSE 0
                            END +
                            CASE
                                WHEN bb_lower > 0 AND close <= bb_lower THEN 15
                                WHEN bb_lower > 0 AND close <= bb_lower * 1.02 THEN 10
                                WHEN bb_middle > 0 AND close < bb_middle THEN 5
                                ELSE 0
                            END +
                            CASE
                                WHEN close > clo20 * 0.95 AND close < clo20 * 1.0 THEN 10
                                WHEN close > clo60 * 0.95 AND close < clo60 * 1.0 THEN 8
                                ELSE 3
                            END
                        ) * 0.8
                    ) AS combined_score

                FROM `{latest_date}`
                WHERE 1=1
                    -- 기본 필터
                    AND close > 0
                    AND volume > 0

                    {konex_exclusion}

                    -- 날짜 기반 OR 하이브리드 조건
                    AND (
                        -- 날짜 기반 조건
                        (volume > vol5 * 1.2 AND clo5 > clo20)
                        OR
                        -- 하이브리드 조건
                        (
                            rsi14 > 0 AND bb_lower > 0 AND
                            (
                                (clo5 > clo20 AND volume > vol20 * 1.2)
                                OR
                                (rsi14 <= 40 AND close <= bb_lower * 1.05)
                            )
                        )
                    )

                    -- 가격 범위
                    AND close BETWEEN 1000 AND 500000
            ) AS scored_table
            WHERE combined_score >= {min_combined_score}
            ORDER BY combined_score DESC
            LIMIT {top_n}
            """

            df = pd.read_sql(query, con)
            con.close()

            if df.empty:
                return pd.DataFrame()

            # 추가 계산 (volume_ratio 등)
            df['volume_ratio'] = df['volume'] / df['vol20']
            df['composite_score'] = df['score']  # 호환성을 위해
            df['weighted_score'] = df['score']  # 가중 점수도 동일

            return df

        except Exception as e:
            print(f"혼합 전략 SQL 실행 오류: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()

    def is_table_exist_daily_buy_list(self, date):
        sql = "select 1 from information_schema.tables where table_schema ='daily_buy_list' and table_name = '%s'"
        rows = self.open_api.engine_daily_buy_list.execute(sql % (date)).fetchall()

        if len(rows) == 1:
            return True
        elif len(rows) == 0:
            return False

    def is_table_exist(self, db_name, table_name):
        sql = "select 1 from information_schema.tables where table_schema ='{}' and table_name = '{}'"
        rows = self.open_api.engine_craw.execute(sql.format(db_name, table_name)).fetchall()
        if len(rows) == 1:
            # logger.debug("is_table_exist True!!")
            return True
        elif len(rows) == 0:
            # logger.debug("is_table_exist False!!")
            return False

    def daily_buy_list_check(self):
        # dbl 에서 가져온다
        self.dbl.daily_buy_list()
        logger.debug("daily_buy_list success !!!")

        # 타임스탬프 저장 (yyyyMMddHHmm)
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M")
        sql = "UPDATE setting_data SET daily_buy_list='%s' limit 1"
        self.engine_JB.execute(sql % timestamp)
        logger.debug(f"daily_buy_list 완료 시간 저장: {timestamp}")

    # min_craw데이터베이스를 구축
    def db_to_min_craw(self):
        logger.debug("db_to_min_craw!!!!!!")
        sql = "select code,code_name, check_min_crawler from stock_item_all"
        target_code = self.open_api.engine_daily_buy_list.execute(sql).fetchall()
        num = len(target_code)

        # 수집 대상 종목 수 계산
        targets_to_collect = sum(1 for code in target_code if int(code[2]) == 0)

        print(f"    총 {num}개 종목 중 {targets_to_collect}개 종목 수집 예정")

        sql = "UPDATE stock_item_all SET check_min_crawler='%s' WHERE code='%s'"

        collected = 0
        start_time = time.time()

        for i in range(num):
            # check_item 확인
            if int(target_code[i][2]) != 0:
                continue

            code = target_code[i][0]
            code_name = target_code[i][1]

            collected += 1
            logger.debug("++++++++++++++" + str(code_name) + "++++++++++++++++++++" + str(collected) + '/' + str(targets_to_collect))

            # 진행률 표시 (10개마다 또는 마지막)
            if collected % 10 == 0 or collected == targets_to_collect:
                self.print_progress(collected, targets_to_collect, "    분봉 수집", start_time)

            check_item_gubun = self.set_min_crawler_table(code, code_name)

            self.open_api.engine_daily_buy_list.execute(sql % (check_item_gubun, code))

    def db_to_daily_craw(self):
        logger.debug("db_to_daily_craw 함수에 들어왔습니다!")
        sql = "select code,code_name, check_daily_crawler from stock_item_all"

        # 데이타 Fetch
        # rows 는 list안에 튜플이 있는 [()] 형태로 받아온다

        target_code = self.open_api.engine_daily_buy_list.execute(sql).fetchall()
        num = len(target_code)

        # 수집 대상 종목 수 계산
        targets_to_collect = sum(1 for code in target_code if int(code[2]) not in (1, 3))

        print(f"    총 {num}개 종목 중 {targets_to_collect}개 종목 수집 예정")

        sql = "UPDATE stock_item_all SET check_daily_crawler='%s' WHERE code='%s'"

        collected = 0
        start_time = time.time()

        for i in range(num):
            # check_daily_crawler 확인 후 1, 3이 아닌 경우만 업데이트
            # (1: 금일 콜렉팅 완료, 3:과거에 이미 콜렉팅 완료, 0: 콜렉팅 전, 4: 액면분할, 증자 등으로 인한 업데이트 필요)
            if int(target_code[i][2]) in (1, 3):
                continue

            code = target_code[i][0]
            code_name = target_code[i][1]

            collected += 1
            logger.debug("++++++++++++++" + str(code_name) + "++++++++++++++++++++" + str(collected) + '/' + str(targets_to_collect))

            # 진행률 표시 (매 종목마다 업데이트)
            self.print_progress(collected, targets_to_collect, "    일봉 수집", start_time,
                              stock_name=code_name, stock_code=code)

            check_item_gubun = self.set_daily_crawler_table(code, code_name)

            self.open_api.engine_daily_buy_list.execute(sql % (check_item_gubun, code))

    def min_crawler_check(self):
        self.db_to_min_craw()
        logger.debug("min_crawler success !!!")

        sql = "UPDATE setting_data SET min_crawler='%s' limit 1"
        self.engine_JB.execute(sql % (self.open_api.today))

    def daily_crawler_check(self):
        # 종가 업데이트를 위해 check_daily_crawler를 0으로 리셋
        # 장후(16시 이후): '3'(과거 완료) 포함 리셋 — 장전 수집 시 '3'으로 저장된 종목도 오늘 종가 없으므로 재수집 필요
        # 장전/장중: '1'(오늘 완료)만 리셋
        import datetime as _dt
        _is_post_market = _dt.datetime.now().hour >= 16
        if _is_post_market:
            sql_reset = "UPDATE stock_item_all SET check_daily_crawler = '0' WHERE check_daily_crawler IN ('1','3')"
            logger.debug("daily_crawler_check 시작 - check_daily_crawler 리셋 (1,3→0) [장후 종가 재수집]")
        else:
            sql_reset = "UPDATE stock_item_all SET check_daily_crawler = '0' WHERE check_daily_crawler = '1'"
            logger.debug("daily_crawler_check 시작 - check_daily_crawler 리셋 (1→0)")
        self.open_api.engine_daily_buy_list.execute(sql_reset)

        self.db_to_daily_craw()
        logger.debug("daily_crawler success !!!")

        # 타임스탬프 저장 (yyyyMMddHHmm)
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M")
        sql = "UPDATE setting_data SET daily_crawler='%s' limit 1"
        self.engine_JB.execute(sql % timestamp)
        logger.debug(f"daily_crawler 완료 시간 저장: {timestamp}")

    def _stock_to_sql(self, origin_df, type):
        checking_stocks = ['kosdaq', 'kospi', 'konex', 'etf']
        stock_df = DataFrame()
        stock_df['code'] = origin_df['code']
        name_list = []
        for KIND_info in origin_df.itertuples():
            kiwoom_name = self.open_api.dynamicCall("GetMasterCodeName(QString)", KIND_info.code).strip()
            # Kiwoom COM API bug: returns CP949 bytes "widened" to Latin-1 code points
            # e.g. '케이뱅크' CP949 bytes → returned as 'ÄÉÀÌ¹ðÅ©'
            # Fix: encode back to bytes as Latin-1, then decode as CP949
            try:
                kiwoom_name = kiwoom_name.encode('latin-1').decode('cp949')
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass  # Already correct Unicode (shouldn't happen, but safe fallback)
            name_list.append(kiwoom_name)
            if not kiwoom_name:
                if type in checking_stocks:
                    logger.error(
                        f"종목명이 비어있습니다. - "
                        f"종목: {KIND_info.code_name}, "
                        f"코드: {KIND_info.code}"
                    )

        stock_df['code_name'] = name_list
        stock_df['check_item'] = 0
        if type in checking_stocks:
            stock_df = stock_df[stock_df['code_name'].map(len) > 0]

        if type == 'item_all':
            stock_df['check_daily_crawler'] = "0"
            stock_df['check_min_crawler'] = "0"

        dtypes = dict(zip(list(stock_df.columns), [Text] * len(stock_df.columns)))  # 모든 타입을 Text로
        dtypes['check_item'] = Integer  # check_item만 int로 변경

        if len(stock_df) > 0:
            stock_df.to_sql(f'stock_{type}', self.open_api.engine_daily_buy_list, if_exists='replace', dtype=dtypes)
        else:  # insincerity와 managing이 비어있는 경우
            stock_df.to_sql(f'stock_{type}', self.open_api.engine_daily_buy_list, if_exists='replace', dtype=dtypes, index=False)
        return stock_df

    # 종목코드에 숫자가 아닌 타입이 포함되어 있는 경우 해당되는 종목 제거
    def remove_code_included_char(self, df):
        return df.drop(list(df.loc[~df['code'].astype(str).str.isdigit(), 'code'].index))

    def get_item_kospi(self):
        kospi_api = self._get_code_list_by_market(0)
        while '' in kospi_api:  # 비어있는값 제거
            kospi_api.remove('')
        kospi_api_dic = defaultdict(list)
        for code in kospi_api:
            kospi_api_dic['code'].append(code)
            kospi_api_dic['code_name'].append(self.open_api.dynamicCall("GetMasterCodeName(QString)", code))
        kospi_api_df = DataFrame(kospi_api_dic)
        # ETF와 ETN 들어간 종목 제거
        etf_api = self._get_code_list_by_market(8)
        while '' in etf_api:  # 비어있는값 제거
            etf_api.remove('')
        etf_api_dic = defaultdict(list)
        for code in etf_api:
            etf_api_dic['code'].append(code)
            etf_api_dic['code_name'].append(self.open_api.dynamicCall("GetMasterCodeName(QString)", code))
        etf_api_df = DataFrame(etf_api_dic)
        temp = kospi_api_df[(kospi_api_df['code'].isin(etf_api_df.code) == False)]
        self.kospi_api_df = self.remove_code_included_char(temp[temp['code_name'].str.contains('ETN') == False])

    def get_item_kosdaq(self):
        kosdaq_api = self._get_code_list_by_market(10)
        while '' in kosdaq_api:  # 비어있는값 제거
            kosdaq_api.remove('')
        kosdaq_api_dic = defaultdict(list)
        for code in kosdaq_api:
            kosdaq_api_dic['code'].append(code)
            kosdaq_api_dic['code_name'].append(self.open_api.dynamicCall("GetMasterCodeName(QString)", code))
        self.kosdaq_api_df = self.remove_code_included_char(DataFrame(kosdaq_api_dic))

    def get_item_konex(self):
        konex_api = self._get_code_list_by_market(50)
        while '' in konex_api:  # 비어있는값 제거
            konex_api.remove('')
        konex_api_dic = defaultdict(list)
        for code in konex_api:
            konex_api_dic['code'].append(code)
            konex_api_dic['code_name'].append(self.open_api.dynamicCall("GetMasterCodeName(QString)", code))
        self.konex_api_df = self.remove_code_included_char(DataFrame(konex_api_dic))

    def get_item(self):
        dfs = [self.kospi_api_df, self.kosdaq_api_df, self.konex_api_df]
        cols = list(self.kospi_api_df.keys())
        self.code_df = pd.concat([d.set_index(cols) for d in dfs], axis=1).reset_index()

    def get_item_managing(self):
        # 데이터는 없지만 테이블 생성을 위해 빈 데이터프레임 저장
        self.code_df_managing = pd.DataFrame(columns={'code', 'code_name'})

    def get_item_insincerity(self):
        # 데이터는 없지만 테이블 생성을 위해 빈 데이터프레임 저장
        self.code_df_insincerity = pd.DataFrame(columns={'code', 'code_name'})

    def get_code_list(self):
        # 아래 부분은 영상 촬영 후 좀 더 효율적으로 업그레이드 되었으므로 강의 영상속의 코드와 다를 수 있습니다.

        # ### KIND 사이트에서 종목 데이터 가져오는 버전 ###
        # <KIND version start------------------------------------------------------------------------------------------>
        self.dc.cc.get_item()
        self.dc.cc.get_item_kospi()
        self.dc.cc.get_item_kosdaq()
        self.dc.cc.get_item_konex()
        self.dc.cc.get_item_managing()
        self.dc.cc.get_item_insincerity()

        # OrderedDict를 사용해 순서 보장
        stock_data = OrderedDict(
            kospi=self.dc.cc.code_df_kospi,
            kosdaq=self.dc.cc.code_df_kosdaq,
            konex=self.dc.cc.code_df_konex,
            insincerity=self.dc.cc.code_df_insincerity,
            managing=self.dc.cc.code_df_managing
        )
        # <KIND version end------------------------------------------------------------------------------------------>





        # ### 키움증권에서 종목 데이터 가져오는 버전 ###
        # 키움 api로부터 kospi, kosdaq, konex 데이터를 가져온다 (우선주 포함)
        # 아래 버전은 위와 같이 kind 사이트에서 종목 데이터를 크롤링 하는 방식을 키움증권 OpenAPI로부터 가져오도록 변환된 방식입니다.
        # (지속적인 kind 사이트 크롤링 시 IP차단 문제 예방 차원 + 우선주 종목 또한 콜렉팅 하기 위함)
        # 이에 따라 daily_buy_list DB의 stock_managing(관리종목), stock_insincerity(불성실공시법인종목) 테이블은 비어 있게 되며
        # 고급챕터에서 관리, 위험, 주의 종목 등을 필터링 하는 방법을 다룹니다.
        # 방법 : 위 <KIND version start---> ~ <KIND version end---> 사이 주석 처리 후 아래 <OPEN_API version start--> ~ <OPEN_API version end--> 사이 주석 해제
        # <OPEN_API version start------------------------------------------------------------------------------------------>
        # self.get_item_kospi()
        # self.get_item_kosdaq()
        # self.get_item_konex()
        # self.get_item()
        # self.get_item_managing()
        # self.get_item_insincerity()
        # logger.debug("get_code_list")
        #
        # # OrderedDict를 사용해 순서 보장
        # stock_data = OrderedDict(
        #     kospi=self.kospi_api_df,
        #     kosdaq=self.kosdaq_api_df,
        #     konex=self.konex_api_df,
        #     insincerity=self.code_df_insincerity,
        #     managing=self.code_df_managing
        # )
        # <OPEN_API version end------------------------------------------------------------------------------------------>

        if cf.use_etf:
            stock_data['etf'] = self.remove_code_included_char(DataFrame([(c, '') for c in self._get_code_list_by_market(8) if c],
                                                                         columns=['code', 'code_name']))

        for _type, data in stock_data.items():
            stock_data[_type] = self._stock_to_sql(data, _type)

        # stock_insincerity와 stock_managing의 종목은 따로 중복하여 넣지 않음
        excluded_tables = ['insincerity', 'managing']
        stock_item_all_df = pd.concat(
            [v[v['code_name'].map(len) > 0] for k, v in stock_data.items() if k not in excluded_tables],
            ignore_index=True
        ).drop_duplicates(subset=['code', 'code_name'])
        self._stock_to_sql(stock_item_all_df, "item_all")

        sql = "UPDATE setting_data SET code_update='%s' limit 1"
        self.engine_JB.execute(sql % (self.open_api.today))

    def _get_code_list_by_market(self, market_num):
        codes = self.open_api.dynamicCall(f'GetCodeListByMarket("{market_num}")')
        return codes.split(';')

    # 틱(1분 별) 데이터를 가져오는 함수
    def set_min_crawler_table(self, code, code_name):
        is_new = True
        df = self.open_api.get_total_data_min(code, code_name, self.open_api.today)
        if len(df) == 0:
            return 1
        df_temp = DataFrame(df,
                            columns=['date', 'check_item', 'code', 'code_name', 'd1_diff_rate', 'close', 'open', 'high',
                                     'low',
                                     'volume', 'sum_volume', 'clo5', 'clo10', 'clo20', 'clo40', 'clo60', 'clo80',
                                     'clo100', 'clo120', "clo5_diff_rate", "clo10_diff_rate",
                                     "clo20_diff_rate", "clo40_diff_rate", "clo60_diff_rate",
                                     "clo80_diff_rate", "clo100_diff_rate", "clo120_diff_rate",
                                     'yes_clo5', 'yes_clo10', 'yes_clo20', 'yes_clo40', 'yes_clo60', 'yes_clo80',
                                     'yes_clo100', 'yes_clo120',
                                     'vol5', 'vol10', 'vol20', 'vol40', 'vol60', 'vol80',
                                     'vol100', 'vol120'
                                     ])

        df_temp = df_temp.sort_values(by=['date'], ascending=True)

        df_temp['code'] = code
        # # 뒤에 0없애기 (초)
        df_temp['code_name'] = code_name
        d1_diff_rate = round((df_temp['close'] - df_temp['close'].shift(1)) / df_temp['close'].shift(1) * 100, 2)
        df_temp['d1_diff_rate'] = d1_diff_rate.replace(numpy.inf, numpy.nan)

        # 하나씩 추가할때는 append 아니면 replace
        clo5 = df_temp['close'].rolling(window=5).mean()
        clo10 = df_temp['close'].rolling(window=10).mean()
        clo20 = df_temp['close'].rolling(window=20).mean()
        clo40 = df_temp['close'].rolling(window=40).mean()
        clo60 = df_temp['close'].rolling(window=60).mean()
        clo80 = df_temp['close'].rolling(window=80).mean()
        clo100 = df_temp['close'].rolling(window=100).mean()
        clo120 = df_temp['close'].rolling(window=120).mean()
        df_temp['clo5'] = round(clo5, 2)
        df_temp['clo10'] = round(clo10, 2)
        df_temp['clo20'] = round(clo20, 2)
        df_temp['clo40'] = round(clo40, 2)
        df_temp['clo60'] = round(clo60, 2)
        df_temp['clo80'] = round(clo80, 2)
        df_temp['clo100'] = round(clo100, 2)
        df_temp['clo120'] = round(clo120, 2)

        df_temp['clo5_diff_rate'] = round((df_temp['close'] - clo5) / clo5 * 100, 2)
        df_temp['clo10_diff_rate'] = round((df_temp['close'] - clo10) / clo10 * 100, 2)
        df_temp['clo20_diff_rate'] = round((df_temp['close'] - clo20) / clo20 * 100, 2)
        df_temp['clo40_diff_rate'] = round((df_temp['close'] - clo40) / clo40 * 100, 2)
        df_temp['clo60_diff_rate'] = round((df_temp['close'] - clo60) / clo60 * 100, 2)
        df_temp['clo80_diff_rate'] = round((df_temp['close'] - clo80) / clo80 * 100, 2)
        df_temp['clo100_diff_rate'] = round((df_temp['close'] - clo100) / clo100 * 100, 2)
        df_temp['clo120_diff_rate'] = round((df_temp['close'] - clo120) / clo120 * 100, 2)

        df_temp['yes_clo5'] = df_temp['clo5'].shift(1)
        df_temp['yes_clo10'] = df_temp['clo10'].shift(1)
        df_temp['yes_clo20'] = df_temp['clo20'].shift(1)
        df_temp['yes_clo40'] = df_temp['clo40'].shift(1)
        df_temp['yes_clo60'] = df_temp['clo60'].shift(1)
        df_temp['yes_clo80'] = df_temp['clo80'].shift(1)
        df_temp['yes_clo100'] = df_temp['clo100'].shift(1)
        df_temp['yes_clo120'] = df_temp['clo120'].shift(1)

        df_temp['vol5'] = df_temp['volume'].rolling(window=5).mean()
        df_temp['vol10'] = df_temp['volume'].rolling(window=10).mean()
        df_temp['vol20'] = df_temp['volume'].rolling(window=20).mean()
        df_temp['vol40'] = df_temp['volume'].rolling(window=40).mean()
        df_temp['vol60'] = df_temp['volume'].rolling(window=60).mean()
        df_temp['vol80'] = df_temp['volume'].rolling(window=80).mean()
        df_temp['vol100'] = df_temp['volume'].rolling(window=100).mean()
        df_temp['vol120'] = df_temp['volume'].rolling(window=120).mean()

        if self.open_api.craw_table_exist:
            df_temp = df_temp[df_temp.date > self.open_api.craw_db_last_min]
            is_new = False

        if len(df_temp) == 0:
            logger.debug("이미 min_craw db의 " + code_name + " 테이블에 콜렉팅 완료 했다! df_temp가 비었다!!")

            # 이렇게 안해주면 아래 프로세스들을 안하고 바로 넘어가기때문에 그만큼 tr 조회 하는 시간이 짧아지고 1초에 5회 이상의 조회를 할 수 가있다 따라서 비었을 경우는 sleep해줘야 안멈춘다
            time.sleep(0.03)
            check_item_gubun = 3
            return check_item_gubun

        df_temp[['close', 'open', 'high', 'low', 'volume', 'sum_volume', 'clo5', 'clo10', 'clo20', 'clo40', 'clo60',
                 'clo80', 'clo100', 'clo120',
                 'yes_clo5', 'yes_clo10', 'yes_clo20', 'yes_clo40', 'yes_clo60', 'yes_clo80', 'yes_clo100',
                 'yes_clo120',
                 'vol5', 'vol10', 'vol20', 'vol40', 'vol60', 'vol80', 'vol100', 'vol120']] = \
            df_temp[
                ['close', 'open', 'high', 'low', 'volume', 'sum_volume', 'clo5', 'clo10', 'clo20', 'clo40', 'clo60',
                 'clo80', 'clo100', 'clo120',
                 'yes_clo5', 'yes_clo10', 'yes_clo20', 'yes_clo40', 'yes_clo60', 'yes_clo80', 'yes_clo100',
                 'yes_clo120',
                 'vol5', 'vol10', 'vol20', 'vol40', 'vol60', 'vol80', 'vol100', 'vol120']].fillna(0).astype(int)
        temp_date = self.open_api.craw_db_last_min

        sum_volume = self.open_api.craw_db_last_min_sum_volume
        for i in range(0, len(df_temp)):
            try:
                # index가 역순이라 거꾸로 되어있어서 아래처럼
                temp_index = len(df_temp) - i - 1

                if ((int(df_temp.loc[temp_index, 'date']) - int(temp_date)) > 9000):
                    sum_volume = 0

                temp_date = df_temp.loc[temp_index, 'date']

                sum_volume += df_temp.loc[temp_index, 'volume']

                df_temp.loc[temp_index, 'sum_volume'] = sum_volume
            except Exception as e:
                logger.critical(e)

        df_temp.to_sql(name=code_name, con=self.open_api.engine_craw, if_exists='append', index=False)
        if is_new:
            index_name = ''.join(c for c in code_name if c.isalnum())
            try:
                self.open_api.engine_craw.execute(f"""
                    CREATE INDEX ix_{index_name}_date
                    ON min_craw.`{code_name}` (date(12)) 
                """)
            except Exception:
                pass

        # 콜렉팅하다가 max_api_call 횟수까지 가게 된 경우는 다시 콜렉팅 못한 정보를 가져와야 하니까 check_item_gubun=0
        if self.open_api.rq_count == cf.max_api_call - 1:
            check_item_gubun = 0
        else:
            check_item_gubun = 1
        return check_item_gubun

    def set_daily_crawler_table(self, code, code_name):
        # 기준일자: 장전이면 전 영업일(어제 종가까지), 장후면 오늘(오늘 종가 포함)
        # today를 그대로 넘기면 Kiwoom이 pre-market junk row(open=high=low=close=전일종가)를 반환해
        # daily_craw의 last_date를 오늘로 앞당겨 버려 실제 오늘 OHLCV가 영구 누락됨
        from library.utils import get_latest_complete_date
        ref_date = get_latest_complete_date()
        self.update_status("데이터 조회 중...")
        df = self.open_api.get_total_data(code, code_name, ref_date)
        if len(df) == 0:
            self.update_status("데이터 없음 - 스킵")
            return 1
        oldest_row = df.iloc[-1]
        check_row = None
        deleted = False
        diff = False  # True 인 경우 수정주가 반영하여 업데이트

        # daily_buy_list 테이블 리스트를 추출
        dbl_dates = self.open_api.engine_daily_buy_list.execute("""
                SELECT table_name as tname FROM information_schema.tables 
                WHERE table_schema ='daily_buy_list' AND table_name REGEXP '[0-9]{8}'
            """).fetchall()

        check_daily_crawler_sql = """
            UPDATE daily_buy_list.stock_item_all SET check_daily_crawler = '4' WHERE code = '{}'
        """

        self.update_status("기존 데이터 확인 중...")
        if self.open_api.engine_daily_craw.dialect.has_table(self.open_api.engine_daily_craw, code_name):
            check_row = self.open_api.engine_daily_craw.execute(f"""
                SELECT * FROM `{code_name}` WHERE date = '{oldest_row['date']}' LIMIT 1
            """).fetchall()

            # daily_buy_list 에 저장 된 주가와 daily_craw에 저장 된 주가가 다른 경우 diff를 True로 변경해서 업데이트
            if dbl_dates:
                if dbl_dates[0][0] > oldest_row['date']: #daily_buy_list 의 날짜 테이블 중 가장 과거의 날짜테이블이 API로 부터 받는 oldest_row 보다 더 최근 날짜이면
                    search_date = dbl_dates[0][0]
                else:
                    search_date = oldest_row['date']

                dc_item = self.open_api.engine_daily_craw.execute(f"""
                                SELECT date, close FROM `{code_name}` WHERE date >= '{search_date}' ORDER BY date asc limit 1
                            """).first() # daily_craw 종목테이블에서 search_date 보다는 과거 데이터이고 가장 오래된 row를 찾는다.
                if dc_item:
                    dc_date, dc_close = dc_item
                    if self.open_api.engine_daily_buy_list.dialect.has_table(self.open_api.engine_daily_buy_list, dc_date):
                        dbl_close = self.engine_JB.execute(f"""
                            SELECT close FROM daily_buy_list.`{dc_date}` WHERE code = '{code}'
                        """).fetchall()
                        if dbl_close:
                            if dbl_close[0][0] == dc_close:  # daily_craw, daily_buy_list 의 close 값이 같은 경우
                                diff = False
                            else:  # daily_craw, daily_buy_list 의 close 가 다른 경우
                                diff = True
                        else:  # daily_buy_list 날짜 테이블에 해당 종목이 없는 경우
                            diff = True
                    else:
                        diff = False  # daily_buy_list를 해당 날짜까지 아직 생성하지 못한 경우, 어차피 날짜테이블은 없으면 다시 생성한다. 비교대상이 없으므로 False
                else:
                    diff = True # 분할 재상장 하는 경우 (ex. F&F) daily_buy_list에 분할재상장 이전 데이터가 있을 수 있다. -> 삭제 후 다시 받도록
            else:
                diff = False # daily_buy_list에 아무런 날짜 테이블이 없는 경우 (처음 콜렉팅을 하는 경우)
        else:
            self.engine_JB.execute(check_daily_crawler_sql.format(code))
            deleted = True

        if (check_row and (check_row[0]['close'] != oldest_row['close'])) or diff:
            self.update_status("수정주가 변경 감지 - 재수집 중...")
            logger.info(f'{code} {code_name}의 액면분할/증자 등의 이유로 수정주가가 달라져서 처음부터 다시 콜렉팅')
            # daily_craw 삭제
            logger.info('daily_craw와 min_craw 삭제 중..')
            commands = [
                f'DROP TABLE IF EXISTS daily_craw.`{code_name}`',
                f'DROP TABLE IF EXISTS min_craw.`{code_name}`'
            ]

            for com in commands:
                self.open_api.engine_daily_buy_list.execute(com)
            logger.info('삭제 완료')
            df = self.open_api.get_total_data(code, code_name, ref_date)
            self.engine_JB.execute(check_daily_crawler_sql.format(code))
            deleted = True

        check_daily_crawler = self.engine_JB.execute(f"""
            SELECT check_daily_crawler FROM daily_buy_list.stock_item_all WHERE code = '{code}'
        """).fetchall()[0].check_daily_crawler

        df_temp = DataFrame(df,
                            columns=['date', 'check_item', 'code', 'code_name', 'd1_diff_rate', 'close', 'open', 'high',
                                     'low',
                                     'volume', 'clo5', 'clo10', 'clo20', 'clo40', 'clo60', 'clo80',
                                     'clo100', 'clo120', "clo5_diff_rate", "clo10_diff_rate",
                                     "clo20_diff_rate", "clo40_diff_rate", "clo60_diff_rate",
                                     "clo80_diff_rate", "clo100_diff_rate", "clo120_diff_rate",
                                     'yes_clo5', 'yes_clo10', 'yes_clo20', 'yes_clo40', 'yes_clo60', 'yes_clo80',
                                     'yes_clo100', 'yes_clo120',
                                     'vol5', 'vol10', 'vol20', 'vol40', 'vol60', 'vol80',
                                     'vol100', 'vol120'
                                     ])

        df_temp = df_temp.sort_values(by=['date'], ascending=True)
        # df_temp = df_temp[1:]

        self.update_status("이동평균 계산 중...")
        df_temp['code'] = code
        df_temp['code_name'] = code_name
        df_temp['d1_diff_rate'] = round(
            (df_temp['close'] - df_temp['close'].shift(1)) / df_temp['close'].shift(1) * 100, 2)

        # 하나씩 추가할때는 append 아니면 replace
        clo5 = df_temp['close'].rolling(window=5).mean()
        clo10 = df_temp['close'].rolling(window=10).mean()
        clo20 = df_temp['close'].rolling(window=20).mean()
        clo40 = df_temp['close'].rolling(window=40).mean()
        clo60 = df_temp['close'].rolling(window=60).mean()
        clo80 = df_temp['close'].rolling(window=80).mean()
        clo100 = df_temp['close'].rolling(window=100).mean()
        clo120 = df_temp['close'].rolling(window=120).mean()
        df_temp['clo5'] = clo5
        df_temp['clo10'] = clo10
        df_temp['clo20'] = clo20
        df_temp['clo40'] = clo40
        df_temp['clo60'] = clo60
        df_temp['clo80'] = clo80
        df_temp['clo100'] = clo100
        df_temp['clo120'] = clo120

        df_temp['clo5_diff_rate'] = round((df_temp['close'] - clo5) / clo5 * 100, 2)
        df_temp['clo10_diff_rate'] = round((df_temp['close'] - clo10) / clo10 * 100, 2)
        df_temp['clo20_diff_rate'] = round((df_temp['close'] - clo20) / clo20 * 100, 2)
        df_temp['clo40_diff_rate'] = round((df_temp['close'] - clo40) / clo40 * 100, 2)
        df_temp['clo60_diff_rate'] = round((df_temp['close'] - clo60) / clo60 * 100, 2)
        df_temp['clo80_diff_rate'] = round((df_temp['close'] - clo80) / clo80 * 100, 2)
        df_temp['clo100_diff_rate'] = round((df_temp['close'] - clo100) / clo100 * 100, 2)
        df_temp['clo120_diff_rate'] = round((df_temp['close'] - clo120) / clo120 * 100, 2)

        df_temp['yes_clo5'] = df_temp['clo5'].shift(1)
        df_temp['yes_clo10'] = df_temp['clo10'].shift(1)
        df_temp['yes_clo20'] = df_temp['clo20'].shift(1)
        df_temp['yes_clo40'] = df_temp['clo40'].shift(1)
        df_temp['yes_clo60'] = df_temp['clo60'].shift(1)
        df_temp['yes_clo80'] = df_temp['clo80'].shift(1)
        df_temp['yes_clo100'] = df_temp['clo100'].shift(1)
        df_temp['yes_clo120'] = df_temp['clo120'].shift(1)

        df_temp['vol5'] = df_temp['volume'].rolling(window=5).mean()
        df_temp['vol10'] = df_temp['volume'].rolling(window=10).mean()
        df_temp['vol20'] = df_temp['volume'].rolling(window=20).mean()
        df_temp['vol40'] = df_temp['volume'].rolling(window=40).mean()
        df_temp['vol60'] = df_temp['volume'].rolling(window=60).mean()
        df_temp['vol80'] = df_temp['volume'].rolling(window=80).mean()
        df_temp['vol100'] = df_temp['volume'].rolling(window=100).mean()
        df_temp['vol120'] = df_temp['volume'].rolling(window=120).mean()

        # 여기 이렇게 추가해야함
        if self.open_api.engine_daily_craw.dialect.has_table(self.open_api.engine_daily_craw, code_name):
            last_date = self.open_api.get_daily_craw_db_last_date(code_name)

            # 시간대별 재수집 여부 판단:
            #   08:00~09:00 (장전): ref_date(전 영업일) 데이터가 있어도 오늘 첫 수집이므로 강제 재수집
            #   09:00~16:00 (장중): ref_date = 전 영업일 → 이미 확정된 과거 데이터, 재수집 불필요
            #   16:00~24:00 (장후): ref_date = 오늘 → 오늘 장중 stale row 삭제 후 종가로 재수집
            #   00:00~08:00 (야간): 재수집 불필요
            import datetime as _dt
            _now = _dt.datetime.now()
            _h = _now.hour
            _should_recollect = (
                (8 <= _h < 9) or                                          # 장전: 무조건
                (_h >= 16 and last_date == ref_date and ref_date == self.open_api.today)  # 장후: 오늘 데이터만
            )
            if last_date == ref_date and _should_recollect:
                _reason = "장전 첫 수집" if 8 <= _h < 9 else "장후 종가 업데이트"
                logger.debug(f"{code_name}: {_reason} → {ref_date} 데이터 삭제 후 재수집.")
                try:
                    self.open_api.engine_daily_craw.execute(f"""
                        DELETE FROM `{code_name}` WHERE date = '{ref_date}'
                    """)
                except Exception as e:
                    logger.error(f"{code_name}: ref_date 데이터 삭제 실패: {e}")

                # ref_date 이후만 필터링 (ref_date는 이미 삭제했으므로 포함됨)
                df_temp = df_temp[df_temp.date >= ref_date]
            else:
                # ref_date 이후만 추가 (last_date 초과 ~ ref_date 이하)
                df_temp = df_temp[df_temp.date > last_date]

        if len(df_temp) == 0 and check_daily_crawler != '4':
            self.update_status("이미 최신 - 스킵")
            logger.debug("이미 daily_craw db의 " + code_name + " 테이블에 콜렉팅 완료 했다! df_temp가 비었다!!")

            # 이렇게 안해주면 아래 프로세스들을 안하고 바로 넘어가기때문에 그만큼 tr 조회 하는 시간이 짧아지고 1초에 5회 이상의 조회를 할 수 가있다 따라서 비었을 경우는 sleep해줘야 안멈춘다
            time.sleep(0.03)
            check_item_gubun = 3
            return check_item_gubun

        df_temp[['close', 'open', 'high', 'low', 'volume', 'clo5', 'clo10', 'clo20', 'clo40', 'clo60',
                 'clo80', 'clo100', 'clo120',
                 'yes_clo5', 'yes_clo10', 'yes_clo20', 'yes_clo40', 'yes_clo60', 'yes_clo80', 'yes_clo100',
                 'yes_clo120',
                 'vol5', 'vol10', 'vol20', 'vol40', 'vol60', 'vol80', 'vol100', 'vol120']] = \
            df_temp[
                ['close', 'open', 'high', 'low', 'volume', 'clo5', 'clo10', 'clo20', 'clo40', 'clo60',
                 'clo80', 'clo100', 'clo120',
                 'yes_clo5', 'yes_clo10', 'yes_clo20', 'yes_clo40', 'yes_clo60', 'yes_clo80', 'yes_clo100',
                 'yes_clo120',
                 'vol5', 'vol10', 'vol20', 'vol40', 'vol60', 'vol80', 'vol100', 'vol120']].fillna(0).astype(int)

        # inf 를 NaN으로 변경 (inf can not be used with MySQL 에러 방지)
        df_temp = df_temp.replace([numpy.inf, -numpy.inf], numpy.nan)

        self.update_status("DB 저장 중...")
        df_temp.to_sql(name=code_name, con=self.open_api.engine_daily_craw, if_exists='append', index=False)
        index_name = ''.join(c for c in code_name if c.isalnum())
        if deleted:
            try:
                self.open_api.engine_daily_craw.execute(f"""
                    CREATE INDEX ix_{index_name}_date
                    ON daily_craw.`{code_name}` (date(8)) 
                """)
            except Exception:
                pass

        # check_daily_crawler 가 4 인 경우는 액면분할, 증자 등으로 인해 daily_buy_list 업데이트를 해야하는 경우
        if check_daily_crawler == '4':
            self.update_status("daily_buy_list 동기화 중...")
            logger.debug(f'daily_craw.{code_name} 업데이트 완료 {code}')
            logger.debug('daily_buy_list 업데이트 중..')


            for row in dbl_dates:
                logger.debug(f'{code} {code_name} - daily_buy_list.`{row.tname}` 업데이트')
                try:
                    new_data = df_temp[df_temp.date == row.tname]
                except KeyError:
                    continue
                if self.open_api.engine_daily_craw.dialect.has_table(self.open_api.engine_daily_buy_list, row.tname):
                    self.open_api.engine_daily_buy_list.execute(f"""
                        DELETE FROM `{row.tname}` WHERE code = '{code}'
                    """)
                    if not new_data.empty:
                        new_data.to_sql(
                            name=row.tname,
                            con=self.open_api.engine_daily_buy_list,
                            index=False,
                            if_exists='append',
                            dtype={'code': String(6)}
                        )

            logger.debug('daily_buy_list 업데이트 완료')

        self.update_status("완료")
        check_item_gubun = 1
        return check_item_gubun

    def update_buy_list(self, buy_list):
        f = open("buy_list.txt", "wt")
        for code in buy_list:
            f.writelines("매수;%s;시장가;10;0;매수전\n" % (code))
        f.close()

    def db_to_today_profit_list(self):

        logger.debug("db_to_today_profit_list!!!")
        # 1차원 / 2차원 인스턴스 변수 생성
        self.open_api.reset_opt10073_output()
        # comm_rq_data 호출하기 전에 반드시 set_input_value 해야한다.

        self.open_api.set_input_value("계좌번호", self.open_api.account_number)
        # 여긴 시작일자가 최근 일자로 보면 된다. 하루만 가져오기 위해서 시작일자, 종료일자 동일하게 today로 했음
        self.open_api.set_input_value("시작일자", self.open_api.today)
        self.open_api.set_input_value("종료일자", self.open_api.today)

        self.open_api.comm_rq_data("opt10073_req", "opt10073", 0, "0328")

        while self.open_api.remained_data:
            # # comm_rq_data 호출하기 전에 반드시 set_input_value 해야한다. 초기화 되기 때문
            self.open_api.set_input_value("계좌번호", self.open_api.account_number)

            self.open_api.comm_rq_data("opt10073_req", "opt10073", 2, "0328")

        logger.debug("self.opt10073_output['multi']!!!!!")
        logger.debug(self.open_api.opt10073_output['multi'])

        today_profit_item_temp = {'date': [], 'code': [], 'code_name': [], 'amount': [], 'today_profit': [],
                                  'earning_rate': []}

        # logger.debug(possesed_item_temp)
        today_profit_item = DataFrame(today_profit_item_temp,
                                      columns=['date', 'code', 'code_name', 'amount', 'today_profit',
                                               'earning_rate'])

        item_count = len(self.open_api.opt10073_output['multi'])
        for i in range(item_count):
            row = self.open_api.opt10073_output['multi'][i]
            today_profit_item.loc[i, 'date'] = row[0]
            today_profit_item.loc[i, 'code'] = row[1]
            today_profit_item.loc[i, 'code_name'] = row[2]
            # logger.debug(int(row[3]))
            today_profit_item.loc[i, 'amount'] = int(row[3])
            # logger.debug(today_profit_item.loc[i, 'amount'])
            today_profit_item.loc[i, 'today_profit'] = float(row[4])
            today_profit_item.loc[i, 'earning_rate'] = float(row[5])

        logger.debug("today_profit_item!!!")
        logger.debug(today_profit_item)

        if len(today_profit_item) > 0:
            today_profit_item.to_sql('today_profit_list', self.engine_JB, if_exists='append', index=False)
        sql = "UPDATE setting_data SET today_profit='%s' limit 1"
        self.engine_JB.execute(sql % (self.open_api.today))
        # self.open_api.jackbot_db_con.commit()

    def set_invest_unit(self):
        logger.debug("set_invest_unit!!!")

        self.open_api.invest_unit = int(self.total_invest / self.open_api.max_invest_count)
        logger.debug("self.invest_unit !!!!")
        logger.debug(self.open_api.invest_unit)

        # 오늘 리스트 다 뽑았으면 today를 setting_data에 체크

        sql = "UPDATE setting_data SET invest_unit='%s',set_invest_unit='%s' limit 1"
        self.engine_JB.execute(sql % (self.open_api.invest_unit, self.open_api.today))

    def db_to_jango(self):
        """
        일별 자산 및 매매 성과 데이터를 jango_data 테이블에 저장
        기존 DB 스키마(18개 컬럼)에 맞춤
        """
        self.total_invest = self.open_api.change_format(
            str(int(self.open_api.d2_deposit_before_format) + int(self.open_api.total_purchase_price)))

        # 기존 DB 스키마에 맞는 18개 컬럼만 사용
        jango_col_list = [
            'date',
            'total_asset',
            'd2_deposit',
            'total_invest',
            'today_profit',
            'today_earning_rate',
            'today_buy_count',
            'today_sell_count',
            'today_buy_total_sell_count',
            'today_buy_total_possess_count',
            'today_buy_today_profitcut_count',
            'today_buy_today_profitcut_rate',
            'today_buy_today_losscut_count',
            'today_buy_today_losscut_rate',
            'today_buy_total_profitcut_count',
            'today_buy_total_profitcut_rate',
            'today_buy_total_losscut_count',
            'today_buy_total_losscut_rate'
        ]

        jango = DataFrame(columns=jango_col_list)
        jango.loc[0, 'date'] = self.open_api.today

        logger.debug("self.open_api.today!!!!!!!!")
        logger.debug(self.open_api.today)

        # 자산 정보
        jango.loc[0, 'total_invest'] = self.total_invest
        jango.loc[0, 'd2_deposit'] = self.open_api.d2_deposit

        # 일일 수익
        jango.loc[0, 'today_profit'] = self.open_api.today_profit
        jango.loc[0, 'today_earning_rate'] = float(self.open_api.change_total_earning_rate) / self.open_api.mod_gubun if self.open_api.mod_gubun else 0

        # 매수/매도 통계 (기본값 0)
        jango.loc[0, 'today_buy_count'] = 0
        jango.loc[0, 'today_sell_count'] = 0
        jango.loc[0, 'today_buy_total_sell_count'] = 0
        jango.loc[0, 'today_buy_total_possess_count'] = 0

        # 익절/손절 통계 (당일 매수 → 당일 매도)
        jango.loc[0, 'today_buy_today_profitcut_count'] = 0
        jango.loc[0, 'today_buy_today_profitcut_rate'] = 0
        jango.loc[0, 'today_buy_today_losscut_count'] = 0
        jango.loc[0, 'today_buy_today_losscut_rate'] = 0

        # 익절/손절 통계 (당일 매수 → 전체 기간)
        jango.loc[0, 'today_buy_total_profitcut_count'] = 0
        jango.loc[0, 'today_buy_total_profitcut_rate'] = 0
        jango.loc[0, 'today_buy_total_losscut_count'] = 0
        jango.loc[0, 'today_buy_total_losscut_rate'] = 0

        # 데이터베이스에 테이블이 존재할 때 수행 동작을 지정한다. 'fail', 'replace', 'append' 중 하나를 사용할 수 있는데 기본값은 'fail'이다. 'fail'은 데이터베이스에 테이블이 있다면 아무 동작도 수행하지 않는다. 'replace'는 테이블이 존재하면 기존 테이블을 삭제하고 새로 테이블을 생성한 후 데이터를 삽입한다. 'append'는 테이블이 존재하면 데이터만을 추가한다.
        # 중복 키 에러는 무시 (상위 조건문에서 이미 체크하므로 발생하지 않아야 함)
        try:
            jango.to_sql('jango_data', self.engine_JB, if_exists='append', index=False)
        except Exception as e:
            logger.debug(f"jango_data 삽입 중 오류 (중복 키일 가능성): {e}")

        sql = "select date from jango_data"
        rows = self.engine_JB.execute(sql).fetchall()

        logger.debug("jango_data rows!!!")
        logger.debug(rows)

        logger.debug("jango_data len(rows)!!!")

        logger.debug(len(rows))

        # 위에 전체
        for i in range(len(rows)):
            # logger.debug(rows[i][0])

            # today_earning_rate
            sql = "update jango_data set today_earning_rate =round(today_profit / total_invest  * '%s',2) WHERE date='%s'"
            # rows[i][0] 하는 이유는 rows[i]는 튜플로 나온다 그 튜플의 원소를 꺼내기 위해 [0]을 추가
            self.engine_JB.execute(sql % (100, rows[i][0]))

            # today_buy_count
            sql = "UPDATE jango_data SET today_buy_count=(select count(*) from (select code from all_item_db where buy_date like '%s' group by code ) temp) WHERE date='%s'"

            self.engine_JB.execute(sql % (rows[i][0] + "%%", rows[i][0]))

            # today_buy_total_sell_count ( 익절, 손절 포함)
            sql = "UPDATE jango_data SET today_buy_total_sell_count=(select count(*) from (select code from all_item_db a where buy_date like '%s' and a.sell_date is not null and a.sell_date != '0' group by code ) temp) WHERE date='%s'"

            self.engine_JB.execute(sql % (rows[i][0] + "%%", rows[i][0]))

            # today_buy_total_possess_count
            sql = "UPDATE jango_data SET today_buy_total_possess_count=(select count(*) from (select code from all_item_db a where buy_date like '%s' and a.sell_date = '%s' group by code ) temp) WHERE date='%s'"
            self.engine_JB.execute(sql % (rows[i][0] + "%%", 0, rows[i][0]))

            # today_buy_today_profitcut_count (오늘 매수 -> 오늘 매도 중 익절)
            sql = "UPDATE jango_data SET today_buy_today_profitcut_count=(select count(*) from (select code from all_item_db where buy_date like '%s' and sell_date like '%s' and sell_rate >='%s' group by code ) temp) WHERE date='%s'"
            # rows[i][0] 하는 이유는 rows[i]는 튜플로 나온다 그 튜플의 원소를 꺼내기 위해 [0]을 추가
            self.engine_JB.execute(sql % (rows[i][0] + "%%", rows[i][0] + "%%", 0, rows[i][0]))
            # self.open_api.jackbot_db_con.commit()

            # today_buy_today_profitcut_rate , 오늘 산놈들 중에서 오늘 익절한놈
            sql = "UPDATE jango_data SET today_buy_today_profitcut_rate=(select * from (select round(today_buy_today_profitcut_count /today_buy_count*100,2)  from jango_data WHERE date ='%s' limit 1) tmp)  WHERE date ='%s' limit 1"
            # rows[i][0] 하는 이유는 rows[i]는 튜플로 나온다 그 튜플의 원소를 꺼내기 위해 [0]을 추가
            self.engine_JB.execute(sql % (rows[i][0], rows[i][0]))
            # self.open_api.jackbot_db_con.commit()

            # today_buy_today_losscut_count
            sql = "UPDATE jango_data SET today_buy_today_losscut_count=(select count(*) from (select code from all_item_db where buy_date like '%s' and sell_date like '%s' and sell_rate < '%s'  group by code ) tmp) WHERE date='%s' limit 1"
            # rows[i][0] 하는 이유는 rows[i]는 튜플로 나온다 그 튜플의 원소를 꺼내기 위해 [0]을 추가
            self.engine_JB.execute(sql % (rows[i][0] + "%%", rows[i][0] + "%%", 0, rows[i][0]))
            # self.open_api.jackbot_db_con.commit()

            # today_buy_today_losscut_rate
            sql = "UPDATE jango_data SET today_buy_today_losscut_rate=(select * from (select round(today_buy_today_losscut_count /today_buy_count *100,2)  from jango_data WHERE date ='%s' limit 1) tmp) WHERE date ='%s' limit 1"
            # rows[i][0] 하는 이유는 rows[i]는 튜플로 나온다 그 튜플의 원소를 꺼내기 위해 [0]을 추가
            self.engine_JB.execute(sql % (rows[i][0], rows[i][0]))
            # self.open_api.jackbot_db_con.commit()

            # today_buy_total_profitcut_count
            sql = "UPDATE jango_data SET today_buy_total_profitcut_count=(select count(*) from (select code from all_item_db where buy_date like '%s' and sell_rate >='%s'  group by code ) tmp) WHERE date='%s' limit 1"
            # rows[i][0] 하는 이유는 rows[i]는 튜플로 나온다 그 튜플의 원소를 꺼내기 위해 [0]을 추가
            self.engine_JB.execute(sql % (rows[i][0] + "%%", 0, rows[i][0]))
            # self.open_api.jackbot_db_con.commit()

            # today_buy_total_profitcut_rate
            sql = "UPDATE jango_data SET today_buy_total_profitcut_rate=(select * from (select round(today_buy_total_profitcut_count /today_buy_count *100,2)  from jango_data WHERE date ='%s' limit 1) tmp) WHERE date ='%s' limit 1"
            # rows[i][0] 하는 이유는 rows[i]는 튜플로 나온다 그 튜플의 원소를 꺼내기 위해 [0]을 추가
            self.engine_JB.execute(sql % (rows[i][0], rows[i][0]))
            # self.open_api.jackbot_db_con.commit()

            # today_buy_total_losscut_count
            sql = "UPDATE jango_data SET today_buy_total_losscut_count=(select count(*) from (select code from all_item_db where buy_date like '%s' and sell_rate < '%s'  group by code ) tmp) WHERE date='%s' limit 1"
            # rows[i][0] 하는 이유는 rows[i]는 튜플로 나온다 그 튜플의 원소를 꺼내기 위해 [0]을 추가
            self.engine_JB.execute(sql % (rows[i][0] + "%%", 0, rows[i][0]))
            # self.open_api.jackbot_db_con.commit()

            # today_buy_total_losscut_rate
            sql = "UPDATE jango_data SET today_buy_total_losscut_rate=(select * from (select round(today_buy_total_losscut_count/today_buy_count *100,2)  from jango_data WHERE date ='%s' limit 1) tmp) WHERE date ='%s' limit 1"
            # rows[i][0] 하는 이유는 rows[i]는 튜플로 나온다 그 튜플의 원소를 꺼내기 위해 [0]을 추가
            self.engine_JB.execute(sql % (rows[i][0], rows[i][0]))
            # self.open_api.jackbot_db_con.commit()

            # ====================================================================
            # 아래 reinvest_count 관련 UPDATE들은 DB 스키마에 컬럼이 없어서 주석처리
            # - jango_data 테이블에 today_buy_reinvest_count* 컬럼들이 없음
            # - all_item_db 테이블에 reinvest_count 컬럼이 없음
            # ====================================================================

            # # today_buy_reinvest_count0_sell_count 오늘만 해당되는게 아니고 전체 다
            # sql = "UPDATE jango_data SET today_buy_reinvest_count0_sell_count=(select count(*) from (select code from all_item_db where buy_date like '%s' and sell_date is not null and reinvest_count=0 group by code ) tmp) WHERE date='%s'"
            # # rows[i][0] 하는 이유는 rows[i]는 튜플로 나온다 그 튜플의 원소를 꺼내기 위해 [0]을 추가
            # self.engine_JB.execute(sql % (rows[i][0] + "%%", rows[i][0]))
            # # self.open_api.jackbot_db_con.commit()

            # # today_buy_reinvest_count1_sell_count
            # sql = "UPDATE jango_data SET today_buy_reinvest_count1_sell_count=(select count(*) from (select code from all_item_db where buy_date like '%s' and sell_date is not null and reinvest_count=1 group by code ) tmp) WHERE date='%s'"
            # # rows[i][0] 하는 이유는 rows[i]는 튜플로 나온다 그 튜플의 원소를 꺼내기 위해 [0]을 추가
            # self.engine_JB.execute(sql % (rows[i][0] + "%%", rows[i][0]))
            # # self.open_api.jackbot_db_con.commit()

            # # today_buy_reinvest_count2_sell_count
            # sql = "UPDATE jango_data SET today_buy_reinvest_count2_sell_count=(select count(*) from (select code from all_item_db where buy_date like '%s' and sell_date is not null and reinvest_count=2 group by code ) tmp) WHERE date='%s'"
            # # rows[i][0] 하는 이유는 rows[i]는 튜플로 나온다 그 튜플의 원소를 꺼내기 위해 [0]을 추가
            # self.engine_JB.execute(sql % (rows[i][0] + "%%", rows[i][0]))
            # # self.open_api.jackbot_db_con.commit()

            # # today_buy_reinvest_count3_sell_count
            # sql = "UPDATE jango_data SET today_buy_reinvest_count3_sell_count=(select count(*) from (select code from all_item_db where buy_date like '%s' and sell_date is not null and reinvest_count=3 group by code ) tmp) WHERE date='%s'"
            # # rows[i][0] 하는 이유는 rows[i]는 튜플로 나온다 그 튜플의 원소를 꺼내기 위해 [0]을 추가
            # self.engine_JB.execute(sql % (rows[i][0] + "%%", rows[i][0]))
            # # self.open_api.jackbot_db_con.commit()

            # # today_buy_reinvest_count4_sell_count
            # sql = "UPDATE jango_data SET today_buy_reinvest_count4_sell_count=(select count(*) from (select code from all_item_db where buy_date like '%s' and sell_date is not null and reinvest_count=4 group by code ) tmp) WHERE date='%s'"
            # # rows[i][0] 하는 이유는 rows[i]는 튜플로 나온다 그 튜플의 원소를 꺼내기 위해 [0]을 추가
            # self.engine_JB.execute(sql % (rows[i][0] + "%%", rows[i][0]))
            # # self.open_api.jackbot_db_con.commit()

            # # today_buy_reinvest_count4_sell_profitcut_count
            # sql = "UPDATE jango_data SET today_buy_reinvest_count4_sell_profitcut_count=(select count(*) from (select code from all_item_db where buy_date like '%s' and sell_date is not null and reinvest_count=4 and sell_rate >='%s' group by code ) tmp) WHERE date='%s'"
            # # rows[i][0] 하는 이유는 rows[i]는 튜플로 나온다 그 튜플의 원소를 꺼내기 위해 [0]을 추가
            # self.engine_JB.execute(sql % (rows[i][0] + "%%", 0, rows[i][0]))
            # # self.open_api.jackbot_db_con.commit()

            # #   today_buy_reinvest_count4_sell_losscut_count
            # sql = "UPDATE jango_data SET today_buy_reinvest_count4_sell_losscut_count=(select count(*) from (select code from all_item_db where buy_date like '%s' and sell_date is not null and reinvest_count=4 and sell_rate <'%s' group by code ) tmp) WHERE date='%s'"
            # # rows[i][0] 하는 이유는 rows[i]는 튜플로 나온다 그 튜플의 원소를 꺼내기 위해 [0]을 추가
            # self.engine_JB.execute(sql % (rows[i][0] + "%%", 0, rows[i][0]))
            # # self.open_api.jackbot_db_con.commit()

            # # today_buy_reinvest_count5_sell_count

            # sql = "UPDATE jango_data SET today_buy_reinvest_count5_sell_count=(select count(*) from (select code from all_item_db where buy_date like '%s' and sell_date is not null and reinvest_count=5 group by code ) tmp) WHERE date='%s'"
            # # rows[i][0] 하는 이유는 rows[i]는 튜플로 나온다 그 튜플의 원소를 꺼내기 위해 [0]을 추가
            # self.engine_JB.execute(sql % (rows[i][0] + "%%", rows[i][0]))
            # # self.open_api.jackbot_db_con.commit()

            # # today_buy_reinvest_count5_sell_profitcut_count
            # sql = "UPDATE jango_data SET today_buy_reinvest_count5_sell_profitcut_count=(select count(*) from (select code from all_item_db where buy_date like '%s' and sell_date is not null and reinvest_count=5 and sell_rate >='%s' group by code ) tmp) WHERE date='%s'"
            # # rows[i][0] 하는 이유는 rows[i]는 튜플로 나온다 그 튜플의 원소를 꺼내기 위해 [0]을 추가
            # self.engine_JB.execute(sql % (rows[i][0] + "%%", 0, rows[i][0]))
            # # self.open_api.jackbot_db_con.commit()

            # #  today_buy_reinvest_count5_sell_losscut_count
            # sql = "UPDATE jango_data SET today_buy_reinvest_count5_sell_losscut_count=(select count(*) from (select code from all_item_db where buy_date like '%s' and sell_date is not null and reinvest_count=5 and sell_rate <'%s' group by code ) tmp) WHERE date='%s'"
            # # rows[i][0] 하는 이유는 rows[i]는 튜플로 나온다 그 튜플의 원소를 꺼내기 위해 [0]을 추가
            # self.engine_JB.execute(sql % (rows[i][0] + "%%", 0, rows[i][0]))
            # # self.open_api.jackbot_db_con.commit()

            # # today_buy_reinvest_count0_remain_count
            # sql = "UPDATE jango_data SET today_buy_reinvest_count0_remain_count=(select count(*) from (select code from all_item_db where buy_date like '%s' and sell_date = '%s' and reinvest_count=0 group by code ) tmp) WHERE date='%s'"
            # # rows[i][0] 하는 이유는 rows[i]는 튜플로 나온다 그 튜플의 원소를 꺼내기 위해 [0]을 추가
            # self.engine_JB.execute(sql % (rows[i][0] + "%%", 0, rows[i][0]))
            # # self.open_api.jackbot_db_con.commit()

            # # today_buy_reinvest_count1_remain_count
            # sql = "UPDATE jango_data SET today_buy_reinvest_count1_remain_count=(select count(*) from (select code from all_item_db where buy_date like '%s' and sell_date = '%s' and reinvest_count=1 group by code ) tmp) WHERE date='%s'"
            # # rows[i][0] 하는 이유는 rows[i]는 튜플로 나온다 그 튜플의 원소를 꺼내기 위해 [0]을 추가
            # self.engine_JB.execute(sql % (rows[i][0] + "%%", 0, rows[i][0]))
            # # self.open_api.jackbot_db_con.commit()

            # # today_buy_reinvest_count2_remain_count
            # sql = "UPDATE jango_data SET today_buy_reinvest_count2_remain_count=(select count(*) from (select code from all_item_db where buy_date like '%s' and sell_date = '%s' and reinvest_count=2 group by code ) tmp) WHERE date='%s'"
            # # rows[i][0] 하는 이유는 rows[i]는 튜플로 나온다 그 튜플의 원소를 꺼내기 위해 [0]을 추가
            # self.engine_JB.execute(sql % (rows[i][0] + "%%", 0, rows[i][0]))
            # # self.open_api.jackbot_db_con.commit()

            # # today_buy_reinvest_count3_remain_count
            # sql = "UPDATE jango_data SET today_buy_reinvest_count3_remain_count=(select count(*) from (select code from all_item_db where buy_date like '%s' and sell_date = '%s' and reinvest_count=3 group by code ) tmp) WHERE date='%s'"
            # # rows[i][0] 하는 이유는 rows[i]는 튜플로 나온다 그 튜플의 원소를 꺼내기 위해 [0]을 추가
            # self.engine_JB.execute(sql % (rows[i][0] + "%%", 0, rows[i][0]))

            # sql = "UPDATE jango_data SET today_buy_reinvest_count4_remain_count=(select count(*) from (select code from all_item_db where buy_date like '%s' and sell_date = '%s' and reinvest_count=4 group by code ) tmp) WHERE date='%s'"
            # self.engine_JB.execute(sql % (rows[i][0] + "%%", 0, rows[i][0]))

            # sql = "UPDATE jango_data SET today_buy_reinvest_count5_remain_count=(select count(*) from (select code from all_item_db where buy_date like '%s' and sell_date = '%s' and reinvest_count=5 group by code ) tmp) WHERE date='%s'"

            # self.engine_JB.execute(sql % (rows[i][0] + "%%", 0, rows[i][0]))

        sql = "UPDATE setting_data SET jango_data_db_check='%s' limit 1"
        self.engine_JB.execute(sql % (self.open_api.today))
        # self.open_api.jackbot_db_con.commit()

    # 일자별 실현손익
    def py_check_balance(self):
        logger.debug("py_check_balance!!!")
        # 일자별 실현손익 출력
        self.open_api.set_input_value("계좌번호", self.open_api.account_number)
        # 	시작일자 = YYYYMMDD (20170101 연도4자리, 월 2자리, 일 2자리 형식)
        self.open_api.set_input_value("시작일자", "20170101")
        # 	종료일자 = YYYYMMDD (20170101 연도4자리, 월 2자리, 일 2자리 형식)
        self.open_api.set_input_value("종료일자", self.open_api.today)
        self.open_api.comm_rq_data("opt10074_req", "opt10074", 0, "0329")
        while self.open_api.remained_data:
            # # comm_rq_data 호출하기 전에 반드시 set_input_value 해야한다. 초기화 되기 때문
            self.open_api.set_input_value("계좌번호", self.open_api.account_number)
            # 	시작일자 = YYYYMMDD (20170101 연도4자리, 월 2자리, 일 2자리 형식)
            self.open_api.set_input_value("시작일자", "20170101")
            # 	종료일자 = YYYYMMDD (20170101 연도4자리, 월 2자리, 일 2자리 형식)
            self.open_api.set_input_value("종료일자", self.open_api.today)
            self.open_api.comm_rq_data("opt10074_req", "opt10074", 2, "0329")
