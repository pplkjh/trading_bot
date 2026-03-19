@echo off
REM ===================================================
REM Auto Trader Startup Script
REM - 정상 종료(exit 0): 재시작 안 함
REM - 크래시(exit non-0) + 장 시간 내: 자동 재시작 (최대 5회)
REM ===================================================

set SCRIPT_DIR=%~dp0
cd /d %SCRIPT_DIR%..
call C:\Users\USER\anaconda3\Scripts\activate.bat py37_32

echo ========================================
echo Auto Trader Starting
echo Start time: %date% %time%
echo ========================================
echo.

echo [INFO] Working directory: %cd%
echo.

REM Check if trading day
echo [INFO] Checking trading day...
python check_trading_day.py
if %errorlevel% neq 0 (
    echo [INFO] Market is closed today.
    goto END
)
echo.

REM Kill existing python process for clean start
tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I "python.exe" >NUL
if "%ERRORLEVEL%"=="0" (
    echo [INFO] Existing Python process found. Killing for clean start...
    taskkill /F /IM python.exe >NUL 2>&1
    timeout /t 3 /nobreak >NUL
)

REM 재시작 횟수 초기화
set MAX_RESTART=5
set RESTART_COUNT=0

:TRADER_LOOP
    set /a RESTART_COUNT+=1
    echo.
    echo ========================================
    echo [%date% %time%] Trader 시작 (시도 %RESTART_COUNT%/%MAX_RESTART%)
    echo ========================================
    echo [%date% %time%] [BAT] trader 시작 시도 %RESTART_COUNT%/%MAX_RESTART% >> log\jackbot.log

    python trader_advanced.py
    set TRADER_EXIT=%ERRORLEVEL%

    echo.
    echo [%date% %time%] Trader 종료 (exit code: %TRADER_EXIT%)
    echo [%date% %time%] [BAT] trader exit code=%TRADER_EXIT% attempt=%RESTART_COUNT% >> log\jackbot.log
    echo [%date% %time%] trader exit code=%TRADER_EXIT% attempt=%RESTART_COUNT% >> automation_log.txt

    REM 정상 종료(exit 0) → 재시작 안 함
    if %TRADER_EXIT% EQU 0 (
        echo [INFO] 정상 종료. 재시작 안 함.
        echo [%date% %time%] [BAT] 정상 종료 >> log\jackbot.log
        goto END
    )

    REM 크래시 → 재시작 가능 여부 확인
    echo [WARN] 비정상 종료 감지 (code=%TRADER_EXIT%)

    REM 최대 재시작 횟수 초과
    if %RESTART_COUNT% GEQ %MAX_RESTART% (
        echo [WARN] 최대 재시작 횟수(%MAX_RESTART%) 초과. 포기.
        echo [%date% %time%] [BAT] 최대 재시작 초과 >> log\jackbot.log
        goto END
    )

    REM 장 시간 체크 (09:00 ~ 15:30)
    for /f "tokens=1-2 delims=:." %%a in ("%TIME: =0%") do (
        set /a CURRENT_HHMM=%%a*100+%%b
    )
    if %CURRENT_HHMM% LSS 900 (
        echo [INFO] 장 시작 전. 재시작 안 함.
        echo [%date% %time%] [BAT] 장 시작 전 재시작 안 함 >> log\jackbot.log
        goto END
    )
    if %CURRENT_HHMM% GEQ 1530 (
        echo [INFO] 장 마감 후. 재시작 안 함.
        echo [%date% %time%] [BAT] 장 마감 후 재시작 안 함 >> log\jackbot.log
        goto END
    )

    REM 30초 대기 후 재시작 (Kiwoom COM 정리 시간)
    echo [INFO] 30초 후 재시작... (Ctrl+C로 중단 가능)
    echo [%date% %time%] [BAT] 30초 후 재시작 >> log\jackbot.log
    timeout /t 30 /nobreak
    goto TRADER_LOOP

:END
echo.
echo ========================================
echo Trader 완료
echo End time: %date% %time%
echo ========================================
echo.

echo %date% %time% - Trader exit (code=%TRADER_EXIT%) >> automation_log.txt

REM Return to caller (collector_auto_restart.bat)
exit /b
