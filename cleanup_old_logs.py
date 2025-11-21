#!/usr/bin/env python
"""
오래된 로그 파일 자동 삭제 스크립트

10일 이상 지난 로그 파일을 자동으로 삭제합니다.
"""

import os
import datetime
import pathlib
from typing import List

# 로그 디렉토리
LOG_DIRS = [
    pathlib.Path(__file__).parent / 'log',
    pathlib.Path(__file__).parent / 'logs'
]

# 보관 기간 (일)
RETENTION_DAYS = 10


def get_old_log_files(log_dir: pathlib.Path, days: int = RETENTION_DAYS) -> List[pathlib.Path]:
    """
    오래된 로그 파일 목록 가져오기

    Parameters:
    -----------
    log_dir : pathlib.Path
        로그 디렉토리
    days : int
        보관 기간 (일)

    Returns:
    --------
    List[pathlib.Path] : 삭제 대상 파일 리스트
    """
    if not log_dir.exists():
        return []

    cutoff_time = datetime.datetime.now() - datetime.timedelta(days=days)
    old_files = []

    for log_file in log_dir.glob('*.log*'):
        # 현재 활성 로그 파일은 제외
        if log_file.name in ['jackbot.log', 'trading_events.log']:
            continue

        # 파일 수정 시간 확인
        file_mtime = datetime.datetime.fromtimestamp(log_file.stat().st_mtime)

        if file_mtime < cutoff_time:
            old_files.append(log_file)

    return old_files


def cleanup_logs(dry_run: bool = False) -> dict:
    """
    오래된 로그 파일 삭제

    Parameters:
    -----------
    dry_run : bool
        True면 삭제하지 않고 목록만 출력

    Returns:
    --------
    dict : 삭제 결과
    """
    result = {
        'total_files': 0,
        'total_size': 0,
        'deleted_files': [],
        'errors': []
    }

    for log_dir in LOG_DIRS:
        if not log_dir.exists():
            continue

        old_files = get_old_log_files(log_dir, RETENTION_DAYS)

        for log_file in old_files:
            file_size = log_file.stat().st_size
            result['total_files'] += 1
            result['total_size'] += file_size

            if dry_run:
                print(f"[DRY-RUN] 삭제 대상: {log_file.name} ({file_size / 1024:.1f} KB)")
                result['deleted_files'].append(str(log_file))
            else:
                try:
                    log_file.unlink()
                    print(f"✅ 삭제: {log_file.name} ({file_size / 1024:.1f} KB)")
                    result['deleted_files'].append(str(log_file))
                except Exception as e:
                    print(f"❌ 삭제 실패: {log_file.name} - {e}")
                    result['errors'].append({'file': str(log_file), 'error': str(e)})

    return result


def print_summary(result: dict):
    """삭제 결과 요약 출력"""
    print("\n" + "=" * 80)
    print("📊 로그 정리 결과")
    print("=" * 80)
    print(f"삭제된 파일: {len(result['deleted_files'])}개")
    print(f"확보된 공간: {result['total_size'] / 1024 / 1024:.2f} MB")

    if result['errors']:
        print(f"❌ 오류 발생: {len(result['errors'])}건")
        for error in result['errors']:
            print(f"  - {error['file']}: {error['error']}")

    print("=" * 80)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='오래된 로그 파일 자동 삭제')
    parser.add_argument('--days', type=int, default=RETENTION_DAYS,
                       help=f'보관 기간 (일, 기본값: {RETENTION_DAYS})')
    parser.add_argument('--dry-run', action='store_true',
                       help='실제로 삭제하지 않고 목록만 출력')

    args = parser.parse_args()

    RETENTION_DAYS = args.days

    print("=" * 80)
    print("🧹 로그 파일 정리 시작")
    print("=" * 80)
    print(f"보관 기간: {RETENTION_DAYS}일")
    print(f"실행 모드: {'테스트 (삭제 안 함)' if args.dry_run else '실제 삭제'}")
    print()

    result = cleanup_logs(dry_run=args.dry_run)
    print_summary(result)

    if args.dry_run:
        print("\n💡 실제로 삭제하려면 --dry-run 옵션 없이 실행하세요.")
