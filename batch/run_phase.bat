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

echo [run_phase] COLLECTOR_PHASE=%COLLECTOR_PHASE% >> %LOG%
python -u collector_v3.py --phase %COLLECTOR_PHASE% >> %LOG% 2>&1
set PYEXIT=%ERRORLEVEL%
echo [run_phase] python exit=%PYEXIT% >> %LOG%

echo  Python done. Clearing Kiwoom helpers...
powershell -NoProfile -Command "Get-Process | Where-Object { try { $_.Path -like 'C:\OpenAPI\*' } catch { $false } } | ForEach-Object { try { Stop-Process -Id $_.Id -Force } catch {} }; Get-WmiObject Win32_Process | Where-Object { $_.ExecutablePath -like 'C:\OpenAPI\*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >> %LOG% 2>&1

timeout /t 10 /nobreak >NUL

powershell -NoProfile -Command "exit (Get-WmiObject Win32_Process | Where-Object { $_.ExecutablePath -like 'C:\OpenAPI\*' }).Count" >NUL 2>&1
if !ERRORLEVEL! EQU 0 (
    echo [run_phase] Kiwoom cleared >> %LOG%
    echo  Kiwoom cleared. Phase %COLLECTOR_PHASE% done.
) else (
    echo [run_phase] WARNING: Kiwoom helpers still running after 10s >> %LOG%
    echo  WARNING: Kiwoom helpers still running.
)
echo.
exit /b %PYEXIT%
