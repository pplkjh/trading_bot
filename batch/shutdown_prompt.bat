@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
REM ===================================================
REM 자동 종료 확인 스크립트
REM 장 종료 후 30분 타이머 + 사용자 확인 팝업
REM ===================================================

echo ========================================
echo 자동 종료 확인 프로세스
echo ========================================
echo.
echo 시작 시각: %date% %time%
echo.

set SCRIPT_DIR=%~dp0

REM 작업 디렉토리로 이동
cd /d %SCRIPT_DIR%..

REM 로그 기록
echo %date% %time% - 자동 종료 확인 시작 >> automation_log.txt

echo.
echo [INFO] 30분 후 시스템이 자동 종료됩니다.
echo [INFO] 계속 작업하시려면 아래 팝업에서 "예"를 선택하세요.
echo.
echo ========================================
echo.

REM 30분 = 1800초 카운트다운 시작 (백그라운드)
REM 매 5분마다 상태 표시, 마지막 1분은 매 10초마다

set TOTAL_SECONDS=1800
set REMAINING=%TOTAL_SECONDS%

:COUNTDOWN
    REM 남은 시간 계산
    set /a MINUTES=%REMAINING%/60
    set /a SECONDS=%REMAINING%%%60

    REM 5분마다 또는 1분 미만일 때 표시
    set /a CHECK_INTERVAL=%REMAINING%%%300
    if %REMAINING% LEQ 60 (
        set /a CHECK_INTERVAL=%REMAINING%%%10
    )

    if %CHECK_INTERVAL%==0 (
        echo   [%time%] 남은 시간: %MINUTES%분 %SECONDS%초
    )

    REM 15분, 5분, 1분 남았을 때 팝업 표시
    if %REMAINING%==900 goto SHOW_POPUP_15
    if %REMAINING%==300 goto SHOW_POPUP_5
    if %REMAINING%==60 goto SHOW_POPUP_1

    goto CONTINUE_COUNTDOWN

:SHOW_POPUP_15
    echo.
    echo [POPUP] 15분 후 시스템 종료 예정 - 확인 팝업 표시 중...
    powershell -Command "Add-Type -AssemblyName PresentationFramework; $result = [System.Windows.MessageBox]::Show('시스템이 15분 후 자동 종료됩니다.`n`n계속 작업하시겠습니까?', '자동 종료 알림', 'YesNo', 'Question'); if($result -eq 'Yes') { exit 1 } else { exit 0 }"
    if %ERRORLEVEL%==1 goto USER_CONTINUE
    goto CONTINUE_COUNTDOWN

:SHOW_POPUP_5
    echo.
    echo [POPUP] 5분 후 시스템 종료 예정 - 확인 팝업 표시 중...
    powershell -Command "Add-Type -AssemblyName PresentationFramework; $result = [System.Windows.MessageBox]::Show('시스템이 5분 후 자동 종료됩니다!`n`n계속 작업하시겠습니까?', '자동 종료 알림', 'YesNo', 'Warning'); if($result -eq 'Yes') { exit 1 } else { exit 0 }"
    if %ERRORLEVEL%==1 goto USER_CONTINUE
    goto CONTINUE_COUNTDOWN

:SHOW_POPUP_1
    echo.
    echo [POPUP] 1분 후 시스템 종료 예정 - 최종 확인 팝업 표시 중...
    powershell -Command "Add-Type -AssemblyName PresentationFramework; $result = [System.Windows.MessageBox]::Show('시스템이 1분 후 자동 종료됩니다!`n`n[예] 계속 작업`n[아니오] 종료 진행', '최종 확인', 'YesNo', 'Exclamation'); if($result -eq 'Yes') { exit 1 } else { exit 0 }"
    if %ERRORLEVEL%==1 goto USER_CONTINUE
    goto CONTINUE_COUNTDOWN

:CONTINUE_COUNTDOWN
    timeout /t 1 /nobreak > nul
    set /a REMAINING=%REMAINING%-1

    if %REMAINING% GTR 0 goto COUNTDOWN

REM 30분 타임아웃 - 시스템 종료
echo.
echo ========================================
echo [SHUTDOWN] 시간 초과 - 시스템을 종료합니다...
echo ========================================
echo.

REM 로그 기록
echo %date% %time% - 자동 종료 실행 (타임아웃) >> automation_log.txt

shutdown /s /t 60 /c "트레이딩 봇 자동 종료: 30분 동안 응답이 없어 시스템을 종료합니다."
exit

:USER_CONTINUE
echo.
echo ========================================
echo [OK] 사용자가 계속 작업을 선택했습니다.
echo ========================================
echo.
echo 자동 종료가 취소되었습니다.
echo 다음 예약된 종료 시간까지 시스템이 유지됩니다.
echo.

REM 로그 기록
echo %date% %time% - 자동 종료 취소 (사용자 선택) >> automation_log.txt

echo 5초 후 이 창이 닫힙니다...
timeout /t 5 /nobreak
exit
