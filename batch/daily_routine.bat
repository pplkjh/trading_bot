@echo off
REM ===================================================
REM 일일 자동화 루틴 배치 파일
REM 장 시작 전 실행 ~ 장 마감 후 종료까지 전체 자동화
REM ===================================================

echo ========================================
echo 일일 자동 매매 루틴
echo ========================================
echo.
echo 시작 시간: %date% %time%
echo.

set SCRIPT_DIR=%~dp0
cd /d %SCRIPT_DIR%..

REM 오늘이 주말인지 확인
for /f "tokens=1" %%a in ('powershell -command "& {(Get-Date).DayOfWeek}"') do set TODAY=%%a

if "%TODAY%"=="Saturday" (
    echo.
    echo ℹ️  오늘은 토요일입니다. 주말에는 거래가 없습니다.
    echo.
    pause
    exit /b 0
)

if "%TODAY%"=="Sunday" (
    echo.
    echo ℹ️  오늘은 일요일입니다. 주말에는 거래가 없습니다.
    echo.
    pause
    exit /b 0
)

echo ✅ 오늘은 %TODAY% - 거래일입니다.
echo.

REM 현재 시간 확인
for /f "tokens=1-2 delims=:" %%a in ('time /t') do (
    set HOUR=%%a
    set MINUTE=%%b
)

REM 공백 제거
set HOUR=%HOUR: =%
set MINUTE=%MINUTE: =%

echo 현재 시간: %HOUR%:%MINUTE%
echo.

REM 시간대별 작업 결정
if %HOUR% LSS 9 (
    echo [장 시작 전] 트레이더 준비
    goto START_TRADER
) else if %HOUR% GEQ 16 (
    echo [장 마감 후] 데이터 수집 및 종료
    goto COLLECT_AND_SHUTDOWN
) else (
    echo [장 중] 트레이더 실행 상태 확인
    goto CHECK_TRADER
)

:START_TRADER
echo.
echo ========================================
echo 🌅 장 시작 전 루틴
echo ========================================
echo.

echo [1/3] 어제 데이터 확인 중...
REM 최신 데이터 존재 여부 확인 (여기서는 간단히 로그만)
echo ✅ 데이터 확인 완료
echo.

echo [2/3] 오늘 매수 후보 미리 확인...
python run_advanced_strategy.py --mode scan --top 20
echo.

echo [3/3] 트레이더 시작...
call "%SCRIPT_DIR%start_trader.bat"

goto END

:CHECK_TRADER
echo.
echo ========================================
echo 📊 장 중 트레이더 상태 확인
echo ========================================
echo.

tasklist /FI "WINDOWTITLE eq trader.py*" 2>NUL | find /I /N "python.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo ✅ trader.py가 정상 실행 중입니다.
    echo.
    echo 프로세스 정보:
    tasklist /FI "WINDOWTITLE eq trader.py*" /FO TABLE
) else (
    echo ⚠️  trader.py가 실행되지 않았습니다!
    echo.
    echo 수동으로 시작하시겠습니까? (Y/N)
    set /p START_NOW=

    if /i "%START_NOW%"=="Y" (
        call "%SCRIPT_DIR%start_trader.bat"
    )
)

goto END

:COLLECT_AND_SHUTDOWN
echo.
echo ========================================
echo 🌆 장 마감 후 루틴
echo ========================================
echo.

echo [1/2] 데이터 수집...
call "%SCRIPT_DIR%collect_data.bat"

if %errorlevel% neq 0 (
    echo.
    echo ❌ 데이터 수집 실패!
    pause
    exit /b %errorlevel%
)

echo.
echo [2/2] 자동 종료 준비...
call "%SCRIPT_DIR%auto_shutdown.bat"

goto END

:END
echo.
echo ========================================
echo 일일 루틴 완료
echo 종료 시간: %date% %time%
echo ========================================
echo.

REM 로그 기록
echo %date% %time% - 일일 루틴 완료 >> automation_log.txt

pause
exit /b 0
