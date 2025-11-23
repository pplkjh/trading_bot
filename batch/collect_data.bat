@echo off
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

REM Python 경로 설정 (본인 환경에 맞게 수정)
set PYTHON_PATH=python
set SCRIPT_DIR=%~dp0

REM 작업 디렉토리로 이동
cd /d %SCRIPT_DIR%

echo [1/3] 데이터 수집 중...
echo.

REM 데이터 수집 실행
%PYTHON_PATH% collector_v3.py

if %errorlevel% neq 0 (
    echo.
    echo ❌ 데이터 수집 실패!
    echo 오류 코드: %errorlevel%
    echo.
    echo 로그를 확인하세요.
    pause
    exit /b %errorlevel%
)

echo.
echo ✅ 데이터 수집 완료!
echo.

echo [2/3] 내일 매수 후보 스캔 중...
echo.

REM 고급 전략으로 내일 매수 후보 미리 생성
%PYTHON_PATH% run_advanced_strategy.py --mode scan --top 20

if %errorlevel% neq 0 (
    echo.
    echo ⚠️  매수 후보 스캔 실패 (무시하고 계속)
)

echo.
echo ✅ 매수 후보 스캔 완료!
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
