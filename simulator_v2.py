# -*- coding: utf-8 -*-
import os
import sys
from datetime import datetime

# import 전에 설정해야 logging_pack.py가 올바른 파일 경로를 사용함
_simul_num = sys.argv[1] if len(sys.argv) >= 2 else 'X'
_date = datetime.now().strftime('%Y%m%d')
os.environ['JACKBOT_LOG_FILE'] = f'backtest_sim{_simul_num}_{_date}.log'
os.environ.setdefault('JACKBOT_LOG_NAME', 'simulator')

from library.simulator_func_mysql import *


class simulator_v2():
    def __init__(self):
        if len(sys.argv) == 1:
            self.print_info()
        elif len(sys.argv) == 3:
            self.simul_num = sys.argv[1]
            self.simul_reset = sys.argv[2]
        self.input_value()

    def print_info(self):
        # 시뮬레이터 번호 설정
        self.simul_num = int(input("시뮬레이팅 할 알고리즘 번호를 입력 하세요: "))

        # self.simul_reset 설정
        #       'y'  :  self.simul_num 에서 설정한 번호에 해당 하는 시뮬레이터 데이터베이스를 초기화 하고 처음 부터 실행
        #       'n' : self.simul_num 에서 설정한 번호에 해당 하는 시뮬레이터 데이터베이스를 초기화 하지 않고 이어서 실행
        #                    ex) 2020년 01월 01일까지 시뮬레이터를 마쳤는데, 그 이후로 연달아서 2020년 01월 02일 부터 시뮬레이터 테스트를 하고 싶은 경우

        option = str(input("시뮬레이팅 데이터베이스 초기화 여부 : (y or n) "))

        if option == 'y':
            self.simul_reset = 'reset'
        elif option == 'n':
            self.simul_reset = 'continue'
        else:
            print("y or n (소문자) 만 입력 가능 합니다.")
            exit(1)

    def input_value(self):
        # 시뮬레이터 시작 헤더
        print("\n" + "=" * 60)
        print("🚀 백테스트 시뮬레이터")
        print("=" * 60)
        print(f"📊 알고리즘: {self.simul_num}번")
        print(f"🔄 모드: {'초기화 후 실행' if self.simul_reset == 'reset' else '이어서 실행'}")
        print("=" * 60 + "\n")

        # simulator_func_mysql 라이브러리 클래스 호출
        sim = simulator_func_mysql(self.simul_num, self.simul_reset, 0)

        # 시뮬레이터 완료 메시지
        print("\n" + "=" * 60)
        print("✅ 백테스트 완료!")
        print("=" * 60)

        # 그래프 저장 여부 확인
        print("\n" + "-" * 60)
        save_graph = input("📊 누적 수익률 그래프를 저장하시겠습니까? (y/n): ").strip().lower()
        if save_graph == 'y':
            print("💾 그래프가 이미 저장되었습니다.")
        else:
            print("⏭️  그래프 저장을 건너뜁니다.")

        # 상세 분석 레포트 생성 여부 확인
        print("\n" + "-" * 60)
        generate_report = input("📝 상세 분석 레포트를 생성하시겠습니까? (y/n): ").strip().lower()
        if generate_report == 'y':
            print("\n" + "=" * 60)
            print("📊 상세 분석 레포트 생성 중...")
            print("=" * 60 + "\n")
            sim.generate_detailed_analysis_report()
        else:
            print("⏭️  레포트 생성을 건너뜁니다.")

        print("\n" + "=" * 60)


if __name__ == "__main__":
    # simulator 클래스 호출
    simulator_v2()
