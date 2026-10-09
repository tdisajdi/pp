#!/usr/bin/env python3
"""gallery-dl이 뽑은 계정 목록(raw)을 명단 파일에 합친다.

사용: python merge_following.py 명단파일.txt raw파일.txt 내아이디 [following|saved]
 - raw 파일의 각 줄은 인스타그램 주소 또는 아이디.
 - 기존 줄(# 제외 표시 포함)은 그대로 두고, 명단에 없던 계정만 맨 아래에 추가한다.
 - following 모드: 팔로우 해제된 계정은 지우지 않고 알려 주기만 한다.
 - saved 모드: 저장한 게시물의 작성자 계정을 추가한다. (팔로잉하지 않아도 추가됨)
 - 새 계정을 하나도 못 읽었으면(차단/쿠키 실패) 파일을 건드리지 않고 종료코드 1.
"""
import os
import re
import sys
import time

URL = re.compile(r"^https?://(?:www\.)?instagram\.com/([A-Za-z0-9._]+)/?$")
BARE = re.compile(r"^[A-Za-z0-9._]{1,30}$")


def read_accounts(raw_file):
    names = []
    seen = set()
    if os.path.exists(raw_file):
        with open(raw_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                s = line.strip()
                m = URL.match(s)
                name = m.group(1) if m else (s if BARE.match(s) else None)
                if name and name.lower() not in seen:
                    seen.add(name.lower())
                    names.append(name)
    return names


def main():
    if len(sys.argv) < 4:
        print("usage: merge_following.py LIST RAW MYID [following|saved]")
        return 2
    list_file, raw_file, me = sys.argv[1:4]
    mode = sys.argv[4] if len(sys.argv) > 4 else "following"

    accounts = [n for n in read_accounts(raw_file) if n.lower() != me.lower()]
    if not accounts:
        print("No accounts were read (blocked or cookies not working). List file left unchanged.")
        return 1

    if not os.path.exists(list_file):
        with open(list_file, "w", encoding="utf-8") as f:
            f.write(f"# @{me} 의 계정 목록\n")
            f.write("# 다운로드 하기 싫은 계정은 앞에 # 을 붙여주세요. 예: #username\n")
            f.write("# ------------------------------------------------\n")
            f.write("\n".join(accounts) + "\n")
        print(f"Created {list_file}: {len(accounts)} accounts")
        return 0

    with open(list_file, "r", encoding="utf-8") as f:
        old_lines = f.read().splitlines()
    known = {l.strip().lstrip("#").strip().lower() for l in old_lines if l.strip()}
    added = [n for n in accounts if n.lower() not in known]

    if added:
        label = "from saved posts" if mode == "saved" else "new accounts"
        with open(list_file, "a", encoding="utf-8") as f:
            if old_lines and old_lines[-1] != "":
                f.write("\n")
            f.write(f"# ---- {label} ({time.strftime('%Y-%m-%d')}) ----\n")
            f.write("\n".join(added) + "\n")

    if mode == "saved":
        print(f"Accounts in saved posts: {len(accounts)} | newly added: {len(added)}")
        return 0

    # "from saved posts" 구간에 있는 계정은 원래 팔로잉이 아니므로 해제 알림에서 제외
    current = {n.lower() for n in accounts}
    unfollowed = []
    in_saved = False
    for l in old_lines:
        s = l.strip()
        if s.startswith("# ----"):
            in_saved = "from saved posts" in s
        elif s and not s.startswith("#") and not in_saved and s.lower() not in current:
            unfollowed.append(s)
    print(f"Following now: {len(accounts)} | newly added: {len(added)}")
    if unfollowed:
        shown = ", ".join(unfollowed[:10]) + (" ..." if len(unfollowed) > 10 else "")
        print(f"Not in the following list anymore (kept in file): {len(unfollowed)} -> {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
