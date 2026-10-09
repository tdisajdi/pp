@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem ============ settings ============
set BROWSER=chrome
set LIST=following_lilillliilu.txt
set SLEEP_REQUEST=12-25
set SLEEP_BETWEEN=8
set MAX_ACCOUNTS=0
rem MAX_ACCOUNTS=0 means all accounts. A number means only the first N accounts.
rem BROWSER can be chrome, edge or firefox.
rem ==================================

echo.
echo ========================================
echo   Instagram downloader - gallery-dl
echo ========================================
echo   browser      : %BROWSER%
echo   list file    : %LIST%
echo   request delay: %SLEEP_REQUEST% sec
echo   account delay: %SLEEP_BETWEEN% sec
if %MAX_ACCOUNTS% GTR 0 (echo   max accounts : %MAX_ACCOUNTS%) else (echo   max accounts : all)
echo ========================================
echo.
echo  Before you start:
echo  1. Be logged in to instagram.com in %BROWSER%.
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
  %PY% -m gallery_dl --cookies-from-browser %BROWSER% --download-archive gallery_dl_archive.sqlite3 --sleep-request %SLEEP_REQUEST% -o videos=false -d instagram_downloads "https://www.instagram.com/%%u/"
  if errorlevel 1 (
    echo   [failed or partial] continuing with the next account
    set /a FAIL+=1
  ) else (
    set /a SUCCESS+=1
  )
  if %SLEEP_BETWEEN% GTR 0 timeout /t %SLEEP_BETWEEN% /nobreak >nul
)

:finish
echo.
echo ========================================
echo  Done
echo  accounts tried : !N!
echo  ok             : !SUCCESS!
echo  failed         : !FAIL!
echo  saved to       : %cd%\instagram_downloads\instagram\
echo ========================================
echo  Run this file again any time to resume and fetch new posts.
echo.
pause
