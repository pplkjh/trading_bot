@echo off
cd /d %~dp0..
echo Starting JackBot Dashboard...
start "" C:\Users\%USERNAME%\anaconda3\python.exe -m streamlit run dashboard.py --server.headless true
echo Waiting for server to start...
timeout /t 6 /nobreak >NUL
start http://localhost:8501
echo Browser opened: http://localhost:8501
echo (Close this window anytime - dashboard runs independently)
pause
