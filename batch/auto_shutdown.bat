@echo off
REM ===================================================
REM 자동 종료 배치 파일
REM 장 마감 후 데이터 수집 완료 후 컴퓨터를 자동으로 종료합니다
REM ===================================================

echo ========================================
echo 자동 종료 프로세스 시작
echo ========================================
echo.
echo 현재 시간: %date% %time%
echo.

set SCRIPT_DIR=%~dp0

REM 작업 디렉토리로 이동
cd /d %SCRIPT_DIR%..

echo [1/4] 실행 중인 trader.py 종료 중...
echo.

REM trader.py 프로세스 종료
tasklist /FI "WINDOWTITLE eq trader.py*" 2>NUL | find /I /N "python.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo trader.py 종료 중...
    taskkill /F /FI "WINDOWTITLE eq trader.py*" >NUL 2>&1
    timeout /t 5 >NUL
    echo ✅ trader.py 종료 완료
) else (
    echo ℹ️  실행 중인 trader.py가 없습니다
)

echo.
echo [2/4] 데이터 수집 중...
echo.

REM 데이터 수집 배치 파일 실행
call "%SCRIPT_DIR%collect_data.bat"

if %errorlevel% neq 0 (
    echo.
    echo ❌ 데이터 수집 실패!
    echo 컴퓨터를 종료하지 않습니다.
    pause
    exit /b %errorlevel%
)

echo.
echo [3/4] 정리 작업 중...
echo.

REM 임시 파일 정리 (선택사항)
if exist "*.tmp" del /q "*.tmp" >NUL 2>&1
if exist "__pycache__" rmdir /s /q "__pycache__" >NUL 2>&1

echo ✅ 정리 완료
echo.

echo [4/4] 컴퓨터 종료 준비...
echo.

REM 로그 기록
echo %date% %time% - 자동 종료 시작 >> automation_log.txt

REM 종료 옵션 선택
echo 종료 옵션을 선택하세요:
echo   1 = 종료 (Shutdown)
echo   2 = 절전 모드 (Sleep)
echo   3 = 최대 절전 모드 (Hibernate)
echo   4 = 취소
echo.
set /p SHUTDOWN_MODE=선택 (기본값: 1):

if "%SHUTDOWN_MODE%"=="" set SHUTDOWN_MODE=1

if "%SHUTDOWN_MODE%"=="1" (
    echo.
    echo 💤 30초 후 컴퓨터를 종료합니다...
    echo 취소하려면 Ctrl+C를 누르세요.
    echo.
    shutdown /s /t 30 /c "자동 매매 데이터 수집 완료. 컴퓨터를 종료합니다."
) else if "%SHUTDOWN_MODE%"=="2" (
    echo.
    echo 💤 10초 후 절전 모드로 전환합니다...
    timeout /t 10
    rundll32.exe powrprof.dll,SetSuspendState 0,1,0
) else if "%SHUTDOWN_MODE%"=="3" (
    echo.
    echo 💤 10초 후 최대 절전 모드로 전환합니다...
    timeout /t 10
    shutdown /h
) else (
    echo.
    echo ℹ️  종료가 취소되었습니다.
)

echo.
echo ========================================
echo 작업 완료
echo 종료 시간: %date% %time%
echo ========================================
echo.

exit /b 0
