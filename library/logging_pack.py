import os
import re
import logging
import pathlib
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler


class DeduplicateFilter(logging.Filter):
    """동일한 (파일, 줄번호, 메시지 패턴) 조합의 반복 로그를 억제한다.
    ERROR/WARNING/CRITICAL은 항상 통과.
    숫자를 '#'으로 정규화하여 카운트다운/타이머 메시지도 억제한다."""

    def __init__(self):
        super().__init__()
        self._last = {}  # key: (filename, lineno) → last normalized message

    def filter(self, record):
        if record.levelno >= logging.WARNING:
            return True  # WARNING 이상 항상 통과
        if getattr(record, 'no_dedup', False):
            return True  # no_dedup 마커 있으면 항상 통과
        key = (record.filename, record.lineno)
        msg = record.getMessage()
        normalized = re.sub(r'\d+', '#', msg)  # 숫자 → '#' 정규화
        if self._last.get(key) == normalized:
            return False  # 동일 패턴 억제
        self._last[key] = normalized
        return True

# 목적
# 콜렉터, 시뮬레이터, 봇 모두 logging_pack.py를 import 하고있다.
# jackbot.log 라는 이름으로 로그파일이 만들어진다.

# log파일 위치와 로그 이름을 설정한다.
# JACKBOT_LOG_NAME 환경변수로 로그 파일명 지정 가능 (시뮬레이터는 'simulator' 사용)
_log_name = os.environ.get('JACKBOT_LOG_NAME', 'jackbot')
file_path = pathlib.Path(__file__).parent.parent.absolute() / 'log' / f'{_log_name}.log'

os.makedirs(file_path.parents[0], exist_ok=True)  # 로그 폴더가 존재하는지 확인 후 없으면 생성

# 프로세스 시작 시점에 jackbot.log가 오늘 이전 날짜 파일이면 YYYYMMDD_jackbot.log로 rename
_today = datetime.now().strftime("%Y%m%d")
if file_path.exists():
    _mtime = datetime.fromtimestamp(file_path.stat().st_mtime).strftime("%Y%m%d")
    if _mtime < _today:
        _archive = file_path.parent / f"{_mtime}_{_log_name}.log"
        try:
            file_path.rename(_archive)
        except Exception:
            pass

# 로그 파일 더블클릭 -> 연결 프로그램 -> 메모장

# logger instance 생성
logger = logging.getLogger(__name__)


# logger instance로 로그찍기
# 로그레벨 순서 debug > info > warning > error > critical
# setLevel 에서 logger. + 대문자 DEBUG, INFO, WANRING, ERROR, CRITICAL 옵션 설정
# 여기서 설정된 로그레벨은 콜렉터, 시뮬레이터, 봇 등의 프로그램에 모두 적용이 됨
# 시뮬레이터는 print로만 설정한 이유는 속도 때문. logger 보다 print가 속도가 빠르다.
# 공부를 할 때는 시뮬레이터에 있는 모든 print를 ctrl + shift + r -> scope -> Current File 설정 후
# print 를 logger.debug로 모두 대체 해서 사용하면 logger 출력 위치를 알 수 있기 때문에 도움이 됨
logger.setLevel(logging.DEBUG)

# 콘솔 핸들러 (INFO 이상만 표시)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)  # 콘솔에는 INFO 이상만 출력

# 파일 핸들러 (DEBUG 모두 기록, 중복 억제)
file_handler = TimedRotatingFileHandler(file_path, when="midnight", encoding='utf-8')
file_handler.setLevel(logging.DEBUG)  # 파일에는 DEBUG 모두 기록
file_handler.addFilter(DeduplicateFilter())

# 자정 rotate 시 jackbot.log.20260407 → 20260407_jackbot.log 형식으로 변환
def _log_namer(default_name):
    # default_name 예: /path/log/jackbot.log.20260407
    base = pathlib.Path(default_name)
    parts = base.name.rsplit('.', 1)  # ['jackbot.log', '20260407']
    if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) == 8:
        return str(base.parent / f"{parts[1]}_{_log_name}.log")
    return default_name

file_handler.namer = _log_namer

# formatter 생성
formatter = logging.Formatter('[%(levelname)s|%(filename)s:%(lineno)s] %(asctime)s > %(message)s')
stream_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)
file_handler.suffix = "%Y%m%d"

# logger instance에 handler 설정
logger.addHandler(stream_handler)
logger.addHandler(file_handler)


# logger.debug('debug 모드!')
# logger.info('info 모드!')
# logger.warning('warning 모드!')
# logger.error('error 모드!')
# logger.critical('critical 모드!')
