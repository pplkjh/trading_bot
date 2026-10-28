@echo off
REM Single-phase Python invocation. Kills Kiwoom helpers after Python exits.
setlocal enabledelayedexpansion
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%.."
set LOG=log\collector_stdout.log
set PYTHONIOENCODING=utf-8
echo [run_collector] phase=%COLLECTOR_PHASE% >> %LOG%
python collector_v3.py --phase %COLLECTOR_PHASE% >> %LOG% 2>&1
set PYEXIT=%ERRORLEVEL%
echo [run_collector] python exit=%PYEXIT% >> %LOG%

REM Kill Kiwoom helper processes (C:\OpenAPI\*)
echo [run_collector] killing Kiwoom helpers >> %LOG%
powershell -NoProfile -Command "Get-Process | Where-Object { try { $_.Path -like 'C:\OpenAPI\*' } catch { $false } } | ForEach-Object { try { Stop-Process -Id $_.Id -Force } catch {} }" >> %LOG% 2>&1

REM Poll until helpers are gone (max 120s = 24 x 5s)
set /a POLL=0
:poll_kiwoom
set /a POLL+=1
if !POLL! GTR 24 goto kiwoom_done
powershell -NoProfile -Command "exit (Get-Process | Where-Object { try { $_.Path -like 'C:\OpenAPI\*' } catch { $false } }).Count" >NUL 2>&1
if !ERRORLEVEL! EQU 0 goto kiwoom_done
echo [run_collector] waiting Kiwoom helpers !POLL!/24 >> %LOG%
timeout /t 5 /nobreak >NUL
goto poll_kiwoom
:kiwoom_done
echo [run_collector] Kiwoom helpers cleared >> %LOG%
exit /b %PYEXIT%
