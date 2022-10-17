forfiles /P "%~dp0..\log" /S /M *.log* /D -10 /C "cmd /c del @file"
timeout 5