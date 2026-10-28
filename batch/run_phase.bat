@echo off
setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%.."

set LOG=log\collector_stdout.log

echo [run_phase] START Phase=%COLLECTOR_PHASE% %date% %time% >> automation_log.txt 2>&1

if not exist "log\" (
    echo [run_phase] ERROR log dir missing >> automation_log.txt 2>&1
    exit /b 1
)

echo [run_phase] === START Phase=%COLLECTOR_PHASE% %date% %time% === >> %LOG% 2>&1
if errorlevel 1 (
    echo [run_phase] ERROR cannot write to %LOG% - LOG still locked >> automation_log.txt 2>&1
) else (
    echo [run_phase] LOG write OK >> automation_log.txt 2>&1
)

echo [run_phase] pre-kill stale collector_v3... >> %LOG% 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*collector_v3*' } | ForEach-Object { Write-Host '[pre-kill] PID=' $_.ProcessId; Stop-Process -Id $_.ProcessId -Force }" >> %LOG% 2>&1

echo [run_phase] launching python --phase %COLLECTOR_PHASE% >> %LOG% 2>&1
echo [run_phase] launching python --phase %COLLECTOR_PHASE% >> automation_log.txt 2>&1
python -u collector_v3.py --phase %COLLECTOR_PHASE% >> %LOG% 2>&1
set PYEXIT=%ERRORLEVEL%

echo [run_phase] python exit=%PYEXIT% -- killing chromedriver/CEF >> automation_log.txt 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -File "batch\kill_kiwoom.ps1" >> automation_log.txt 2>&1

echo [run_phase] END Phase=%COLLECTOR_PHASE% exit=%PYEXIT% >> automation_log.txt 2>&1
exit /b %PYEXIT%
