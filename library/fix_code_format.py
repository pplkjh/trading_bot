"""
daily_craw_config.py의 종목코드 포맷 에러 수정 패치
실행: python library/fix_code_format.py
"""

import re

file_path = 'library/daily_craw_config.py'

print("=" * 60)
print("종목코드 포맷 에러 수정")
print("=" * 60)

# 파일 읽기
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 원본 백업
with open(file_path + '.backup', 'w', encoding='utf-8') as f:
    f.write(content)
print(f"✅ 원본 백업: {file_path}.backup")

# 패턴: self.code_df*.종목코드 = self.code_df*.종목코드.map('{:06d}'.format)
# 수정: 정수 변환 후 포맷팅 또는 문자열이면 zfill 사용

old_pattern = r"(self\.code_df\w*\.종목코드)\s*=\s*\1\.map\('\{:06d\}'\.format\)"

new_code = r"\1 = \1.astype(str).str.zfill(6)"

# 치환
new_content = re.sub(old_pattern, new_code, content)

# 변경 사항 확인
if new_content != content:
    changes = content.count(".map('{:06d}'.format)")
    print(f"\n🔍 발견된 패턴: {changes}개")
    print(f"   변경: .map('{{:06d}}'.format) → .astype(str).str.zfill(6)")

    # 파일 저장
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"\n✅ 수정 완료: {file_path}")
    print(f"\n설명:")
    print(f"  - 종목코드를 문자열로 변환 후 6자리로 zero-padding")
    print(f"  - 문자열/정수 모두 처리 가능")
    print(f"  - pandas 버전 관계없이 작동")

else:
    print("\n⚠️  변경할 패턴을 찾지 못했습니다.")
    print("   이미 수정되었거나 파일 구조가 다를 수 있습니다.")

print("\n" + "=" * 60)
print("다음 단계: python collector_v3.py 재실행")
print("=" * 60)
