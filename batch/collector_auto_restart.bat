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
call C:\Users\USER\anaconda3\Scripts\activate.bat py37_32

:LOOP
    echo.
    echo [%date% %time%] Collector starting...
    echo ========================================

    REM Run collector
    python collector_v3.py
    set COLLECTOR_EXIT=%ERRORLEVEL%
    echo [DEBUG] Collector exit code: %COLLECTOR_EXIT% >> automation_log.txt

    REM Check exit code: only restart on code 1 (explicit error from collector)
    if %COLLECTOR_EXIT% EQU 1 (
        echo.
        echo [%date% %time%] Collector error. Restarting in 5 seconds...
        echo ========================================
        echo.
        timeout /t 5 /nobreak
        goto LOOP
    )

    REM All other codes (0, PyQt5 crash, etc) - proceed to trader
    echo.
    echo [%date% %time%] Collector finished. (code: %COLLECTOR_EXIT%)
    echo ========================================
    echo.
    goto END

:END
echo.
echo ========================================
echo Collector Complete - Starting Trader
echo %date% %time%
echo ========================================
echo.

REM Start Trader after Collector completes
echo [INFO] Starting Trader...
call "%SCRIPT_DIR%start_trader.bat"

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
