@echo off
setlocal enabledelayedexpansion
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%.."
set LOG=log\collector_stdout.log
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

title [Phase %COLLECTOR_PHASE%]

echo.
echo ----------------------------------------
echo  Phase %COLLECTOR_PHASE%  [%time%]
echo ----------------------------------------

REM ===== Pre-kill: stale collector_v3 python (trader 방식 동일) =====
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*collector_v3*' } | ForEach-Object { Write-Host '[pre-kill] Killing stale collector PID' $_.ProcessId; Stop-Process -Id $_.ProcessId -Force }" >> %LOG% 2>&1

echo [run_phase] COLLECTOR_PHASE=%COLLECTOR_PHASE% >> %LOG%
python -u collector_v3.py --phase %COLLECTOR_PHASE% >> %LOG% 2>&1
set PYEXIT=%ERRORLEVEL%
echo [run_phase] python exit=%PYEXIT% >> %LOG%

echo  Python done. Clearing Kiwoom helpers...
powershell -NoProfile -ExecutionPolicy Bypass -File "batch\kill_kiwoom.ps1" >> %LOG% 2>&1

timeout /t 10 /nobreak >NUL

echo [run_phase] Kiwoom cleared >> %LOG%
echo  Kiwoom cleared. Phase %COLLECTOR_PHASE% done.
echo.
exit /b %PYEXIT%
