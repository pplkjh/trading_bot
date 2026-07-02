@echo off
setlocal enabledelayedexpansion
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%.."
call C:\Users\%USERNAME%\anaconda3\Scripts\activate.bat py37_32
echo [%date% %time%] [BAT] start >> automation_log.txt
echo.
echo === Collector Auto-Restart (chain) ===
echo   Phase 1 - OHLCV + indicators
echo   Phase 2 - fundamental
echo   Phase 3 - scoring
echo.
REM Launch Phase 1 in its own CMD window. It will chain to Phase 2, 3, Trader.
set NEXT_PHASE=1
start "" cmd /c "batch\run_phase.bat"
REM This CMD exits immediately. The chain continues in Phase 1 CMD.
exit
