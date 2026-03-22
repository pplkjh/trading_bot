@echo off
REM ========================================
REM Collector Auto-Restart Script
REM ========================================
REM Auto restart on error
REM Exit on success
REM ========================================

echo ========================================
echo Collector Auto-Restart Script
echo ========================================
echo.
echo Auto restart on error.
echo Auto exit on success.
echo.
echo Press Ctrl+C to stop
echo ========================================
echo.

REM Python path setup
set SCRIPT_DIR=%~dp0

REM Move to project root directory
cd /d %SCRIPT_DIR%..

REM Activate Anaconda py37_32 environment
call C:\Users\%USERNAME%\anaconda3\Scripts\activate.bat py37_32

REM 재시작 횟수 초기화 (최대 5회)
set RESTART_COUNT=0

:LOOP
    set /a RESTART_COUNT+=1
    echo.
    echo [%date% %time%] Collector starting... (시도 %RESTART_COUNT%/5)
    echo ========================================

    REM Run collector
    python collector_v3.py
    set COLLECTOR_EXIT=%ERRORLEVEL%
    echo [DEBUG] Collector exit code: %COLLECTOR_EXIT% (attempt %RESTART_COUNT%) >> automation_log.txt
    echo [DEBUG] Collector exit code: %COLLECTOR_EXIT% (attempt %RESTART_COUNT%)
    echo [%date% %time%] [BAT] collector_v3.py exited with code %COLLECTOR_EXIT% (attempt %RESTART_COUNT%/5) >> log\jackbot.log

    REM 재시작 횟수 초과 → trader로 강제 이동
    if %RESTART_COUNT% GEQ 5 (
        echo.
        echo [%date% %time%] [WARN] Max retries 5 reached. Moving to trader.
        echo [%date% %time%] [BAT] WARN max retries reached moving to trader >> log\jackbot.log
        echo ========================================
        echo.
        goto END
    )

    REM 스코어링 완료 여부 먼저 확인 (exit code 무관 - 작업 완료가 우선)
    REM 이유: Python/Qt 프로세스가 종료 시 크래시해도 실제 작업은 완료됐을 수 있음
    python "%SCRIPT_DIR%check_collector_done.py"
    set DONE_CHECK=%ERRORLEVEL%
    echo [DEBUG] DONE_CHECK=%DONE_CHECK%, EXIT=%COLLECTOR_EXIT% >> automation_log.txt
    echo [DEBUG] DONE_CHECK=%DONE_CHECK%, EXIT=%COLLECTOR_EXIT%
    echo [%date% %time%] [BAT] DONE_CHECK=%DONE_CHECK% EXIT=%COLLECTOR_EXIT% >> log\jackbot.log

    if "%DONE_CHECK%"=="0" (
        REM 스코어링 완료 → exit code 무관하게 trader로 진행
        echo.
        echo [%date% %time%] Scoring complete. Starting Trader.
        echo ========================================
        echo.
        goto END
    )

    REM 스코어링 미완료 → 크래시 여부 확인 후 재시작
    if NOT "%COLLECTOR_EXIT%"=="0" (
        echo.
        echo [%date% %time%] Collector crashed code %COLLECTOR_EXIT%. Restarting in 5 seconds...
        echo [%date% %time%] [BAT] crash detected restarting >> log\jackbot.log
        echo ========================================
        echo.
        timeout /t 5 /nobreak
        goto LOOP
    )

    REM 정상 종료인데 스코어링 미완료 → 재시작
    echo.
    echo [%date% %time%] [WARN] Scoring incomplete despite normal exit. Restarting in 5 seconds...
    echo [%date% %time%] [BAT] scoring incomplete restarting >> log\jackbot.log
    echo ========================================
    echo.
    timeout /t 5 /nobreak
    goto LOOP

:END
echo.
echo ========================================
echo Collector Complete - Starting Trader
echo %date% %time%
echo ========================================
echo.

REM collector 크래시 후 COM/Qt 정리 대기
echo [INFO] Waiting 15s for COM cleanup before trader...
echo [%date% %time%] [BAT] waiting 15s for COM cleanup before trader >> log\jackbot.log
timeout /t 15 /nobreak >NUL

REM Start Trader after Collector completes
echo [INFO] Starting Trader...
start /wait cmd /c "%SCRIPT_DIR%start_trader.bat"

echo.
echo ========================================
echo Trader Exit - Shutdown Check
echo %date% %time%
echo ========================================
echo.

REM Start shutdown prompt after Trader completes (30min timer)
echo [INFO] Starting shutdown prompt...
call "%SCRIPT_DIR%shutdown_prompt.bat"

exit
