@echo off
REM ===================================================
REM 스마트 자동 종료 배치 파일
REM 주말/휴장일에는 바로 종료, 평일에는 설정된 시간에 종료
REM ===================================================

echo ========================================
echo 스마트 자동 종료 시스템
echo ========================================
echo.

set SCRIPT_DIR=%~dp0
cd /d %SCRIPT_DIR%..

REM 현재 요일 확인
for /f "tokens=1" %%a in ('powershell -command "& {(Get-Date).DayOfWeek}"') do set TODAY=%%a

echo 오늘: %TODAY%
echo.

REM 주말 체크
if "%TODAY%"=="Saturday" (
    echo ℹ️  오늘은 토요일입니다.
    goto WEEKEND_SHUTDOWN
)

if "%TODAY%"=="Sunday" (
    echo ℹ️  오늘은 일요일입니다.
    goto WEEKEND_SHUTDOWN
)

REM 평일 - 한국 공휴일 체크 (선택)
echo ✅ 오늘은 %TODAY% - 거래일입니다.
echo.

REM 현재 시간 확인
for /f "tokens=1-2 delims=:" %%a in ('time /t') do (
    set HOUR=%%a
    set MINUTE=%%b
)

REM 공백 제거
set HOUR=%HOUR: =%
set MINUTE=%MINUTE: =%

echo 현재 시간: %HOUR%:%MINUTE%
echo.

REM 시간에 따른 종료 결정
if %HOUR% LSS 21 (
    echo ℹ️  아직 21시 이전입니다.
    echo    - 21시에 자동 종료됩니다.
    echo    - 수동으로 종료하려면 Ctrl+C를 누르세요.
    echo.

    REM 21시까지 남은 시간 계산
    set /a REMAINING_HOURS=21-%HOUR%
    set /a REMAINING_MINUTES=60-%MINUTE%

    if %REMAINING_MINUTES% EQU 60 (
        set REMAINING_MINUTES=0
    ) else (
        set /a REMAINING_HOURS=%REMAINING_HOURS%-1
    )

    echo 남은 시간: 약 %REMAINING_HOURS%시간 %REMAINING_MINUTES%분
    echo.

    goto SCHEDULE_SHUTDOWN
) else (
    echo ✅ 21시가 지났습니다. 종료합니다.
    goto NORMAL_SHUTDOWN
)

:WEEKEND_SHUTDOWN
echo.
echo ========================================
echo 🌴 주말 모드
echo ========================================
echo.
echo 주말에는 매매가 없으므로 바로 종료합니다.
echo.

REM 로그 기록
echo %date% %time% - 주말 자동 종료 >> automation_log.txt

echo 💤 30초 후 컴퓨터를 종료합니다...
echo 취소하려면 Ctrl+C를 누르세요.
echo.
timeout /t 30
shutdown /s /t 0 /c "주말 자동 종료"
goto END

:NORMAL_SHUTDOWN
echo.
echo ========================================
echo 🌙 평일 종료
echo ========================================
echo.

REM 로그 기록
echo %date% %time% - 평일 자동 종료 (21시 이후) >> automation_log.txt

echo 💤 60초 후 컴퓨터를 종료합니다...
echo 취소하려면 Ctrl+C를 누르세요.
echo.
timeout /t 60
shutdown /s /t 0 /c "21시 자동 종료"
goto END

:SCHEDULE_SHUTDOWN
echo.
echo ========================================
echo ⏰ 예약 종료
echo ========================================
echo.

REM 로그 기록
echo %date% %time% - 21시 자동 종료 예약 >> automation_log.txt

REM 21시 = 21:00:00 (초 단위로 계산)
set /a TARGET_SECONDS=21*3600

REM 현재 시간을 초로 변환
set /a CURRENT_SECONDS=%HOUR%*3600 + %MINUTE%*60

REM 남은 시간 (초)
set /a REMAINING_SECONDS=%TARGET_SECONDS% - %CURRENT_SECONDS%

REM 음수면 내일로 계산 (이미 21시 지남 - 위에서 걸러져야 하지만 안전장치)
if %REMAINING_SECONDS% LSS 0 (
    set /a REMAINING_SECONDS=%REMAINING_SECONDS% + 86400
)

echo 21시에 자동으로 종료됩니다.
echo 남은 시간: %REMAINING_SECONDS%초
echo.
echo 취소하려면 다음 명령어를 실행하세요:
echo   shutdown /a
echo.

shutdown /s /t %REMAINING_SECONDS% /c "21시 자동 종료"

echo ✅ 종료 예약 완료
goto END

:END
echo.
echo ========================================
echo 작업 완료
echo 종료 시간: %date% %time%
echo ========================================
echo.

exit /b 0
