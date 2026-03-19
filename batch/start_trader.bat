@echo off
REM ===================================================
REM Auto Trader Startup Script
REM exit 0 = normal exit, no restart
REM exit non-0 = crash, restart if within market hours
REM ===================================================

set SCRIPT_DIR=%~dp0
cd /d %SCRIPT_DIR%..
call C:\Users\USER\anaconda3\Scripts\activate.bat py37_32

echo ========================================
echo Auto Trader Starting
echo Start time: %date% %time%
echo ========================================

echo [INFO] Working directory: %cd%

python check_trading_day.py
if %errorlevel% neq 0 (
    echo [INFO] Market is closed today.
    goto END
)

tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I "python.exe" >NUL
if "%ERRORLEVEL%"=="0" (
    echo [INFO] Killing existing python process...
    taskkill /F /IM python.exe >NUL 2>&1
    timeout /t 3 /nobreak >NUL
)

set MAX_RESTART=5
set RESTART_COUNT=0
set TRADER_EXIT=0

:TRADER_LOOP
    set /a RESTART_COUNT+=1
    echo.
    echo [%date% %time%] Starting trader (attempt %RESTART_COUNT%/%MAX_RESTART%)
    echo [%date% %time%] [BAT] trader start attempt %RESTART_COUNT%/%MAX_RESTART% >> log\jackbot.log

    python trader_advanced.py
    set TRADER_EXIT=%ERRORLEVEL%

    echo [%date% %time%] Trader exited (code: %TRADER_EXIT%)
    echo [%date% %time%] [BAT] trader exit code=%TRADER_EXIT% attempt=%RESTART_COUNT% >> log\jackbot.log
    echo %date% %time% trader exit code=%TRADER_EXIT% attempt=%RESTART_COUNT% >> automation_log.txt

    if %TRADER_EXIT% EQU 0 (
        echo [INFO] Normal exit. No restart.
        goto END
    )

    if %RESTART_COUNT% GEQ %MAX_RESTART% (
        echo [WARN] Max restarts (%MAX_RESTART%) reached. Giving up.
        echo [%date% %time%] [BAT] max restarts reached >> log\jackbot.log
        goto END
    )

    for /f "tokens=1-2 delims=:." %%a in ("%TIME: =0%") do (
        set /a CURRENT_HHMM=%%a*100+%%b
    )
    if %CURRENT_HHMM% LSS 900 (
        echo [INFO] Before market open. No restart.
        goto END
    )
    if %CURRENT_HHMM% GEQ 1530 (
        echo [INFO] After market close. No restart.
        goto END
    )

    echo [WARN] Crash detected. Restarting in 30s...
    echo [%date% %time%] [BAT] crash restart in 30s >> log\jackbot.log
    timeout /t 30 /nobreak
    goto TRADER_LOOP

:END
echo.
echo ========================================
echo Trader done
echo End time: %date% %time%
echo ========================================

echo %date% %time% - Trader exit (code=%TRADER_EXIT%) >> automation_log.txt
exit /b
