# version 1.3.7
import sys
import os
import traceback
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# conda py37_32 환경에서 conda activate 없이 실행될 때 Library\bin이 PATH에 없으면
# _ssl.pyd가 libssl-1_1.dll 을 못 찾아 ssl import 실패 → HTTPS 연결 불가.
# 첫 import 전에 PATH 보정.
_lib_bin = os.path.join(os.path.dirname(sys.executable), 'Library', 'bin')
if os.path.isdir(_lib_bin) and _lib_bin not in os.environ.get('PATH', ''):
    os.environ['PATH'] = _lib_bin + os.pathsep + os.environ.get('PATH', '')
from PyQt5.QtWidgets import QApplication
from library.collector_api import *
from library.report_generator import generate_collector_report
from datetime import datetime  # collector_api의 import 이후에 선언

def _global_exception_handler(exc_type, exc_value, exc_tb):
    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logger.error(f"[UNCAUGHT EXCEPTION] {exc_type.__name__}: {exc_value}")
    logger.error(tb_str)

sys.excepthook = _global_exception_handler

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

    def collecting(self, phase=None):
        self.collector_api.code_update_check(phase=phase)

if __name__ == "__main__":
    # --phase 1|2|3 인자 파싱 (없으면 전체 실행)
    phase = None
    for arg in sys.argv[1:]:
        if arg.startswith('--phase='):
            phase = int(arg.split('=')[1])
        elif arg in ('1', '2', '3') and sys.argv.index(arg) > 0 and sys.argv[sys.argv.index(arg)-1] == '--phase':
            phase = int(arg)
    # '--phase 1' 형식 (공백 구분)
    if '--phase' in sys.argv:
        idx = sys.argv.index('--phase')
        if idx + 1 < len(sys.argv):
            phase = int(sys.argv[idx + 1])

    try:
        # 아래는 키움증권 openapi를 사용하기 위해 사용하는 한 줄! 이해 할 필요 X
        app = QApplication(sys.argv)
        c = Collector()
        # 데이터 수집 시작 -> 주식 종목, 종목별 금융 데이터 모두 데이터베이스에 저장.
        c.collecting(phase=phase)

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
        print("Collector finished. Starting Trader...")
        print("="*100 + "\n")

        # Kiwoom COM 해제: Python GC가 QAxWidget 소멸자를 호출해 COM Release()가 실행됨.
        # os._exit(0)은 GC를 건너뛰어 COM 공유 상태(레지스트리/공유 메모리)가 "살아있는" 채로
        # 남아 다음 phase Python이 Kiwoom DLL 로드 시 ACCESS VIOLATION(0xC0000005) 유발.
        # sys.exit(0)은 SystemExit를 발생시켜 Python GC가 COM 객체를 정상 소멸시킴.
        try:
            print(f"[collector] phase={phase} COM clear() start", flush=True)
            c.collector_api.open_api.clear()
            print(f"[collector] phase={phase} COM clear() done", flush=True)
            import gc; gc.collect()
            print(f"[collector] phase={phase} GC done", flush=True)
            import time as _t; _t.sleep(3)
        except Exception as _ce:
            print(f"[collector] phase={phase} COM clear error: {_ce}", flush=True)

        print(f"[collector] phase={phase} sys.exit(0)", flush=True)
        sys.exit(0)

    except Exception as e:
        import traceback
        import logging
        tb_str = traceback.format_exc()

        print("\n" + "="*100)
        print(f"❌ 데이터 수집 중 오류 발생!")
        print("="*100)
        print(f"\n오류 내용: {e}")
        print(tb_str)

        logger.error(f"❌ collector 오류 발생: {e}")
        logger.error(tb_str)

        # 에러를 직접 파일에 기록 (os._exit가 버퍼를 flush하지 않으므로)
        try:
            with open('log/collector_error.log', 'a', encoding='utf-8') as f:
                f.write(f"\n[{datetime.now()}] ❌ collector 오류 (phase={phase})\n")
                f.write(f"오류: {e}\n")
                f.write(tb_str)
                f.write("="*80 + "\n")
        except Exception:
            pass

        logging.shutdown()  # 로그 버퍼 강제 flush

        # Kiwoom COM 해제
        try:
            print(f"[collector] phase={phase} error-path COM clear() start", flush=True)
            c.collector_api.open_api.clear()
            import gc; gc.collect()
            import time as _t; _t.sleep(3)
            print(f"[collector] phase={phase} error-path COM clear() done", flush=True)
        except Exception as _ce2:
            print(f"[collector] phase={phase} error-path COM clear error: {_ce2}", flush=True)

        # 에러 발생 - exit code 1로 종료 (batch에서 재시작)
        print("\n" + "="*100)
        print("Error occurred. Collector will restart...")
        print("="*100 + "\n")
        print(f"[collector] phase={phase} sys.exit(1)", flush=True)
        sys.exit(1)
