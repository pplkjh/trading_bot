import os
import logging
import pathlib
from logging.handlers import TimedRotatingFileHandler


class DeduplicateFilter(logging.Filter):
    """동일한 (파일, 줄번호, 메시지) 조합의 반복 로그를 억제한다.
    ERROR/WARNING/CRITICAL은 항상 통과. 내용이 바뀌면 다시 찍힌다."""

    def __init__(self):
        super().__init__()
        self._last = {}  # key: (filename, lineno) → last message

    def filter(self, record):
        if record.levelno >= logging.WARNING:
            return True  # WARNING 이상 항상 통과
        key = (record.filename, record.lineno)
        msg = record.getMessage()
        if self._last.get(key) == msg:
            return False  # 동일 메시지 억제
        self._last[key] = msg
        return True

# 목적
# 콜렉터, 시뮬레이터, 봇 모두 logging_pack.py를 import 하고있다.
# jackbot.log 라는 이름으로 로그파일이 만들어진다.

# JACKBOT_LOG_FILE env var가 있으면 backtest 전용 로그 (backtest_report 폴더, INFO 레벨)
# JACKBOT_LOG_NAME=simulator 이면 log/simulator.log (jackbot.log와 분리)
# 그 외 기본 jackbot.log (log 폴더, DEBUG 레벨)
_log_file_override = os.environ.get('JACKBOT_LOG_FILE')
_log_name = os.environ.get('JACKBOT_LOG_NAME', '')
_log_base = pathlib.Path(__file__).parent.parent.absolute() / 'log'

if _log_file_override:
    _log_dir = pathlib.Path(__file__).parent.parent.absolute() / 'backtest_report'
    os.makedirs(_log_dir, exist_ok=True)
    file_path = _log_dir / _log_file_override
    # JACKBOT_LOG_LEVEL=DEBUG 이면 백테스트 로그도 DEBUG 전부 기록
    _env_level = os.environ.get('JACKBOT_LOG_LEVEL', '').upper()
    _file_log_level = logging.DEBUG if _env_level == 'DEBUG' else logging.INFO
elif _log_name == 'simulator':
    file_path = _log_base / 'simulator.log'
    _file_log_level = logging.DEBUG
else:
    file_path = _log_base / 'jackbot.log'
    _file_log_level = logging.DEBUG

os.makedirs(file_path.parents[0], exist_ok=True)

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
file_handler.setLevel(_file_log_level)
file_handler.addFilter(DeduplicateFilter())

# formatter 생성
formatter = logging.Formatter('[%(levelname)s|%(filename)s:%(lineno)s] %(asctime)s > %(message)s')
stream_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)
file_handler.suffix = "%Y%m%d"

# logger instance에 handler 설정
logger.addHandler(stream_handler)
logger.addHandler(file_handler)


logger.debug('debug 모드!')
# logger.info('info 모드!')
# logger.warning('warning 모드!')
# logger.error('error 모드!')
# logger.critical('critical 모드!')
