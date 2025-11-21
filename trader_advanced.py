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

from library.open_api import *
from PyQt5.QtWidgets import *
import sys

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

        # ==================================================
        # 📊 고급 전략 파라미터
        # ==================================================

        # 멀티팩터 최소 스코어 (0-100)
        self.min_factor_score = 70.0

        # 최대 동시 보유 종목 수
        self.max_positions = 10

        # 일일 최대 손실 한도 (%)
        self.max_daily_loss_pct = -8.0

        # ==================================================
        # 🔄 매수 후보 스캔 상태 플래그
        # ==================================================

        # 오늘 매수 후보 스캔 완료 여부
        self.buy_scan_done = False

        # 매수 후보 존재 여부 (None: 미스캔, True: 있음, False: 없음)
        self.buy_candidates_available = None

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
        logger.info("=" * 80)

    def init_advanced_strategy(self):
        """
        고급 전략 엔진 초기화
        """
        try:
            if self.use_advanced_buy or self.use_advanced_sell:
                logger.info("🔧 고급 전략 엔진 초기화 중...")

                # 포트폴리오 가치 계산
                self.open_api.check_balance()
                self.open_api.get_d2_deposit()

                portfolio_value = int(self.open_api.d2_deposit_before_format) + \
                                int(self.open_api.total_purchase_price)

                # 엔진 초기화
                success = self.open_api.init_advanced_trading_engine(portfolio_value)

                if success:
                    logger.info(f"✅ 고급 전략 엔진 초기화 완료 (포트폴리오: {portfolio_value:,}원)")
                    self.advanced_engine_ready = True
                else:
                    logger.warning("⚠️  고급 전략 엔진 초기화 실패 - 기존 방식 사용")
                    self.advanced_engine_ready = False
                    self.use_advanced_buy = False
                    self.use_advanced_sell = False
            else:
                logger.info("ℹ️  기본 전략 사용 (고급 전략 미사용)")
                self.advanced_engine_ready = False

        except Exception as e:
            logger.error(f"❌ 고급 전략 엔진 초기화 오류: {e}")
            logger.warning("기본 전략으로 전환합니다")
            self.advanced_engine_ready = False
            self.use_advanced_buy = False
            self.use_advanced_sell = False

    def auto_trade_stock(self):
        """
        자동 매수 함수

        고급 전략 설정에 따라 매수 방식 선택
        """
        logger.debug("auto_trade_stock 함수 실행")

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
                    else:
                        # 확인 불가 시 안전하게 True로 설정
                        self.buy_candidates_available = True
            else:
                # 기존 방식으로 매수
                logger.info("📋 기본 방식으로 매수")
                self.open_api.get_today_buy_list()

        except Exception as e:
            logger.error(f"❌ 매수 실행 오류: {e}")
            logger.warning("기본 방식으로 재시도합니다")
            self.open_api.get_today_buy_list()

    def get_sell_list_trade(self):
        """
        매도 리스트 생성

        고급 전략 설정에 따라 매도 방식 선택
        """
        logger.debug("get_sell_list_trade 함수 실행")

        # 체결 확인
        self.open_api.chegyul_check()

        # 수익률 업데이트
        self.open_api.rate_check()

        try:
            if self.use_advanced_sell and self.advanced_engine_ready:
                # 고급 청산 전략
                logger.info("🎯 고급 청산 전략으로 매도 리스트 생성")

                sell_signals = self.open_api.get_advanced_sell_list()

                # 고급 매도 리스트를 기존 형식으로 변환
                self.sell_list = []
                for signal in sell_signals:
                    if signal['decision']['should_exit']:
                        # (code, rate, present_price, valuation_profit) 형식
                        self.sell_list.append([
                            signal['code'],
                            signal.get('pnl_pct', 0),
                            signal.get('current_price', 0),
                            0  # valuation_profit (미사용)
                        ])

                logger.info(f"고급 청산: {len(self.sell_list)}개 매도 시그널")

            else:
                # 기존 방식
                logger.info("📉 기본 방식으로 매도 리스트 생성")
                self.open_api.sf.get_date_for_simul()
                self.sell_list = self.open_api.sf.get_sell_list(
                    len(self.open_api.sf.date_rows)
                )

            logger.debug(f"매도 리스트: {self.sell_list}")

        except Exception as e:
            logger.error(f"❌ 매도 리스트 생성 오류: {e}")
            logger.warning("기본 방식으로 재시도합니다")
            self.open_api.sf.get_date_for_simul()
            self.sell_list = self.open_api.sf.get_sell_list(
                len(self.open_api.sf.date_rows)
            )

    def auto_trade_sell_stock(self):
        """
        자동 매도 실행
        """
        logger.debug("auto_trade_sell_stock 함수 실행")

        try:
            # 계좌 정보 업데이트
            self.open_api.check_balance()

            # possessed_item 테이블 동기화
            self.open_api.db_to_possesed_item()

            # 봇 꺼졌을 때 매도 반영
            self.open_api.final_chegyul_check()

            # 매도 리스트 가져오기
            self.get_sell_list_trade()

            # 매도 실행
            for i in range(len(self.sell_list)):
                try:
                    # 종목 코드
                    sell_code = self.sell_list[i][0]

                    # 수익률
                    sell_rate = float(self.sell_list[i][1])

                    # 매도 수량
                    sell_num = self.open_api.get_holding_amount(sell_code)

                    if sell_num == False or sell_num == 0:
                        continue

                    if sell_code and sell_code != "0":
                        if sell_rate < 0:
                            logger.info(f"💔 손절 매도: {sell_code} ({sell_rate:.2f}%) - {sell_num}주")
                        else:
                            logger.info(f"💰 익절 매도: {sell_code} ({sell_rate:.2f}%) - {sell_num}주")

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
            return True
        else:
            logger.debug(f"매수 마감 시간 초과 (현재: {self.current_time.toString()}, 마감: {self.buy_end_time.toString()})")
            return False

    def run(self):
        """
        메인 루프

        장시간 동안 매수/매도를 자동으로 실행합니다.
        """
        print("\n" + "=" * 80)
        print("🚀 고급 전략 트레이더 실행 중...")
        print("=" * 80)
        print(f"시작 시간: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"장 시작: {self.market_start_time.toString()}")
        print(f"장 마감: {self.market_end_time.toString()}")
        print(f"매수 마감: {self.buy_end_time.toString()}")
        print("=" * 80)
        print()

        logger.info("메인 루프 시작")

        # 메인 루프
        last_date = None

        while True:
            try:
                # 날짜 업데이트
                self.open_api.date_setting()

                # 날짜가 바뀌면 매수 스캔 플래그 리셋
                if last_date != self.open_api.today:
                    if last_date is not None:
                        logger.info(f"📅 날짜 변경: {last_date} → {self.open_api.today}")
                        logger.info("🔄 매수 후보 스캔 플래그 리셋")
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
                        # 보유 종목 있음 → 실시간 모니터링 (0.3초)
                        sleep_time = 0.3
                        logger.debug("💼 보유 종목 있음 - 실시간 모니터링 모드")
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

                    # 2. 매수 조건 확인
                    # - 매수 후보가 없으면 스킵 (첫 스캔 제외)
                    # - 잔액 있는지
                    # - 매수 시간인지
                    # - 매수 정지 옵션 체크
                    should_try_buy = (
                        # 첫 스캔이거나 매수 후보가 있는 경우만
                        (self.buy_candidates_available is None or self.buy_candidates_available == True) and
                        self.open_api.jango_check() and
                        self.buy_time_check() and
                        self.open_api.buy_check()
                    )

                    if should_try_buy:
                        # 매수 실행
                        self.auto_trade_stock()

                    # 다음 루프까지 대기
                    time.sleep(sleep_time)
                else:
                    # 장시간 외: 10초마다 체크
                    time.sleep(10)

            except KeyboardInterrupt:
                logger.info("\n사용자에 의해 중단되었습니다")
                print("\n" + "=" * 80)
                print("🛑 트레이더 중단")
                print("=" * 80)
                break

            except Exception as e:
                logger.error(f"메인 루프 오류: {e}")
                import traceback
                traceback.print_exc()
                # 오류가 발생해도 계속 실행
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

    except Exception as e:
        print(f"\n❌ 치명적 오류: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
