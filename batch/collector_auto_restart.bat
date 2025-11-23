@echo off
REM ========================================
REM collector 자동 재시작 스크립트
REM ========================================
REM 999회 호출 후 종료되면 자동으로 다시 시작
REM 데이터 수집이 완료될 때까지 반복
REM ========================================

echo ========================================
echo Collector 자동 재시작 스크립트
echo ========================================
echo.
echo 이 스크립트는 collector가 종료되면 자동으로 재시작합니다.
echo 수집이 완료될 때까지 계속 실행됩니다.
echo.
echo 중지하려면: Ctrl+C
echo ========================================
echo.

REM Python 경로 설정
set PYTHON_PATH=python

REM 프로젝트 경로 (필요시 수정)
REM set PROJECT_PATH=C:\Users\USER\Desktop\Personal project\trading_bot
REM cd /d "%PROJECT_PATH%"

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
        echo 5초 후 재시작...
        timeout /t 5 /nobreak
        goto LOOP
    ) else (
        echo.
        echo [%date% %time%] Collector가 에러로 종료되었습니다. (코드: %ERRORLEVEL%)
        echo 에러 확인이 필요합니다.
        echo.
        choice /C YN /M "다시 시작하시겠습니까?"
        if %ERRORLEVEL% EQU 1 (
            echo 재시작 중...
            timeout /t 3 /nobreak
            goto LOOP
        ) else (
            echo 중지되었습니다.
            goto END
        )
    )

:END
echo.
echo ========================================
echo Collector 자동 재시작 종료
echo ========================================
pause
