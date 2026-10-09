@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem ============ settings ============
set USE_LOGIN=1
set BROWSER=firefox
set LIST=following_lilillliilu.txt
set COOKIES=cookies.txt
set UPDATE_FOLLOWING=0
set TARGET=lilillliilu
set UPDATE_FROM_SAVED=0
set SAVED_RANGE=
set SLEEP_REQUEST=25-50
set BETWEEN_MIN=45
set BETWEEN_MAX=120
set MAX_RUN=10
set MAX_ACCOUNTS=0
set MAX_RETRY=5
set RETRY_WAIT=180
set MAX_CONSEC_FAIL=3
set DONE_MODE=skip
set NEW_CHECK=10
rem USE_LOGIN=0 downloads WITHOUT any login. Your account is not touched at all.
rem   The list file is used as it is. Following and saved refresh are skipped. Public accounts only.
rem   Without login Instagram limits requests sooner, so use small batches: MAX_ACCOUNTS=5.
rem UPDATE_FOLLOWING=1 refreshes the following list of TARGET before downloading. 0 skips it.
rem It uses the same browser cookies as the download, so no password is needed.
rem UPDATE_FROM_SAVED=1 also adds the owners of your SAVED posts to the list. These accounts
rem are downloaded even if you do not follow them, as long as they are public.
rem SAVED_RANGE limits how many saved posts are scanned, for example 1-300. Empty means all.
rem GENTLE SETTINGS to avoid blocks:
rem   SLEEP_REQUEST = seconds to wait between Instagram requests. Bigger is safer.
rem   BETWEEN_MIN / BETWEEN_MAX = random pause in seconds after each account.
rem   MAX_RUN = stop after this many accounts were really downloaded in one run. 0 means no limit.
rem     Accounts marked complete do not count, so each new run continues with the next accounts.
rem MAX_ACCOUNTS=0 means all accounts. A number means only the first N accounts.
rem BROWSER can be firefox, chrome or edge. Chrome and Edge often fail to decrypt cookies.
rem If a cookies.txt file exists in this folder it is used instead of the browser.
rem Photos are saved. Videos are not, but reels and video posts are saved as their cover image.
rem MAX_RETRY = how many times to resume the SAME account when it stops midway.
rem RETRY_WAIT = seconds to wait before resuming the same account.
rem DONE_MODE decides what happens to accounts that were already downloaded to the end:
rem   skip = do not touch them at all. all = scan everything again.
rem   new  = only look for new posts, stopping after NEW_CHECK known files in a row.
rem An account is marked as complete only when a run finishes without errors.
rem The mark is a hidden file named .done inside the account folder. Delete it to force a rescan.
rem MAX_CONSEC_FAIL = stop the whole run after this many accounts in a row gave up.
rem   This protects your account when Instagram rejects the login session.
rem ==================================

echo.
echo ========================================
echo   START : refresh following list, then download posts and reels
echo ========================================
echo   use login    : %USE_LOGIN%  1=yes 0=no login at all
echo   browser      : %BROWSER%
echo   cookies file : %COOKIES% - used first if the file exists
echo   list file    : %LIST%
echo   update list  : %UPDATE_FOLLOWING%  1=yes 0=no  target=%TARGET%
echo   add saved    : %UPDATE_FROM_SAVED%  1=yes 0=no
echo   request delay: %SLEEP_REQUEST% sec
echo   account delay: %BETWEEN_MIN%-%BETWEEN_MAX% sec random
echo   max per run  : %MAX_RUN% accounts, 0 means no limit
echo   done accounts: %DONE_MODE%  skip / new / all
echo   retry        : up to %MAX_RETRY% times per account, %RETRY_WAIT% sec apart
if %MAX_ACCOUNTS% GTR 0 (echo   max accounts : %MAX_ACCOUNTS%) else (echo   max accounts : all)
echo ========================================
echo.
echo  Before you start:
echo  1. USE_LOGIN=1 needs a login: %BROWSER% logged in to instagram.com, or cookies.txt here.
echo  2. Close %BROWSER% completely. Check Task Manager: no %BROWSER% processes.
echo  3. Already downloaded posts are skipped automatically.
echo.
pause

rem ---------- find python ----------
set PY=
where python >nul 2>nul
if not errorlevel 1 set PY=python
if "%PY%"=="" (
  where py >nul 2>nul
  if not errorlevel 1 set PY=py
)
if "%PY%"=="" (
  echo.
  echo [ERROR] Python is not installed.
  echo  1. Install Python from https://www.python.org/downloads/
  echo  2. Check "Add python.exe to PATH" during setup.
  echo  3. Run this file again.
  echo.
  pause
  exit /b 1
)

rem ---------- install gallery-dl if missing ----------
%PY% -m pip show gallery-dl >nul 2>nul
if errorlevel 1 (
  echo gallery-dl not found. Installing...
  %PY% -m pip install -U gallery-dl
  if errorlevel 1 (
    echo.
    echo [ERROR] Failed to install gallery-dl. Check your internet connection.
    pause
    exit /b 1
  )
)

set AUTH=--cookies-from-browser %BROWSER%
if exist "%COOKIES%" set AUTH=--cookies "%COOKIES%"
if "%USE_LOGIN%"=="0" set AUTH=
if "%USE_LOGIN%"=="0" set UPDATE_FOLLOWING=0
if "%USE_LOGIN%"=="0" set UPDATE_FROM_SAVED=0
if "%USE_LOGIN%"=="0" (echo Login source: none - no login is used) else (echo Login source: %AUTH%)

rem ---------- refresh the following list ----------
if "%UPDATE_FOLLOWING%"=="1" (
  echo.
  echo Refreshing the following list of %TARGET% ...
  %PY% -m gallery_dl %AUTH% --sleep-request %SLEEP_REQUEST% -g "https://www.instagram.com/%TARGET%/following/" > following_raw.txt
  %PY% merge_following.py "%LIST%" following_raw.txt %TARGET%
  if errorlevel 1 echo [WARNING] Could not refresh the list. Continuing with the current list file.
)

rem ---------- add owners of saved posts ----------
if "%UPDATE_FROM_SAVED%"=="1" (
  echo.
  echo Adding accounts from the saved posts of %TARGET% ...
  set RANGE_OPT=
  if not "%SAVED_RANGE%"=="" set RANGE_OPT=--range %SAVED_RANGE%
  %PY% -m gallery_dl %AUTH% --sleep-request %SLEEP_REQUEST% !RANGE_OPT! -N "{username}" "https://www.instagram.com/%TARGET%/saved/" > saved_raw.txt
  %PY% merge_following.py "%LIST%" saved_raw.txt %TARGET% saved
  if errorlevel 1 echo [WARNING] Could not read saved posts. Continuing with the current list file.
)

if not exist "%LIST%" (
  echo.
  echo [ERROR] List file not found: %LIST%
  echo Put it in the same folder as this file.
  pause
  exit /b 1
)

echo.
echo Starting download. You can stop any time and run again to resume.
echo.

set /a N=0
set /a SUCCESS=0
set /a FAIL=0
set /a CONSEC=0
set /a SKIPPED=0
set /a RUNCOUNT=0

for /f "usebackq eol=# tokens=*" %%u in ("%LIST%") do (
  if %MAX_ACCOUNTS% GTR 0 if !N! GEQ %MAX_ACCOUNTS% goto :finish
  if %MAX_RUN% GTR 0 if !RUNCOUNT! GEQ %MAX_RUN% goto :runlimit
  set /a N+=1
  echo.
  echo ----------------------------------------
  echo [!N!] %%u
  echo ----------------------------------------
  set RAN=1
  call :do_account %%u
  if !CONSEC! GEQ %MAX_CONSEC_FAIL% goto :abort
  if "!RAN!"=="1" set /a RUNCOUNT+=1
  if "!RAN!"=="1" call :between_pause
)

:finish
echo.
echo ========================================
echo  Done
echo  accounts tried : !N!
echo  completed      : !SUCCESS!
echo  already done   : !SKIPPED!
echo  gave up/skipped: !FAIL!
echo  saved to       : %cd%\instagram_downloads\instagram\
echo ========================================
echo  Run this file again any time to resume and fetch new posts.
echo  Face sorting is separate. Run sort_faces.bat yourself when downloading is done.
echo.
pause
exit /b 0

rem ---------- download one account, resume until finished ----------
:do_account
set EXTRA=
set DONEDIR=instagram_downloads\instagram\%~1
if not exist "%DONEDIR%\.done" goto :start_try
if "%DONE_MODE%"=="skip" goto :already_done
if "%DONE_MODE%"=="new" set EXTRA=-A %NEW_CHECK%
:start_try
set TRY=0
:retry
set /a TRY+=1
%PY% -m gallery_dl %AUTH% --download-archive gallery_dl_archive.sqlite3 --sleep-request %SLEEP_REQUEST% %EXTRA% -o include=posts,reels -o videos=false -o previews=video -d instagram_downloads "https://www.instagram.com/%~1/"
set ERR=!errorlevel!
if "!ERR!"=="0" goto :acct_ok
set /a "NOTFOUND=ERR & 16"
set /a "NOFILES=ERR & 64"
if not "!NOTFOUND!"=="0" goto :acct_skip
if not "!NOFILES!"=="0" goto :acct_skip
if !TRY! GEQ %MAX_RETRY% goto :acct_fail
echo   [attempt !TRY! of %MAX_RETRY% stopped midway] waiting %RETRY_WAIT% sec, then resuming the same account
timeout /t %RETRY_WAIT% /nobreak >nul
goto :retry

:acct_ok
echo   [account finished]
set /a SUCCESS+=1
if exist "%DONEDIR%\" type nul > "%DONEDIR%\.done"
set /a CONSEC=0
exit /b 0

:already_done
echo   [already complete - skipped]
set /a SKIPPED+=1
set RAN=0
exit /b 0

:acct_skip
echo   [skipped: account not found or nothing to download]
set /a FAIL+=1
exit /b 0

:acct_fail
echo   [gave up after %MAX_RETRY% attempts - run this file again later]
set /a FAIL+=1
set /a CONSEC+=1
exit /b 0

:abort
echo.
echo ========================================
echo  [STOPPED] %MAX_CONSEC_FAIL% accounts in a row failed.
echo  Instagram is probably rejecting the login session or blocking this network.
echo  - Open instagram.com in %BROWSER% and check for a security prompt.
echo  - Wait a few hours, then run this file again. Finished work is kept.
echo  - Try a phone hotspot, or log in again in %BROWSER% to refresh the cookies.
echo ========================================
goto :finish

:between_pause
set /a "WAIT=BETWEEN_MIN + RANDOM %% (BETWEEN_MAX - BETWEEN_MIN + 1)"
echo   resting !WAIT! sec before the next account ...
timeout /t !WAIT! /nobreak >nul
exit /b 0

:runlimit
echo.
echo ========================================
echo  Reached MAX_RUN=%MAX_RUN% accounts for this run. This is on purpose, to stay gentle.
echo  Run this file again later. Finished accounts are skipped, so it continues with the next ones.
echo ========================================
goto :finish
