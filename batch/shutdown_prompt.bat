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
echo [INFO] 계속 작업하시려면 팝업에서 "예"를 선택하세요.
echo.
echo ========================================
echo.

REM 15분 후 첫 번째 팝업 (900초 대기)
echo [WAIT] 15분 대기 중...
timeout /t 900 /nobreak > nul

echo.
echo [POPUP] 15분 후 시스템 종료 예정 - 확인 팝업 표시 중...
cscript //nologo "%SCRIPT_DIR%popup_timeout.vbs" "15분 후 시스템 종료" "시스템이 15분 후 자동 종료됩니다.\n\n계속 작업하시겠습니까?\n\n(60초 후 자동으로 닫힙니다)" 60 > "%TEMP%\popup_result.txt"
set /p RESULT=<"%TEMP%\popup_result.txt"
if "!RESULT!"=="6" goto USER_CONTINUE
echo [INFO] 종료 진행 - 카운트다운 계속...

REM 10분 후 두 번째 팝업 (600초 대기)
echo [WAIT] 10분 대기 중...
timeout /t 600 /nobreak > nul

echo.
echo [POPUP] 5분 후 시스템 종료 예정 - 확인 팝업 표시 중...
cscript //nologo "%SCRIPT_DIR%popup_timeout.vbs" "5분 후 시스템 종료" "시스템이 5분 후 자동 종료됩니다!\n\n계속 작업하시겠습니까?\n\n(60초 후 자동으로 닫힙니다)" 60 > "%TEMP%\popup_result.txt"
set /p RESULT=<"%TEMP%\popup_result.txt"
if "!RESULT!"=="6" goto USER_CONTINUE
echo [INFO] 종료 진행 - 카운트다운 계속...

REM 4분 후 세 번째 팝업 (240초 대기)
echo [WAIT] 4분 대기 중...
timeout /t 240 /nobreak > nul

echo.
echo [POPUP] 1분 후 시스템 종료 예정 - 최종 확인 팝업 표시 중...
cscript //nologo "%SCRIPT_DIR%popup_timeout.vbs" "최종 확인 - 1분 후 종료" "시스템이 1분 후 자동 종료됩니다!\n\n[예] 계속 작업\n[아니오] 종료 진행\n\n(30초 후 자동으로 닫힙니다)" 30 > "%TEMP%\popup_result.txt"
set /p RESULT=<"%TEMP%\popup_result.txt"
if "!RESULT!"=="6" goto USER_CONTINUE
echo [INFO] 종료 진행...

REM 마지막 1분 대기
echo [WAIT] 1분 대기 중...
timeout /t 60 /nobreak > nul

REM 시스템 종료
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
