#!/usr/bin/env python3
"""Edge 등에서 복사한 sessionid 값으로 gallery-dl용 cookies.txt 를 만든다.

사용: python make_cookies.py            (값을 물어봅니다)
      python make_cookies.py 값         (바로 만들기)
sessionid 는 로그인 정보와 같습니다. cookies.txt 를 다른 사람에게 보내지 마세요.
"""
import os
import sys
import time


def clean(value):
    v = value.strip().strip('"').strip("'").strip()
    return v


def main():
    if len(sys.argv) > 1:
        raw = " ".join(sys.argv[1:])
    else:
        print("Paste the sessionid value from Edge and press Enter.")
        print("(Edge: F12 > Application > Storage > Cookies > https://www.instagram.com > sessionid > Value)")
        raw = input("sessionid: ")
    sid = clean(raw)
    if sid.lower().startswith("sessionid"):
        sid = sid.split("=", 1)[-1].strip() if "=" in sid else sid[len("sessionid"):].strip()
    if len(sid) < 20 or any(c.isspace() for c in sid):
        print("That does not look like a sessionid. It is a long value without spaces.")
        return 1

    expires = int(time.time()) + 365 * 24 * 3600
    lines = [
        "# Netscape HTTP Cookie File",
        f".instagram.com\tTRUE\t/\tTRUE\t{expires}\tsessionid\t{sid}",
        "",
    ]
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    print(f"Saved: {out}")
    print("Keep this file private. Do not log out of Instagram in Edge while downloading.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
