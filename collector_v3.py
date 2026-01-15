# version 1.3.5
import sys
import time
from PyQt5.QtWidgets import QApplication
from library.collector_api import *
from library.report_generator import generate_collector_report
from datetime import datetime  # collector_api의 import 이후에 선언

print("\n" + "="*100)
print("🚀 JackBot 데이터 수집 시스템")
print("="*100)
print(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*100)

class Collector:

    def __init__(self):
        print("\n📡 키움증권 OpenAPI 연결 중...")
        self.collector_api = collector_api()
        print("✅ 연결 완료")

    def collecting(self):
        self.collector_api.code_update_check()

if __name__ == "__main__":
    try:
        # 아래는 키움증권 openapi를 사용하기 위해 사용하는 한 줄! 이해 할 필요 X
        app = QApplication(sys.argv)
        c = Collector()
        # 데이터 수집 시작 -> 주식 종목, 종목별 금융 데이터 모두 데이터베이스에 저장.
        c.collecting()

        # 완료 메시지 및 대기
        print("\n" + "="*100)
        print(f"✅ 데이터 수집 완료! (종료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
        print("="*100)

        # 데일리 리포트 생성
        print("\n📊 수집 결과 리포트 생성 중...")
        try:
            report_path = generate_collector_report(c.collector_api)
            if report_path:
                print(f"✅ 리포트 생성 완료!")
                print(f"📁 파일 위치: {report_path}")
            else:
                print("⚠️  리포트 생성 실패")
        except Exception as e:
            print(f"⚠️  리포트 생성 오류: {e}")

        print("\n" + "="*100)
        print("💡 리포트 파일을 열어 상세한 수집 결과를 확인하세요")
        print("⏰ 60초 후 자동으로 종료됩니다 (Ctrl+C로 중단 가능)")
        print("="*100 + "\n")

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

        # 60초 정상 완료 시 종료 (batch에서 cmd 종료 처리)
        if not user_interrupted:
            sys.exit(0)

    except Exception as e:
        print("\n" + "="*100)
        print(f"❌ 데이터 수집 중 오류 발생!")
        print("="*100)
        print(f"\n오류 내용: {e}")
        import traceback
        traceback.print_exc()

        # 오류 발생 시에도 60초 대기
        print("\n" + "="*100)
        print("⏰ 60초 후 자동으로 종료됩니다 (Ctrl+C로 중단 가능)")
        print("📝 상세 로그: log/jackbot.log")
        print("="*100 + "\n")

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

        # 60초 정상 완료 시 에러 코드로 종료 (batch에서 cmd 종료 처리)
        if not user_interrupted:
            sys.exit(1)
