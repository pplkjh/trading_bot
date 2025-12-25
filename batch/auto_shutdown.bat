@echo off
setlocal enabledelayedexpansion
REM ===================================================
REM 자동 종료 배치 파일
REM 저녁 7시 이후 실행 - 10분 카운트다운 후 컴퓨터 종료
REM ===================================================

echo ========================================
echo 자동 종료 프로세스 시작
echo ========================================
echo.
echo 현재 시간: %date% %time%
echo.

set SCRIPT_DIR=%~dp0

REM 작업 디렉토리로 이동
cd /d %SCRIPT_DIR%..

echo.
echo [WARNING] 10분 후 컴퓨터를 종료합니다!
echo.
echo [INFO] 작업을 계속하려면 Ctrl+C를 눌러 취소하세요.
echo.

REM 로그 기록
echo %date% %time% - 자동 종료 시작 (10분 카운트다운) >> automation_log.txt

echo 종료까지 남은 시간:
echo.

REM 10분 = 600초 카운트다운
for /L %%i in (600,-1,1) do (
    set /a minutes=%%i/60
    set /a seconds=%%i%%60

    REM 매 30초마다 메시지 표시
    set /a remainder=%%i%%30
    if !remainder!==0 (
        echo   !minutes!분 !seconds!초 남음...
    )

    timeout /t 1 /nobreak >NUL
)

echo.
echo [SHUTDOWN] 컴퓨터를 종료합니다...
echo.

REM 종료 실행
shutdown /s /t 5 /c "자동 종료: 장 마감 후 일정 시간 경과"

echo.
echo ========================================
echo 자동 종료 실행
echo 종료 시간: %date% %time%
echo ========================================
echo.

REM 최종 로그
echo %date% %time% - 자동 종료 실행됨 >> automation_log.txt

exit /b 0
