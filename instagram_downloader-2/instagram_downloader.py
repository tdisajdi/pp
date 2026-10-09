#!/usr/bin/env python3
"""
인스타그램 공개 게시물 / 팔로잉 명단 다운로더 + 얼굴 분류
(계정별 폴더로 자동 정리)

========================================
1. 게시물 다운로드 (URL 또는 shortcode)
========================================
  python instagram_downloader.py https://www.instagram.com/p/XXXXX/
  python instagram_downloader.py XXXXX
  python instagram_downloader.py URL1 URL2             # 기본: 이미지/썸네일만
  python instagram_downloader.py --video URL1          # 동영상도 받고 싶을 때

========================================
2. 팔로잉 명단 뽑기
========================================
  python instagram_downloader.py --following 아이디
  → following_아이디.txt 파일로 저장됨

========================================
3. 특정 계정 게시물 다운로드 (기본: 전체)
========================================
  python instagram_downloader.py --profile 아이디
  python instagram_downloader.py --profile 아이디 --max 30   # 최근 30개만

========================================
4. 명단 파일로 여러 계정 다운로드
========================================
  python instagram_downloader.py --from-file following_아이디.txt
  python instagram_downloader.py --from-file following_아이디.txt --max 50

========================================
5. 얼굴 개수별 사진 분류 (삭제 안 함)
========================================
  python instagram_downloader.py --sort-faces
  python instagram_downloader.py --sort-faces instagram_downloads

  → 각 계정 폴더 안에 single_face / multi_face / no_face 폴더로 분류
  → 1명 / 2명 이상 / 얼굴 없음
  → 원본은 삭제하지 않고 분류만 합니다.

옵션 공통:
  --login 내아이디       : 로그인해서 실행 (429 차단 / 팔로잉 명단에 필요)
                           처음 한 번만 비밀번호 입력, 이후 세션 파일 재사용
                           예) python instagram_downloader.py --from-file list.txt --max 30 --login 내아이디
  (기본) 이미지/썸네일만 다운로드 (동영상 안 받음)
  --video / --with-video : 동영상도 함께 다운로드하고 싶을 때
  --max N                : 계정당 최대 N개만 (기본: 전체)
  재다운로드 시: 최신부터 받아서 이미 있는 게시물 만나면 자동 중단 (중복 없음)
"""

import sys
import os
import re
import time
import shutil
from pathlib import Path

try:
    import instaloader
except ImportError:
    print("❌ instaloader가 설치되어 있지 않습니다.")
    print("   설치 명령: pip install instaloader")
    sys.exit(1)


LOGIN_USER = None  # --login 아이디 로 지정하면 로그인 상태로 동작


def apply_login(L: instaloader.Instaloader) -> None:
    """저장된 세션 파일을 불러오고, 없으면 비밀번호를 물어 로그인 후 세션 저장"""
    if not LOGIN_USER:
        return
    try:
        L.load_session_from_file(LOGIN_USER)
        print(f"🔑 저장된 세션으로 로그인됨: @{LOGIN_USER}")
        return
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"⚠ 저장된 세션을 쓸 수 없어 다시 로그인합니다: {e}")

    try:
        L.interactive_login(LOGIN_USER)  # 비밀번호(및 2단계 인증 코드) 입력창
        L.save_session_to_file()
        print(f"🔑 로그인 성공, 세션 저장됨: @{LOGIN_USER} (다음부터는 비밀번호 불필요)")
    except Exception as e:
        print(f"❌ 로그인 실패: {e}")
        sys.exit(1)


def create_loader(photo_only: bool = True) -> instaloader.Instaloader:
    """Instaloader 인스턴스 생성 (기본: 이미지/썸네일만 다운로드)"""
    L = instaloader.Instaloader(
        download_videos=not photo_only,          # 기본 False → 동영상 안 받음
        download_video_thumbnails=photo_only,    # 기본 True  → 썸네일(커버) 받음
        download_geotags=False,
        download_comments=False,
        save_metadata=True,
        compress_json=False,
        post_metadata_txt_pattern="",
        max_connection_attempts=3,
        filename_pattern="{date_utc:%Y%m%d_%H%M%S}_{shortcode}",
    )
    L.context.log = lambda *args, **kwargs: None
    apply_login(L)
    return L


def extract_shortcode(url_or_code: str) -> str | None:
    """URL 또는 shortcode에서 shortcode를 추출"""
    url_or_code = url_or_code.strip()

    if re.fullmatch(r"[A-Za-z0-9_-]{5,20}", url_or_code):
        return url_or_code

    patterns = [
        r"instagram\.com/p/([A-Za-z0-9_-]+)",
        r"instagram\.com/reel/([A-Za-z0-9_-]+)",
        r"instagram\.com/tv/([A-Za-z0-9_-]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, url_or_code)
        if match:
            return match.group(1)
    return None


def already_downloaded(target_dir: str, shortcode: str) -> bool:
    """해당 shortcode로 된 파일이 이미 있으면 True (중복 방지)"""
    if not os.path.isdir(target_dir):
        return False
    for fname in os.listdir(target_dir):
        if shortcode in fname:
            return True
    # 분류 폴더 안도 검사
    for sub in ("single_face", "multi_face", "no_face", "with_face"):
        subdir = os.path.join(target_dir, sub)
        if os.path.isdir(subdir):
            for fname in os.listdir(subdir):
                if shortcode in fname:
                    return True
    return False


def download_post(L: instaloader.Instaloader, shortcode: str, base_dir: str) -> bool:
    """단일 게시물 다운로드 (중복 방지)"""
    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        username = post.owner_username
        target_dir = os.path.join(base_dir, username)

        if already_downloaded(target_dir, shortcode):
            print(f"⏭ 이미 다운로드됨 → @{username} / {shortcode} (건너뜀)\n")
            return True

        caption_preview = (post.caption[:50] + '...') if post.caption and len(post.caption) > 50 else (post.caption or '(캡션 없음)')
        print(f"📥 @{username} - {caption_preview}")

        if post.typename == 'GraphSidecar':
            type_str = '캐러셀'
        elif post.typename == 'GraphImage':
            type_str = '사진'
        else:
            type_str = '영상/릴스'

        print(f"   타입: {type_str} | 좋아요: {post.likes:,} | 댓글: {post.comments:,}")

        L.download_post(post, target=target_dir)
        print(f"✅ 저장됨 → {target_dir}/\n")
        return True

    except instaloader.exceptions.PrivateProfileNotFollowedException:
        print(f"❌ 비공개 계정입니다.\n")
        return False
    except Exception as e:
        print(f"❌ 오류: {e}\n")
        return False


def get_following_list(username: str) -> list[str]:
    """공개 계정의 팔로잉 명단 가져오기"""
    L = create_loader()
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        can_view = (not profile.is_private) or profile.followed_by_viewer or LOGIN_USER == username
        if not can_view:
            print(f"❌ @{username} 은(는) 비공개 계정입니다. 팔로잉 목록을 볼 수 없습니다.")
            return []
        if not LOGIN_USER:
            print("⚠ 로그인 없이는 팔로잉 목록을 가져오지 못할 수 있습니다. --login 아이디 를 붙여 보세요.")

        print(f"📋 @{username} 의 팔로잉 목록을 가져오는 중... (시간이 걸릴 수 있습니다)")
        followees = []
        for i, followee in enumerate(profile.get_followees(), 1):
            followees.append(followee.username)
            if i % 50 == 0:
                print(f"   ... {i}명 수집 중")
                time.sleep(1)

        print(f"✅ 총 {len(followees)}명 수집 완료\n")
        return followees

    except instaloader.exceptions.ProfileNotExistsException:
        print(f"❌ @{username} 계정을 찾을 수 없습니다.")
        return []
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        print("   (Instagram이 요청을 차단했을 수 있습니다. 잠시 후 다시 시도해 보세요.)")
        return []


def download_profile_posts(username: str, max_count: int | None = None, photo_only: bool = True, base_dir: str = "instagram_downloads") -> bool:
    """특정 계정의 게시물 다운로드 (최신부터, 이미 받은 게시물 만나면 중단)"""
    L = create_loader(photo_only)
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        if profile.is_private:
            print(f"❌ @{username} 은(는) 비공개 계정 → 건너뜀")
            return False

        target_dir = os.path.join(base_dir, username)
        total = profile.mediacount
        if max_count is None:
            print(f"📥 @{username} 전체 게시물 다운로드 중... (총 {total}개)")
        else:
            print(f"📥 @{username} 최근 {max_count}개 다운로드 중... (총 {total}개)")

        # .complete 표시 파일: 전체 다운로드를 끝까지 마친 계정에만 생성됨
        #  - 표시 있음: 이후 업데이트 → 이미 받은 게시물을 만나면 중단 (새 글만 받음)
        #  - 표시 없음: 중간에 끊겼거나 --max로 일부만 받은 상태 → 받은 건 건너뛰고 끝까지 계속
        os.makedirs(target_dir, exist_ok=True)
        marker = os.path.join(target_dir, ".complete")
        incremental = os.path.exists(marker)

        count = 0          # 새로 받은 개수
        skipped = 0        # 이미 있어서 건너뛴 개수
        stopped_early = False
        finished = True    # 끝까지 다 돌았는가
        for post in profile.get_posts():  # 최신 → 오래된 순
            if already_downloaded(target_dir, post.shortcode):
                if incremental:
                    print(f"   ⏭ 이미 있음 → {post.shortcode} (이전 다운로드 지점 도달, 중단)")
                    stopped_early = True
                    break
                skipped += 1
                continue

            L.download_post(post, target=target_dir)
            count += 1
            limit_str = f"/{max_count}" if max_count else f"/{total}"
            print(f"   [{count}{limit_str}] {post.shortcode} 저장됨")

            if max_count is not None and count >= max_count:
                finished = False
                break

        if finished and max_count is None:
            Path(marker).touch()

        msg = f"✅ @{username} 완료 → {target_dir}/"
        if count == 0 and (stopped_early or skipped):
            msg += " (새로 받을 게시물 없음)"
        elif count > 0:
            msg += f" (새로 {count}개 저장)"
            if stopped_early:
                msg += " · 이전 지점에서 중단"
        if skipped:
            msg += f" · 기존 {skipped}개 건너뜀"
        print(msg + "\n")
        return True

    except Exception as e:
        print(f"❌ @{username} 오류: {e}\n")
        return False


def count_faces(image_path: str) -> int:
    """MediaPipe로 얼굴 개수를 반환. 실패 시 0"""
    try:
        import mediapipe as mp
        import cv2
    except ImportError:
        print("❌ 얼굴 분류를 위해 mediapipe와 opencv가 필요합니다.")
        print("   설치 명령: pip install mediapipe opencv-python-headless")
        sys.exit(1)

    try:
        mp_face_detection = mp.solutions.face_detection

        with mp_face_detection.FaceDetection(
            model_selection=1,  # 1: 원거리도 잘 잡음 (여러 사람 사진에 유리)
            min_detection_confidence=0.5
        ) as face_detection:

            img = cv2.imread(image_path)
            if img is None:
                return 0

            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            results = face_detection.process(rgb)

            if results.detections is None:
                return 0
            return len(results.detections)

    except Exception as e:
        print(f"   ⚠ 얼굴 검사 실패 ({os.path.basename(image_path)}): {e}")
        return 0


def sort_faces(base_dir: str = "instagram_downloads"):
    """다운로드된 사진들을 single_face / multi_face / no_face 폴더로 분류 (삭제하지 않음)"""
    base_path = Path(base_dir)
    if not base_path.exists():
        print(f"❌ 폴더를 찾을 수 없습니다: {base_dir}")
        return

    image_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    total_single = 0
    total_multi = 0
    total_without = 0
    total_skipped = 0

    print(f"🔍 얼굴 분류 시작: {base_dir}")
    print("   (1명 / 2명 이상 / 얼굴 없음 으로 분류, 원본 삭제 안 함)\n")

    skip_dirs = {"single_face", "multi_face", "no_face", "with_face"}  # with_face는 예전 폴더명

    for account_dir in sorted(base_path.iterdir()):
        if not account_dir.is_dir():
            continue
        if account_dir.name in skip_dirs:
            continue

        images = [
            f for f in account_dir.iterdir()
            if f.is_file() and f.suffix.lower() in image_exts
            and not f.name.startswith(".")
        ]

        if not images:
            continue

        single_dir = account_dir / "single_face"
        multi_dir = account_dir / "multi_face"
        no_face_dir = account_dir / "no_face"
        single_dir.mkdir(exist_ok=True)
        multi_dir.mkdir(exist_ok=True)
        no_face_dir.mkdir(exist_ok=True)

        print(f"📂 @{account_dir.name} ({len(images)}장 검사 중...)")

        for img_path in images:
            try:
                n = count_faces(str(img_path))
                if n == 0:
                    dest = no_face_dir / img_path.name
                    shutil.move(str(img_path), str(dest))
                    total_without += 1
                    print(f"   ⬜ 얼굴 없음 → no_face/{img_path.name}")
                elif n == 1:
                    dest = single_dir / img_path.name
                    shutil.move(str(img_path), str(dest))
                    total_single += 1
                    print(f"   ✅ 1명 → single_face/{img_path.name}")
                else:
                    dest = multi_dir / img_path.name
                    shutil.move(str(img_path), str(dest))
                    total_multi += 1
                    print(f"   👥 {n}명 → multi_face/{img_path.name}")
            except Exception as e:
                print(f"   ⚠ 건너뜀 {img_path.name}: {e}")
                total_skipped += 1

        print()

    print("=" * 40)
    print(f"분류 완료!")
    print(f"  1명 사진       : {total_single}장  → single_face/")
    print(f"  2명 이상 사진  : {total_multi}장  → multi_face/")
    print(f"  얼굴 없는 사진 : {total_without}장  → no_face/")
    if total_skipped:
        print(f"  건너뛴 파일   : {total_skipped}개")
    print(f"\n결과 위치: {os.path.abspath(base_dir)}/계정명/single_face · multi_face · no_face")


def main():
    global LOGIN_USER
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    # 옵션 파싱
    photo_only = True          # 기본: 이미지/썸네일만 다운로드
    max_count = None           # 기본: 전체 게시물
    mode = None
    target = None
    urls = []
    sort_dir = "instagram_downloads"

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-p", "--photo-only"):
            photo_only = True
        elif arg in ("--video", "--with-video"):
            photo_only = False      # 동영상을 받고 싶을 때만 사용
        elif arg == "--login" and i + 1 < len(args):
            LOGIN_USER = args[i + 1]
            i += 1
        elif arg == "--max" and i + 1 < len(args):
            try:
                max_count = int(args[i + 1])
                i += 1
            except ValueError:
                print("❌ --max 뒤에는 숫자를 입력하세요.")
                sys.exit(1)
        elif arg == "--following" and i + 1 < len(args):
            mode = "following"
            target = args[i + 1]
            i += 1
        elif arg == "--profile" and i + 1 < len(args):
            mode = "profile"
            target = args[i + 1]
            i += 1
        elif arg == "--from-file" and i + 1 < len(args):
            mode = "from_file"
            target = args[i + 1]
            i += 1
        elif arg == "--sort-faces":
            mode = "sort_faces"
            # 다음 인자가 폴더 경로일 수 있음
            if i + 1 < len(args) and not args[i + 1].startswith("-"):
                sort_dir = args[i + 1]
                i += 1
        else:
            urls.append(arg)
        i += 1

    base_dir = "instagram_downloads"
    Path(base_dir).mkdir(exist_ok=True)

    # ---------- 모드별 실행 ----------
    if mode == "following":
        followees = get_following_list(target)
        if not followees:
            sys.exit(1)

        filename = f"following_{target}.txt"
        added = []
        if os.path.exists(filename):
            # 최신화: 기존 줄(# 제외 표시 포함)은 그대로 두고, 새로 팔로우한 계정만 아래에 추가
            with open(filename, "r", encoding="utf-8") as f:
                old_lines = f.read().splitlines()
            known = {l.strip().lstrip("#").strip().lower() for l in old_lines if l.strip()}
            added = [n for n in followees if n.lower() not in known]
            current = {n.lower() for n in followees}
            unfollowed = [l.strip() for l in old_lines
                          if l.strip() and not l.strip().startswith("#")
                          and l.strip().lower() not in current]
            with open(filename, "a", encoding="utf-8") as f:
                if added:
                    f.write(f"# ---- 새로 추가된 계정 ({time.strftime('%Y-%m-%d')}) ----\n")
                    for name in added:
                        f.write(name + "\n")
            print(f"📄 팔로잉 명단 최신화 완료: {filename}")
            print(f"   새로 추가 {len(added)}명 / 현재 팔로잉 {len(followees)}명")
            if unfollowed:
                print(f"   ⚠ 이제 팔로우하지 않는 계정 {len(unfollowed)}명 (파일에는 그대로 남겨 둠): {', '.join(unfollowed[:10])}"
                      + (" ..." if len(unfollowed) > 10 else ""))
        else:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"# @{target} 의 팔로잉 목록\n")
                f.write("# 다운로드 하기 싫은 계정은 앞에 # 을 붙여주세요. 예: #username\n")
                f.write("# ------------------------------------------------\n")
                for name in followees:
                    f.write(name + "\n")
            print(f"📄 팔로잉 명단 저장 완료: {filename}")
            print(f"   총 {len(followees)}명")
        print()
        print("💡 다운로드 안 할 계정이 있으면 파일을 열어서 해당 줄 앞에 # 을 붙이세요.")
        print("   예: #annoying_user")
        print()
        print("다음 단계 예시:")
        print(f"  python instagram_downloader.py --from-file {filename}          # 기본 전체")
        print(f"  python instagram_downloader.py --from-file {filename} --max 30  # 최근 30개만")
        print(f"  python instagram_downloader.py --from-file {filename} --video  # 동영상 포함")
        return

    if mode == "profile":
        if not photo_only:
            print("🎬 동영상 포함 모드 활성화\n")
        else:
            print("📷 이미지/썸네일만 다운로드합니다 (동영상 제외)\n")
        download_profile_posts(target, max_count=max_count, photo_only=photo_only, base_dir=base_dir)
        return

    if mode == "from_file":
        if not os.path.exists(target):
            print(f"❌ 파일을 찾을 수 없습니다: {target}")
            sys.exit(1)

        with open(target, "r", encoding="utf-8") as f:
            all_lines = [line.strip() for line in f if line.strip()]
            usernames = [line for line in all_lines if not line.startswith("#")]
            excluded = len(all_lines) - len(usernames)

        if not usernames:
            print("❌ 파일에 유효한 아이디가 없습니다. (# 주석 처리된 계정만 있는 경우일 수 있습니다)")
            sys.exit(1)

        print(f"📂 {target} 에서 {len(usernames)}명 로드됨", end="")
        if excluded:
            print(f" (제외된 계정 {excluded}명)")
        else:
            print()
        if max_count:
            print(f"   계정당 최대 {max_count}개씩 다운로드합니다.\n")
        else:
            print(f"   계정당 전체 게시물을 다운로드합니다.\n")
        if not photo_only:
            print("🎬 동영상 포함 모드 활성화\n")
        else:
            print("📷 이미지/썸네일만 다운로드합니다 (동영상 제외)\n")

        success = 0
        fail = 0
        for idx, username in enumerate(usernames, 1):
            print(f"[{idx}/{len(usernames)}] ", end="")
            if download_profile_posts(username, max_count=max_count, photo_only=photo_only, base_dir=base_dir):
                success += 1
            else:
                fail += 1
            if idx < len(usernames):
                time.sleep(2)

        print("=" * 40)
        print(f"총 {len(usernames)}명 중 성공 {success}명 / 실패 {fail}명")
        print(f"저장 위치: {os.path.abspath(base_dir)}/")
        return

    if mode == "sort_faces":
        sort_faces(sort_dir)
        return

    # ---------- 기본: 게시물 URL/shortcode 다운로드 ----------
    if not urls:
        print("❌ URL 또는 옵션을 입력해 주세요. --help 로 사용법을 확인하세요.")
        sys.exit(1)

    if not photo_only:
        print("🎬 동영상 포함 모드로 다운로드합니다.\n")
    else:
        print("📷 이미지/썸네일만 다운로드합니다 (동영상 제외)\n")

    L = create_loader(photo_only)
    success = 0
    fail = 0

    for arg in urls:
        shortcode = extract_shortcode(arg)
        if not shortcode:
            print(f"❌ 유효하지 않은 URL/코드: {arg}")
            fail += 1
            continue

        print(f"🔍 shortcode: {shortcode}")
        if download_post(L, shortcode, base_dir):
            success += 1
        else:
            fail += 1

    print("=" * 40)
    print(f"총 {success + fail}개 중 성공 {success}개 / 실패 {fail}개")
    if success:
        print(f"저장 위치: {os.path.abspath(base_dir)}/ (계정별 폴더로 정리됨)")


if __name__ == "__main__":
    main()
