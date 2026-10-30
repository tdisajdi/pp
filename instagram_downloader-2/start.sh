#!/usr/bin/env bash
# Instagram downloader for Android (Termux).  Run:  bash start.sh
# Same logic as START.bat. Settings can be changed below or per run, for example:
#   MAX_RUN=10 USE_LOGIN=0 bash start.sh
cd "$(dirname "$0")" || exit 1

# ============ settings ============
USE_LOGIN=${USE_LOGIN:-1}                          # 0 = no login at all. Public accounts only.
LIST=${LIST:-following_camel.3873048.txt}
COOKIES=${COOKIES:-cookies.txt}                    # if this file is missing, runs without login
UPDATE_FOLLOWING=${UPDATE_FOLLOWING:-0}            # needs cookies.txt
TARGET=${TARGET:-camel.3873048}
UPDATE_FROM_SAVED=${UPDATE_FROM_SAVED:-0}          # needs cookies.txt
SAVED_RANGE=${SAVED_RANGE:-}
SLEEP_REQUEST=${SLEEP_REQUEST:-25-50}              # seconds between Instagram requests
BETWEEN_MIN=${BETWEEN_MIN:-45}                     # random rest after each account
BETWEEN_MAX=${BETWEEN_MAX:-120}
POSTS_PER_ACCOUNT=${POSTS_PER_ACCOUNT:-5}          # newest N posts per account. 0 = all posts
MAX_RUN=${MAX_RUN:-30}                             # accounts really downloaded per run. 0 = no limit
MAX_ACCOUNTS=${MAX_ACCOUNTS:-0}                    # only the first N accounts of the list. 0 = all
MAX_RETRY=${MAX_RETRY:-5}
RETRY_WAIT=${RETRY_WAIT:-180}
MAX_CONSEC_FAIL=${MAX_CONSEC_FAIL:-3}
DONE_MODE=${DONE_MODE:-skip}                       # skip / new / all
NEW_CHECK=${NEW_CHECK:-10}
OUT_DIR=${OUT_DIR:-instagram_downloads}            # e.g. $HOME/storage/shared/Download/instagram_downloads
# ==================================

echo
echo "========================================"
echo "  START : download posts (Android / Termux)"
echo "========================================"
echo "  use login    : $USE_LOGIN  (1=yes, 0=no login at all)"
echo "  list file    : $LIST"
echo "  posts/account: $POSTS_PER_ACCOUNT  (0 = all posts)"
echo "  request delay: $SLEEP_REQUEST sec"
echo "  account delay: $BETWEEN_MIN-$BETWEEN_MAX sec random"
echo "  max per run  : $MAX_RUN accounts (0 = no limit)"
echo "  done accounts: $DONE_MODE"
echo "  save to      : $OUT_DIR/instagram/"
echo "========================================"
echo

# ---------- python and gallery-dl ----------
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY=$c; break; fi
done
if [ -z "$PY" ] && command -v pkg >/dev/null 2>&1; then
  echo "Python not found. Installing with pkg ..."
  pkg install -y python && PY=python
fi
if [ -z "$PY" ]; then
  echo "[ERROR] Python is not installed. In Termux run:  pkg install python"
  exit 1
fi
if ! "$PY" -c "import gallery_dl" >/dev/null 2>&1; then
  echo "gallery-dl not found. Installing ..."
  "$PY" -m pip install -U gallery-dl || { echo "[ERROR] Failed to install gallery-dl."; exit 1; }
fi

# keep the phone awake while running, release when done
if command -v termux-wake-lock >/dev/null 2>&1; then
  termux-wake-lock
  trap 'termux-wake-unlock 2>/dev/null' EXIT
fi

# ---------- login source ----------
AUTH=()
if [ "$USE_LOGIN" = "1" ] && [ -f "$COOKIES" ]; then
  AUTH=(--cookies "$COOKIES")
  echo "Login source: $COOKIES"
else
  if [ "$USE_LOGIN" = "1" ]; then
    echo "No $COOKIES found, so this run uses NO login. Public accounts only."
  else
    echo "Login source: none, no login is used."
  fi
  UPDATE_FOLLOWING=0
  UPDATE_FROM_SAVED=0
fi

# ---------- optional list refresh ----------
if [ "$UPDATE_FOLLOWING" = "1" ]; then
  echo
  echo "Refreshing the following list of $TARGET ..."
  "$PY" -m gallery_dl "${AUTH[@]}" --sleep-request "$SLEEP_REQUEST" -g "https://www.instagram.com/$TARGET/following/" > following_raw.txt
  "$PY" merge_following.py "$LIST" following_raw.txt "$TARGET" || echo "[WARNING] Could not refresh the list. Continuing with the current list file."
fi
if [ "$UPDATE_FROM_SAVED" = "1" ]; then
  echo
  echo "Adding accounts from the saved posts of $TARGET ..."
  RANGE_OPT=()
  [ -n "$SAVED_RANGE" ] && RANGE_OPT=(--range "$SAVED_RANGE")
  "$PY" -m gallery_dl "${AUTH[@]}" --sleep-request "$SLEEP_REQUEST" "${RANGE_OPT[@]}" -N "{username}" "https://www.instagram.com/$TARGET/saved/" > saved_raw.txt
  "$PY" merge_following.py "$LIST" saved_raw.txt "$TARGET" saved || echo "[WARNING] Could not read saved posts. Continuing with the current list file."
fi

if [ ! -f "$LIST" ]; then
  echo
  echo "[ERROR] List file not found: $LIST"
  echo "Put it in the same folder as start.sh."
  exit 1
fi

N=0; SUCCESS=0; FAIL=0; CONSEC=0; SKIPPED=0; RUNCOUNT=0; RAN=1

between_pause() {
  local wait=$(( BETWEEN_MIN + RANDOM % (BETWEEN_MAX - BETWEEN_MIN + 1) ))
  echo "  resting $wait sec before the next account ..."
  sleep "$wait"
}

# download one account, resume until finished
do_account() {
  local user=$1 include="posts,reels" mark=".done" try=0 err
  local dir="$OUT_DIR/instagram/$user"
  local extra=()
  if [ "$POSTS_PER_ACCOUNT" != "0" ]; then
    mark=".done_$POSTS_PER_ACCOUNT"
    extra=(--post-range "1-$POSTS_PER_ACCOUNT")
    include="posts"
  fi
  if [ -e "$dir/.done" ] || [ -e "$dir/$mark" ]; then
    if [ "$DONE_MODE" = "skip" ]; then
      echo "  [already complete - skipped]"
      SKIPPED=$((SKIPPED + 1)); RAN=0
      return 0
    fi
    [ "$DONE_MODE" = "new" ] && extra+=(-A "$NEW_CHECK")
  fi
  while :; do
    try=$((try + 1))
    "$PY" -m gallery_dl "${AUTH[@]}" --download-archive gallery_dl_archive.sqlite3 \
      --sleep-request "$SLEEP_REQUEST" "${extra[@]}" -o "include=$include" \
      -o videos=false -o previews=video -d "$OUT_DIR" "https://www.instagram.com/$user/" < /dev/null
    err=$?
    if [ "$err" -eq 0 ]; then
      echo "  [account finished]"
      SUCCESS=$((SUCCESS + 1)); CONSEC=0
      [ -d "$dir" ] && : > "$dir/$mark"
      return 0
    fi
    if [ $((err & 16)) -ne 0 ] || [ $((err & 64)) -ne 0 ]; then
      echo "  [skipped: account not found or nothing to download]"
      FAIL=$((FAIL + 1))
      return 0
    fi
    if [ "$try" -ge "$MAX_RETRY" ]; then
      echo "  [gave up after $MAX_RETRY attempts - run this again later]"
      FAIL=$((FAIL + 1)); CONSEC=$((CONSEC + 1))
      return 0
    fi
    echo "  [attempt $try of $MAX_RETRY stopped midway] waiting $RETRY_WAIT sec, then resuming the same account"
    sleep "$RETRY_WAIT"
  done
}

echo
echo "Starting download. You can stop with Ctrl+C and run again to resume."

while IFS= read -r -u 3 line || [ -n "$line" ]; do
  user=$(printf '%s' "$line" | tr -d '[:space:]')
  case "$user" in ''|\#*) continue ;; esac
  if [ "$MAX_ACCOUNTS" -gt 0 ] && [ "$N" -ge "$MAX_ACCOUNTS" ]; then break; fi
  if [ "$MAX_RUN" -gt 0 ] && [ "$RUNCOUNT" -ge "$MAX_RUN" ]; then
    echo
    echo "========================================"
    echo " Reached MAX_RUN=$MAX_RUN accounts for this run. This is on purpose, to stay gentle."
    echo " Run this again later. Finished accounts are skipped, so it continues with the next ones."
    echo "========================================"
    break
  fi
  N=$((N + 1))
  echo
  echo "----------------------------------------"
  echo "[$N] $user"
  echo "----------------------------------------"
  RAN=1
  do_account "$user"
  if [ "$CONSEC" -ge "$MAX_CONSEC_FAIL" ]; then
    echo
    echo "========================================"
    echo " [STOPPED] $MAX_CONSEC_FAIL accounts in a row failed."
    echo " Instagram is probably rejecting the login session or blocking this network."
    echo " - Wait a few hours, then run this again. Finished work is kept."
    echo " - Switch to another Wi-Fi network, or refresh cookies.txt."
    echo "========================================"
    break
  fi
  if [ "$RAN" = "1" ]; then
    RUNCOUNT=$((RUNCOUNT + 1))
    between_pause
  fi
done 3< "$LIST"

echo
echo "========================================"
echo " Done"
echo " accounts tried : $N"
echo " completed      : $SUCCESS"
echo " already done   : $SKIPPED"
echo " gave up/skipped: $FAIL"
echo " saved to       : $(pwd)/$OUT_DIR/instagram/"
echo "========================================"
echo " Run this again any time to resume and continue with the next accounts."
