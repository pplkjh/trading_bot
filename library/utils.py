"""
공통 유틸리티 함수 모음
"""
import datetime


def get_latest_complete_date(date_rows=None):
    """장마감 여부에 따라 '완전한 데이터'의 최신 날짜를 반환한다.

    - 15:40 이후 : 오늘 종가 확정 → today 반환
    - 15:40 이전 : 오늘 데이터 미완성 → 가장 최근 이전 영업일 반환

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
    market_closed = (now.hour > 15) or (now.hour == 15 and now.minute >= 40)
    today = now.strftime("%Y%m%d")

    if date_rows is not None:
        dates = [str(r[0]) for r in date_rows]
        if not dates:
            return today
        if market_closed:
            return today if today in dates else dates[-1]
        else:
            prev_dates = [d for d in dates if d < today]
            return prev_dates[-1] if prev_dates else dates[-1]
    else:
        if market_closed:
            return today
        else:
            dt = now - datetime.timedelta(days=1)
            while dt.weekday() >= 5:  # 토(5), 일(6) 건너뜀
                dt -= datetime.timedelta(days=1)
            return dt.strftime("%Y%m%d")
