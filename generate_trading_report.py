#!/usr/bin/env python
"""
매매 성과 분석 리포트 생성기

DB에서 매매 이력을 분석하여 HTML 리포트를 생성합니다.
- 전체 수익률
- 승률/패율
- 평균 보유 기간
- 종목별 수익
- 일별 수익 추이 그래프
"""

import pymysql
import pandas as pd
import datetime
from pathlib import Path
from typing import Dict, List
import json

# 설정 import
from library.cf import db_id, db_passwd, db_ip, db_port


class TradingReportGenerator:
    """매매 성과 리포트 생성기"""

    def __init__(self, db_name: str = 'JackBot1_imi1'):
        """
        Parameters:
        -----------
        db_name : str
            분석할 데이터베이스 이름
        """
        self.db_name = db_name
        self.con = None
        self.report_data = {}

    def connect(self):
        """DB 연결"""
        self.con = pymysql.connect(
            user=db_id,
            passwd=db_passwd,
            host=db_ip,
            db=self.db_name,
            charset='utf8',
            port=int(db_port)
        )

    def close(self):
        """DB 연결 종료"""
        if self.con:
            self.con.close()

    def analyze_all_trades(self) -> Dict:
        """전체 매매 이력 분석"""
        query = """
        SELECT
            code,
            code_name,
            buy_date,
            sell_date,
            purchase_price,
            sell_price,
            holding_amount,
            sell_rate,
            item_total_purchase,
            DATEDIFF(sell_date, buy_date) as holding_days
        FROM all_item_db
        WHERE sell_date != '0' AND sell_date != ''
        ORDER BY sell_date DESC
        """

        df = pd.read_sql(query, self.con)

        if df.empty:
            return {
                'total_trades': 0,
                'win_trades': 0,
                'loss_trades': 0,
                'total_profit': 0,
                'avg_profit_rate': 0,
                'win_rate': 0,
                'avg_holding_days': 0
            }

        # 기본 통계
        total_trades = len(df)
        win_trades = len(df[df['sell_rate'] > 0])
        loss_trades = len(df[df['sell_rate'] < 0])
        win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0

        # 수익 계산
        df['profit'] = df.apply(
            lambda row: (row['sell_price'] - row['purchase_price']) * row['holding_amount']
            if pd.notna(row['sell_price']) and pd.notna(row['purchase_price'])
            else 0,
            axis=1
        )

        total_profit = df['profit'].sum()
        avg_profit_rate = df['sell_rate'].mean()
        avg_holding_days = df['holding_days'].mean()

        return {
            'total_trades': total_trades,
            'win_trades': win_trades,
            'loss_trades': loss_trades,
            'total_profit': int(total_profit),
            'avg_profit_rate': float(avg_profit_rate),
            'win_rate': float(win_rate),
            'avg_holding_days': float(avg_holding_days),
            'trades_df': df
        }

    def analyze_by_stock(self, trades_df: pd.DataFrame) -> List[Dict]:
        """종목별 수익 분석"""
        if trades_df.empty:
            return []

        stock_stats = []

        for code in trades_df['code'].unique():
            stock_trades = trades_df[trades_df['code'] == code]
            code_name = stock_trades.iloc[0]['code_name']

            total_trades = len(stock_trades)
            wins = len(stock_trades[stock_trades['sell_rate'] > 0])
            losses = len(stock_trades[stock_trades['sell_rate'] < 0])

            total_profit = stock_trades['profit'].sum()
            avg_rate = stock_trades['sell_rate'].mean()

            stock_stats.append({
                'code': code,
                'name': code_name,
                'trades': total_trades,
                'wins': wins,
                'losses': losses,
                'total_profit': int(total_profit),
                'avg_rate': float(avg_rate),
                'win_rate': (wins / total_trades * 100) if total_trades > 0 else 0
            })

        # 수익 순으로 정렬
        stock_stats.sort(key=lambda x: x['total_profit'], reverse=True)

        return stock_stats

    def analyze_daily_performance(self) -> pd.DataFrame:
        """일별 수익 분석"""
        query = """
        SELECT
            date,
            sum_valuation_profit,
            today_profit,
            today_profitcut_count,
            today_losscut_count,
            d2_deposit,
            total_possess_count
        FROM jango_data
        ORDER BY date
        """

        df = pd.read_sql(query, self.con)
        return df

    def get_current_positions(self) -> pd.DataFrame:
        """현재 보유 종목 조회"""
        query = """
        SELECT
            code,
            code_name,
            date as buy_date,
            puchase_price,
            holding_amount,
            present_price,
            valuation_profit,
            rate,
            item_total_purchase
        FROM possessed_item
        WHERE holding_amount > 0
        ORDER BY rate DESC
        """

        try:
            df = pd.read_sql(query, self.con)
            return df
        except:
            return pd.DataFrame()

    def generate_html_report(self, output_path: str = None) -> str:
        """HTML 리포트 생성"""
        if not output_path:
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f'reports/trading_report_{timestamp}.html'

        # 디렉토리 생성
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # 데이터 분석
        all_trades = self.analyze_all_trades()
        stock_stats = self.analyze_by_stock(all_trades.get('trades_df', pd.DataFrame()))
        daily_perf = self.analyze_daily_performance()
        current_positions = self.get_current_positions()

        # HTML 생성
        html = self._generate_html(all_trades, stock_stats, daily_perf, current_positions)

        # 파일 저장
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        return output_path

    def _generate_html(self, all_trades: Dict, stock_stats: List[Dict],
                      daily_perf: pd.DataFrame, current_positions: pd.DataFrame) -> str:
        """HTML 생성"""
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 일별 수익 데이터 (차트용)
        chart_data = {
            'dates': daily_perf['date'].tolist() if not daily_perf.empty else [],
            'profits': daily_perf['sum_valuation_profit'].tolist() if not daily_perf.empty else []
        }

        html = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>매매 성과 보고서</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #f5f7fa;
            padding: 20px;
            color: #333;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
        }}
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        .header p {{
            opacity: 0.9;
            font-size: 1.1em;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .stat-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 5px 20px rgba(0,0,0,0.12);
        }}
        .stat-label {{
            color: #8492a6;
            font-size: 0.9em;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .stat-value {{
            font-size: 2em;
            font-weight: bold;
            color: #2c3e50;
        }}
        .stat-value.positive {{
            color: #27ae60;
        }}
        .stat-value.negative {{
            color: #e74c3c;
        }}
        .section {{
            background: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        }}
        .section-title {{
            font-size: 1.8em;
            margin-bottom: 20px;
            color: #2c3e50;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        thead {{
            background: #f8f9fa;
        }}
        th {{
            padding: 15px;
            text-align: left;
            font-weight: 600;
            color: #5a6c7d;
            border-bottom: 2px solid #e1e8ed;
        }}
        td {{
            padding: 12px 15px;
            border-bottom: 1px solid #e1e8ed;
        }}
        tr:hover {{
            background: #f8f9fa;
        }}
        .profit {{
            color: #27ae60;
            font-weight: bold;
        }}
        .loss {{
            color: #e74c3c;
            font-weight: bold;
        }}
        .chart-container {{
            position: relative;
            height: 400px;
            margin-top: 20px;
        }}
        .badge {{
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
        }}
        .badge-success {{
            background: #d4edda;
            color: #155724;
        }}
        .badge-danger {{
            background: #f8d7da;
            color: #721c24;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            color: #8492a6;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 매매 성과 보고서</h1>
            <p>Database: {self.db_name} | 생성일시: {now}</p>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">총 거래 횟수</div>
                <div class="stat-value">{all_trades['total_trades']}건</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">총 수익</div>
                <div class="stat-value {'positive' if all_trades['total_profit'] >= 0 else 'negative'}">
                    {all_trades['total_profit']:+,}원
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-label">평균 수익률</div>
                <div class="stat-value {'positive' if all_trades['avg_profit_rate'] >= 0 else 'negative'}">
                    {all_trades['avg_profit_rate']:+.2f}%
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-label">승률</div>
                <div class="stat-value">{all_trades['win_rate']:.1f}%</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">익절 / 손절</div>
                <div class="stat-value">
                    <span class="profit">{all_trades['win_trades']}</span> /
                    <span class="loss">{all_trades['loss_trades']}</span>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-label">평균 보유 기간</div>
                <div class="stat-value">{all_trades['avg_holding_days']:.1f}일</div>
            </div>
        </div>

        <div class="section">
            <h2 class="section-title">📈 수익 추이</h2>
            <div class="chart-container">
                <canvas id="profitChart"></canvas>
            </div>
        </div>

        <div class="section">
            <h2 class="section-title">🎯 종목별 수익 TOP 10</h2>
            <table>
                <thead>
                    <tr>
                        <th>순위</th>
                        <th>종목명</th>
                        <th>종목코드</th>
                        <th>거래횟수</th>
                        <th>익절/손절</th>
                        <th>승률</th>
                        <th>총 수익</th>
                        <th>평균 수익률</th>
                    </tr>
                </thead>
                <tbody>
"""

        # 종목별 통계 (TOP 10)
        for idx, stock in enumerate(stock_stats[:10], 1):
            profit_class = 'profit' if stock['total_profit'] >= 0 else 'loss'
            html += f"""
                    <tr>
                        <td>{idx}</td>
                        <td><strong>{stock['name']}</strong></td>
                        <td>{stock['code']}</td>
                        <td>{stock['trades']}건</td>
                        <td>
                            <span class="badge badge-success">{stock['wins']}</span>
                            <span class="badge badge-danger">{stock['losses']}</span>
                        </td>
                        <td>{stock['win_rate']:.1f}%</td>
                        <td class="{profit_class}">{stock['total_profit']:+,}원</td>
                        <td class="{profit_class}">{stock['avg_rate']:+.2f}%</td>
                    </tr>
"""

        html += """
                </tbody>
            </table>
        </div>
"""

        # 현재 보유 종목
        if not current_positions.empty:
            html += """
        <div class="section">
            <h2 class="section-title">💼 현재 보유 종목</h2>
            <table>
                <thead>
                    <tr>
                        <th>종목명</th>
                        <th>매수일</th>
                        <th>매수가</th>
                        <th>현재가</th>
                        <th>수량</th>
                        <th>평가손익</th>
                        <th>수익률</th>
                    </tr>
                </thead>
                <tbody>
"""
            for _, pos in current_positions.iterrows():
                profit_class = 'profit' if pos['rate'] >= 0 else 'loss'
                html += f"""
                    <tr>
                        <td><strong>{pos['code_name']}</strong> ({pos['code']})</td>
                        <td>{pos['buy_date']}</td>
                        <td>{pos['puchase_price']:,}원</td>
                        <td>{pos['present_price']:,}원</td>
                        <td>{pos['holding_amount']}주</td>
                        <td class="{profit_class}">{pos['valuation_profit']:+,}원</td>
                        <td class="{profit_class}">{pos['rate']:+.2f}%</td>
                    </tr>
"""

            html += """
                </tbody>
            </table>
        </div>
"""

        # 차트 스크립트
        html += f"""
        <div class="footer">
            <p>© 2025 Trading Bot - 자동 매매 시스템</p>
        </div>
    </div>

    <script>
        const ctx = document.getElementById('profitChart').getContext('2d');
        const chartData = {json.dumps(chart_data)};

        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: chartData.dates,
                datasets: [{{
                    label: '누적 수익',
                    data: chartData.profits,
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        display: true,
                        position: 'top'
                    }},
                    tooltip: {{
                        callbacks: {{
                            label: function(context) {{
                                return '수익: ' + context.parsed.y.toLocaleString('ko-KR') + '원';
                            }}
                        }}
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        ticks: {{
                            callback: function(value) {{
                                return value.toLocaleString('ko-KR') + '원';
                            }}
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""

        return html


def main():
    """메인 함수"""
    import argparse

    parser = argparse.ArgumentParser(description='매매 성과 리포트 생성')
    parser.add_argument('--db', default='JackBot1_imi1',
                       help='분석할 DB 이름 (기본값: JackBot1_imi1)')
    parser.add_argument('--output', default=None,
                       help='출력 파일 경로 (기본값: reports/trading_report_TIMESTAMP.html)')

    args = parser.parse_args()

    print("=" * 80)
    print("📊 매매 성과 리포트 생성 중...")
    print("=" * 80)
    print(f"Database: {args.db}")
    print()

    try:
        generator = TradingReportGenerator(db_name=args.db)
        generator.connect()

        output_path = generator.generate_html_report(args.output)

        generator.close()

        print("✅ 리포트 생성 완료!")
        print(f"📄 파일 위치: {output_path}")
        print()
        print("💡 브라우저에서 열어보세요:")
        print(f"   file:///{Path(output_path).absolute()}")
        print("=" * 80)

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
