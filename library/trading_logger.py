"""
매매 이벤트 전용 로깅 시스템

중요한 매매 이벤트를 별도 파일에 기록합니다:
- 매수/매도 체결
- 일일 수익률
- 잔고 변화
- 내일 매수 후보
"""

import os
import logging
import pathlib
from logging.handlers import TimedRotatingFileHandler
import datetime
from typing import Dict, List, Optional

# 로그 디렉토리 설정
LOG_DIR = pathlib.Path(__file__).parent.parent.absolute() / 'logs'
os.makedirs(LOG_DIR, exist_ok=True)

# 이벤트 전용 로거 생성
event_logger = logging.getLogger('trading_events')
event_logger.setLevel(logging.INFO)

# 파일 핸들러 (매일 자정에 로테이트)
event_file = LOG_DIR / 'trading_events.log'
event_handler = TimedRotatingFileHandler(
    event_file,
    when="midnight",
    encoding='utf-8',
    backupCount=10  # 10일치 보관
)
event_handler.suffix = "%Y%m%d"

# 포맷터 (읽기 쉬운 형식)
event_formatter = logging.Formatter(
    '%(asctime)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
event_handler.setFormatter(event_formatter)
event_logger.addHandler(event_handler)

# 콘솔 출력도 추가 (선택적)
console_handler = logging.StreamHandler()
console_handler.setFormatter(event_formatter)
event_logger.addHandler(console_handler)


class TradingEventLogger:
    """매매 이벤트 로깅 클래스"""

    def __init__(self):
        self.logger = event_logger

    def log_buy(self, code: str, name: str, price: int, quantity: int, total_value: int, reason: str = ""):
        """매수 체결 로그"""
        msg = (
            f"📈 [매수] {name}({code}) | "
            f"가격: {price:,}원 | 수량: {quantity}주 | "
            f"총액: {total_value:,}원"
        )
        if reason:
            msg += f" | 사유: {reason}"
        self.logger.info(msg)

    def log_sell(self, code: str, name: str, price: int, quantity: int,
                 total_value: int, profit: int, profit_rate: float, reason: str = ""):
        """매도 체결 로그"""
        profit_emoji = "🟢" if profit >= 0 else "🔴"
        msg = (
            f"{profit_emoji} [매도] {name}({code}) | "
            f"가격: {price:,}원 | 수량: {quantity}주 | "
            f"총액: {total_value:,}원 | "
            f"수익: {profit:+,}원 ({profit_rate:+.2f}%)"
        )
        if reason:
            msg += f" | 사유: {reason}"
        self.logger.info(msg)

    def log_daily_summary(self, date: str, total_profit: int, total_profit_rate: float,
                         win_count: int, loss_count: int, balance: int, position_count: int):
        """일일 수익 요약 로그"""
        profit_emoji = "🟢" if total_profit >= 0 else "🔴"
        self.logger.info("=" * 80)
        self.logger.info(f"📊 [일일 요약] {date}")
        self.logger.info(
            f"{profit_emoji} 총 수익: {total_profit:+,}원 ({total_profit_rate:+.2f}%) | "
            f"익절: {win_count}건 | 손절: {loss_count}건"
        )
        self.logger.info(
            f"💰 잔고: {balance:,}원 | 보유 종목: {position_count}개"
        )
        self.logger.info("=" * 80)

    def log_balance_change(self, before: int, after: int, change: int, reason: str):
        """잔고 변화 로그"""
        change_emoji = "📈" if change >= 0 else "📉"
        self.logger.info(
            f"{change_emoji} [잔고 변화] {before:,}원 → {after:,}원 "
            f"({change:+,}원) | 사유: {reason}"
        )

    def log_buy_candidates(self, date: str, candidates: List[Dict]):
        """내일 매수 후보 로그"""
        self.logger.info("-" * 80)
        self.logger.info(f"🎯 [매수 후보] {date} (총 {len(candidates)}개)")
        for idx, candidate in enumerate(candidates[:10], 1):  # 상위 10개만
            code = candidate.get('code', '')
            name = candidate.get('name', '')
            score = candidate.get('score', 0)
            price = candidate.get('current_price', 0)
            strategy = candidate.get('strategy_type', '')

            self.logger.info(
                f"  {idx}. {name}({code}) | "
                f"점수: {score:.1f} | 가격: {price:,}원 | "
                f"전략: {strategy}"
            )
        self.logger.info("-" * 80)

    def log_strategy_signal(self, code: str, name: str, signal_type: str,
                           score: float, details: str = ""):
        """전략 시그널 로그"""
        signal_emoji = {
            'BUY': '🟢',
            'SELL': '🔴',
            'HOLD': '⚪',
            'TRAILING_STOP': '🟡'
        }.get(signal_type, '⚪')

        msg = (
            f"{signal_emoji} [시그널] {signal_type} | "
            f"{name}({code}) | 점수: {score:.1f}"
        )
        if details:
            msg += f" | {details}"
        self.logger.info(msg)

    def log_system_event(self, event_type: str, message: str):
        """시스템 이벤트 로그"""
        event_emoji = {
            'START': '🚀',
            'STOP': '🛑',
            'ERROR': '❌',
            'WARNING': '⚠️',
            'INFO': 'ℹ️'
        }.get(event_type, 'ℹ️')

        self.logger.info(f"{event_emoji} [{event_type}] {message}")

    def log_market_status(self, status: str, time_str: str, message: str = ""):
        """장 상태 로그"""
        status_emoji = {
            'OPEN': '🔔',
            'CLOSE': '🔕',
            'PRE_MARKET': '⏰',
            'AFTER_MARKET': '🌙'
        }.get(status, '📌')

        msg = f"{status_emoji} [{status}] {time_str}"
        if message:
            msg += f" | {message}"
        self.logger.info(msg)


# 전역 인스턴스
trading_logger = TradingEventLogger()
