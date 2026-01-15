@echo off
chcp 65001 > nul
REM ========================================
REM collector 자동 재시작 스크립트
REM ========================================
REM 에러 발생 시 자동으로 재시작
REM 정상 완료 시 cmd 종료
REM ========================================

echo ========================================
echo Collector 자동 재시작 스크립트
echo ========================================
echo.
echo 에러 발생 시 자동으로 재시작합니다.
echo 정상 완료 시 자동으로 종료됩니다.
echo.
echo 중단하려면: Ctrl+C
echo ========================================
echo.

REM Python 경로 설정
set PYTHON_PATH=python
set SCRIPT_DIR=%~dp0

REM 프로젝트 루트 디렉토리로 이동
cd /d %SCRIPT_DIR%..

:LOOP
    echo.
    echo [%date% %time%] Collector 시작...
    echo ========================================

    REM collector 실행
    %PYTHON_PATH% collector_v3.py

    REM 종료 코드 확인
    if %ERRORLEVEL% EQU 0 (
        echo.
        echo [%date% %time%] Collector가 정상 종료되었습니다.
        echo ========================================
        echo.
        goto END
    ) else (
        echo.
        echo [%date% %time%] Collector가 에러로 종료되었습니다. (코드: %ERRORLEVEL%)
        echo 5초 후 자동으로 재시작합니다...
        echo.
        timeout /t 5 /nobreak
        goto LOOP
    )

:END
echo.
echo ========================================
echo Collector 자동 재시작 스크립트 종료
echo %date% %time%
echo ========================================
REM 자동 종료 (pause 제거)
exit
