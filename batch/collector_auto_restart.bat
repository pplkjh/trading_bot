@echo off
setlocal enabledelayedexpansion
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%.."
call C:\Users\%USERNAME%\anaconda3\Scripts\activate.bat py37_32

echo [%date% %time%] [BAT] Collector start >> automation_log.txt
echo.
echo ===================================================
echo  Collector Auto-Restart  [%date% %time%]
echo  Phase1: OHLCV  /  Phase2: Fundamental  /  Phase3: Scoring
echo ===================================================
echo.

REM ===== Pre-cleanup: ?´ì „ ?¸ì…˜ ?”ë¥˜ Kiwoom ?„ë¡œ?¸ìŠ¤ ?œê±° =====
echo [%date% %time%] Pre-cleanup: killing leftover Kiwoom processes...
echo [%date% %time%] [BAT] Pre-cleanup >> automation_log.txt
powershell -NoProfile -Command "Get-Process | Where-Object { try { $_.Path -like 'C:\OpenAPI\*' } catch { $false } } | ForEach-Object { try { Stop-Process -Id $_.Id -Force } catch {} }; Get-WmiObject Win32_Process | Where-Object { $_.ExecutablePath -like 'C:\OpenAPI\*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >> automation_log.txt 2>&1
timeout /t 5 /nobreak >NUL

REM ===== Phase 1 =====
set P1=0
:P1_LOOP
set /a P1+=1
echo [%date% %time%] Phase 1  attempt !P1!/5
echo [%date% %time%] [BAT] Phase1 attempt !P1! >> automation_log.txt
set COLLECTOR_PHASE=1
start /wait "" cmd /c "batch\run_phase.bat"
python batch\check_collector_done.py --phase 1
if !errorlevel! EQU 0 goto P1_DONE
if !P1! GEQ 5 (
    echo [%date% %time%] Phase 1 max retries - proceeding
    echo [%date% %time%] [BAT] Phase1 max retries >> automation_log.txt
    goto P1_DONE
)
timeout /t 10 /nobreak >NUL
goto P1_LOOP
:P1_DONE
echo [%date% %time%] Phase 1 done. Waiting 10s...
echo [%date% %time%] [BAT] Phase1 done >> automation_log.txt
timeout /t 10 /nobreak >NUL
REM Phase 1 -> Phase 3 rescore: reset today_buy_list so Phase 3 reruns with fresh OHLCV
python batch\reset_scoring_flag.py >> automation_log.txt 2>&1

REM ===== Phase 2 =====
set P2=0
:P2_LOOP
set /a P2+=1
echo [%date% %time%] Phase 2  attempt !P2!/5
echo [%date% %time%] [BAT] Phase2 attempt !P2! >> automation_log.txt
set COLLECTOR_PHASE=2
start /wait "" cmd /c "batch\run_phase.bat"
python batch\check_collector_done.py --phase 2
if !errorlevel! EQU 0 goto P2_DONE
if !P2! GEQ 5 (
    echo [%date% %time%] Phase 2 max retries - proceeding
    echo [%date% %time%] [BAT] Phase2 max retries >> automation_log.txt
    goto P2_DONE
)
timeout /t 10 /nobreak >NUL
goto P2_LOOP
:P2_DONE
echo [%date% %time%] Phase 2 done. Waiting 10s...
echo [%date% %time%] [BAT] Phase2 done >> automation_log.txt
timeout /t 10 /nobreak >NUL

REM ===== Phase 3 =====
set P3=0
:P3_LOOP
set /a P3+=1
echo [%date% %time%] Phase 3  attempt !P3!/5
echo [%date% %time%] [BAT] Phase3 attempt !P3! >> automation_log.txt
set COLLECTOR_PHASE=3
start /wait "" cmd /c "batch\run_phase.bat"
python batch\check_collector_done.py --phase 3
if !errorlevel! EQU 0 goto P3_DONE
if !P3! GEQ 5 (
    echo [%date% %time%] Phase 3 max retries - proceeding
    echo [%date% %time%] [BAT] Phase3 max retries >> automation_log.txt
    goto P3_DONE
)
timeout /t 10 /nobreak >NUL
goto P3_LOOP
:P3_DONE
echo [%date% %time%] Collector done. Waiting 10s before trader...
echo [%date% %time%] [BAT] collector done >> automation_log.txt
timeout /t 10 /nobreak >NUL

REM ===== Trader =====
set TR=0
set TRFLAG=!SCRIPT_DIR!trader_normal_exit.flag
:TR_LOOP
set /a TR+=1
echo [%date% %time%] Trader  attempt !TR!/5
echo [%date% %time%] [BAT] trader attempt !TR! >> automation_log.txt
if exist "!TRFLAG!" del "!TRFLAG!"
start /wait "" cmd /c "batch\start_trader.bat"
if exist "!TRFLAG!" goto TR_DONE
if !TR! GEQ 5 (
    echo [%date% %time%] Trader max retries
    echo [%date% %time%] [BAT] trader max retries >> automation_log.txt
    goto TR_DONE
)
timeout /t 10 /nobreak >NUL
goto TR_LOOP
:TR_DONE
echo [%date% %time%] [BAT] All done >> automation_log.txt
call "!SCRIPT_DIR!shutdown_prompt.bat"
exit
