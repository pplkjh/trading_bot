#!/bin/bash
# 필수 패키지 일괄 설치 스크립트
# 실행: bash install_requirements.sh

echo "=========================================="
echo "자동매매 시스템 필수 패키지 설치"
echo "=========================================="

echo ""
echo "📦 기본 패키지 설치 중..."
pip install PyQt5
pip install pandas
pip install numpy
pip install pymysql
pip install sqlalchemy
pip install requests
pip install beautifulsoup4
pip install lxml

echo ""
echo "🤖 AI/ML 패키지 설치 중 (선택사항, 시간 걸림)..."
read -p "AI 기능을 사용하시겠습니까? (y/n): " use_ai

if [ "$use_ai" = "y" ] || [ "$use_ai" = "Y" ]; then
    pip install tensorflow
    pip install scikit-learn
    pip install scipy
    echo "✅ AI 패키지 설치 완료"
else
    echo "⏭️  AI 패키지 설치 건너뜀"
fi

echo ""
echo "=========================================="
echo "✅ 패키지 설치 완료!"
echo "=========================================="
echo ""
echo "다음 명령어로 설치 확인:"
echo "  python check_packages.py"
echo ""
