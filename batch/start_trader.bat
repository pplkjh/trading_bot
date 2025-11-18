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

REM 기존 trader.py 프로세스 확인
tasklist /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq trader.py*" 2>NUL | find /I /N "python.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo ⚠️  이미 trader.py가 실행 중입니다.
    echo 기존 프로세스를 종료하시겠습니까? (Y/N)
    set /p KILL_PROCESS=

    if /i "%KILL_PROCESS%"=="Y" (
        echo 기존 프로세스 종료 중...
        taskkill /F /FI "WINDOWTITLE eq trader.py*" >NUL 2>&1
        timeout /t 3 >NUL
    ) else (
        echo 기존 프로세스를 유지합니다.
        pause
        exit /b 0
    )
)

echo [1/2] 키움 OpenAPI 연결 확인 중...
echo.

REM 모의투자(1) 또는 실전투자(2) 선택
echo 매매 모드를 선택하세요:
echo   1 = 모의투자 (안전)
echo   2 = 실전투자 (주의!)
echo.
set /p TRADE_MODE=모드 선택 (1 또는 2):

if "%TRADE_MODE%"=="1" (
    echo.
    echo ✅ 모의투자 모드로 시작합니다
    echo.
) else if "%TRADE_MODE%"=="2" (
    echo.
    echo ⚠️⚠️⚠️ 실전투자 모드입니다! ⚠️⚠️⚠️
    echo 정말 실전 계좌로 매매하시겠습니까? (YES 입력)
    set /p CONFIRM=확인:

    if not "%CONFIRM%"=="YES" (
        echo 취소되었습니다.
        pause
        exit /b 0
    )
) else (
    echo ❌ 잘못된 입력입니다.
    pause
    exit /b 1
)

echo [2/2] 트레이더 실행 중...
echo.
echo 📊 trader.py가 실행됩니다.
echo 💡 키움 로그인 창이 나타나면 로그인하세요.
echo.

REM trader.py 실행 (모드를 자동 입력)
echo %TRADE_MODE%| %PYTHON_PATH% trader.py

if %errorlevel% neq 0 (
    echo.
    echo ❌ 트레이더 실행 실패!
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
