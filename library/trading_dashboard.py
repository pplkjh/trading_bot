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
        # Windows 콘솔을 UTF-8로 전환 (이모지/한글 동시 출력)
        import sys, io
        if sys.platform == 'win32':
            os.system('chcp 65001 >nul 2>&1')
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
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

        # ── 헤더 ──────────────────────────────────────────────────────────────
        print("=" * 100)
        print("[DASHBOARD] 고급 전략 트레이더 - 실시간 모니터링".center(100))
        print("=" * 100)

        # 상태 한 줄 요약
        config = self.dashboard_data.get('strategy_config', {})
        portfolio = self.dashboard_data.get('portfolio_summary', {})
        status_parts = [
            self.dashboard_data['current_time'],
            self.dashboard_data['market_status'],
        ]
        if config:
            buy_tag  = "고급매수" if config.get('use_advanced_buy') else "기본매수"
            sell_tag = "고급매도" if config.get('use_advanced_sell') else "기본매도"
            status_parts.append(f"전략: {buy_tag}/{sell_tag}  스코어≥{config.get('min_factor_score','?')}")
        if portfolio:
            trail = portfolio.get('trailing_active_count', 0)
            if trail:
                status_parts.append(f"🟢 트레일링 {trail}개")
        sys_status = self.dashboard_data.get('system_status', '')
        if sys_status:
            status_parts.append(sys_status)
        print("  " + "  |  ".join(status_parts))
        print("=" * 100)
        print()

        # ── 계좌 + 포트폴리오 (통합) ─────────────────────────────────────────
        if self.dashboard_data['account_info']:
            self._render_account_info()

        # ── 보유 종목 ────────────────────────────────────────────────────────
        if self.dashboard_data['positions']:
            self._render_positions()

        # ── 매수 후보 ────────────────────────────────────────────────────────
        if self.dashboard_data['buy_candidates']:
            self._render_buy_candidates()

        # ── 매도 시그널 ──────────────────────────────────────────────────────
        if self.dashboard_data['sell_signals']:
            self._render_sell_signals()

        # ── 최근 거래 ────────────────────────────────────────────────────────
        if self.dashboard_data['recent_trades']:
            self._render_recent_trades()

        # 푸터
        print()
        print("=" * 100)
        print("[INFO] 종료: Ctrl+C | 로그: log/jackbot.log".center(100))
        print("=" * 100)
        sys.stdout.flush()

    def _render_account_info(self):
        """계좌 + 포트폴리오 통합 표시"""
        account  = self.dashboard_data['account_info']
        portfolio = self.dashboard_data.get('portfolio_summary', {})

        print("[ACCOUNT] 계좌 현황")
        print("-" * 100)

        # 총자산 / 원금 대비 손익
        total_assets    = account.get('total_assets', account.get('deposit', 0) + account.get('total_evaluation', 0))
        net_pnl         = account.get('net_pnl', 0)
        net_pnl_rate    = account.get('net_pnl_rate', 0.0)
        initial_capital = account.get('initial_capital', 0)
        sign = "+" if net_pnl >= 0 else ""
        print(f"  총 자산:        {total_assets:>15,}원   (예수금 {account.get('deposit',0):,} + 평가 {account.get('total_evaluation',0):,})")
        if initial_capital:
            print(f"  원금 대비 손익: {sign}{net_pnl:>14,}원   ({sign}{net_pnl_rate:.2f}%)  ← 초기 원금 {initial_capital:,}원 기준")

        # 누적 총손익 (gross, 수수료 전)
        total_profit = account.get('total_profit', 0)
        tp_sign = "+" if total_profit >= 0 else ""
        print(f"  누적 총손익:    {tp_sign}{total_profit:>14,}원   (전체기간 실현+미실현, 수수료 차감 전)")

        # 오늘 실현손익
        today_profit = account.get('today_realized_profit', 0)
        today_rate   = account.get('today_realized_rate', 0.0)
        td_sign = "+" if today_profit >= 0 else ""
        print(f"  오늘 실현손익:  {td_sign}{today_profit:>14,}원   (평균 {td_sign}{today_rate:.2f}%)")

        # 보유 현황 한 줄 요약
        pos_count = portfolio.get('position_count', 0)
        cash_ratio = portfolio.get('cash_ratio', 0.0)
        trail_count = portfolio.get('trailing_active_count', 0)
        summary_parts = [f"보유 {pos_count}종목", f"현금 {cash_ratio:.1f}%"]
        if trail_count:
            summary_parts.append(f"🟢 트레일링 {trail_count}개")
        print(f"  포트폴리오:     " + "  |  ".join(summary_parts))
        print()

    def _render_positions(self):
        """보유 종목 표시"""
        positions = self.dashboard_data['positions']
        print(f"[POSITION] 보유 종목 ({len(positions)}개)")
        print("-" * 100)
        if positions:
            # 트레일링 활성 종목 우선 정렬
            positions = sorted(
                positions,
                key=lambda p: (
                    0 if p.get('trail_active', p.get('profit_rate', 0) >= 3.0) else 1,
                    -p.get('profit_rate', 0)
                )
            )
            # highest_price 정보가 있는지 확인
            has_highest_price = any(pos.get('highest_price') for pos in positions)

            if has_highest_price:
                # 고급 정보 포함 헤더
                print(f"  {'종목코드':<8} {'종목명':<12} {'전략':<4} {'보유수량':>8} {'매입가':>10} {'현재가':>10} {'최고가':>10} {'스톱가':>10} {'수익률':>8} {'상태':>12}")
                print("  " + "-" * 116)
                for pos in positions[:10]:  # 최대 10개만 표시
                    profit_rate = pos.get('profit_rate', 0)
                    profit_color = "[+]" if profit_rate > 0 else "[-]" if profit_rate < 0 else "[=]"

                    # 트레일링 스톱 활성화 여부
                    trail_active = pos.get('trail_active', profit_rate >= 3.0)
                    trailing_status = "🟢 트레일링" if trail_active else "⚪ 대기"

                    # 손절 유예 표시
                    if pos.get('losscut_delay', False):
                        trailing_status = "⏰ 손절유예"

                    highest_price = pos.get('highest_price', pos.get('current_price', 0))
                    stop_price = pos.get('trailing_stop_price')
                    stop_str = f"{stop_price:>10,}원" if stop_price else f"{'---':>10}"
                    st = pos.get('strategy_type', 'A')

                    print(f"  {pos.get('code', ''):<8} {pos.get('name', ''):<12} [{st}] "
                          f"{pos.get('quantity', 0):>8} {pos.get('buy_price', 0):>10,}원 "
                          f"{pos.get('current_price', 0):>10,}원 {highest_price:>10,}원 "
                          f"{stop_str} "
                          f"{profit_color} {profit_rate:>6.2f}% {trailing_status:>12}")
            else:
                # 기본 헤더
                print(f"  {'종목코드':<10} {'종목명':<15} {'전략':<4} {'보유수량':>10} {'매입가':>12} {'현재가':>12} {'수익률':>10} {'평가손익':>12}")
                print("  " + "-" * 106)
                for pos in positions[:10]:  # 최대 10개만 표시
                    profit_rate = pos.get('profit_rate', 0)
                    profit_color = "[+]" if profit_rate > 0 else "[-]" if profit_rate < 0 else "[=]"
                    delay_mark = " ⏰" if pos.get('losscut_delay', False) else ""
                    st = pos.get('strategy_type', 'A')
                    print(f"  {pos.get('code', ''):<10} {pos.get('name', ''):<15} [{st}] "
                          f"{pos.get('quantity', 0):>10} {pos.get('buy_price', 0):>12,}원 "
                          f"{pos.get('current_price', 0):>12,}원 "
                          f"{profit_color} {profit_rate:>7.2f}% {pos.get('profit', 0):>12,}원{delay_mark}")

            if len(positions) > 10:
                print(f"  ... 외 {len(positions) - 10}개 종목")

            # ── 합산 행 ──
            total_eval   = sum(pos.get('current_price', 0) * pos.get('quantity', 0) for pos in positions)
            total_cost   = sum(pos.get('buy_price', 0)     * pos.get('quantity', 0) for pos in positions)
            total_pnl    = total_eval - total_cost
            total_pnl_r  = total_pnl / total_cost * 100 if total_cost > 0 else 0.0
            pnl_sign     = "+" if total_pnl >= 0 else ""
            pnl_color    = "[+]" if total_pnl > 0 else "[-]" if total_pnl < 0 else "[=]"
            print("  " + "─" * 116)
            print(f"  {'합계':<20}"
                  f"  총 매수금액 {total_cost:>14,}원"
                  f"   총 평가금액 {total_eval:>14,}원"
                  f"   총 평가손익 {pnl_color} {pnl_sign}{total_pnl:>12,}원"
                  f"  ({pnl_sign}{total_pnl_r:.2f}%)")
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
        print(f"[SIGNAL] 매도 시그널 ({len(signals)}개)")
        print("-" * 100)
        if signals:
            print(f"  {'종목코드':<10} {'종목명':<15} {'현재가':>12} {'수익률':>10} {'시그널타입':<25} {'우선순위':>8}")
            print("  " + "-" * 95)
            for sig in signals:
                signal_icon = "[-]" if sig.get('profit_rate', 0) < 0 else "[+]"
                print(f"  {signal_icon} {sig.get('code', ''):<8} {sig.get('name', ''):<15} "
                      f"{sig.get('price', 0):>12,}원 {sig.get('profit_rate', 0):>9.2f}% "
                      f"{sig.get('reason', ''):<25} {sig.get('priority', 0):>8}")
        else:
            print("  매도 시그널이 없습니다.")
        print()

    def _render_recent_trades(self):
        """최근 거래 표시"""
        trades = self.dashboard_data['recent_trades']
        print(f"[TRADES] 최근 거래 ({len(trades)}개)")
        print("-" * 100)
        if trades:
            print(f"  {'시간':<10} {'타입':<6} {'종목코드':<10} {'종목명':<15} {'가격':>12} {'수량':>8} {'수익률':>10}")
            print("  " + "-" * 95)
            for trade in trades[:5]:  # 최대 5개만 표시
                trade_icon = "[B]" if trade.get('type') == '매수' else "[S]"
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
