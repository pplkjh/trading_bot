@echo off
echo ========================================
echo ChromeDriver 자동 관리 패키지 설치
echo ========================================
echo.

echo webdriver-manager 설치 중...
pip install webdriver-manager>=3.8.0

if %errorlevel% neq 0 (
    echo.
    echo [오류] webdriver-manager 설치 실패
    echo pip 업그레이드를 시도합니다...
    python -m pip install --upgrade pip
    pip install webdriver-manager>=3.8.0
)

echo.
echo ========================================
echo 설치 완료!
echo ========================================
echo.
echo 이제 collector_v3.py를 실행할 수 있습니다.
echo python collector_v3.py
echo.
pause
