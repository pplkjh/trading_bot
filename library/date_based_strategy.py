"""
날짜별 테이블 기반 매매 전략
daily_buy_list의 날짜별 집계 테이블(20251119, 20251118 등)을 활용한 전략
"""

import pymysql
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional
from library.cf import *


def get_latest_date_table(db_name: str = 'daily_buy_list') -> Optional[str]:
    """
    가장 최근 날짜 테이블 이름 가져오기

    Returns:
    --------
    str : 최신 날짜 테이블명 (예: '20251119')
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

        query = """
        SELECT TABLE_NAME
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = %s
          AND TABLE_NAME REGEXP '^[0-9]{8}$'
        ORDER BY TABLE_NAME DESC
        LIMIT 1
        """

        cursor = con.cursor()
        cursor.execute(query, (db_name,))
        result = cursor.fetchone()
        con.close()

        if result:
            return result[0]
        return None

    except Exception as e:
        print(f"최신 날짜 테이블 조회 오류: {e}")
        return None


def scan_buy_candidates_from_date_table(
    min_score: float = 70.0,
    top_n: int = 20,
    db_name: str = 'daily_buy_list'
) -> pd.DataFrame:
    """
    날짜별 테이블에서 매수 후보 종목 스캔

    매수 조건:
    - 거래량 급증 (vol5 대비 1.5배 이상)
    - 상승 추세 (clo5 > clo20)
    - 과매수 아님 (close < clo20 * 1.05)
    - 변동성 적정 (-3% < d1_diff_rate < 3%)

    Parameters:
    -----------
    min_score : float
        최소 스코어
    top_n : int
        선정할 종목 수
    db_name : str
        데이터베이스 이름

    Returns:
    --------
    pd.DataFrame : 매수 추천 종목 리스트
    """
    try:
        # 최신 날짜 테이블 가져오기
        latest_table = get_latest_date_table(db_name)

        if not latest_table:
            print("❌ 날짜별 테이블을 찾을 수 없습니다.")
            return pd.DataFrame()

        print(f"📅 스캔 날짜: {latest_table}")

        con = pymysql.connect(
            user=db_id,
            passwd=db_passwd,
            host=db_ip,
            db=db_name,
            charset='utf8',
            port=int(db_port)
        )

        # 필터링 테이블 존재 여부 체크
        cursor = con.cursor()
        cursor.execute("""
            SELECT TABLE_NAME
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s
            AND TABLE_NAME IN ('stock_konex', 'stock_invest_warning', 'stock_invest_danger', 'stock_invest_caution')
        """, (db_name,))
        existing_tables = {row[0] for row in cursor.fetchall()}

        # 코넥스 제외 쿼리
        konex_exclusion = ""
        if 'stock_konex' in existing_tables:
            konex_exclusion = "AND code NOT IN (SELECT code FROM stock_konex WHERE 1=1)"

        # 투자위험 종목 제외 쿼리 동적 생성
        warning_exclusion = ""
        warning_tables = [t for t in ['stock_invest_warning', 'stock_invest_danger', 'stock_invest_caution'] if t in existing_tables]
        if warning_tables:
            warning_unions = []
            for table in warning_tables:
                warning_unions.append(f"SELECT code FROM {table}")
            warning_exclusion = f"""
            -- 투자위험 종목 제외
            AND code NOT IN (
                {' UNION '.join(warning_unions)}
            )
            """

        # 매수 후보 종목 스캔 쿼리
        query = f"""
        SELECT
            code,
            code_name,
            close as current_price,
            d1_diff_rate,
            volume,
            vol5,
            vol20,
            clo5,
            clo10,
            clo20,
            clo40,
            clo60,
            clo5_diff_rate,
            clo20_diff_rate,

            -- 종합 스코어 계산
            (
                -- 거래량 스코어 (40점 만점)
                CASE
                    WHEN volume > vol5 * 3 THEN 40
                    WHEN volume > vol5 * 2 THEN 30
                    WHEN volume > vol5 * 1.5 THEN 20
                    ELSE 10
                END +

                -- 모멘텀 스코어 (30점 만점)
                CASE
                    WHEN clo5 > clo20 AND clo20 > clo40 THEN 30  -- 강한 상승 추세
                    WHEN clo5 > clo20 THEN 20  -- 상승 추세
                    WHEN clo5 > clo40 THEN 10  -- 약한 상승
                    ELSE 0
                END +

                -- 가격 위치 스코어 (20점 만점)
                CASE
                    WHEN close > clo5 AND close < clo5 * 1.03 THEN 20  -- 5일선 근처
                    WHEN close > clo20 AND close < clo20 * 1.05 THEN 15  -- 20일선 근처
                    ELSE 5
                END +

                -- 변동성 스코어 (10점 만점)
                CASE
                    WHEN ABS(d1_diff_rate) < 1 THEN 10  -- 안정적
                    WHEN ABS(d1_diff_rate) < 2 THEN 5
                    ELSE 0
                END
            ) as composite_score,

            -- 전략 타입
            CASE
                WHEN volume > vol5 * 2 AND clo5 > clo20 THEN 'momentum_breakout'
                WHEN close < clo20 AND clo20 > clo40 THEN 'mean_reversion'
                WHEN clo5 > clo20 AND clo20 > clo40 THEN 'strong_uptrend'
                ELSE 'neutral'
            END as strategy_type

        FROM `{latest_table}`
        WHERE 1=1
            -- 기본 필터
            AND close > 0
            AND volume > 0
            AND clo5 > 0
            AND clo20 > 0

            {konex_exclusion}

<<<<<<< Updated upstream
            -- 투자위험 종목 제외 (투자주의는 허용)
            AND code NOT IN (
                SELECT code FROM stock_invest_warning
                UNION
                SELECT code FROM stock_invest_danger
            )
=======
            {warning_exclusion}
>>>>>>> Stashed changes

            -- 매수 조건
            AND volume > vol5 * 1.5  -- 거래량 급증
            AND clo5 > clo20  -- 상승 추세
            AND close < clo20 * 1.05  -- 과매수 아님
            AND d1_diff_rate BETWEEN -3 AND 3  -- 변동성 적정
            AND close BETWEEN 5000 AND 500000  -- 가격 범위

        HAVING composite_score >= {min_score}
        ORDER BY composite_score DESC
        LIMIT {top_n * 2}
        """

        df = pd.read_sql(query, con)
        con.close()

        if df.empty:
            return pd.DataFrame()

        # 추가 계산
        df['volume_ratio'] = df['volume'] / df['vol5']
        df['momentum_score'] = df['clo5_diff_rate']
        df['mean_reversion_score'] = df['clo20_diff_rate']

        # ATR 추정 (간단 버전: 최근 변동성 기반)
        df['atr'] = df['current_price'] * 0.03  # 3% 가정

        # 포지션 사이징 (간단 버전)
        df['risk_score'] = df['d1_diff_rate'].abs() * 10  # 변동성 기반 리스크

        # Top N 선정
        df = df.head(top_n)

        return df

    except Exception as e:
        print(f"❌ 스캔 오류: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


def calculate_position_size(
    current_price: float,
    portfolio_value: float,
    risk_pct: float = 0.15,
    atr: float = None
) -> dict:
    """
    포지션 사이징 계산

    Parameters:
    -----------
    current_price : float
        현재가
    portfolio_value : float
        포트폴리오 가치
    risk_pct : float
        포지션 비율 (0.15 = 15%)
    atr : float
        ATR (없으면 가격의 3%로 추정)

    Returns:
    --------
    dict : 수량, 금액, 손절가, 목표가
    """
    if atr is None:
        atr = current_price * 0.03

    # 포지션 금액
    position_value = portfolio_value * risk_pct

    # 수량 계산
    shares = int(position_value / current_price)

    # 실제 투자 금액
    actual_value = shares * current_price

    # 손절가 (ATR 2배)
    stop_loss = current_price - (atr * 2)

    # 목표가 (ATR 3배)
    profit_target = current_price + (atr * 3)

    # 손익비
    risk_reward_ratio = (profit_target - current_price) / (current_price - stop_loss)

    return {
        'recommended_shares': shares,
        'recommended_value': actual_value,
        'position_pct': actual_value / portfolio_value,
        'stop_loss': stop_loss,
        'profit_target': profit_target,
        'risk_reward_ratio': risk_reward_ratio,
        'atr': atr
    }


def generate_buy_signals(
    portfolio_value: float = 10000000,
    top_n: int = 20,
    min_score: float = 70.0,
    risk_per_position: float = 0.15
) -> pd.DataFrame:
    """
    매수 시그널 생성 (올인원 함수)

    Parameters:
    -----------
    portfolio_value : float
        포트폴리오 가치
    top_n : int
        선정할 종목 수
    min_score : float
        최소 스코어
    risk_per_position : float
        종목당 투자 비율

    Returns:
    --------
    pd.DataFrame : 매수 추천 종목 리스트
    """
    # 매수 후보 스캔
    df = scan_buy_candidates_from_date_table(
        min_score=min_score,
        top_n=top_n
    )

    if df.empty:
        return df

    # 각 종목별 포지션 계산
    positions = []
    for idx, row in df.iterrows():
        pos = calculate_position_size(
            current_price=row['current_price'],
            portfolio_value=portfolio_value,
            risk_pct=risk_per_position,
            atr=row['atr']
        )
        positions.append(pos)

    # 결과 합치기
    df_positions = pd.DataFrame(positions)
    result = pd.concat([df.reset_index(drop=True), df_positions], axis=1)

    return result


if __name__ == "__main__":
    # 테스트
    print("📊 날짜별 테이블 기반 스캔 테스트")
    print("=" * 80)

    df = generate_buy_signals(
        portfolio_value=10000000,
        top_n=20,
        min_score=70.0
    )

    print(f"\n✅ 매수 후보: {len(df)}개")

    if not df.empty:
        print("\n상위 5개:")
        for idx, row in df.head(5).iterrows():
            print(f"\n[{idx+1}] {row['code']} - {row['code_name']}")
            print(f"  현재가: {row['current_price']:,}원")
            print(f"  스코어: {row['composite_score']:.1f}/100")
            print(f"  전략: {row['strategy_type']}")
            print(f"  거래량 비율: {row['volume_ratio']:.2f}x")
