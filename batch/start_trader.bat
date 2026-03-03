@echo off
REM ===================================================
REM Auto Trader Startup Script
REM Run before market opens to start auto trading
REM ===================================================

echo ========================================
echo Auto Trader Starting
echo ========================================
echo.
echo Start time: %date% %time%
echo.

REM Python path setup
set SCRIPT_DIR=%~dp0

REM Move to working directory (parent of batch folder)
cd /d %SCRIPT_DIR%..

REM Activate Anaconda py37_32 environment
call C:\Users\USER\anaconda3\Scripts\activate.bat py37_32

echo [INFO] Working directory: %cd%
echo.

REM Check if trading day
echo [INFO] Checking trading day...
python check_trading_day.py
if %errorlevel% neq 0 (
    echo.
    echo [INFO] Market is closed today.
    echo [INFO] See message above for details.
    goto END
)
echo.

REM Check for existing trader_advanced.py process and kill if found (auto mode)
tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I "python.exe" >NUL
if "%ERRORLEVEL%"=="0" (
    echo [INFO] Existing Python process found. Killing for clean start...
    taskkill /F /IM python.exe >NUL 2>&1
    timeout /t 3 /nobreak >NUL
)

echo [1/2] Checking Kiwoom OpenAPI connection...
echo.
echo [OK] Auto execution mode
echo.

echo [2/2] Starting trader...
echo.
echo [START] trader_advanced.py is starting.
echo [INFO] Login when Kiwoom login window appears.
echo.

REM Run trader_advanced.py
python trader_advanced.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Trader execution failed!
    echo Error code: %errorlevel%
    echo.
    echo Exiting in 5 seconds...
    timeout /t 5 /nobreak
    goto END
)

echo.
echo ========================================
echo Trader finished successfully
echo End time: %date% %time%
echo ========================================
echo.

:END
REM Log record
echo %date% %time% - Trader exit >> automation_log.txt

REM Return to caller (collector_auto_restart.bat)
exit /b
