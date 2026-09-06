@echo off
chcp 65001 > nul
title 매수 전략 테스트 (읽기 전용)

echo.
echo ================================================================================
echo 🧪 매수 전략 테스트 (읽기 전용)
echo ================================================================================
echo.
echo ✅ 안전:
echo   - 실제 DB를 수정하지 않습니다
echo   - realtime_daily_buy_list를 업데이트하지 않습니다
echo   - trader에 영향을 주지 않습니다
echo.
echo 📊 기능:
echo   - 이미 수집된 daily_buy_list 테이블을 읽기만 합니다
echo   - 하이브리드 전략으로 매수 후보를 분석합니다
echo   - 결과를 화면에 출력하고 CSV로 저장합니다
echo.
echo 💡 용도:
echo   - 전략 파라미터 테스트 및 검증
echo   - 문제 없으면 수동으로 collector에 적용
echo.
echo ⚠️  주의: daily_buy_list 테이블이 있어야 합니다
echo          (collector_v3.py를 먼저 실행하세요)
echo.
echo ================================================================================
echo.

cd /d "%~dp0.."

REM Anaconda 환경 활성화
call C:\Users\%USERNAME%\anaconda3\Scripts\activate.bat py37_32

REM Python 스크립트 실행
python test_buy_strategy.py

REM 환경 비활성화
call conda deactivate

pause
