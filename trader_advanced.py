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
from library.trading_dashboard import update_dashboard
from library.report_generator import generate_trader_report
from PyQt5.QtWidgets import *
import sys
import os
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
        """장 마감(15:30) 후 이 시간만큼 대기한 뒤 종료"""

        # 매수 후보 없을 시 자동 종료 여부
        self.exit_on_no_candidates = True
        """
        True: 매수 후보 없으면 즉시 종료 (권장, 일봉 collector용)
        False: 60초마다 체크 계속 (분봉 collector 대비)
        """

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

        # 종료 요청 플래그
        self.should_exit = False
        self.exit_reason = ""

        # 오늘의 거래 내역 추적
        self.trade_history = []

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

                # 고급 청산이 실패하거나 데이터가 없으면 기본 방식 사용
                if sell_signals is None or len(sell_signals) == 0:
                    # 보유 종목이 있는데 시그널이 없으면 데이터 문제일 수 있음
                    self.open_api.check_balance()
                    has_positions = len(self.open_api.opw00018_output['multi']) > 0

                    if has_positions:
                        logger.warning("⚠️  고급 청산 시그널 없음 - 기본 방식으로 전환")
                        logger.info("💡 일봉 데이터가 없을 수 있습니다. collector_v3.py 실행을 확인하세요")
                        self.open_api.sf.get_date_for_simul()
                        self.sell_list = self.open_api.sf.get_sell_list(
                            len(self.open_api.sf.date_rows)
                        )
                        logger.info(f"기본 청산: {len(self.sell_list)}개 매도 시그널")

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
                        # 종목명 찾기
                        stock_name = ""
                        for item in self.open_api.opw00018_output['multi']:
                            if item[6] == sell_code:
                                stock_name = item[0]
                                break

                        # 매도 사유 결정
                        if sell_rate < 0:
                            logger.info(f"💔 손절 매도: {sell_code} ({sell_rate:.2f}%) - {sell_num}주")
                            trade_type = "손절매도"
                        else:
                            logger.info(f"💰 익절 매도: {sell_code} ({sell_rate:.2f}%) - {sell_num}주")
                            trade_type = "익절매도"

                        # 거래 내역 기록
                        self.trade_history.append({
                            'time': datetime.now().strftime('%H:%M:%S'),
                            'type': '매도',
                            'code': sell_code,
                            'name': stock_name,
                            'price': int(self.sell_list[i][2]) if len(self.sell_list[i]) > 2 else 0,
                            'quantity': sell_num,
                            'strategy': trade_type,
                            'profit_rate': sell_rate
                        })

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

    def update_dashboard_display(self):
        """대시보드 업데이트"""
        try:
            # 현재 시간
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # 장 상태
            if self.market_time_check():
                market_status = "🟢 장 운영 중"
            else:
                market_status = "🔴 장 마감"

            # 전략 설정
            strategy_config = {
                'use_advanced_buy': self.use_advanced_buy,
                'use_advanced_sell': self.use_advanced_sell,
                'risk_profile': self.risk_profile,
                'min_factor_score': self.min_factor_score,
                'max_positions': self.max_positions
            }

            # 계좌 정보
            account_info = {
                'deposit': int(self.open_api.deposit) if hasattr(self.open_api, 'deposit') else 0,
                'd2_deposit': int(self.open_api.d2_deposit_before_format) if hasattr(self.open_api, 'd2_deposit_before_format') else 0,
                'total_purchase': int(self.open_api.total_purchase_price) if hasattr(self.open_api, 'total_purchase_price') else 0,
                'total_evaluation': int(self.open_api.total_evaluation_price) if hasattr(self.open_api, 'total_evaluation_price') else 0,
                'total_profit': int(self.open_api.total_evaluation_profit_loss_price) if hasattr(self.open_api, 'total_evaluation_profit_loss_price') else 0,
                'total_profit_rate': float(self.open_api.total_earning_rate) if hasattr(self.open_api, 'total_earning_rate') else 0.0
            }

            # 보유 종목
            positions = []
            if hasattr(self.open_api, 'opw00018_output') and 'multi' in self.open_api.opw00018_output:
                for item in self.open_api.opw00018_output['multi']:
                    try:
                        positions.append({
                            'code': item[6] if len(item) > 6 else '',
                            'name': item[0] if len(item) > 0 else '',
                            'quantity': int(item[1]) if len(item) > 1 else 0,
                            'buy_price': int(item[2]) if len(item) > 2 else 0,
                            'current_price': int(item[3]) if len(item) > 3 else 0,
                            'profit_rate': float(item[5]) if len(item) > 5 else 0.0,
                            'profit': int(item[4]) if len(item) > 4 else 0
                        })
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

            # 매도 시그널
            sell_signals = []
            if hasattr(self, 'sell_list') and self.sell_list:
                for sell in self.sell_list:
                    sell_signals.append({
                        'code': sell[0],
                        'name': '',  # 종목명은 별도로 조회 필요
                        'price': int(sell[2]),
                        'profit_rate': float(sell[1]),
                        'reason': '매도 시그널',
                        'priority': 50
                    })

            # 포트폴리오 요약
            portfolio_summary = {
                'position_count': len(positions),
                'total_value': account_info['total_evaluation'] + account_info['deposit'],
                'cash_ratio': (account_info['deposit'] / (account_info['total_evaluation'] + account_info['deposit']) * 100) if (account_info['total_evaluation'] + account_info['deposit']) > 0 else 100,
                'daily_profit': account_info['total_profit'],
                'daily_profit_rate': account_info['total_profit_rate']
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
        print("🚀 고급 전략 트레이더 시작")
        print(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"장 시작: {self.market_start_time.toString()}, 장 마감: {self.market_end_time.toString()}")
        print("📊 실시간 대시보드 로딩 중...")
        print("📝 자세한 로그: log/jackbot.log")
        print("=" * 100)
        print("\n잠시만 기다려주세요...\n")

        # 메인 루프
        last_date = None
        last_dashboard_update = 0  # 첫 업데이트를 즉시 실행하도록 0으로 설정
        dashboard_update_interval = 1.0  # 1초마다 대시보드 업데이트

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
                            logger.info("=" * 80)
                            break

                        # 종료 시간까지 대기 (대시보드는 계속 업데이트)
                        remaining_seconds = self.current_time.secsTo(exit_time)
                        logger.debug(f"⏰ 장 마감 후 대기 중 (종료까지 {remaining_seconds//60}분 {remaining_seconds%60}초)")

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

        # 60초 정상 완료 시 cmd 창 닫기
        if not user_interrupted:
            os.system("taskkill /f /im cmd.exe")

    except Exception as e:
        logger.error(f"❌ 치명적 오류: {e}")
        logger.debug("오류 상세:", exc_info=True)

        # 오류 발생 시에도 리포트 생성 시도
        if 'trader' in locals():
            print("\n📊 트레이딩 결과 리포트 생성 중...")
            try:
                report_path = generate_trader_report(trader, trader.trade_history)
                if report_path:
                    print(f"✅ 리포트 생성 완료: {report_path}")
            except:
                pass

        # 오류 발생 시에도 60초 대기
        print("\n⏰ 60초 후 자동으로 종료됩니다... (로그 확인 가능)")
        print("📊 로그: log/jackbot.log\n")

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

        # 60초 정상 완료 시 cmd 창 닫기
        if not user_interrupted:
            os.system("taskkill /f /im cmd.exe")

        sys.exit(1)


if __name__ == "__main__":
    main()
