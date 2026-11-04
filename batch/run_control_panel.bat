@echo off
cd /d %~dp0..
call C:\Users\%USERNAME%\anaconda3\Scripts\activate.bat py37_32
echo [ControlPanel] Starting JackBot Control Panel...
python control_panel\main.py
pause
