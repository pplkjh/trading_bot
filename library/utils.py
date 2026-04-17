"""
공통 유틸리티 함수 모음
"""
import datetime


def get_latest_complete_date(date_rows=None):
    """기준 날짜를 반환한다 — 어느 DB에 저장/조회할지 결정하는 핵심 함수.

    - 09:00 이전 (장전) : 오늘 데이터 미완성 → 직전 영업일 반환
    - 09:00 이후 (장중·장후) : 오늘 live/종가 사용 가능 → today 반환

    의도:
      - 08:10 실행 → previous business day (전날 종가 기준)
      - 12:30 실행 → today (장중 live 가격 기준)
      - 17:10 실행 → today (오늘 종가 기준)

    Parameters
    ----------
    date_rows : list of tuples or None
        daily_craw 날짜 목록 [(date,), ...] 형태.
        None 이면 캘린더 추정(주말만 제외)을 사용.

    Returns
    -------
    str : 'YYYYMMDD' 형식
    """
    now = datetime.datetime.now()
    market_open = now.hour >= 9  # 09:00 이후: 장중(live) + 장후(final) 모두 today 반환
    today = now.strftime("%Y%m%d")

    if date_rows is not None:
        dates = [str(r[0]) for r in date_rows]
        if not dates:
            return today
        if market_open:
            return today if today in dates else dates[-1]
        else:  # 장전 (hour < 9)
            prev_dates = [d for d in dates if d < today]
            return prev_dates[-1] if prev_dates else dates[-1]
    else:
        if market_open:
            return today
        else:  # 장전 (hour < 9)
            dt = now - datetime.timedelta(days=1)
            while dt.weekday() >= 5:  # 토(5), 일(6) 건너뜀
                dt -= datetime.timedelta(days=1)
            return dt.strftime("%Y%m%d")
