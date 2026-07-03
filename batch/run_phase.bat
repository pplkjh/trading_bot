@echo off
setlocal enabledelayedexpansion
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%.."
set LOG=log\collector_stdout.log
set PYTHONIOENCODING=utf-8

title [Phase %COLLECTOR_PHASE%]

echo.
echo ----------------------------------------
echo  Phase %COLLECTOR_PHASE%  [%time%]
echo ----------------------------------------

echo [run_phase] COLLECTOR_PHASE=%COLLECTOR_PHASE% >> %LOG%
python collector_v3.py --phase %COLLECTOR_PHASE% >> %LOG% 2>&1
set PYEXIT=%ERRORLEVEL%
echo [run_phase] python exit=%PYEXIT% >> %LOG%

echo  Python done. Clearing Kiwoom helpers...
powershell -NoProfile -Command "Get-Process | Where-Object { try { $_.Path -like 'C:\OpenAPI\*' } catch { $false } } | ForEach-Object { try { Stop-Process -Id $_.Id -Force } catch {} }" >> %LOG% 2>&1

set /a POLL=0
:poll_kiwoom
set /a POLL+=1
if !POLL! GTR 24 goto kiwoom_done
powershell -NoProfile -Command "exit (Get-Process | Where-Object { try { $_.Path -like 'C:\OpenAPI\*' } catch { $false } }).Count" >NUL 2>&1
if !ERRORLEVEL! EQU 0 goto kiwoom_done
echo  Waiting Kiwoom helpers... !POLL!/24
timeout /t 5 /nobreak >NUL
goto poll_kiwoom
:kiwoom_done
echo [run_phase] Kiwoom cleared >> %LOG%
echo  Kiwoom cleared. Phase %COLLECTOR_PHASE% done.
echo.
exit /b %PYEXIT%
