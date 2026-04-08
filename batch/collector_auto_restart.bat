@echo off
REM ========================================
REM Collector Auto-Restart Script (3-Phase)
REM ========================================
REM Phase 1: OHLCV + technical indicators  (~3500 API calls)
REM Phase 2: Fundamental data              (~2769 API calls)
REM Phase 3: Scoring (no API calls)
REM
REM Kiwoom restarts between phases to reset rq_count
REM ========================================

echo ========================================
echo Collector Auto-Restart Script (3-Phase)
echo ========================================
echo.
echo Phase 1: OHLCV + technical indicators
echo Phase 2: Fundamental data
echo Phase 3: Scoring
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

REM ========================================
REM Phase 1
REM ========================================
echo.
echo ========================================
echo [%date% %time%] Phase 1 Start: OHLCV + technical indicators
echo ========================================
echo.
echo [%date% %time%] [BAT] Phase 1 start >> log\jackbot.log

set PHASE1_COUNT=0

:PHASE1_LOOP
    set /a PHASE1_COUNT+=1
    echo [%date% %time%] Phase 1 running... (attempt %PHASE1_COUNT%/5)
    echo [%date% %time%] [BAT] Phase1 attempt %PHASE1_COUNT% >> log\jackbot.log

    python collector_v3.py --phase 1
    set PHASE1_EXIT=%ERRORLEVEL%
    echo [DEBUG] Phase1 exit code: %PHASE1_EXIT% (attempt %PHASE1_COUNT%) >> automation_log.txt
    echo [DEBUG] Phase1 exit code: %PHASE1_EXIT% (attempt %PHASE1_COUNT%)

    if %PHASE1_COUNT% GEQ 5 (
        echo [%date% %time%] [WARN] Phase 1 max retries reached. Moving forward.
        echo [%date% %time%] [BAT] Phase1 max retries >> log\jackbot.log
        goto PHASE1_DONE
    )

    python "%SCRIPT_DIR%check_collector_done.py" --phase 1
    set PHASE1_DONE_CHECK=%ERRORLEVEL%
    echo [DEBUG] Phase1 DONE_CHECK=%PHASE1_DONE_CHECK% >> automation_log.txt

    if "%PHASE1_DONE_CHECK%"=="0" (
        echo [%date% %time%] Phase 1 complete.
        echo [%date% %time%] [BAT] Phase1 done >> log\jackbot.log
        goto PHASE1_DONE
    )

    echo [%date% %time%] Phase 1 incomplete. Retrying in 5s...
    echo [%date% %time%] [BAT] Phase1 incomplete restarting >> log\jackbot.log
    timeout /t 5 /nobreak
    goto PHASE1_LOOP

:PHASE1_DONE

echo.
echo [INFO] Phase 1 done. Waiting 15s for Kiwoom rq_count reset...
echo [%date% %time%] [BAT] Phase1 done, waiting 15s >> log\jackbot.log
timeout /t 15 /nobreak >NUL

REM ========================================
REM Phase 2
REM ========================================
echo.
echo ========================================
echo [%date% %time%] Phase 2 Start: Fundamental data
echo ========================================
echo.
echo [%date% %time%] [BAT] Phase 2 start >> log\jackbot.log

set PHASE2_COUNT=0

:PHASE2_LOOP
    set /a PHASE2_COUNT+=1
    echo [%date% %time%] Phase 2 running... (attempt %PHASE2_COUNT%/5)
    echo [%date% %time%] [BAT] Phase2 attempt %PHASE2_COUNT% >> log\jackbot.log

    python collector_v3.py --phase 2
    set PHASE2_EXIT=%ERRORLEVEL%
    echo [DEBUG] Phase2 exit code: %PHASE2_EXIT% (attempt %PHASE2_COUNT%) >> automation_log.txt
    echo [DEBUG] Phase2 exit code: %PHASE2_EXIT% (attempt %PHASE2_COUNT%)

    if %PHASE2_COUNT% GEQ 5 (
        echo [%date% %time%] [WARN] Phase 2 max retries reached. Moving forward.
        echo [%date% %time%] [BAT] Phase2 max retries >> log\jackbot.log
        goto PHASE2_DONE
    )

    python "%SCRIPT_DIR%check_collector_done.py" --phase 2
    set PHASE2_DONE_CHECK=%ERRORLEVEL%
    echo [DEBUG] Phase2 DONE_CHECK=%PHASE2_DONE_CHECK% >> automation_log.txt

    if "%PHASE2_DONE_CHECK%"=="0" (
        echo [%date% %time%] Phase 2 complete.
        echo [%date% %time%] [BAT] Phase2 done >> log\jackbot.log
        goto PHASE2_DONE
    )

    echo [%date% %time%] Phase 2 incomplete. Retrying in 5s...
    echo [%date% %time%] [BAT] Phase2 incomplete restarting >> log\jackbot.log
    timeout /t 5 /nobreak
    goto PHASE2_LOOP

:PHASE2_DONE

echo.
echo [INFO] Phase 2 done. Waiting 15s for Kiwoom rq_count reset...
echo [%date% %time%] [BAT] Phase2 done, waiting 15s >> log\jackbot.log
timeout /t 15 /nobreak >NUL

REM ========================================
REM Phase 3
REM ========================================
echo.
echo ========================================
echo [%date% %time%] Phase 3 Start: Scoring
echo ========================================
echo.
echo [%date% %time%] [BAT] Phase 3 start >> log\jackbot.log

set PHASE3_COUNT=0

:PHASE3_LOOP
    set /a PHASE3_COUNT+=1
    echo [%date% %time%] Phase 3 running... (attempt %PHASE3_COUNT%/5)
    echo [%date% %time%] [BAT] Phase3 attempt %PHASE3_COUNT% >> log\jackbot.log

    python collector_v3.py --phase 3
    set PHASE3_EXIT=%ERRORLEVEL%
    echo [DEBUG] Phase3 exit code: %PHASE3_EXIT% (attempt %PHASE3_COUNT%) >> automation_log.txt
    echo [DEBUG] Phase3 exit code: %PHASE3_EXIT% (attempt %PHASE3_COUNT%)

    if %PHASE3_COUNT% GEQ 5 (
        echo [%date% %time%] [WARN] Phase 3 max retries reached. Moving to trader.
        echo [%date% %time%] [BAT] Phase3 max retries >> log\jackbot.log
        goto END
    )

    python "%SCRIPT_DIR%check_collector_done.py" --phase 3
    set PHASE3_DONE_CHECK=%ERRORLEVEL%
    echo [DEBUG] Phase3 DONE_CHECK=%PHASE3_DONE_CHECK% >> automation_log.txt

    if "%PHASE3_DONE_CHECK%"=="0" (
        echo [%date% %time%] Phase 3 complete. Starting Trader.
        echo [%date% %time%] [BAT] Phase3 done >> log\jackbot.log
        goto END
    )

    echo [%date% %time%] Phase 3 incomplete. Retrying in 5s...
    echo [%date% %time%] [BAT] Phase3 incomplete restarting >> log\jackbot.log
    timeout /t 5 /nobreak
    goto PHASE3_LOOP

:END
echo.
echo ========================================
echo Collector Complete (3-Phase) - Starting Trader
echo %date% %time%
echo ========================================
echo.

echo [INFO] Waiting 15s for COM cleanup before trader...
echo [%date% %time%] [BAT] waiting 15s for COM cleanup before trader >> log\jackbot.log
timeout /t 15 /nobreak >NUL

echo [INFO] Starting Trader...
start /wait cmd /c "%SCRIPT_DIR%start_trader.bat"

echo.
echo ========================================
echo Trader Exit - Shutdown Check
echo %date% %time%
echo ========================================
echo.

echo [INFO] Starting shutdown prompt...
call "%SCRIPT_DIR%shutdown_prompt.bat"

exit
