"""
Performance Analytics Module
백테스팅 및 실전 트레이딩 성과 분석

주요 메트릭:
1. 수익률 지표 (Total Return, CAGR, Monthly/Daily Returns)
2. 리스크 조정 수익률 (Sharpe Ratio, Sortino Ratio, Calmar Ratio)
3. 손실 지표 (Maximum Drawdown, Recovery Time, VaR)
4. 매매 통계 (Win Rate, Profit Factor, Avg Win/Loss)
5. 벤치마크 비교 (Alpha, Beta, Information Ratio)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import pymysql
from library.cf import *


class PerformanceAnalytics:
    """
    성과 분석 클래스

    백테스팅 결과 또는 실전 매매 성과를 분석하여 다양한 메트릭 제공
    """

    def __init__(
        self,
        risk_free_rate: float = 0.035,  # 한국 무위험 이자율 (3.5%)
        benchmark_return: Optional[float] = None
    ):
        """
        Parameters:
        -----------
        risk_free_rate : float
            무위험 이자율 (연율, default: 3.5%)
        benchmark_return : Optional[float]
            벤치마크 수익률 (KOSPI 등)
        """
        self.risk_free_rate = risk_free_rate
        self.benchmark_return = benchmark_return


    def calculate_total_return(
        self,
        equity_curve: pd.Series
    ) -> float:
        """
        총 수익률 계산

        Parameters:
        -----------
        equity_curve : pd.Series
            자산 곡선 (시계열)

        Returns:
        --------
        float : 총 수익률 (%)
        """
        if len(equity_curve) == 0:
            return 0.0

        initial = equity_curve.iloc[0]
        final = equity_curve.iloc[-1]

        return ((final / initial) - 1) * 100


    def calculate_cagr(
        self,
        equity_curve: pd.Series,
        days: Optional[int] = None
    ) -> float:
        """
        CAGR (Compound Annual Growth Rate) 계산

        Parameters:
        -----------
        equity_curve : pd.Series
            자산 곡선
        days : Optional[int]
            기간 (일), 없으면 자동 계산

        Returns:
        --------
        float : CAGR (%)
        """
        if len(equity_curve) == 0:
            return 0.0

        initial = equity_curve.iloc[0]
        final = equity_curve.iloc[-1]

        if days is None:
            days = len(equity_curve)

        years = days / 252  # 거래일 기준

        if years == 0:
            return 0.0

        cagr = ((final / initial) ** (1 / years) - 1) * 100

        return cagr


    def calculate_sharpe_ratio(
        self,
        returns: pd.Series,
        periods_per_year: int = 252
    ) -> float:
        """
        Sharpe Ratio 계산

        (평균 수익률 - 무위험 이자율) / 수익률 표준편차

        Parameters:
        -----------
        returns : pd.Series
            일별 수익률
        periods_per_year : int
            연간 기간 수 (일봉: 252, 주봉: 52)

        Returns:
        --------
        float : Sharpe Ratio
        """
        if len(returns) == 0 or returns.std() == 0:
            return 0.0

        excess_returns = returns - (self.risk_free_rate / periods_per_year)
        sharpe = (excess_returns.mean() / returns.std()) * np.sqrt(periods_per_year)

        return sharpe


    def calculate_sortino_ratio(
        self,
        returns: pd.Series,
        periods_per_year: int = 252
    ) -> float:
        """
        Sortino Ratio 계산

        Sharpe와 유사하지만 하방 변동성만 고려

        Parameters:
        -----------
        returns : pd.Series
            일별 수익률
        periods_per_year : int
            연간 기간 수

        Returns:
        --------
        float : Sortino Ratio
        """
        if len(returns) == 0:
            return 0.0

        excess_returns = returns - (self.risk_free_rate / periods_per_year)

        # 하방 편차 (음수 수익률만)
        downside_returns = returns[returns < 0]

        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0.0

        downside_std = downside_returns.std()
        sortino = (excess_returns.mean() / downside_std) * np.sqrt(periods_per_year)

        return sortino


    def calculate_max_drawdown(
        self,
        equity_curve: pd.Series
    ) -> Dict[str, float]:
        """
        Maximum Drawdown 계산

        Parameters:
        -----------
        equity_curve : pd.Series
            자산 곡선

        Returns:
        --------
        Dict : {
            'max_drawdown': float (최대 낙폭 %),
            'max_drawdown_duration': int (최대 낙폭 기간),
            'recovery_time': int (회복 기간),
            'peak_date': datetime (최고점 날짜),
            'trough_date': datetime (최저점 날짜)
        }
        """
        if len(equity_curve) == 0:
            return {
                'max_drawdown': 0.0,
                'max_drawdown_duration': 0,
                'recovery_time': 0,
                'peak_date': None,
                'trough_date': None
            }

        # 누적 최고점
        running_max = equity_curve.expanding().max()

        # Drawdown 계산
        drawdown = (equity_curve - running_max) / running_max * 100

        # 최대 낙폭
        max_dd = drawdown.min()

        # 최대 낙폭 발생 지점
        max_dd_idx = drawdown.idxmin()

        # 최고점 찾기 (최대 낙폭 이전)
        peak_idx = equity_curve.loc[:max_dd_idx].idxmax()

        # 낙폭 기간
        dd_duration = max_dd_idx - peak_idx if isinstance(max_dd_idx, int) and isinstance(peak_idx, int) else 0

        # 회복 기간 (최저점 이후 최고점 갱신까지)
        recovery_time = 0
        if max_dd_idx < len(equity_curve) - 1:
            peak_value = equity_curve.loc[peak_idx]
            for i in range(max_dd_idx + 1, len(equity_curve)):
                if equity_curve.iloc[i] >= peak_value:
                    recovery_time = i - max_dd_idx
                    break
            else:
                recovery_time = len(equity_curve) - max_dd_idx  # 아직 회복 안됨

        return {
            'max_drawdown': max_dd,
            'max_drawdown_duration': dd_duration,
            'recovery_time': recovery_time,
            'peak_idx': peak_idx,
            'trough_idx': max_dd_idx
        }


    def calculate_calmar_ratio(
        self,
        cagr: float,
        max_drawdown: float
    ) -> float:
        """
        Calmar Ratio 계산

        CAGR / |Maximum Drawdown|

        Parameters:
        -----------
        cagr : float
            연평균 수익률
        max_drawdown : float
            최대 낙폭 (음수)

        Returns:
        --------
        float : Calmar Ratio
        """
        if max_drawdown == 0:
            return 0.0

        return cagr / abs(max_drawdown)


    def calculate_win_rate(
        self,
        trades: List[Dict]
    ) -> Dict[str, float]:
        """
        승률 및 매매 통계 계산

        Parameters:
        -----------
        trades : List[Dict]
            매매 기록 [{'profit': float, 'return_pct': float, ...}]

        Returns:
        --------
        Dict : 매매 통계
        """
        if not trades:
            return {
                'win_rate': 0.0,
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0
            }

        total = len(trades)
        winning = sum(1 for t in trades if t.get('profit', 0) > 0)
        losing = total - winning

        win_rate = (winning / total * 100) if total > 0 else 0

        return {
            'win_rate': win_rate,
            'total_trades': total,
            'winning_trades': winning,
            'losing_trades': losing
        }


    def calculate_profit_factor(
        self,
        trades: List[Dict]
    ) -> float:
        """
        Profit Factor 계산

        총 이익 / 총 손실

        Parameters:
        -----------
        trades : List[Dict]
            매매 기록

        Returns:
        --------
        float : Profit Factor
        """
        if not trades:
            return 0.0

        total_profit = sum(t.get('profit', 0) for t in trades if t.get('profit', 0) > 0)
        total_loss = abs(sum(t.get('profit', 0) for t in trades if t.get('profit', 0) < 0))

        if total_loss == 0:
            return 0.0 if total_profit == 0 else float('inf')

        return total_profit / total_loss


    def calculate_avg_win_loss(
        self,
        trades: List[Dict]
    ) -> Dict[str, float]:
        """
        평균 수익/손실 계산

        Parameters:
        -----------
        trades : List[Dict]
            매매 기록

        Returns:
        --------
        Dict : {
            'avg_win': float,
            'avg_loss': float,
            'avg_win_pct': float,
            'avg_loss_pct': float,
            'win_loss_ratio': float
        }
        """
        if not trades:
            return {
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'avg_win_pct': 0.0,
                'avg_loss_pct': 0.0,
                'win_loss_ratio': 0.0
            }

        wins = [t.get('profit', 0) for t in trades if t.get('profit', 0) > 0]
        losses = [t.get('profit', 0) for t in trades if t.get('profit', 0) < 0]

        avg_win = np.mean(wins) if wins else 0
        avg_loss = abs(np.mean(losses)) if losses else 0

        # 수익률 기준
        win_pcts = [t.get('return_pct', 0) for t in trades if t.get('return_pct', 0) > 0]
        loss_pcts = [t.get('return_pct', 0) for t in trades if t.get('return_pct', 0) < 0]

        avg_win_pct = np.mean(win_pcts) if win_pcts else 0
        avg_loss_pct = abs(np.mean(loss_pcts)) if loss_pcts else 0

        win_loss_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0

        return {
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'avg_win_pct': avg_win_pct,
            'avg_loss_pct': avg_loss_pct,
            'win_loss_ratio': win_loss_ratio
        }


    def calculate_var(
        self,
        returns: pd.Series,
        confidence: float = 0.95
    ) -> float:
        """
        VaR (Value at Risk) 계산

        Parameters:
        -----------
        returns : pd.Series
            수익률 시계열
        confidence : float
            신뢰 수준 (default: 95%)

        Returns:
        --------
        float : VaR (%)
        """
        if len(returns) == 0:
            return 0.0

        return np.percentile(returns, (1 - confidence) * 100)


    def calculate_monthly_returns(
        self,
        equity_curve: pd.Series,
        dates: pd.Series
    ) -> pd.DataFrame:
        """
        월별 수익률 계산

        Parameters:
        -----------
        equity_curve : pd.Series
            자산 곡선
        dates : pd.Series
            날짜 시계열

        Returns:
        --------
        pd.DataFrame : 월별 수익률 표
        """
        df = pd.DataFrame({
            'date': dates,
            'equity': equity_curve
        })

        df['date'] = pd.to_datetime(df['date'])
        df['year_month'] = df['date'].dt.to_period('M')

        # 월별 마지막 값
        monthly = df.groupby('year_month')['equity'].last()

        # 월간 수익률
        monthly_returns = monthly.pct_change() * 100

        return monthly_returns.to_frame('return')


    def generate_performance_report(
        self,
        equity_curve: pd.Series,
        trades: List[Dict],
        dates: Optional[pd.Series] = None
    ) -> Dict:
        """
        종합 성과 리포트 생성

        Parameters:
        -----------
        equity_curve : pd.Series
            자산 곡선
        trades : List[Dict]
            매매 기록
        dates : Optional[pd.Series]
            날짜 시계열

        Returns:
        --------
        Dict : 종합 성과 지표
        """
        if len(equity_curve) == 0:
            return {}

        # 일별 수익률 계산
        returns = equity_curve.pct_change().dropna()

        # 기본 수익률 지표
        total_return = self.calculate_total_return(equity_curve)
        cagr = self.calculate_cagr(equity_curve)

        # 리스크 조정 수익률
        sharpe = self.calculate_sharpe_ratio(returns)
        sortino = self.calculate_sortino_ratio(returns)

        # 손실 지표
        dd_info = self.calculate_max_drawdown(equity_curve)
        max_dd = dd_info['max_drawdown']
        calmar = self.calculate_calmar_ratio(cagr, max_dd)

        # 매매 통계
        win_stats = self.calculate_win_rate(trades)
        profit_factor = self.calculate_profit_factor(trades)
        avg_stats = self.calculate_avg_win_loss(trades)

        # VaR
        var_95 = self.calculate_var(returns, 0.95)

        # 변동성
        volatility = returns.std() * np.sqrt(252) * 100  # 연간 변동성

        report = {
            # 수익률 지표
            'total_return': total_return,
            'cagr': cagr,
            'volatility': volatility,

            # 리스크 조정 수익률
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'calmar_ratio': calmar,

            # 손실 지표
            'max_drawdown': max_dd,
            'max_dd_duration': dd_info['max_drawdown_duration'],
            'recovery_time': dd_info['recovery_time'],
            'var_95': var_95,

            # 매매 통계
            'total_trades': win_stats['total_trades'],
            'win_rate': win_stats['win_rate'],
            'winning_trades': win_stats['winning_trades'],
            'losing_trades': win_stats['losing_trades'],
            'profit_factor': profit_factor,

            # 평균 수익/손실
            'avg_win': avg_stats['avg_win'],
            'avg_loss': avg_stats['avg_loss'],
            'avg_win_pct': avg_stats['avg_win_pct'],
            'avg_loss_pct': avg_stats['avg_loss_pct'],
            'win_loss_ratio': avg_stats['win_loss_ratio'],

            # 기타
            'total_days': len(equity_curve)
        }

        # 월별 수익률 (dates 있을 경우)
        if dates is not None:
            monthly_returns = self.calculate_monthly_returns(equity_curve, dates)
            report['monthly_returns'] = monthly_returns

        return report


    def print_report(self, report: Dict):
        """
        성과 리포트 출력

        Parameters:
        -----------
        report : Dict
            성과 리포트
        """
        print("=" * 60)
        print("📊 PERFORMANCE REPORT")
        print("=" * 60)

        print("\n🎯 수익률 지표:")
        print(f"  총 수익률:        {report['total_return']:>10.2f}%")
        print(f"  연평균 수익률:    {report['cagr']:>10.2f}%")
        print(f"  연간 변동성:      {report['volatility']:>10.2f}%")

        print("\n📈 리스크 조정 수익률:")
        print(f"  Sharpe Ratio:     {report['sharpe_ratio']:>10.2f}")
        print(f"  Sortino Ratio:    {report['sortino_ratio']:>10.2f}")
        print(f"  Calmar Ratio:     {report['calmar_ratio']:>10.2f}")

        print("\n📉 손실 지표:")
        print(f"  최대 낙폭:        {report['max_drawdown']:>10.2f}%")
        print(f"  낙폭 지속:        {report['max_dd_duration']:>10d}일")
        print(f"  회복 기간:        {report['recovery_time']:>10d}일")
        print(f"  VaR (95%):        {report['var_95']:>10.2f}%")

        print("\n💼 매매 통계:")
        print(f"  총 매매 횟수:     {report['total_trades']:>10d}회")
        print(f"  승률:             {report['win_rate']:>10.1f}%")
        print(f"  승리 매매:        {report['winning_trades']:>10d}회")
        print(f"  손실 매매:        {report['losing_trades']:>10d}회")
        print(f"  Profit Factor:    {report['profit_factor']:>10.2f}")

        print("\n💰 평균 수익/손실:")
        print(f"  평균 수익:        {report['avg_win']:>10,.0f}원 ({report['avg_win_pct']:>6.2f}%)")
        print(f"  평균 손실:        {report['avg_loss']:>10,.0f}원 ({report['avg_loss_pct']:>6.2f}%)")
        print(f"  손익비:           {report['win_loss_ratio']:>10.2f}:1")

        print("\n📅 기간:")
        print(f"  총 거래일:        {report['total_days']:>10d}일")

        print("=" * 60)


def analyze_backtest_from_db(
    db_name: str,
    simul_num: int = 1
) -> Dict:
    """
    데이터베이스에서 백테스트 결과 분석

    Parameters:
    -----------
    db_name : str
        시뮬레이터 데이터베이스 이름
    simul_num : int
        시뮬레이터 번호

    Returns:
    --------
    Dict : 성과 리포트
    """
    try:
        con = pymysql.connect(
            user=db_id,
            passwd=db_passwd,
            host=db_ip,
            db=db_name,
            charset='utf8',
            port=int(db_port)
        )

        # jango_data 테이블에서 자산 곡선 가져오기
        query_jango = """
        SELECT date, total_asset
        FROM jango_data
        ORDER BY date
        """

        df_jango = pd.read_sql(query_jango, con)

        # all_item_db 테이블에서 매매 기록 가져오기
        query_trades = """
        SELECT code, code_name, buy_date, sell_date,
               purchase_price, present_price, sell_rate,
               holding_amount
        FROM all_item_db
        WHERE sell_date IS NOT NULL
        """

        df_trades = pd.read_sql(query_trades, con)
        con.close()

        if len(df_jango) == 0:
            print("백테스트 데이터가 없습니다.")
            return {}

        # 자산 곡선
        equity_curve = df_jango['total_asset']
        dates = pd.to_datetime(df_jango['date'])

        # 매매 기록 변환
        trades = []
        for _, row in df_trades.iterrows():
            profit = (row['present_price'] - row['purchase_price']) * row['holding_amount']
            return_pct = row['sell_rate']

            trades.append({
                'code': row['code'],
                'profit': profit,
                'return_pct': return_pct
            })

        # 성과 분석
        analytics = PerformanceAnalytics()
        report = analytics.generate_performance_report(equity_curve, trades, dates)

        return report

    except Exception as e:
        print(f"백테스트 분석 오류: {e}")
        return {}


if __name__ == "__main__":
    # 테스트 코드
    print("=== Performance Analytics 테스트 ===\n")

    # 샘플 자산 곡선 생성
    np.random.seed(42)
    days = 252  # 1년

    # 드리프트 + 변동성 모델
    returns = np.random.normal(0.0005, 0.015, days)  # 일 0.05% 수익, 1.5% 변동성
    equity = [10000000]  # 초기 1000만원

    for r in returns:
        equity.append(equity[-1] * (1 + r))

    equity_curve = pd.Series(equity)

    # 샘플 매매 기록
    trades = []
    for i in range(50):
        # 승률 55% 시뮬레이션
        is_win = np.random.random() < 0.55

        if is_win:
            profit = np.random.uniform(20000, 150000)
            return_pct = np.random.uniform(3, 12)
        else:
            profit = -np.random.uniform(10000, 80000)
            return_pct = -np.random.uniform(1, 6)

        trades.append({
            'profit': profit,
            'return_pct': return_pct
        })

    # 성과 분석
    analytics = PerformanceAnalytics(risk_free_rate=0.035)
    report = analytics.generate_performance_report(equity_curve, trades)

    # 리포트 출력
    analytics.print_report(report)

    print("\n✅ Performance Analytics 모듈 생성 완료!")
