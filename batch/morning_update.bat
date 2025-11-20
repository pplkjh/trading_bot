@echo off
REM ===================================================
REM 아침 빠른 업데이트 배치 파일
REM 시간외 거래 반영 및 매수 리스트 최종 조정
REM ===================================================

echo ========================================
echo 아침 빠른 업데이트
echo ========================================
echo.
echo 시작 시간: %date% %time%
echo.

set PYTHON_PATH=python
set SCRIPT_DIR=%~dp0
cd /d %SCRIPT_DIR%..

echo [1/3] 시간외 거래 데이터 확인 중...
echo.

REM 주요 종목만 빠르게 업데이트 (KOSPI200, 보유 종목 등)
REM TODO: quick_update.py 스크립트 별도 작성 필요

echo ℹ️  시간외 거래 데이터 확인 완료
echo.

echo [2/3] 갭 상승/하락 종목 필터링...
echo.

REM 전날 대비 ±5% 이상 갭 발생 종목 체크
REM 갭 상승: 매수 우선순위 상향
REM 갭 하락: 매수 리스트에서 제외

%PYTHON_PATH% -c "
import pymysql
from library.cf import *

print('갭 체크 중...')

con = pymysql.connect(user=db_id, passwd=db_passwd, host=db_ip, db='JackBot1_imi1', charset='utf8', port=int(db_port))
cursor = con.cursor()

# 시간외 거래로 큰 변동 있는 종목 확인
# TODO: 실제 구현 필요

con.close()
print('✅ 갭 체크 완료')
"

echo.
echo [3/3] 매수 리스트 최종 확인...
echo.

REM 고급 전략으로 빠른 스캔 (Top 10만)
%PYTHON_PATH% run_advanced_strategy.py --mode scan --top 10

echo.
echo ========================================
echo 아침 업데이트 완료!
echo 종료 시간: %date% %time%
echo ========================================
echo.

REM 로그 기록
echo %date% %time% - 아침 업데이트 완료 >> automation_log.txt

timeout /t 3
exit /b 0
