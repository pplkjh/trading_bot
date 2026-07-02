@echo off
setlocal enabledelayedexpansion

set PHASE=!NEXT_PHASE!
if "!PHASE!"=="" set PHASE=1

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%.."
set ALOG=automation_log.txt
set LOG=log\collector_stdout.log

title [Phase !PHASE!]
echo.
echo ==========================================
echo  Phase !PHASE! started  [%date% %time%]
echo ==========================================
echo [%date% %time%] [BAT] Phase!PHASE! CMD started >> !ALOG!

set /a COUNT=0
:retry
set /a COUNT+=1
echo.
echo   [%time%] Phase !PHASE! attempt !COUNT!/5
echo [%date% %time%] [BAT] Phase!PHASE! attempt !COUNT! >> !ALOG!

set COLLECTOR_PHASE=!PHASE!
cmd /c "batch\run_collector.bat"
echo [%date% %time%] [BAT] Phase!PHASE! python done attempt !COUNT! >> !ALOG!

python batch\check_collector_done.py --phase !PHASE!
set CHK=!ERRORLEVEL!
echo [%date% %time%] [BAT] Phase!PHASE! check=!CHK! >> !ALOG!

if "!CHK!"=="0" goto phase_done
if !COUNT! GEQ 5 (
    echo   [WARN] Phase !PHASE! max retries - proceeding anyway
    echo [%date% %time%] [BAT] Phase!PHASE! max retries >> !ALOG!
    goto phase_done
)
echo   [FAIL] Phase !PHASE! incomplete - retry in 10s...
timeout /t 10 /nobreak >NUL
goto retry

:phase_done
echo.
echo   Phase !PHASE! done [%time%]
echo   Waiting 30s before next phase...
echo [%date% %time%] [BAT] Phase!PHASE! done, waiting 30s >> !ALOG!
timeout /t 30 /nobreak >NUL

REM Chain to next step
if "!PHASE!"=="1" (
    echo [%date% %time%] [BAT] launching Phase2 CMD >> !ALOG!
    set NEXT_PHASE=2
    start "" cmd /c "batch\run_phase.bat"
    goto end
)
if "!PHASE!"=="2" (
    echo [%date% %time%] [BAT] launching Phase3 CMD >> !ALOG!
    set NEXT_PHASE=3
    start "" cmd /c "batch\run_phase.bat"
    goto end
)
if "!PHASE!"=="3" (
    echo [%date% %time%] [BAT] launching Trader CMD >> !ALOG!
    start "" cmd /c "batch\start_trader.bat"
    goto end
)

:end
echo [%date% %time%] [BAT] Phase!PHASE! CMD exit >> !ALOG!
exit
