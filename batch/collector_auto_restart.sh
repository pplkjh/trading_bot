#!/bin/bash
# ========================================
# collector 자동 재시작 스크립트 (Linux/Mac)
# ========================================
# 999회 호출 후 종료되면 자동으로 다시 시작
# 데이터 수집이 완료될 때까지 반복
# ========================================

echo "========================================"
echo "Collector 자동 재시작 스크립트"
echo "========================================"
echo ""
echo "이 스크립트는 collector가 종료되면 자동으로 재시작합니다."
echo "수집이 완료될 때까지 계속 실행됩니다."
echo ""
echo "중지하려면: Ctrl+C"
echo "========================================"
echo ""

# Python 경로
PYTHON_PATH="python3"

# 무한 루프
while true; do
    echo ""
    echo "[$(date)] Collector 시작..."
    echo "========================================"

    # collector 실행
    $PYTHON_PATH collector_v3.py

    # 종료 코드 확인
    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ]; then
        echo ""
        echo "[$(date)] Collector가 정상 종료되었습니다."
        echo "5초 후 재시작..."
        sleep 5
    else
        echo ""
        echo "[$(date)] Collector가 에러로 종료되었습니다. (코드: $EXIT_CODE)"
        echo "에러 확인이 필요합니다."
        echo ""
        read -p "다시 시작하시겠습니까? (y/n): " answer

        if [ "$answer" != "y" ] && [ "$answer" != "Y" ]; then
            echo "중지되었습니다."
            break
        fi

        echo "재시작 중..."
        sleep 3
    fi
done

echo ""
echo "========================================"
echo "Collector 자동 재시작 종료"
echo "========================================"
