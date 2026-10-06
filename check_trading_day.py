"""
주식 장 영업일 체크 스크립트
주말(토, 일)과 공휴일을 감지하여 비영업일이면 10분 후 시스템 종료

참고:
- 한국 주식시장은 크리스마스에도 정상 영업합니다
- 근로자의 날(5/1)에도 정상 영업합니다
"""
import datetime
import time
import os
import sys

# Windows 콘솔 UTF-8 인코딩 설정
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# 한국 공휴일 (2025년) - 주식시장 휴장일 기준
HOLIDAYS_2025 = [
    '20250101',  # 신정
    '20250127',  # 설날 연휴
    '20250128',  # 설날
    '20250129',  # 설날 연휴
    '20250130',  # 설날 대체공휴일
    '20250301',  # 삼일절
    '20250303',  # 삼일절 대체공휴일
    '20250505',  # 어린이날
    '20250506',  # 어린이날 대체공휴일 / 부처님오신날
    '20250606',  # 현충일
    '20250815',  # 광복절
    '20251003',  # 개천절
    '20251006',  # 추석 연휴
    '20251007',  # 추석
    '20251008',  # 추석 연휴
    '20251009',  # 한글날
]

# 한국 공휴일 (2026년) - 주식시장 휴장일 기준
HOLIDAYS_2026 = [
    '20260101',  # 신정
    '20260216',  # 설날 연휴
    '20260217',  # 설날
    '20260218',  # 설날 연휴
    '20260301',  # 삼일절
    '20260302',  # 삼일절 대체공휴일
    '20260505',  # 어린이날
    '20260524',  # 부처님 오신날
    '20260525',  # 부처님 오신날 대체공휴일
    '20260606',  # 현충일
    '20260815',  # 광복절
    '20260817',  # 광복절 대체공휴일
    '20260924',  # 추석 연휴
    '20260925',  # 추석
    '20260926',  # 추석 연휴
    '20261003',  # 개천절
    '20261005',  # 개천절 대체공휴일
    '20261009',  # 한글날
]

# 한국 공휴일 (2027년) - 주식시장 휴장일 기준
HOLIDAYS_2027 = [
    '20270101',  # 신정
    '20270206',  # 설날 연휴
    '20270207',  # 설날
    '20270208',  # 설날 연휴
    '20270209',  # 설날 대체공휴일
    '20270301',  # 삼일절
    '20270505',  # 어린이날
    '20270513',  # 부처님 오신날
    '20270606',  # 현충일
    '20270815',  # 광복절
    '20270816',  # 광복절 대체공휴일
    '20270914',  # 추석 연휴
    '20270915',  # 추석
    '20270916',  # 추석 연휴
    '20271003',  # 개천절
    '20271004',  # 개천절 대체공휴일
    '20271009',  # 한글날
    '20271011',  # 한글날 대체공휴일
]

# 연도별 공휴일 매핑
HOLIDAYS_BY_YEAR = {
    2025: HOLIDAYS_2025,
    2026: HOLIDAYS_2026,
    2027: HOLIDAYS_2027,
}

def is_trading_day():
    """
    오늘이 주식 시장 영업일인지 체크

    Returns:
        bool: 영업일이면 True, 주말/공휴일이면 False
    """
    today = datetime.date.today()
    today_str = today.strftime('%Y%m%d')
    year = today.year

    # 주말 체크 (토요일=5, 일요일=6)
    if today.weekday() >= 5:
        return False

    # 공휴일 체크 (해당 연도 데이터가 있는 경우만)
    if year in HOLIDAYS_BY_YEAR:
        if today_str in HOLIDAYS_BY_YEAR[year]:
            return False
    else:
        # 연도 데이터가 없으면 경고 메시지 출력하고 영업일로 간주
        print(f"⚠️  경고: {year}년 공휴일 데이터가 없습니다. check_trading_day.py를 업데이트하세요!")

    return True

def get_day_name():
    """오늘 요일 한글로 반환"""
    days = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
    return days[datetime.date.today().weekday()]

if __name__ == "__main__":
    today = datetime.date.today()
    today_str = f"{today.year}년 {today.month:02d}월 {today.day:02d}일"
    day_name = get_day_name()

    if is_trading_day():
        print(f"✅ {today_str} ({day_name}) - 정규 장날입니다.")
        sys.exit(0)  # 영업일
    else:
        print(f"\n⚠️  {today_str} ({day_name}) - 주식 시장이 열리지 않습니다.")

        # 주말인지 공휴일인지 구분
        if today.weekday() >= 5:
            print("   사유: 주말")
        else:
            print("   사유: 공휴일")

        print("\n" + "="*80)
        print("💡 10분 후 시스템을 자동으로 종료합니다.")
        print("="*80)
        print("\n⏰ 카운트다운 시작...\n")

        # 10분 카운트다운
        for i in range(600, 0, -1):
            mins = i // 60
            secs = i % 60
            print(f"\r종료까지 {mins:02d}:{secs:02d} 남음 (Ctrl+C로 취소)", end="", flush=True)
            time.sleep(1)

        print("\n\n🔌 시스템을 종료합니다...")

        # 윈도우 종료 (60초 후)
        os.system("shutdown /s /t 60 /c \"주식 장이 열리지 않는 날입니다. 시스템을 종료합니다.\"")

        sys.exit(1)  # 비영업일
