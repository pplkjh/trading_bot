# version 1.3.2
print("collector 프로그램이 시작 되었습니다!")

import time
from library.collector_api import *

class Collector:
    print("collector 클래스에 들어왔습니다.")

    def __init__(self):
        print("__init__ 함수에 들어왔습니다.")
        self.collector_api = collector_api()

    def collecting(self):
        self.collector_api.code_update_check()

if __name__ == "__main__":
    print("__main__에 들어왔습니다.")
    # 아래는 키움증권 openapi를 사용하기 위해 사용하는 한 줄! 이해 할 필요 X
    app = QApplication(sys.argv)
    c = Collector()
    # 데이터 수집 시작 -> 주식 종목, 종목별 금융 데이터 모두 데이터베이스에 저장.
    c.collecting()

    # 완료 메시지 및 대기
    print("\n" + "="*70)
    print("✅ 데이터 수집이 완료되었습니다!")
    print("="*70)
    print("📊 수집된 데이터를 확인하려면 Ctrl+C를 눌러 창을 유지하세요.")
    print("⏰ 60초 후 자동으로 종료됩니다...")
    print("="*70 + "\n")

    try:
        for i in range(60, 0, -1):
            print(f"\r종료까지 {i}초 남음... (Ctrl+C로 중단 가능)", end="", flush=True)
            time.sleep(1)
        print("\n\n프로그램을 종료합니다.")
    except KeyboardInterrupt:
        print("\n\n사용자가 종료를 취소했습니다. 창이 유지됩니다.")
        print("종료하려면 아무 키나 누르세요...")
        input()
