@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem ============ settings ============
set BROWSER=chrome
set LIST=following_lilillliilu.txt
set COOKIES=cookies.txt
set UPDATE_FOLLOWING=1
set TARGET=lilillliilu
set UPDATE_FROM_SAVED=1
set SAVED_RANGE=
set SLEEP_REQUEST=12-25
set SLEEP_BETWEEN=8
set MAX_ACCOUNTS=0
set MAX_RETRY=15
set RETRY_WAIT=60
rem UPDATE_FOLLOWING=1 refreshes the following list of TARGET before downloading. 0 skips it.
rem It uses the same browser cookies as the download, so no password is needed.
rem UPDATE_FROM_SAVED=1 also adds the owners of your SAVED posts to the list. These accounts
rem are downloaded even if you do not follow them, as long as they are public.
rem SAVED_RANGE limits how many saved posts are scanned, for example 1-300. Empty means all.
rem MAX_ACCOUNTS=0 means all accounts. A number means only the first N accounts.
rem BROWSER can be firefox, chrome or edge. Chrome and Edge often fail to decrypt cookies.
rem If a cookies.txt file exists in this folder it is used instead of the browser.
rem Photos are saved. Videos are not, but reels and video posts are saved as their cover image.
rem MAX_RETRY = how many times to resume the SAME account when it stops midway.
rem RETRY_WAIT = seconds to wait before resuming the same account.
rem ==================================

echo.
echo ========================================
echo   START : refresh following list, then download posts and reels
echo ========================================
echo   browser      : %BROWSER%
echo   cookies file : %COOKIES% - used first if the file exists
echo   list file    : %LIST%
echo   update list  : %UPDATE_FOLLOWING%  1=yes 0=no  target=%TARGET%
echo   add saved    : %UPDATE_FROM_SAVED%  1=yes 0=no
echo   request delay: %SLEEP_REQUEST% sec
echo   account delay: %SLEEP_BETWEEN% sec
echo   retry        : up to %MAX_RETRY% times per account, %RETRY_WAIT% sec apart
if %MAX_ACCOUNTS% GTR 0 (echo   max accounts : %MAX_ACCOUNTS%) else (echo   max accounts : all)
echo ========================================
echo.
echo  Before you start:
echo  1. Be logged in to instagram.com in %BROWSER%, or put cookies.txt in this folder.
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
echo Login source: %AUTH%

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

for /f "usebackq eol=# tokens=*" %%u in ("%LIST%") do (
  if %MAX_ACCOUNTS% GTR 0 if !N! GEQ %MAX_ACCOUNTS% goto :finish
  set /a N+=1
  echo.
  echo ----------------------------------------
  echo [!N!] %%u
  echo ----------------------------------------
  call :do_account %%u
  if %SLEEP_BETWEEN% GTR 0 timeout /t %SLEEP_BETWEEN% /nobreak >nul
)

:finish
echo.
echo ========================================
echo  Done
echo  accounts tried : !N!
echo  completed      : !SUCCESS!
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
set TRY=0
:retry
set /a TRY+=1
%PY% -m gallery_dl %AUTH% --download-archive gallery_dl_archive.sqlite3 --sleep-request %SLEEP_REQUEST% -o include=posts,reels -o videos=false -o previews=video -d instagram_downloads "https://www.instagram.com/%~1/"
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
exit /b 0

:acct_skip
echo   [skipped: account not found or nothing to download]
set /a FAIL+=1
exit /b 0

:acct_fail
echo   [gave up after %MAX_RETRY% attempts - run this file again later]
set /a FAIL+=1
exit /b 0
