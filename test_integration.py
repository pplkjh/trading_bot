"""
고급 전략 시스템 통합 테스트 스크립트

이 스크립트는 새로운 고급 모듈들이 기존 시스템과 잘 통합되는지 확인합니다.
"""

import sys
import traceback
from datetime import datetime

def test_1_imports():
    """테스트 1: 모듈 import 확인"""
    print("=" * 80)
    print("테스트 1: 모듈 Import 확인")
    print("=" * 80)

    modules = [
        ('library.cf', 'DB 설정'),
        ('library.risk_manager', 'RiskManager'),
        ('library.multi_factor_scoring', 'MultiFactorScoring'),
        ('library.hybrid_strategy', 'HybridStrategy'),
        ('library.exit_strategy', 'ExitStrategy'),
        ('library.performance_analytics', 'PerformanceAnalytics'),
        ('library.advanced_strategy_system', 'AdvancedStrategySystem'),
    ]

    failed = []
    for module_name, description in modules:
        try:
            __import__(module_name)
            print(f"✓ {module_name:<45} - {description}")
        except Exception as e:
            print(f"✗ {module_name:<45} - 실패: {e}")
            failed.append((module_name, e))

    if failed:
        print(f"\n⚠️  {len(failed)}개 모듈 import 실패")
        for module, error in failed:
            print(f"  - {module}: {error}")
        return False
    else:
        print("\n✅ 모든 모듈 import 성공!")
        return True


def test_2_db_connection():
    """테스트 2: 데이터베이스 연결 확인"""
    print("\n" + "=" * 80)
    print("테스트 2: 데이터베이스 연결 확인")
    print("=" * 80)

    try:
        import pymysql
        from library.cf import db_id, db_passwd, db_ip, db_port

        print(f"\nDB 설정:")
        print(f"  Host: {db_ip}:{db_port}")
        print(f"  User: {db_id}")

        # daily_buy_list DB 연결 테스트
        con = pymysql.connect(
            user=db_id,
            passwd=db_passwd,
            host=db_ip,
            db='daily_buy_list',
            charset='utf8',
            port=int(db_port)
        )

        cursor = con.cursor()

        # stock_item_all 테이블 확인
        cursor.execute("SELECT COUNT(*) FROM stock_item_all WHERE check_item = 1")
        count = cursor.fetchone()[0]
        print(f"\n✓ daily_buy_list DB 연결 성공")
        print(f"  활성 종목 수: {count}개")

        # 샘플 종목 조회
        cursor.execute("SELECT code, code_name FROM stock_item_all WHERE check_item = 1 LIMIT 5")
        samples = cursor.fetchall()
        print(f"\n  샘플 종목:")
        for code, name in samples:
            print(f"    - {code}: {name}")

        con.close()

        print("\n✅ 데이터베이스 연결 성공!")
        return True

    except Exception as e:
        print(f"\n✗ 데이터베이스 연결 실패: {e}")
        traceback.print_exc()
        return False


def test_3_class_initialization():
    """테스트 3: 클래스 초기화 확인"""
    print("\n" + "=" * 80)
    print("테스트 3: 클래스 초기화 확인")
    print("=" * 80)

    try:
        from library.risk_manager import RiskManager
        from library.multi_factor_scoring import MultiFactorScoring
        from library.hybrid_strategy import HybridStrategy
        from library.exit_strategy import ExitStrategy
        from library.performance_analytics import PerformanceAnalytics

        print("\n클래스 초기화 테스트...")

        # RiskManager
        rm = RiskManager(portfolio_value=10000000, risk_profile='aggressive')
        print(f"✓ RiskManager 초기화 성공 (포트폴리오: {rm.portfolio_value:,}원)")

        # MultiFactorScoring
        mfs = MultiFactorScoring()
        print(f"✓ MultiFactorScoring 초기화 성공 (팩터 수: {len(mfs.weights)}개)")

        # HybridStrategy
        hs = HybridStrategy(momentum_weight=0.6, mean_reversion_weight=0.4)
        print(f"✓ HybridStrategy 초기화 성공 (모멘텀: {hs.momentum_weight}, 평균회귀: {hs.mean_reversion_weight})")

        # ExitStrategy
        es = ExitStrategy()
        print(f"✓ ExitStrategy 초기화 성공 (ATR 배수: {es.atr_stop_multiplier})")

        # PerformanceAnalytics
        pa = PerformanceAnalytics()
        print(f"✓ PerformanceAnalytics 초기화 성공")

        print("\n✅ 모든 클래스 초기화 성공!")
        return True

    except Exception as e:
        print(f"\n✗ 클래스 초기화 실패: {e}")
        traceback.print_exc()
        return False


def test_4_advanced_system():
    """테스트 4: 통합 시스템 초기화"""
    print("\n" + "=" * 80)
    print("테스트 4: AdvancedStrategySystem 초기화")
    print("=" * 80)

    try:
        from library.advanced_strategy_system import AdvancedStrategySystem

        print("\n시스템 초기화 중...")
        system = AdvancedStrategySystem(
            portfolio_value=10000000,
            risk_profile='aggressive'
        )

        print(f"\n✓ AdvancedStrategySystem 초기화 성공")
        print(f"\n시스템 설정:")
        print(f"  포트폴리오: {system.portfolio_value:,}원")
        print(f"  리스크 프로필: {system.risk_profile}")
        print(f"  최대 포지션: {system.config['max_positions']}개")
        print(f"  포지션당 최대: {system.config['position_pct']*100:.0f}%")
        print(f"  일일 최대 손실: {system.config['max_daily_loss_pct']*100:.0f}%")
        print(f"  최대 보유기간: {system.config['max_holding_days']}일")

        print("\n✅ 통합 시스템 초기화 성공!")
        return True

    except Exception as e:
        print(f"\n✗ 통합 시스템 초기화 실패: {e}")
        traceback.print_exc()
        return False


def test_5_data_fetch():
    """테스트 5: 실제 데이터 조회 테스트"""
    print("\n" + "=" * 80)
    print("테스트 5: 실제 데이터 조회 테스트")
    print("=" * 80)

    try:
        import pymysql
        import pandas as pd
        from library.cf import db_id, db_passwd, db_ip, db_port

        print("\n종목 데이터 조회 중...")

        con = pymysql.connect(
            user=db_id,
            passwd=db_passwd,
            host=db_ip,
            db='daily_buy_list',
            charset='utf8',
            port=int(db_port)
        )

        # 활성 종목 1개 선택
        query = """
        SELECT code, code_name
        FROM stock_item_all
        WHERE check_item = 1
        LIMIT 1
        """
        df = pd.read_sql(query, con)

        if df.empty:
            print("✗ 활성 종목이 없습니다. collector_v3.py를 먼저 실행하세요.")
            con.close()
            return False

        code = df.iloc[0]['code']
        code_name = df.iloc[0]['code_name']

        print(f"✓ 테스트 종목: {code} ({code_name})")

        # daily_craw에서 주가 데이터 조회
        con_craw = pymysql.connect(
            user=db_id,
            passwd=db_passwd,
            host=db_ip,
            db='daily_craw',
            charset='utf8',
            port=int(db_port)
        )

        query = f"""
        SELECT date, open, high, low, close, volume
        FROM `{code}`
        ORDER BY date DESC
        LIMIT 120
        """

        df_price = pd.read_sql(query, con_craw)

        if df_price.empty:
            print(f"✗ {code} 종목의 주가 데이터가 없습니다.")
            con.close()
            con_craw.close()
            return False

        print(f"✓ 주가 데이터 조회 성공: {len(df_price)}일치")
        print(f"\n  최근 데이터:")
        print(f"    날짜: {df_price.iloc[0]['date']}")
        print(f"    종가: {df_price.iloc[0]['close']:,}원")
        print(f"    거래량: {df_price.iloc[0]['volume']:,}주")

        con.close()
        con_craw.close()

        print("\n✅ 데이터 조회 성공!")
        return True

    except Exception as e:
        print(f"\n✗ 데이터 조회 실패: {e}")
        traceback.print_exc()
        return False


def main():
    """메인 테스트 실행"""
    print("\n")
    print("*" * 80)
    print("*" + " " * 78 + "*")
    print("*" + " " * 20 + "고급 전략 시스템 통합 테스트" + " " * 28 + "*")
    print("*" + " " * 78 + "*")
    print("*" * 80)
    print(f"\n실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    tests = [
        ("모듈 Import", test_1_imports),
        ("데이터베이스 연결", test_2_db_connection),
        ("클래스 초기화", test_3_class_initialization),
        ("통합 시스템", test_4_advanced_system),
        ("데이터 조회", test_5_data_fetch),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ {test_name} 테스트 중 예외 발생: {e}")
            traceback.print_exc()
            results.append((test_name, False))

    # 최종 결과
    print("\n" + "=" * 80)
    print("테스트 결과 요약")
    print("=" * 80)

    for test_name, result in results:
        status = "✅ 성공" if result else "❌ 실패"
        print(f"{status} - {test_name}")

    success_count = sum(1 for _, result in results if result)
    total_count = len(results)

    print("\n" + "=" * 80)
    print(f"총 {total_count}개 테스트 중 {success_count}개 성공")
    print("=" * 80)

    if success_count == total_count:
        print("\n🎉 모든 테스트 통과! 시스템이 정상적으로 작동합니다.")
        print("\n다음 단계:")
        print("  1. python run_advanced_strategy.py --mode scan")
        print("  2. 생성된 buy_list CSV 파일 확인")
        print("  3. 모의투자로 테스트")
        return 0
    else:
        print(f"\n⚠️  {total_count - success_count}개 테스트 실패")
        print("\n실패한 테스트를 확인하고 필요한 패키지를 설치하세요:")
        print("  pip install numpy pandas scipy scikit-learn pymysql PyQt5 tensorflow")
        return 1


if __name__ == "__main__":
    sys.exit(main())
