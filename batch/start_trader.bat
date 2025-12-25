@echo off
REM ===================================================
REM 자동 트레이더 실행 배치 파일
REM 장 시작 30분 전에 실행하여 자동 매매를 시작합니다
REM ===================================================

echo ========================================
echo 자동 매매 트레이더 시작
echo ========================================
echo.
echo 시작 시간: %date% %time%
echo.

REM Python 경로 설정
set PYTHON_PATH=python
set SCRIPT_DIR=%~dp0

REM 작업 디렉토리로 이동 (batch 폴더의 상위 디렉토리)
cd /d %SCRIPT_DIR%..

echo [INFO] 작업 디렉토리: %cd%
echo.

REM 영업일 체크
echo [INFO] 주식 장 영업일 확인 중...
%PYTHON_PATH% check_trading_day.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] 오늘은 주식 장이 열리지 않는 날입니다.
    echo [INFO] 자세한 내용은 위 메시지를 확인하세요.
    pause
    exit /b 1
)
echo.

REM 기존 trader_advanced.py 프로세스 확인
tasklist /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq trader_advanced.py*" 2>NUL | find /I /N "python.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo [WARNING] 이미 trader_advanced.py가 실행 중입니다.
    echo 기존 프로세스를 종료하시겠습니까? (Y/N)
    set /p KILL_PROCESS=

    if /i "%KILL_PROCESS%"=="Y" (
        echo 기존 프로세스 종료 중...
        taskkill /F /FI "WINDOWTITLE eq trader_advanced.py*" >NUL 2>&1
        timeout /t 3 >NUL
    ) else (
        echo 기존 프로세스를 유지합니다.
        pause
        exit /b 0
    )
)

echo [1/2] 키움 OpenAPI 연결 확인 중...
echo.
echo [OK] 자동 실행 모드
echo.

echo [2/2] 트레이더 실행 중...
echo.
echo [START] trader_advanced.py가 실행됩니다.
echo [INFO] 키움 로그인 창이 나타나면 로그인하세요.
echo.

REM trader_advanced.py 실행
%PYTHON_PATH% trader_advanced.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] 트레이더 실행 실패!
    echo 오류 코드: %errorlevel%
    pause
    exit /b %errorlevel%
)

echo.
echo ========================================
echo 트레이더 종료됨
echo 종료 시간: %date% %time%
echo ========================================
echo.

REM 로그 기록
echo %date% %time% - 트레이더 종료 >> automation_log.txt

pause
exit /b 0
