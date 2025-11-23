"""
패키지 설치 확인 스크립트
실행: python check_packages.py
"""

import sys

print("=" * 60)
print("필수 패키지 설치 확인")
print("=" * 60)
print()

# 필수 패키지 목록
required_packages = {
    'PyQt5': 'GUI 프레임워크',
    'pandas': '데이터 처리',
    'numpy': '수치 계산',
    'pymysql': 'MySQL 연결',
    'sqlalchemy': 'ORM',
    'requests': 'HTTP 요청',
    'bs4': '웹 크롤링',
    'lxml': 'XML/HTML 파싱',
}

# 선택 패키지 목록
optional_packages = {
    'tensorflow': 'AI 모델 (LSTM)',
    'sklearn': '머신러닝',
    'scipy': '과학 계산',
}

missing_required = []
missing_optional = []

print("📦 필수 패키지 확인:")
print("-" * 60)

for package, description in required_packages.items():
    try:
        __import__(package)
        print(f"  ✅ {package:<20} - {description}")
    except ImportError:
        print(f"  ❌ {package:<20} - {description} (미설치)")
        missing_required.append(package)

print()
print("🤖 선택 패키지 확인 (AI 기능):")
print("-" * 60)

for package, description in optional_packages.items():
    try:
        __import__(package)
        print(f"  ✅ {package:<20} - {description}")
    except ImportError:
        print(f"  ⚠️  {package:<20} - {description} (미설치, 선택사항)")
        missing_optional.append(package)

print()
print("=" * 60)

if missing_required:
    print("❌ 필수 패키지 누락!")
    print()
    print("다음 명령어로 설치하세요:")
    print(f"  pip install {' '.join(missing_required)}")
    print()
    sys.exit(1)
else:
    print("✅ 모든 필수 패키지 설치 완료!")
    print()

    if missing_optional:
        print("⚠️  선택 패키지 누락 (AI 기능 사용 불가):")
        print(f"  pip install {' '.join(missing_optional)}")
        print()
        print("💡 AI 없이도 기본 매매 전략 사용 가능합니다!")
    else:
        print("🎉 선택 패키지까지 모두 설치 완료!")

    print()
    print("다음 단계:")
    print("  1. library/cf.py 설정 확인")
    print("  2. python collector_v3.py 실행")
    sys.exit(0)
