"""
고급 전략 통합 트레이더 (Advanced Strategy Trader)
Version: 2.0.0

기존 trader.py를 기반으로 고급 매매 전략을 통합한 실전 트레이더입니다.

주요 기능:
- 멀티팩터 스코어링 시스템
- 하이브리드 전략 (모멘텀 + 평균회귀)
- 날짜 기반 전략 통합
- ATR 기반 동적 리스크 관리
- 고급 청산 전략 (트레일링 스톱)

사용법:
    python trader_advanced.py

설정:
    variable_setting() 함수에서 전략 설정 변경 가능
"""

ver = "#version 2.0.0 - Advanced Strategy Integrated"
print(f"Trader Advanced Version: {ver}")

import traceback as _traceback
import faulthandler as _faulthandler
_faulthandler.enable(open('log/crash_dump.log', 'w'))

def _global_exception_handler(exc_type, exc_value, exc_tb):
    tb_str = "".join(_traceback.format_exception(exc_type, exc_value, exc_tb))
    logger.error(f"[UNCAUGHT EXCEPTION] {exc_type.__name__}: {exc_value}")
    logger.error(tb_str)

import sys as _sys
_sys.excepthook = _global_exception_handler

from library.open_api import *
from library.trading_dashboard import update_dashboard
from library.report_generator import generate_trader_report
from library import cf
from PyQt5.QtWidgets import *
import sys
from datetime import datetime
import logging
import time

# 콘솔 로깅 비활성화 (대시보드 모드)
# 모든 로그는 파일에만 기록되고, 콘솔에는 대시보드만 표시
for handler in logger.handlers[:]:
    if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
        logger.removeHandler(handler)

logger.debug("===== Trader Advanced Start =====")


class TraderAdvanced(QMainWindow):
    """
    고급 전략 통합 트레이더

    기존 trader.py의 모든 기능 + 고급 전략 시스템
    """

    def __init__(self):
        logger.debug("TraderAdvanced __init__ 시작")
        super().__init__()

        # OpenAPI 초기화
        self.open_api = open_api()

        # 현재 시간
        self.current_time = QTime.currentTime()

        # 변수 설정
        self.variable_setting()

        # 고급 전략 엔진 초기화
        self.init_advanced_strategy()

        # 투자 운용보고서 초기화
        try:
            from library.investment_report import InvestmentReport
            self._reporter = InvestmentReport(self.open_api.engine_JB)
            self._reporter.ensure_exit_reason_column()
            # open_api 에도 연결 → 매수 체결 시 자동 업데이트
            self.open_api._reporter = self._reporter
            logger.info("📊 투자보고서 모듈 초기화 완료 (매수/매도 자동 갱신 활성화)")
        except Exception as _re:
            self._reporter = None
            logger.warning(f"투자보고서 초기화 실패 (무시): {_re}")

        logger.info("=" * 80)
        logger.info("🚀 고급 전략 트레이더 초기화 완료")
        logger.info("=" * 80)

    def variable_setting(self):
        """
        트레이더 설정

        여기서 전략 옵션을 변경할 수 있습니다.
        """
        self.open_api.py_gubun = "trader_advanced"

        # ==================================================
        # ⚙️ 고급 전략 설정
        # ==================================================

        # 1. 고급 매수 전략 사용 여부
        self.use_advanced_buy = True
        """
        True: 고급 전략 시스템으로 매수 리스트 생성
        False: 기존 realtime_daily_buy_list 사용
        """

        # 2. 날짜 기반 전략 사용 비율
        self.use_date_based_strategy = True
        """
        True: 날짜 기반 전략 30% + 하이브리드 전략 70% 혼합
        False: 하이브리드 전략 100%
        """

        # 3. 고급 매도 전략 사용 여부
        self.use_advanced_sell = True
        """
        True: 고급 청산 전략 (트레일링 스톱, ATR 기반 손절/익절)
        False: 기존 매도 로직 사용
        """

        # 4. 리스크 프로필
        self.risk_profile = 'aggressive'
        """
        'conservative': 보수적 (포지션 5%, 손절 ATR 3배)
        'moderate': 중도 (포지션 10%, 손절 ATR 2.5배)
        'aggressive': 공격적 (포지션 15%, 손절 ATR 2배) - 기본값
        """

        # ==================================================
        # ⏰ 장 운영 시간 설정
        # ==================================================

        # 장시작 시간 (09:00)
        self.market_start_time = QTime(9, 0, 0)

        # 장마감 시간 (15:30)
        self.market_end_time = QTime(15, 30, 0)

        # 매수 마감 시간 (15:00)
        # 이 시간 이후에는 새로운 매수를 하지 않습니다
        self.buy_end_time = QTime(15, 0, 0)

        # 장 마감 후 자동 종료 여부
        self.auto_exit_after_market_close = True
        """
        True: 장 마감 후 30분 대기 후 자동 종료 (권장)
        False: 계속 실행 (다음날까지 대기)
        """

        # 장 마감 후 대기 시간 (분)
        self.exit_wait_minutes = 30

        # 매수 후보 없을 시 자동 종료 여부
        self.exit_on_no_candidates = True
        """
        True: 매수 후보 없으면 즉시 종료 (권장, 일봉 collector용)
        False: 60초마다 체크 계속 (분봉 collector 대비)
        """

        # ==================================================
        # 📊 고급 전략 파라미터
        # ==================================================

        # 멀티팩터 최소 스코어 (cf.v2_min_score와 동기화)
        self.min_factor_score = float(cf.v2_min_score)

        # 최대 동시 보유 종목 수 (예수금이 허락하는 한 무제한)
        self.max_positions = 999

        # 일일 최대 손실 한도 (%)
        self.max_daily_loss_pct = -8.0

        # ==================================================
        # 🔄 매수 후보 스캔 상태 플래그
        # ==================================================

        # 오늘 매수 후보 스캔 완료 여부
        self.buy_scan_done = False

        # 매수 후보 존재 여부 (None: 미스캔, True: 있음, False: 없음)
        self.buy_candidates_available = None

        # 종료 요청 플래그
        self.should_exit = False
        self.exit_reason = ""

        # 오늘의 거래 내역 추적
        self.trade_history = []

        # 고급 청산 시그널 상세 (대시보드 표시용 - reason/priority 보존)
        self.sell_signals_detail = []

        # 매도 주문 쿨다운 추적: {code: {'count': int, 'last_time': float}}
        # 동일 종목 매도 주문 3분 쿨다운, 10회 이상이면 당일 스킵
        self._sell_cooldown = {}
        self._sell_cooldown_secs = 180   # 3분
        self._sell_max_attempts = 10
        self._sell_skip_warned = set()

        logger.info("=" * 80)
        logger.info("⚙️  트레이더 설정")
        logger.info("=" * 80)
        logger.info(f"  고급 매수 전략: {'사용' if self.use_advanced_buy else '미사용'}")
        logger.info(f"  날짜 기반 전략: {'사용' if self.use_date_based_strategy else '미사용'}")
        logger.info(f"  고급 매도 전략: {'사용' if self.use_advanced_sell else '미사용'}")
        logger.info(f"  리스크 프로필: {self.risk_profile}")
        logger.info(f"  최소 팩터 스코어: {self.min_factor_score}")
        logger.info(f"  최대 보유 종목: {self.max_positions}개")
        logger.info(f"  일일 최대 손실: {self.max_daily_loss_pct}%")
        logger.info(f"  장 마감 후 자동 종료: {'사용' if self.auto_exit_after_market_close else '미사용'}")
        if self.auto_exit_after_market_close:
            logger.info(f"  종료 대기 시간: {self.exit_wait_minutes}분")
        logger.info(f"  매수 후보 없을 시 자동 종료: {'사용' if self.exit_on_no_candidates else '미사용'}")
        logger.info("=" * 80)

    def init_advanced_strategy(self):
        """
        고급 전략 엔진 초기화
        """
        try:
            # ✅ realtime_position_monitor 테이블 초기화
            self.reset_realtime_position_monitor()

            if self.use_advanced_buy or self.use_advanced_sell:
                logger.info("🔧 고급 전략 사용 설정 확인...")

                # 포트폴리오 가치 계산
                self.open_api.check_balance()
                self.open_api.get_d2_deposit()

                portfolio_value = int(self.open_api.d2_deposit_before_format) + \
                                int(self.open_api.total_purchase_price)

                logger.info(f"✅ 고급 전략 활성화 (포트폴리오: {portfolio_value:,}원)")
                self.advanced_engine_ready = True
            else:
                logger.info("ℹ️  기본 전략 사용 (고급 전략 미사용)")
                self.advanced_engine_ready = False

        except Exception as e:
            logger.error(f"❌ 고급 전략 초기화 오류: {e}")
            logger.warning("기본 전략으로 전환합니다")
            self.advanced_engine_ready = False
            self.use_advanced_buy = False
            self.use_advanced_sell = False

    def reset_realtime_position_monitor(self):
        """
        realtime_position_monitor 테이블 동기화

        TRUNCATE 없이 증분 동기화: 기존 종목의 highest_price를 재시작 후에도 보존.
        - 더 이상 보유하지 않는 종목 → 삭제
        - 이미 테이블에 있는 종목 → highest_price 그대로 유지
        - 신규 매수 종목 → purchase_price로 초기화하여 추가
        """
        try:
            logger.info("🔄 realtime_position_monitor 동기화 중...")

            # 1. 테이블 없으면 생성
            self.open_api.engine_JB.execute("""
                CREATE TABLE IF NOT EXISTS realtime_position_monitor (
                    code VARCHAR(10) NOT NULL,
                    code_name VARCHAR(50),
                    entry_price INT DEFAULT 0,
                    entry_date VARCHAR(10),
                    current_price INT DEFAULT 0,
                    highest_price INT DEFAULT 0,
                    last_update DATETIME,
                    PRIMARY KEY (code)
                )
            """)

            # 2. all_item_db에서 현재 보유 종목 조회
            holdings = self.open_api.engine_JB.execute("""
                SELECT code, code_name, purchase_price, buy_date
                FROM all_item_db WHERE sell_date = '0'
                GROUP BY code
            """).fetchall()
            holding_codes = {h[0] for h in holdings}

            # 3. 테이블에 있는 기존 코드 조회
            existing_rows = self.open_api.engine_JB.execute(
                "SELECT code FROM realtime_position_monitor"
            ).fetchall()
            existing_codes = {row[0] for row in existing_rows}

            # 4. 더 이상 보유하지 않는 종목 삭제
            for code in existing_codes - holding_codes:
                self.open_api.engine_JB.execute(
                    f"DELETE FROM realtime_position_monitor WHERE code = '{code}'"
                )

            # 5. 신규 보유 종목만 INSERT (기존 종목은 highest_price 보존)
            added = 0
            for holding in holdings:
                code = holding[0]
                if code in existing_codes:
                    continue  # 이미 있음 → highest_price 그대로 유지
                code_name = holding[1]
                purchase_price = int(holding[2])
                buy_date = holding[3]
                self.open_api.engine_JB.execute("""
                    INSERT INTO realtime_position_monitor
                    (code, code_name, entry_price, entry_date, current_price, highest_price, last_update)
                    VALUES ('%s', '%s', %d, '%s', %d, %d, NOW())
                """ % (code, code_name, purchase_price, buy_date, purchase_price, purchase_price))
                added += 1

            kept = len(holding_codes & existing_codes)
            removed = len(existing_codes - holding_codes)
            logger.info(
                f"✅ realtime_position_monitor 동기화 완료 — "
                f"유지(highest_price 보존): {kept}개 / 신규: {added}개 / 삭제: {removed}개"
            )

        except Exception as e:
            logger.warning(f"⚠️  realtime_position_monitor 초기화 실패: {e}")

    def auto_trade_stock(self):
        """
        자동 매수 함수

        고급 전략 설정에 따라 매수 방식 선택
        """
        # logger.debug("auto_trade_stock 함수 실행")

        try:
            if self.use_advanced_buy and self.advanced_engine_ready:
                # 고급 전략으로 매수
                logger.info("📊 고급 전략으로 매수 리스트 생성")
                self.open_api.get_advanced_buy_list(use_advanced_strategy=True)

                # 첫 스캔 후 결과 저장
                if not self.buy_scan_done:
                    self.buy_scan_done = True
                    # realtime_daily_buy_list에 데이터가 있는지 확인
                    if hasattr(self.open_api.sf, 'len_df_realtime_daily_buy_list'):
                        if self.open_api.sf.len_df_realtime_daily_buy_list > 0:
                            self.buy_candidates_available = True
                            logger.info(f"✅ 매수 후보 {self.open_api.sf.len_df_realtime_daily_buy_list}개 발견")
                        else:
                            self.buy_candidates_available = False
                            logger.warning("❌ 오늘은 매수 후보가 없습니다 (스캔 완료)")

                            # 매수 후보 없을 시 자동 종료 옵션 체크
                            if self.exit_on_no_candidates:
                                self.open_api.check_balance()
                                has_positions = len(self.open_api.opw00018_output['multi']) > 0

                                if has_positions:
                                    logger.info("💼 보유 종목이 있어 청산 시그널까지 대기합니다")
                                else:
                                    self.should_exit = True
                                    self.exit_reason = "매수 후보 없음 (보유 종목 없음)"
                                    logger.info("🚪 매수 후보 및 보유 종목 없으므로 자동 종료합니다")
                    else:
                        # 확인 불가 시 후보 없음으로 처리
                        self.buy_candidates_available = False
                        logger.warning("❌ 매수 후보 리스트 확인 불가 (스캔 완료)")

                        # 매수 후보 없을 시 자동 종료 옵션 체크
                        if self.exit_on_no_candidates:
                            self.open_api.check_balance()
                            has_positions = len(self.open_api.opw00018_output['multi']) > 0

                            if has_positions:
                                logger.info("💼 보유 종목이 있어 청산 시그널까지 대기합니다")
                            else:
                                self.should_exit = True
                                self.exit_reason = "매수 후보 확인 불가 (보유 종목 없음)"
                                logger.info("🚪 매수 후보 확인 불가 및 보유 종목 없으므로 자동 종료합니다")

                # 매수 후보가 있으면 실제 매수 실행
                if self.buy_candidates_available:
                    self.open_api.get_today_buy_list()
            else:
                # 기존 방식으로 매수
                logger.info("📋 기본 방식으로 매수")
                self.open_api.get_today_buy_list()

        except Exception as e:
            logger.error(f"❌ 매수 실행 오류: {e}")
            logger.warning("기본 방식으로 재시도합니다")

            # 첫 스캔이었다면 플래그 설정 후 자동 종료
            if not self.buy_scan_done:
                self.buy_scan_done = True
                self.buy_candidates_available = False
                logger.warning("❌ 매수 스캔 실패 (에러 발생)")

                if self.exit_on_no_candidates:
                    # 보유 종목 확인
                    self.open_api.check_balance()
                    has_positions = len(self.open_api.opw00018_output['multi']) > 0

                    if has_positions:
                        logger.info("💼 보유 종목이 있어 청산 시그널까지 대기합니다")
                    else:
                        self.should_exit = True
                        self.exit_reason = "매수 스캔 오류 (보유 종목 없음)"
                        logger.info("🚪 매수 스캔 오류 및 보유 종목 없으므로 자동 종료합니다")
                        # 자동 종료 플래그가 설정되었으므로 기존 방식 재시도 안 함
                        return

            self.open_api.get_today_buy_list()

    def get_sell_list_trade(self):
        """
        매도 리스트 생성

        고급 전략 설정에 따라 매도 방식 선택
        """
        # logger.debug("get_sell_list_trade 함수 실행")

        # 체결 확인
        self.open_api.chegyul_check()

        # 수익률 업데이트
        self.open_api.rate_check()

        try:
            # exit_strategy.get_live_sell_signals() — Strategy A/B 분기, ATR 기반 트레일링
            self.sell_list, self.sell_signals_detail = self.open_api.get_sell_list()
            logger.debug(f"매도 리스트: {self.sell_list}")

        except Exception as e:
            import traceback
            logger.error(f"❌ 매도 리스트 생성 오류: {e}", extra={'no_dedup': True})
            logger.error(traceback.format_exc(), extra={'no_dedup': True})
            self.sell_list           = []
            self.sell_signals_detail = []

    def auto_trade_sell_stock(self):
        """
        자동 매도 실행
        """
        # logger.debug("auto_trade_sell_stock 함수 실행")

        try:
            # 계좌 정보는 메인 루프에서 이미 업데이트됨 (check_balance() 제거)

            # possessed_item 테이블 동기화
            self.open_api.db_to_possesed_item()

            # 봇 꺼졌을 때 매도 반영
            self.open_api.final_chegyul_check()

            # 매도 리스트 가져오기
            self.get_sell_list_trade()

            # 매도 실행
            # sell_list 구조: [code, code_name, rate, present_price, valuation_profit]
            for i in range(len(self.sell_list)):
                try:
                    # 종목 코드
                    sell_code = self.sell_list[i][0]

                    # 종목명
                    stock_name = self.sell_list[i][1]

                    # 수익률 (모의투자는 직접 %, 실전은 100 기준)
                    sell_rate = float(self.sell_list[i][2])
                    if self.open_api.mod_gubun != 1:
                        sell_rate = sell_rate - 100

                    # 매도 수량
                    sell_num = self.open_api.get_holding_amount(sell_code)

                    if sell_num == False or sell_num == 0:
                        continue

                    if sell_code and sell_code != "0":
                        # 매도 쿨다운 체크 (거래정지 등 반복 주문 방지)
                        now_ts = time.time()
                        cd = self._sell_cooldown.get(sell_code)
                        if cd:
                            if cd['count'] >= self._sell_max_attempts:
                                if sell_code not in self._sell_skip_warned:
                                    logger.warning(f"⚠️ 매도 스킵 (10회 초과): {stock_name}({sell_code})")
                                    self._sell_skip_warned.add(sell_code)
                                continue
                            elapsed = now_ts - cd['last_time']
                            if elapsed < self._sell_cooldown_secs:
                                if elapsed < 6:  # 쿨다운 시작 시점에만 1회 로그
                                    logger.debug(f"매도 쿨다운 시작 ({sell_code}) - {int(self._sell_cooldown_secs)}초 대기 [{cd['count']}회]")
                                continue

                        # sell_signals_detail에서 실제 exit reason 조회
                        exit_reason = next(
                            (s['reason'] for s in self.sell_signals_detail if s['code'] == sell_code),
                            None
                        )
                        if exit_reason:
                            trade_type = exit_reason
                        elif sell_rate < 0:
                            trade_type = "손절매도"
                        else:
                            trade_type = "익절매도"

                        if sell_rate < 0:
                            logger.info(f"💔 손절 매도: {stock_name}({sell_code}) {sell_rate:.2f}% [{trade_type}] - {sell_num}주")
                        else:
                            logger.info(f"💰 익절 매도: {stock_name}({sell_code}) {sell_rate:.2f}% [{trade_type}] - {sell_num}주")

                        # 거래 내역 기록
                        self.trade_history.append({
                            'time': datetime.now().strftime('%H:%M:%S'),
                            'type': '매도',
                            'code': sell_code,
                            'name': stock_name,
                            'price': int(self.sell_list[i][3]),  # present_price
                            'quantity': sell_num,
                            'strategy': trade_type,
                            'profit_rate': sell_rate
                        })

                        # 매도사유 DB 저장 (리포트용 — exit_reason 컬럼이 있는 DB만 유효)
                        try:
                            self.open_api.engine_JB.execute(
                                "UPDATE all_item_db SET exit_reason=%s "
                                "WHERE code=%s AND sell_date='0' AND simul_num=%s "
                                "ORDER BY buy_date DESC LIMIT 1",
                                (trade_type, sell_code, cf.imi1_simul_num)
                            )
                        except Exception as _e:
                            logger.debug(f"exit_reason 저장 실패 ({sell_code}): {_e}")

                        # 시장가 매도 주문
                        self.open_api.send_order(
                            "send_order_req",
                            "0101",
                            self.open_api.account_number,
                            2,  # 신규매도
                            sell_code,
                            sell_num,
                            0,  # 시장가
                            "03",  # 시장가
                            ""
                        )

                        # 쿨다운 기록 갱신
                        if sell_code not in self._sell_cooldown:
                            self._sell_cooldown[sell_code] = {'count': 0, 'last_time': 0}
                        self._sell_cooldown[sell_code]['count'] += 1
                        self._sell_cooldown[sell_code]['last_time'] = now_ts

                        # 투자보고서 비동기 업데이트 (체결 완료 후 5초 대기 → DB 반영 후 생성)
                        if self._reporter:
                            import threading
                            def _delayed_report():
                                import time as _time
                                _time.sleep(5)
                                self._reporter.generate_async()
                            threading.Thread(target=_delayed_report, daemon=True,
                                             name='ReportDelay').start()

                except Exception as e:
                    logger.error(f"매도 실행 오류 ({sell_code}): {e}")
                    continue

        except Exception as e:
            logger.error(f"❌ 매도 함수 오류: {e}")

    def market_time_check(self):
        """
        장시간 확인

        Returns:
            bool: 장시간이면 True, 아니면 False
        """
        self.current_time = QTime.currentTime()

        if self.market_start_time < self.current_time < self.market_end_time:
            return True
        else:
            return False

    def buy_time_check(self):
        """
        매수 가능 시간 확인

        Returns:
            bool: 매수 가능하면 True, 아니면 False
        """
        self.current_time = QTime.currentTime()

        if self.current_time < self.buy_end_time:
            self._buy_end_logged = False  # 매수 가능 시간엔 플래그 초기화
            return True
        else:
            if not getattr(self, '_buy_end_logged', False):
                logger.debug(f"매수 마감 시간 초과 (현재: {self.current_time.toString()}, 마감: {self.buy_end_time.toString()})")
                self._buy_end_logged = True
            return False

    def update_dashboard_display(self):
        """대시보드 업데이트"""
        try:
            # 현재 시간
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # 장 상태
            if self.market_time_check():
                market_status = "[OPEN] 장 운영 중"
            else:
                market_status = "[CLOSED] 장 마감"

            # 전략 설정
            strategy_config = {
                'use_advanced_buy': self.use_advanced_buy,
                'use_advanced_sell': self.use_advanced_sell,
                'risk_profile': self.risk_profile,
                'min_factor_score': self.min_factor_score,
                'max_positions': self.max_positions
            }

            # 계좌 정보 (opw00018에서 가져온 값 사용)
            total_evaluation = int(self.open_api.change_total_eval_price) if hasattr(self.open_api, 'change_total_eval_price') else 0
            d2_deposit_val = int(self.open_api.d2_deposit_before_format) if hasattr(self.open_api, 'd2_deposit_before_format') else 0

            # 예수금: D+2 출금가능금액을 현금으로 사용 (report_generator와 동일 기준)
            # open_api.deposit이 없으므로 항상 d2_deposit_before_format 사용
            deposit = d2_deposit_val

            # 현재 미실현 평가손익 (Kiwoom: 보유 중인 종목 기준)
            floating_profit = int(self.open_api.change_total_eval_profit_loss_price) if hasattr(self.open_api, 'change_total_eval_profit_loss_price') else 0

            # 전체 기간 실현손익 합산 (DB: 매도 완료된 전체 종목)
            # realized_profit 컬럼은 매도 시 업데이트되지 않으므로 가격차×수량으로 계산
            total_realized_profit = 0
            try:
                result = self.open_api.engine_JB.execute(
                    "SELECT COALESCE(SUM((sell_price - purchase_price) * holding_amount), 0) "
                    "FROM all_item_db WHERE sell_date != '0' AND sell_price > 0"
                ).fetchone()
                if result and result[0]:
                    total_realized_profit = int(result[0])
            except Exception as _e:
                logger.debug(f"전체 실현손익 조회 오류: {_e}")

            # 누적 총손익 = 전체 실현손익 + 현재 미실현손익 (수수료 차감 전 gross)
            total_profit_all = total_realized_profit + floating_profit
            total_purchase = int(self.open_api.change_total_purchase_price) if hasattr(self.open_api, 'change_total_purchase_price') else 0

            # 원금 대비 실제 수익률: (현재 총자산 - 초기 원금) / 초기 원금
            total_assets = deposit + total_evaluation
            net_pnl = total_assets - cf.initial_capital
            net_pnl_rate = round(net_pnl / cf.initial_capital * 100, 2) if cf.initial_capital > 0 else 0.0

            # 오늘 실현손익 (DB: 오늘 매도 완료된 종목만)
            today_str = datetime.now().strftime('%Y%m%d')
            today_realized_profit = 0
            today_realized_rate = 0.0
            try:
                result_today = self.open_api.engine_JB.execute(
                    f"SELECT COALESCE(SUM((sell_price - purchase_price) * holding_amount), 0), "
                    f"COALESCE(AVG(sell_rate), 0) "
                    f"FROM all_item_db WHERE LEFT(sell_date, 8) = '{today_str}' "
                    f"AND sell_date != '0' AND sell_price > 0"
                ).fetchone()
                if result_today and result_today[0]:
                    today_realized_profit = int(result_today[0])
                    today_realized_rate = round(float(result_today[1]), 2)
            except Exception as _e:
                logger.debug(f"오늘 실현손익 조회 오류: {_e}")

            account_info = {
                'deposit': deposit,
                'd2_deposit': int(self.open_api.d2_deposit_before_format) if hasattr(self.open_api, 'd2_deposit_before_format') else 0,
                'total_purchase': total_purchase,
                'total_evaluation': total_evaluation,
                'total_assets': total_assets,
                'net_pnl': net_pnl,
                'net_pnl_rate': net_pnl_rate,
                'initial_capital': cf.initial_capital,
                'total_profit': total_profit_all,
                'today_realized_profit': today_realized_profit,
                'today_realized_rate': today_realized_rate,
            }

            # 보유 종목
            positions = []
            trailing_active_count = 0  # 트레일링 스톱 활성화 종목 수

            # 보유 종목 코드 목록으로 atr14/adx 배치 조회 (트레일링 스톱 가격 계산용)
            _indicator_map = {}
            _strategy_map  = {}   # {code: 'A' or 'B'} — 스탑가 계산 배율 결정용
            if hasattr(self.open_api, 'opw00018_output') and 'multi' in self.open_api.opw00018_output:
                try:
                    import pymysql
                    _codes = [str(item[7]) for item in self.open_api.opw00018_output['multi'] if len(item) > 7 and item[7]]
                    if _codes:
                        _con = pymysql.connect(
                            user=cf.db_id, passwd=cf.db_passwd, host=cf.db_ip,
                            db='daily_buy_list', charset='utf8', port=int(cf.db_port)
                        )
                        _cur = _con.cursor()
                        _cur.execute(
                            "SELECT TABLE_NAME FROM information_schema.tables "
                            "WHERE table_schema='daily_buy_list' AND table_name REGEXP '^[0-9]{8}$' "
                            "ORDER BY TABLE_NAME DESC LIMIT 1"
                        )
                        _tbl = _cur.fetchone()
                        if _tbl:
                            _ph = ','.join(['%s'] * len(_codes))
                            _cur.execute(f"SELECT code, adx, atr14 FROM `{_tbl[0]}` WHERE code IN ({_ph})", _codes)
                            for _r in _cur.fetchall():
                                _indicator_map[str(_r[0]).zfill(6)] = {'adx': float(_r[1] or 0), 'atr14': float(_r[2] or 0)}
                        _con.close()

                    # strategy_type 배치 조회 (all_item_db) — B 종목 스탑가 배율 구분용
                    if _codes:
                        _ph2 = ','.join(['%s'] * len(_codes))
                        _rows_st = self.open_api.engine_JB.execute(
                            f"SELECT code, strategy_type FROM all_item_db "
                            f"WHERE code IN ({_ph2}) AND sell_date='0'",
                            _codes
                        ).fetchall()
                        for _r in _rows_st:
                            _strategy_map[str(_r[0]).zfill(6)] = str(_r[1] or 'A')
                except Exception as _e:
                    logger.debug(f"indicator 배치 조회 오류: {_e}")

            if hasattr(self.open_api, 'opw00018_output') and 'multi' in self.open_api.opw00018_output:
                for item in self.open_api.opw00018_output['multi']:
                    try:
                        code = item[7] if len(item) > 7 else ''  # 종목코드 (index 7)
                        current_price = int(item[3]) if len(item) > 3 else 0
                        profit_rate = float(item[5]) if len(item) > 5 else 0.0

                        # realtime_position_monitor에서 highest_price 조회
                        highest_price = None
                        if self.use_advanced_sell and code:
                            try:
                                sql = f"SELECT highest_price FROM realtime_position_monitor WHERE code = '{code}'"
                                result = self.open_api.engine_JB.execute(sql).fetchone()
                                if result:
                                    highest_price = result[0]
                                    # 트레일링 스톱 활성화 체크 (수익 5% 이상)
                                    if profit_rate >= 3.0:  # 추세장 +3% / 횡보장 +5% 중 낮은 기준으로 표시
                                        trailing_active_count += 1
                            except Exception as e:
                                logger.debug(f"highest_price 조회 오류: {e}")

                        # 손절 유예 체크 (매수 후 30분 이내)
                        losscut_delay_active = False
                        if code:
                            try:
                                sql_buy = f"SELECT buy_date FROM all_item_db WHERE code='{code}' AND sell_date='0' ORDER BY buy_date DESC LIMIT 1"
                                buy_result = self.open_api.engine_JB.execute(sql_buy).fetchone()
                                if buy_result and buy_result[0]:
                                    buy_dt = datetime.strptime(str(buy_result[0])[:12], '%Y%m%d%H%M')
                                    elapsed = (datetime.now() - buy_dt).total_seconds() / 60
                                    losscut_delay_active = elapsed < 30
                            except Exception:
                                pass

                        position_data = {
                            'code': code,
                            'name': item[0] if len(item) > 0 else '',
                            'quantity': int(item[1]) if len(item) > 1 else 0,
                            'buy_price': int(item[2]) if len(item) > 2 else 0,
                            'current_price': current_price,
                            'profit_rate': profit_rate,
                            'profit': int(item[4]) if len(item) > 4 else 0,
                            'losscut_delay': losscut_delay_active,
                            'strategy_type': _strategy_map.get(code, 'A'),
                        }

                        # highest_price 추가 (있으면)
                        if highest_price:
                            position_data['highest_price'] = highest_price
                            # 트레일링 스톱 가격 계산
                            ind  = _indicator_map.get(code, {})
                            adx  = ind.get('adx', 0)
                            atr14 = ind.get('atr14', 0)
                            st   = _strategy_map.get(code, 'A')
                            buy_price_disp = position_data.get('buy_price', 0)
                            pct_stop = int(highest_price * 0.95)
                            if atr14 > 0:
                                # exit_strategy.py와 동일 배율 사용
                                if st == 'B':
                                    trail_mult = 1.0   # B(반전): 고정 1.0x
                                else:
                                    trail_mult = 2.5 if adx >= 25 else (2.0 if adx >= 20 else 1.5)  # A(돌파): ADX 기반
                                atr_stop = int(highest_price - atr14 * trail_mult)
                                raw_stop = max(atr_stop, pct_stop)
                            else:
                                raw_stop = pct_stop  # ATR 없으면 5% 고정 fallback
                            floor_price = int(buy_price_disp * 1.01) if buy_price_disp > 0 else 0
                            position_data['trailing_stop_price'] = max(floor_price, raw_stop) if floor_price > 0 else raw_stop
                            # 트레일 활성 여부: highest_gain 기준으로 판단 (exit_strategy.py와 동일)
                            highest_gain_pct = (highest_price / buy_price_disp - 1) * 100 if buy_price_disp > 0 else 0
                            position_data['trail_active'] = highest_gain_pct >= 3.0  # exit_strategy.py 기준 고정

                        positions.append(position_data)

                    except (IndexError, ValueError) as e:
                        logger.debug(f"보유 종목 파싱 오류: {e}")

            # 매수 후보 (realtime_daily_buy_list에서)
            buy_candidates = []
            if hasattr(self.open_api.sf, 'df_realtime_daily_buy_list'):
                df = self.open_api.sf.df_realtime_daily_buy_list
                if df is not None and not df.empty:
                    for _, row in df.head(10).iterrows():
                        buy_candidates.append({
                            'code': row.get('code', ''),
                            'name': row.get('code_name', ''),
                            'price': int(row.get('close', 0)),
                            'score': float(row.get('composite_score', 0)) if 'composite_score' in row else 0,
                            'strategy_type': row.get('strategy_type', ''),
                            'volume_ratio': float(row.get('volume_ratio', 0)) if 'volume_ratio' in row else 0
                        })

            # 매도 시그널: sell_signals_detail(reason/priority 포함)이 있으면 우선 사용
            sell_signals = []
            if hasattr(self, 'sell_signals_detail') and self.sell_signals_detail:
                sell_signals = list(self.sell_signals_detail)
            elif hasattr(self, 'sell_list') and self.sell_list:
                for sell in self.sell_list:
                    profit_rate = float(sell[2]) if self.open_api.mod_gubun == 1 else float(sell[2]) - 100
                    sell_signals.append({
                        'code': sell[0],
                        'name': sell[1],
                        'price': int(sell[3]),
                        'profit_rate': profit_rate,
                        'reason': '매도 시그널',
                        'priority': 50
                    })

            # 포트폴리오 요약
            portfolio_summary = {
                'position_count': len(positions),
                'total_value': account_info['total_evaluation'] + account_info['deposit'],
                'cash_ratio': (account_info['deposit'] / (account_info['total_evaluation'] + account_info['deposit']) * 100) if (account_info['total_evaluation'] + account_info['deposit']) > 0 else 100,
                'daily_profit': account_info['today_realized_profit'],
                'daily_profit_rate': account_info['today_realized_rate'],
                'trailing_active_count': trailing_active_count  # 트레일링 스톱 활성화 종목 수
            }

            # 시스템 상태
            if self.buy_candidates_available == False:
                system_status = "매수 후보 없음 - 대기 중"
            elif self.buy_candidates_available == True:
                system_status = f"매수 후보 {len(buy_candidates)}개 발견 - 모니터링 중"
            else:
                system_status = "초기화 중..."

            # 대시보드 업데이트
            update_dashboard(
                current_time=current_time,
                market_status=market_status,
                strategy_config=strategy_config,
                account_info=account_info,
                positions=positions,
                buy_candidates=buy_candidates,
                sell_signals=sell_signals,
                portfolio_summary=portfolio_summary,
                system_status=system_status
            )

        except Exception as e:
            logger.error(f"대시보드 업데이트 오류: {e}", exc_info=True)

    def process_manual_orders(self):
        """Control Panel(control_panel/)에서 수동 접수한 주문을 처리한다."""
        try:
            rows = self.open_api.engine_JB.execute(
                "SELECT id, order_type, code, code_name, quantity "
                "FROM manual_orders WHERE status='PENDING' ORDER BY id ASC"
            ).fetchall()
        except Exception:
            return  # 테이블 미생성 시 무시

        for row in rows:
            oid   = row[0]
            otype = row[1]
            code  = row[2]
            name  = row[3]
            qty   = int(row[4] or 0)
            try:
                if otype in ('SELL', 'PART_SELL'):
                    if qty <= 0:
                        qty = self.open_api.get_holding_amount(code)
                    if qty > 0:
                        self.open_api.send_order(
                            "cp_sell", "9999", self.open_api.account,
                            2, code, qty, 0, "03", "")
                        logger.info(f"[CP] 수동 매도 실행: {name}({code}) {qty}주")
                elif otype == 'BUY':
                    if qty > 0:
                        self.open_api.send_order(
                            "cp_buy", "9999", self.open_api.account,
                            1, code, qty, 0, "03", "")
                        logger.info(f"[CP] 수동 매수 실행: {name}({code}) {qty}주")
                self.open_api.engine_JB.execute(
                    f"UPDATE manual_orders SET status='EXECUTED', executed_at=NOW() WHERE id={oid}")
            except Exception as e:
                logger.warning(f"[CP] 수동 주문 실패 id={oid}: {e}")
                msg = str(e)[:200].replace("'", "''")
                try:
                    self.open_api.engine_JB.execute(
                        f"UPDATE manual_orders SET status='FAILED', result_msg='{msg}' WHERE id={oid}")
                except Exception:
                    pass

    def run(self):
        """
        메인 루프

        장시간 동안 매수/매도를 자동으로 실행합니다.
        """
        # 파일 로그에만 기록
        logger.info("=" * 80)
        logger.info("🚀 고급 전략 트레이더 시작")
        logger.info(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"장 시작: {self.market_start_time.toString()}, 장 마감: {self.market_end_time.toString()}")
        logger.info("=" * 80)

        # 콘솔에 초기 메시지 표시
        print("\n" + "=" * 100)
        print("[START] 고급 전략 트레이더 시작")
        print(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"장 시작: {self.market_start_time.toString()}, 장 마감: {self.market_end_time.toString()}")
        print("[INFO] 실시간 대시보드 로딩 중...")
        print("[LOG] 자세한 로그: log/jackbot.log")
        print("=" * 100)
        print("\n잠시만 기다려주세요...\n")

        # 메인 루프
        last_date = None
        last_dashboard_update = 0  # 첫 업데이트를 즉시 실행하도록 0으로 설정
        dashboard_update_interval = 1.0  # 1초마다 대시보드 업데이트
        last_heartbeat = 0  # 30분마다 heartbeat 로그

        # 초기 계좌 정보 로드
        try:
            self.open_api.check_balance()
            self.open_api.get_d2_deposit()
        except Exception as e:
            logger.error(f"초기 계좌 정보 로드 실패: {e}")

        while True:
            try:
                # 날짜 업데이트
                self.open_api.date_setting()

                # 날짜가 바뀌면 매수 스캔 플래그 리셋
                if last_date != self.open_api.today:
                    if last_date is not None:
                        logger.info(f"📅 날짜 변경: {last_date} → {self.open_api.today}")
                    last_date = self.open_api.today
                    self.buy_scan_done = False
                    self.buy_candidates_available = None

                # 장시간 체크
                if self.market_time_check():

                    # 보유 종목 확인
                    self.open_api.check_balance()
                    has_positions = len(self.open_api.opw00018_output['multi']) > 0

                    # 보유 종목 및 매수 후보에 따라 대기 시간 조정
                    if has_positions:
                        # 보유 종목 있음 → 실시간 모니터링 (3초)
                        sleep_time = 3
                        logger.debug("💼 보유 종목 있음 - 실시간 모니터링 모드 (3초 간격)")
                    elif self.buy_candidates_available == False:
                        # 보유 종목 없고 + 매수 후보도 없음 → 대기 모드 (60초)
                        sleep_time = 60
                        logger.debug("😴 보유 종목 없음 + 매수 후보 없음 - 대기 모드 (60초 간격)")
                    else:
                        # 보유 종목 없지만 매수 후보 있거나 미스캔 → 30초
                        sleep_time = 30
                        logger.debug("💤 보유 종목 없음 - 매수 대기 모드 (30초 간격)")

                    # 1. 매도 실행 (보유 종목 있을 때만)
                    if has_positions:
                        self.auto_trade_sell_stock()

                    # 1-1. Control Panel 수동 주문 처리
                    self.process_manual_orders()

                    # 2. 매수 조건 확인
                    should_try_buy = (
                        (self.buy_candidates_available is None or self.buy_candidates_available == True) and
                        self.open_api.jango_check() and
                        self.buy_time_check() and
                        self.open_api.buy_check()
                    )

                    if should_try_buy:
                        self.auto_trade_stock()

                    # 대시보드 업데이트 (1초마다)
                    current_time = time.time()
                    if current_time - last_dashboard_update >= dashboard_update_interval:
                        self.update_dashboard_display()
                        last_dashboard_update = current_time

                    # 30분마다 heartbeat 로그 (DeduplicateFilter 우회)
                    if current_time - last_heartbeat >= 1800:
                        heartbeat_record = logger.makeRecord(
                            logger.name, logging.INFO,
                            '(trader_loop)', 0,
                            f"💓 Heartbeat - 보유:{len(self.open_api.opw00018_output.get('multi', []))}종목 | 매수후보:{self.buy_candidates_available} | 루프정상",
                            (), None
                        )
                        heartbeat_record.no_dedup = True
                        logger.handle(heartbeat_record)
                        last_heartbeat = current_time

                    # 종료 플래그 체크
                    if self.should_exit:
                        logger.info("=" * 80)
                        logger.info(f"🚪 자동 종료: {self.exit_reason}")
                        logger.info(f"종료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                        logger.info("=" * 80)
                        break

                    # 다음 루프까지 대기
                    time.sleep(sleep_time)
                else:
                    # 장시간 외
                    if self.auto_exit_after_market_close:
                        # 장 마감 후 대기 시간 체크
                        self.current_time = QTime.currentTime()
                        exit_time = self.market_end_time.addSecs(self.exit_wait_minutes * 60)

                        if self.current_time > exit_time:
                            logger.info("=" * 80)
                            logger.info(f"🕐 장 마감 후 {self.exit_wait_minutes}분 경과 - 자동 종료")
                            logger.info(f"종료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                            # 일일 매매 요약 (DB 기준 - 재시작해도 전체 매매 반영)
                            try:
                                today_str = datetime.now().strftime('%Y%m%d')
                                rows = self.open_api.engine_JB.execute(
                                    f"SELECT purchase_price, sell_price FROM all_item_db WHERE LEFT(sell_date, 8) = '{today_str}' AND simul_num=3"
                                ).fetchall()
                                sell_rates = [(float(r[1]) / float(r[0]) - 1) * 100 for r in rows if float(r[0]) > 0]
                                wins_db = [r for r in sell_rates if r > 0]
                                losses_db = [r for r in sell_rates if r <= 0]
                                avg_profit = sum(wins_db) / len(wins_db) if wins_db else 0
                                avg_loss = sum(losses_db) / len(losses_db) if losses_db else 0
                                logger.info(f"📊 일일 요약 (전체): 매도 {len(sell_rates)}건 (익절 {len(wins_db)} / 손절 {len(losses_db)}) | 평균익절 {avg_profit:.1f}% | 평균손절 {avg_loss:.1f}%")
                            except Exception as _e:
                                logger.warning(f"일일 요약 DB 조회 실패: {_e}")
                                trades = self.trade_history
                                sells = [t for t in trades if t.get('type') == '매도']
                                wins = [t for t in sells if t.get('profit_rate', 0) > 0]
                                losses = [t for t in sells if t.get('profit_rate', 0) <= 0]
                                avg_profit = sum(t['profit_rate'] for t in wins) / len(wins) if wins else 0
                                avg_loss = sum(t['profit_rate'] for t in losses) / len(losses) if losses else 0
                                logger.info(f"📊 일일 요약 (세션): 매도 {len(sells)}건 (익절 {len(wins)} / 손절 {len(losses)}) | 평균익절 {avg_profit:.1f}% | 평균손절 {avg_loss:.1f}%")
                            logger.info("=" * 80)
                            break

                        # 종료 시간까지 대기 (대시보드는 계속 업데이트)
                        remaining_seconds = self.current_time.secsTo(exit_time)

                        # 대시보드 업데이트
                        current_time = time.time()
                        if current_time - last_dashboard_update >= dashboard_update_interval:
                            self.update_dashboard_display()
                            last_dashboard_update = current_time

                        time.sleep(min(1, remaining_seconds))  # 1초마다 체크
                    else:
                        # 자동 종료 안 함: 다음날까지 대기
                        logger.debug("⏰ 장시간 외 - 다음날 장 시작 대기 중")

                        # 대시보드는 계속 업데이트
                        current_time = time.time()
                        if current_time - last_dashboard_update >= dashboard_update_interval:
                            self.update_dashboard_display()
                            last_dashboard_update = current_time

                        time.sleep(1)

            except KeyboardInterrupt:
                logger.info("=" * 80)
                logger.info("🛑 사용자에 의해 중단되었습니다")
                logger.info("=" * 80)
                break

            except Exception as e:
                logger.error(f"⚠️  메인 루프 오류: {e}")
                logger.debug(f"오류 상세:", exc_info=True)
                # 오류가 발생해도 계속 실행
                time.sleep(5)
                continue


def main():
    """
    메인 함수
    """
    try:
        # Qt Application 생성
        app = QApplication(sys.argv)

        # 트레이더 생성 및 실행
        trader = TraderAdvanced()
        trader.run()

        # 완료 메시지
        logger.info("=" * 70)
        logger.info("✅ 트레이더가 정상 종료되었습니다!")
        logger.info("=" * 70)

        # 최종 계좌 정보 업데이트
        trader.open_api.check_balance()
        trader.open_api.get_d2_deposit()

        # 데일리 리포트 생성
        print("\n" + "=" * 100)
        print("📊 트레이딩 결과 리포트 생성 중...")
        try:
            report_path = generate_trader_report(trader, trader.trade_history)
            if report_path:
                print(f"✅ 리포트 생성 완료: {report_path}")
                logger.info(f"리포트 생성 완료: {report_path}")
            else:
                print("⚠️  리포트 생성 실패")
                logger.warning("리포트 생성 실패")
        except Exception as e:
            print(f"⚠️  리포트 생성 오류: {e}")
            logger.error(f"리포트 생성 오류: {e}")

        print("=" * 100)
        print("\n📊 로그: log/jackbot.log")
        print("⏰ 60초 후 자동으로 종료됩니다...\n")

        user_interrupted = False
        try:
            for i in range(60, 0, -1):
                print(f"\r종료까지 {i}초 남음... (Ctrl+C로 중단 가능)", end="", flush=True)
                time.sleep(1)
            print("\n\n프로그램을 종료합니다.")
        except KeyboardInterrupt:
            user_interrupted = True
            print("\n\n사용자가 종료를 취소했습니다. 창이 유지됩니다.")
            print("종료하려면 아무 키나 누르세요...")
            input()

        # 정상 종료 플래그 파일 생성 (batch가 크래시와 구분하는 데 사용)
        if not user_interrupted:
            import pathlib
            flag = pathlib.Path(__file__).parent / 'batch' / 'trader_normal_exit.flag'
            try:
                flag.touch()
                logger.info(f"정상 종료 플래그 생성: {flag}")
            except Exception:
                pass
            sys.exit(0)

    except Exception as e:
        logger.error(f"[ERROR] 치명적 오류: {e}")
        logger.error("오류 상세:", exc_info=True)

        # 오류 발생 시에도 리포트 생성 시도
        if 'trader' in locals():
            print("\n[REPORT] 트레이딩 결과 리포트 생성 중...")
            try:
                report_path = generate_trader_report(trader, trader.trade_history)
                if report_path:
                    print(f"[OK] 리포트 생성 완료: {report_path}")
            except:
                pass

        # 오류 발생 시에도 60초 대기
        print("\n[WAIT] 60초 후 자동으로 종료됩니다... (로그 확인 가능)")
        print("[LOG] 로그: log/jackbot.log\n")

        user_interrupted = False
        try:
            for i in range(60, 0, -1):
                print(f"\r종료까지 {i}초 남음... (Ctrl+C로 중단 가능)", end="", flush=True)
                time.sleep(1)
            print("\n\n프로그램을 종료합니다.")
        except KeyboardInterrupt:
            user_interrupted = True
            print("\n\n사용자가 종료를 취소했습니다. 창이 유지됩니다.")
            print("종료하려면 아무 키나 누르세요...")
            input()

        # 60초 정상 완료 시 에러 코드로 종료 (batch에서 cmd 종료 처리)
        if not user_interrupted:
            sys.exit(1)


if __name__ == "__main__":
    main()
