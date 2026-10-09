#!/usr/bin/env python3
"""gallery-dl이 뽑은 팔로잉 URL 목록(raw)을 명단 파일에 합친다.

사용: python merge_following.py 명단파일.txt raw파일.txt 대상아이디
 - 기존 줄(# 제외 표시 포함)은 그대로 둔다.
 - 새로 팔로우한 계정만 파일 맨 아래에 추가한다.
 - 팔로우 해제된 계정은 지우지 않고 알려 주기만 한다.
 - 새 계정을 하나도 못 읽었으면(차단/쿠키 실패) 파일을 건드리지 않고 종료코드 1.
"""
import os
import re
import sys
import time

URL = re.compile(r"^https?://(?:www\.)?instagram\.com/([A-Za-z0-9._]+)/?$")


def main():
    if len(sys.argv) < 4:
        print("사용법: merge_following.py 명단파일 raw파일 대상아이디")
        return 2
    list_file, raw_file, target = sys.argv[1:4]

    followees = []
    if os.path.exists(raw_file):
        with open(raw_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                m = URL.match(line.strip())
                if m and m.group(1) not in followees:
                    followees.append(m.group(1))

    if not followees:
        print("No following accounts were read (blocked or cookies not working). List file left unchanged.")
        return 1

    if not os.path.exists(list_file):
        with open(list_file, "w", encoding="utf-8") as f:
            f.write(f"# @{target} 의 팔로잉 목록\n")
            f.write("# 다운로드 하기 싫은 계정은 앞에 # 을 붙여주세요. 예: #username\n")
            f.write("# ------------------------------------------------\n")
            f.write("\n".join(followees) + "\n")
        print(f"Created {list_file}: {len(followees)} accounts")
        return 0

    with open(list_file, "r", encoding="utf-8") as f:
        old_lines = f.read().splitlines()
    known = {l.strip().lstrip("#").strip().lower() for l in old_lines if l.strip()}
    current = {n.lower() for n in followees}
    added = [n for n in followees if n.lower() not in known]
    unfollowed = [l.strip() for l in old_lines
                  if l.strip() and not l.strip().startswith("#")
                  and l.strip().lower() not in current]

    if added:
        with open(list_file, "a", encoding="utf-8") as f:
            if old_lines and old_lines[-1] != "":
                f.write("\n")
            f.write(f"# ---- new accounts ({time.strftime('%Y-%m-%d')}) ----\n")
            f.write("\n".join(added) + "\n")

    print(f"Following now: {len(followees)} | newly added: {len(added)}")
    if unfollowed:
        shown = ", ".join(unfollowed[:10]) + (" ..." if len(unfollowed) > 10 else "")
        print(f"No longer followed (kept in file): {len(unfollowed)} -> {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
