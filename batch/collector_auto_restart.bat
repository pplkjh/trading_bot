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
echo [%date% %time%] [BAT] Phase 1 start >> automation_log.txt

set PHASE1_COUNT=0

:PHASE1_LOOP
    set /a PHASE1_COUNT+=1
    echo [%date% %time%] Phase 1 running... (attempt %PHASE1_COUNT%/5)
    echo [%date% %time%] [BAT] Phase1 attempt %PHASE1_COUNT% >> automation_log.txt

    python collector_v3.py --phase 1
    set PHASE1_EXIT=%ERRORLEVEL%
    echo [DEBUG] Phase1 exit code: %PHASE1_EXIT% (attempt %PHASE1_COUNT%) >> automation_log.txt
    echo [DEBUG] Phase1 exit code: %PHASE1_EXIT% (attempt %PHASE1_COUNT%)

    if %PHASE1_COUNT% GEQ 5 (
        echo [%date% %time%] [WARN] Phase 1 max retries reached. Moving forward.
        echo [%date% %time%] [BAT] Phase1 max retries >> automation_log.txt
        goto PHASE1_DONE
    )

    python "%SCRIPT_DIR%check_collector_done.py" --phase 1
    set PHASE1_DONE_CHECK=%ERRORLEVEL%
    echo [DEBUG] Phase1 DONE_CHECK=%PHASE1_DONE_CHECK% >> automation_log.txt

    if "%PHASE1_DONE_CHECK%"=="0" (
        echo [%date% %time%] Phase 1 complete.
        echo [%date% %time%] [BAT] Phase1 done >> automation_log.txt
        goto PHASE1_DONE
    )

    echo [%date% %time%] Phase 1 incomplete. Retrying in 5s...
    echo [%date% %time%] [BAT] Phase1 incomplete restarting >> automation_log.txt
    timeout /t 5 /nobreak
    goto PHASE1_LOOP

:PHASE1_DONE

echo.
echo [INFO] Phase 1 done. Waiting 15s for Kiwoom rq_count reset...
echo [%date% %time%] [BAT] Phase1 done, waiting 15s >> automation_log.txt
timeout /t 15 /nobreak >NUL

REM ========================================
REM Phase 2
REM ========================================
echo.
echo ========================================
echo [%date% %time%] Phase 2 Start: Fundamental data
echo ========================================
echo.
echo [%date% %time%] [BAT] Phase 2 start >> automation_log.txt

set PHASE2_COUNT=0

:PHASE2_LOOP
    set /a PHASE2_COUNT+=1
    echo [%date% %time%] Phase 2 running... (attempt %PHASE2_COUNT%/5)
    echo [%date% %time%] [BAT] Phase2 attempt %PHASE2_COUNT% >> automation_log.txt

    python collector_v3.py --phase 2
    set PHASE2_EXIT=%ERRORLEVEL%
    echo [DEBUG] Phase2 exit code: %PHASE2_EXIT% (attempt %PHASE2_COUNT%) >> automation_log.txt
    echo [DEBUG] Phase2 exit code: %PHASE2_EXIT% (attempt %PHASE2_COUNT%)

    if %PHASE2_COUNT% GEQ 5 (
        echo [%date% %time%] [WARN] Phase 2 max retries reached. Moving forward.
        echo [%date% %time%] [BAT] Phase2 max retries >> automation_log.txt
        goto PHASE2_DONE
    )

    python "%SCRIPT_DIR%check_collector_done.py" --phase 2
    set PHASE2_DONE_CHECK=%ERRORLEVEL%
    echo [DEBUG] Phase2 DONE_CHECK=%PHASE2_DONE_CHECK% >> automation_log.txt

    if "%PHASE2_DONE_CHECK%"=="0" (
        echo [%date% %time%] Phase 2 complete.
        echo [%date% %time%] [BAT] Phase2 done >> automation_log.txt
        goto PHASE2_DONE
    )

    echo [%date% %time%] Phase 2 incomplete. Retrying in 5s...
    echo [%date% %time%] [BAT] Phase2 incomplete restarting >> automation_log.txt
    timeout /t 5 /nobreak
    goto PHASE2_LOOP

:PHASE2_DONE

echo.
echo [INFO] Phase 2 done. Waiting 15s for Kiwoom rq_count reset...
echo [%date% %time%] [BAT] Phase2 done, waiting 15s >> automation_log.txt
timeout /t 15 /nobreak >NUL

REM ========================================
REM Phase 3
REM ========================================
echo.
echo ========================================
echo [%date% %time%] Phase 3 Start: Scoring
echo ========================================
echo.
echo [%date% %time%] [BAT] Phase 3 start >> automation_log.txt

set PHASE3_COUNT=0

:PHASE3_LOOP
    set /a PHASE3_COUNT+=1
    echo [%date% %time%] Phase 3 running... (attempt %PHASE3_COUNT%/5)
    echo [%date% %time%] [BAT] Phase3 attempt %PHASE3_COUNT% >> automation_log.txt

    python collector_v3.py --phase 3
    set PHASE3_EXIT=%ERRORLEVEL%
    echo [DEBUG] Phase3 exit code: %PHASE3_EXIT% (attempt %PHASE3_COUNT%) >> automation_log.txt
    echo [DEBUG] Phase3 exit code: %PHASE3_EXIT% (attempt %PHASE3_COUNT%)

    if %PHASE3_COUNT% GEQ 5 (
        echo [%date% %time%] [WARN] Phase 3 max retries reached. Moving to trader.
        echo [%date% %time%] [BAT] Phase3 max retries >> automation_log.txt
        goto END
    )

    python "%SCRIPT_DIR%check_collector_done.py" --phase 3
    set PHASE3_DONE_CHECK=%ERRORLEVEL%
    echo [DEBUG] Phase3 DONE_CHECK=%PHASE3_DONE_CHECK% >> automation_log.txt

    if "%PHASE3_DONE_CHECK%"=="0" (
        echo [%date% %time%] Phase 3 complete. Starting Trader.
        echo [%date% %time%] [BAT] Phase3 done >> automation_log.txt
        goto END
    )

    echo [%date% %time%] Phase 3 incomplete. Retrying in 5s...
    echo [%date% %time%] [BAT] Phase3 incomplete restarting >> automation_log.txt
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
echo [%date% %time%] [BAT] waiting 15s for COM cleanup before trader >> automation_log.txt
timeout /t 15 /nobreak >NUL

REM ========================================
REM Trader 실행 + 재시작 루프 (collector_auto_restart 에서 관리)
REM start_trader.bat 은 1회 실행만 담당
REM 플래그 없이 종료 = 크래시 → 최대 5회 재시작
REM 플래그 있으면 정상 종료 → 루프 탈출
REM ========================================
set TRADER_RETRY=0
set TRADER_MAX=5
set TRADER_FLAG=%SCRIPT_DIR%trader_normal_exit.flag

:TRADER_START
    set /a TRADER_RETRY+=1
    echo [%date% %time%] [BAT] trader start attempt %TRADER_RETRY%/%TRADER_MAX% >> automation_log.txt
    echo [INFO] Starting Trader (attempt %TRADER_RETRY%/%TRADER_MAX%)...

    REM 시작 전 플래그 초기화
    if exist "%TRADER_FLAG%" del "%TRADER_FLAG%"

    start /wait cmd /c "%SCRIPT_DIR%start_trader.bat"

    REM 정상 종료 플래그 확인
    if exist "%TRADER_FLAG%" (
        echo [INFO] Trader normal exit confirmed.
        echo [%date% %time%] [BAT] trader normal exit confirmed >> automation_log.txt
        goto TRADER_DONE
    )

    echo [WARN] Trader crash detected (attempt %TRADER_RETRY%/%TRADER_MAX%)
    echo [%date% %time%] [BAT] trader crash - attempt %TRADER_RETRY%/%TRADER_MAX% >> automation_log.txt

    if %TRADER_RETRY% GEQ %TRADER_MAX% (
        echo [WARN] Max trader restarts reached. Giving up.
        echo [%date% %time%] [BAT] trader max restarts reached >> automation_log.txt
        goto TRADER_DONE
    )

    echo [INFO] Restarting trader in 30s...
    echo [%date% %time%] [BAT] trader restart in 30s >> automation_log.txt
    timeout /t 30 /nobreak
    goto TRADER_START

:TRADER_DONE
echo.
echo ========================================
echo Trader Exit - Shutdown Check
echo %date% %time%
echo ========================================
echo.

echo [INFO] Starting shutdown prompt...
call "%SCRIPT_DIR%shutdown_prompt.bat"

exit
