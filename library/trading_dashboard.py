"""
실시간 트레이딩 대시보드
Windows에서 watch 명령어처럼 동작하는 실시간 모니터링 화면
"""

import os
import sys
from datetime import datetime
from typing import Dict, List, Optional


class TradingDashboard:
    """
    실시간 트레이딩 대시보드

    화면을 지우고 최신 정보로 갱신하여 표시
    """

    def __init__(self):
        self.last_update = None
        self.dashboard_data = {
            'current_time': '',
            'market_status': '',
            'strategy_config': {},
            'account_info': {},
            'positions': [],
            'buy_candidates': [],
            'sell_signals': [],
            'portfolio_summary': {},
            'recent_trades': [],
            'system_status': ''
        }

    def clear_screen(self):
        """화면 지우기"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def update_data(
        self,
        current_time: str = None,
        market_status: str = None,
        strategy_config: Dict = None,
        account_info: Dict = None,
        positions: List = None,
        buy_candidates: List = None,
        sell_signals: List = None,
        portfolio_summary: Dict = None,
        recent_trades: List = None,
        system_status: str = None
    ):
        """대시보드 데이터 업데이트"""
        if current_time:
            self.dashboard_data['current_time'] = current_time
        if market_status:
            self.dashboard_data['market_status'] = market_status
        if strategy_config is not None:
            self.dashboard_data['strategy_config'] = strategy_config
        if account_info is not None:
            self.dashboard_data['account_info'] = account_info
        if positions is not None:
            self.dashboard_data['positions'] = positions
        if buy_candidates is not None:
            self.dashboard_data['buy_candidates'] = buy_candidates
        if sell_signals is not None:
            self.dashboard_data['sell_signals'] = sell_signals
        if portfolio_summary is not None:
            self.dashboard_data['portfolio_summary'] = portfolio_summary
        if recent_trades is not None:
            self.dashboard_data['recent_trades'] = recent_trades
        if system_status:
            self.dashboard_data['system_status'] = system_status

        self.last_update = datetime.now()

    def render(self):
        """대시보드 렌더링"""
        self.clear_screen()

        # 헤더
        print("=" * 100)
        print("🚀 고급 전략 트레이더 - 실시간 모니터링 대시보드".center(100))
        print("=" * 100)
        print(f"현재 시간: {self.dashboard_data['current_time']}")
        print(f"장 상태: {self.dashboard_data['market_status']}")
        print(f"최종 업데이트: {self.last_update.strftime('%Y-%m-%d %H:%M:%S') if self.last_update else 'N/A'}")
        print("=" * 100)
        print()

        # 전략 설정
        if self.dashboard_data['strategy_config']:
            self._render_strategy_config()

        # 계좌 정보
        if self.dashboard_data['account_info']:
            self._render_account_info()

        # 포트폴리오 요약
        if self.dashboard_data['portfolio_summary']:
            self._render_portfolio_summary()

        # 보유 종목
        if self.dashboard_data['positions']:
            self._render_positions()

        # 매수 후보
        if self.dashboard_data['buy_candidates']:
            self._render_buy_candidates()

        # 매도 시그널
        if self.dashboard_data['sell_signals']:
            self._render_sell_signals()

        # 최근 거래
        if self.dashboard_data['recent_trades']:
            self._render_recent_trades()

        # 시스템 상태
        if self.dashboard_data['system_status']:
            print(f"\n💬 시스템 상태: {self.dashboard_data['system_status']}")

        # 푸터
        print()
        print("=" * 100)
        print("💡 종료: Ctrl+C | 자세한 로그: log/jackbot.log".center(100))
        print("=" * 100)

    def _render_strategy_config(self):
        """전략 설정 표시"""
        config = self.dashboard_data['strategy_config']
        print("📊 전략 설정")
        print("-" * 100)
        print(f"  고급 매수 전략: {'사용' if config.get('use_advanced_buy') else '미사용'}")
        print(f"  고급 매도 전략: {'사용' if config.get('use_advanced_sell') else '미사용'}")
        print(f"  리스크 프로필: {config.get('risk_profile', 'N/A')}")
        print(f"  최소 팩터 스코어: {config.get('min_factor_score', 'N/A')}")
        print(f"  최대 보유 종목: {config.get('max_positions', 'N/A')}개")
        print()

    def _render_account_info(self):
        """계좌 정보 표시"""
        account = self.dashboard_data['account_info']
        print("💰 계좌 정보")
        print("-" * 100)
        print(f"  예수금: {account.get('deposit', 0):,}원")
        print(f"  D+2 예수금: {account.get('d2_deposit', 0):,}원")
        print(f"  총 매입금액: {account.get('total_purchase', 0):,}원")
        print(f"  총 평가금액: {account.get('total_evaluation', 0):,}원")
        print(f"  총 평가손익: {account.get('total_profit', 0):,}원 ({account.get('total_profit_rate', 0):.2f}%)")
        print()

    def _render_portfolio_summary(self):
        """포트폴리오 요약 표시"""
        portfolio = self.dashboard_data['portfolio_summary']
        print("📈 포트폴리오 요약")
        print("-" * 100)
        print(f"  보유 종목 수: {portfolio.get('position_count', 0)}개")
        print(f"  포트폴리오 가치: {portfolio.get('total_value', 0):,}원")
        print(f"  현금 비율: {portfolio.get('cash_ratio', 0):.1f}%")
        print(f"  오늘 수익: {portfolio.get('daily_profit', 0):,}원 ({portfolio.get('daily_profit_rate', 0):.2f}%)")
        print()

    def _render_positions(self):
        """보유 종목 표시"""
        positions = self.dashboard_data['positions']
        print(f"💼 보유 종목 ({len(positions)}개)")
        print("-" * 100)
        if positions:
            print(f"  {'종목코드':<10} {'종목명':<15} {'보유수량':>10} {'매입가':>12} {'현재가':>12} {'수익률':>10} {'평가손익':>12}")
            print("  " + "-" * 95)
            for pos in positions[:10]:  # 최대 10개만 표시
                profit_color = "🟢" if pos.get('profit_rate', 0) > 0 else "🔴" if pos.get('profit_rate', 0) < 0 else "⚪"
                print(f"  {pos.get('code', ''):<10} {pos.get('name', ''):<15} "
                      f"{pos.get('quantity', 0):>10} {pos.get('buy_price', 0):>12,}원 "
                      f"{pos.get('current_price', 0):>12,}원 "
                      f"{profit_color} {pos.get('profit_rate', 0):>7.2f}% {pos.get('profit', 0):>12,}원")
            if len(positions) > 10:
                print(f"  ... 외 {len(positions) - 10}개 종목")
        else:
            print("  보유 종목이 없습니다.")
        print()

    def _render_buy_candidates(self):
        """매수 후보 표시"""
        candidates = self.dashboard_data['buy_candidates']
        print(f"🎯 매수 후보 ({len(candidates)}개)")
        print("-" * 100)
        if candidates:
            print(f"  {'종목코드':<10} {'종목명':<15} {'현재가':>12} {'스코어':>8} {'전략타입':<20} {'거래량비율':>10}")
            print("  " + "-" * 95)
            for cand in candidates[:10]:  # 최대 10개만 표시
                print(f"  {cand.get('code', ''):<10} {cand.get('name', ''):<15} "
                      f"{cand.get('price', 0):>12,}원 {cand.get('score', 0):>8.1f} "
                      f"{cand.get('strategy_type', ''):<20} {cand.get('volume_ratio', 0):>9.1f}x")
            if len(candidates) > 10:
                print(f"  ... 외 {len(candidates) - 10}개 종목")
        else:
            print("  매수 후보가 없습니다.")
        print()

    def _render_sell_signals(self):
        """매도 시그널 표시"""
        signals = self.dashboard_data['sell_signals']
        print(f"⚠️  매도 시그널 ({len(signals)}개)")
        print("-" * 100)
        if signals:
            print(f"  {'종목코드':<10} {'종목명':<15} {'현재가':>12} {'수익률':>10} {'시그널타입':<25} {'우선순위':>8}")
            print("  " + "-" * 95)
            for sig in signals:
                signal_icon = "💔" if sig.get('profit_rate', 0) < 0 else "💰"
                print(f"  {signal_icon} {sig.get('code', ''):<8} {sig.get('name', ''):<15} "
                      f"{sig.get('price', 0):>12,}원 {sig.get('profit_rate', 0):>9.2f}% "
                      f"{sig.get('reason', ''):<25} {sig.get('priority', 0):>8}")
        else:
            print("  매도 시그널이 없습니다.")
        print()

    def _render_recent_trades(self):
        """최근 거래 표시"""
        trades = self.dashboard_data['recent_trades']
        print(f"📝 최근 거래 ({len(trades)}개)")
        print("-" * 100)
        if trades:
            print(f"  {'시간':<10} {'타입':<6} {'종목코드':<10} {'종목명':<15} {'가격':>12} {'수량':>8} {'수익률':>10}")
            print("  " + "-" * 95)
            for trade in trades[:5]:  # 최대 5개만 표시
                trade_icon = "🟢" if trade.get('type') == '매수' else "🔴"
                print(f"  {trade.get('time', ''):<10} {trade_icon} {trade.get('type', ''):<4} "
                      f"{trade.get('code', ''):<10} {trade.get('name', ''):<15} "
                      f"{trade.get('price', 0):>12,}원 {trade.get('quantity', 0):>8} "
                      f"{trade.get('profit_rate', 0):>9.2f}%")
        else:
            print("  최근 거래 내역이 없습니다.")
        print()


# 전역 대시보드 인스턴스
_dashboard = None


def get_dashboard() -> TradingDashboard:
    """대시보드 싱글톤 인스턴스 가져오기"""
    global _dashboard
    if _dashboard is None:
        _dashboard = TradingDashboard()
    return _dashboard


def update_dashboard(**kwargs):
    """대시보드 업데이트 및 렌더링"""
    dashboard = get_dashboard()
    dashboard.update_data(**kwargs)
    dashboard.render()
