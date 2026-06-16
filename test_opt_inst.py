# -*- coding: utf-8 -*-
"""
OPT10044 / OPT10045 필드 구조 확인 스크립트
실행: python test_opt_inst.py
결과를 콘솔에 출력하므로 그대로 복붙해주면 됨
"""
import sys
import os
import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QEventLoop
from library.open_api import open_api
from library import cf

TODAY = datetime.datetime.now().strftime('%Y%m%d')
YESTERDAY = (datetime.datetime.now() - datetime.timedelta(days=3)).strftime('%Y%m%d')
TEST_CODE = '005930'   # 삼성전자 (opt10045 테스트용)
SCREEN = '9999'

app = QApplication(sys.argv)
api = open_api()

# ── 로그인 대기 ─────────────────────────────────────────────────
login_loop = QEventLoop()
api.OnEventConnect.connect(lambda err: login_loop.exit())
api.dynamicCall("CommConnect()")
login_loop.exec_()
print(f"[로그인 완료] 상태: {api.dynamicCall('GetConnectState()')}")


# ───────────────────────────────────────────────────────────────
# 공통: GetCommDataEx로 전체 필드 덤프
# ───────────────────────────────────────────────────────────────
def dump_all_fields(rqname, trcode):
    """GetCommDataEx — 멀티행 데이터 전체 반환 (필드명 + 값 포함)"""
    try:
        result = api.dynamicCall(
            "GetCommDataEx(QString, QString)", trcode, rqname)
        return result   # list of list
    except Exception as e:
        print(f"  GetCommDataEx 실패: {e}")
        return None


# ───────────────────────────────────────────────────────────────
# OPT10044 테스트
# ───────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("OPT10044 — 일별기관매매종목요청")
print(f"  시작일자: {YESTERDAY}  종료일자: {TODAY}")
print(f"  매매구분: 2(순매수)  시장구분: 001(코스피)")
print("="*60)

result_44 = {}

def on_receive_44(screen, rqname, trcode, record, next):
    try:
        data = dump_all_fields(rqname, trcode)
        if data:
            print(f"\n[GetCommDataEx] 행수: {len(data)}")
            if len(data) > 0:
                print(f"  첫 행 컬럼수: {len(data[0]) if data[0] else 0}")
                print(f"  첫 행 샘플: {data[0][:10] if data[0] else '없음'}")
            for i, row in enumerate(data[:3]):   # 처음 3행만 출력
                print(f"  row[{i}]: {row}")
        else:
            # GetCommDataEx 안 되면 repeat_cnt 방식
            cnt = api.dynamicCall("GetRepeatCnt(QString,QString)", trcode, rqname)
            print(f"\n[GetRepeatCnt] 행수: {cnt}")
            # 추정 필드 목록 시도
            fields = ["종목코드","종목명","현재가","전일대비","등락률","거래량",
                      "기관합계","기관순매수","외국인합계","외국인순매수",
                      "기관순매매수량","외국인순매매수량","기관매수","기관매도",
                      "외국인매수","외국인매도","프로그램매수","프로그램매도"]
            for i in range(min(cnt, 3)):
                print(f"  --- row {i} ---")
                for f in fields:
                    val = api.dynamicCall(
                        "GetCommData(QString,QString,int,QString)", trcode, rqname, i, f)
                    if val.strip():
                        print(f"    {f}: {val.strip()}")
    except Exception as e:
        print(f"  처리 오류: {e}")
    finally:
        result_44['done'] = True
        loop_44.exit()

loop_44 = QEventLoop()
api.OnReceiveTrData.connect(on_receive_44)
api.dynamicCall("SetInputValue(QString,QString)", "시작일자", YESTERDAY)
api.dynamicCall("SetInputValue(QString,QString)", "종료일자", TODAY)
api.dynamicCall("SetInputValue(QString,QString)", "매매구분", "2")
api.dynamicCall("SetInputValue(QString,QString)", "시장구분", "001")
api.dynamicCall("CommRqData(QString,QString,int,QString)", "opt10044_req", "OPT10044", 0, SCREEN)
loop_44.exec_()
api.OnReceiveTrData.disconnect(on_receive_44)


# ───────────────────────────────────────────────────────────────
# OPT10045 테스트 (삼성전자 최근 5일)
# ───────────────────────────────────────────────────────────────
import time; time.sleep(0.5)

START_5D = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%Y%m%d')

print("\n" + "="*60)
print("OPT10045 — 종목별기관매매추이요청")
print(f"  종목코드: {TEST_CODE}  기간: {START_5D} ~ {TODAY}")
print("="*60)

def on_receive_45(screen, rqname, trcode, record, next):
    try:
        data = dump_all_fields(rqname, trcode)
        if data:
            print(f"\n[GetCommDataEx] 행수: {len(data)}")
            for i, row in enumerate(data[:5]):
                print(f"  row[{i}]: {row}")
        else:
            cnt = api.dynamicCall("GetRepeatCnt(QString,QString)", trcode, rqname)
            print(f"\n[GetRepeatCnt] 행수: {cnt}")
            fields = ["일자","현재가","전일대비","거래량",
                      "기관합계","기관순매수","기관순매매수량",
                      "외국인합계","외국인순매수","외국인순매매수량",
                      "기관추정단가","외인추정단가",
                      "기관매수","기관매도","외국인매수","외국인매도",
                      "개인순매수","프로그램순매수"]
            for i in range(min(cnt, 5)):
                print(f"  --- row {i} ---")
                for f in fields:
                    val = api.dynamicCall(
                        "GetCommData(QString,QString,int,QString)", trcode, rqname, i, f)
                    if val.strip():
                        print(f"    {f}: {val.strip()}")
    except Exception as e:
        print(f"  처리 오류: {e}")
    finally:
        loop_45.exit()

loop_45 = QEventLoop()
api.OnReceiveTrData.connect(on_receive_45)
api.dynamicCall("SetInputValue(QString,QString)", "종목코드", TEST_CODE)
api.dynamicCall("SetInputValue(QString,QString)", "시작일자", START_5D)
api.dynamicCall("SetInputValue(QString,QString)", "종료일자", TODAY)
api.dynamicCall("SetInputValue(QString,QString)", "기관추정단가구분", "1")
api.dynamicCall("SetInputValue(QString,QString)", "외인추정단가구분", "1")
api.dynamicCall("CommRqData(QString,QString,int,QString)", "opt10045_req", "OPT10045", 0, SCREEN)
loop_45.exec_()
api.OnReceiveTrData.disconnect(on_receive_45)

print("\n[완료]")
sys.exit(0)
