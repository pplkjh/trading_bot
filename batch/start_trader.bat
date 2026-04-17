@echo off
REM ===================================================
REM Auto Trader Startup Script

REM exit 0 = normal exit, no restart
REM exit non-0 = crash, restart if within market hours
REM ===================================================

set SCRIPT_DIR=%~dp0
cd /d %SCRIPT_DIR%..
call C:\Users\%USERNAME%\anaconda3\Scripts\activate.bat py37_32

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

set TRADER_EXIT=0

REM Single execution only - restart loop managed by collector_auto_restart.bat
echo [%date% %time%] [BAT] trader start >> automation_log.txt

python trader_advanced.py
set TRADER_EXIT=%ERRORLEVEL%

echo [%date% %time%] Trader exited (code: %TRADER_EXIT%)
echo [%date% %time%] [BAT] trader exit code=%TRADER_EXIT% >> automation_log.txt
echo %date% %time% trader exit code=%TRADER_EXIT% >> automation_log.txt

:END
echo.
echo ========================================
echo Trader done
echo End time: %date% %time%
echo ========================================

echo %date% %time% - Trader exit (code=%TRADER_EXIT%) >> automation_log.txt

if %TRADER_EXIT% NEQ 0 (
    echo.
    echo [ERROR] Trader exited abnormally (code=%TRADER_EXIT%)
    echo --- Recent log (last 10 lines) ---
    powershell -Command "Get-Content 'log\jackbot.log' -Tail 10" 2>NUL
    echo ----------------------------------
    echo.
    echo Closing in 30 seconds... (Press Ctrl+C to cancel)
    timeout /t 30
) else (
    echo Closing in 5 seconds...
    timeout /t 5
)
exit /b
