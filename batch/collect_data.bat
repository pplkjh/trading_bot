@echo off
chcp 65001 >nul
REM ===================================================
REM 자동 데이터 수집 배치 파일
REM 장 마감 후 데이터를 자동으로 수집합니다
REM ===================================================

echo ========================================
echo 자동 주식 데이터 수집 시작
echo ========================================
echo.
echo 시작 시간: %date% %time%
echo.

REM Python 경로 설정 (Anaconda py37_32 환경 사용)
set PYTHON_PATH=C:\Users\admin\anaconda3\envs\py37_32\python.exe

REM Python 출력 인코딩 설정 (UTF-8)
set PYTHONIOENCODING=utf-8
set BATCH_DIR=%~dp0
set SCRIPT_DIR=%BATCH_DIR%..

REM 작업 디렉토리로 이동 (프로젝트 루트로)
cd /d %SCRIPT_DIR%

echo [1/3] 데이터 수집 중...
echo.

REM 데이터 수집 실행 (API 제한으로 중단되면 자동 재시도)
set RETRY_COUNT=0
set MAX_RETRIES=10

:COLLECT_LOOP
set /a RETRY_COUNT+=1
echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo 데이터 수집 시도 #%RETRY_COUNT%/%MAX_RETRIES%
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo 현재 디렉토리: %cd%
echo Python 경로: %PYTHON_PATH%
echo.

%PYTHON_PATH% collector_v3.py

if %errorlevel% equ 0 (
    echo.
    echo [SUCCESS] 데이터 수집 완료!
    echo.
    goto COLLECT_DONE
)

REM API 제한으로 중단된 경우
echo.
echo [WARNING] collector_v3 종료됨 - API 제한 가능성
echo.

if %RETRY_COUNT% geq %MAX_RETRIES% (
    echo.
    echo [ERROR] 최대 재시도 횟수 %MAX_RETRIES%회 도달
    echo 수집을 중단합니다.
    echo.
    pause
    exit /b 1
)

echo 5초 후 자동으로 재시도합니다...
timeout /t 5 >nul
goto COLLECT_LOOP

:COLLECT_DONE

echo [2/3] 내일 매수 후보 스캔 중...
echo.

REM 고급 전략으로 내일 매수 후보 미리 생성
%PYTHON_PATH% run_advanced_strategy.py --mode scan --top 20

if %errorlevel% neq 0 (
    echo.
    echo [WARNING] 매수 후보 스캔 실패 - 무시하고 계속
)

echo.
echo [SUCCESS] 매수 후보 스캔 완료!
echo.

echo [3/3] 성과 분석 중...
echo.

REM 오늘 성과 분석
%PYTHON_PATH% run_advanced_strategy.py --mode analyze --db JackBot1_imi1

echo.
echo ========================================
echo 모든 작업 완료!
echo 종료 시간: %date% %time%
echo ========================================
echo.

REM 로그 파일에 기록
echo %date% %time% - 데이터 수집 완료 >> automation_log.txt

REM 5초 후 자동 종료
timeout /t 5

exit /b 0
