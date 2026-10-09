@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem ============ settings ============
set BROWSER=chrome
set COOKIES=cookies.txt
set LIST=following_lilillliilu.txt
set TARGET=lilillliilu
set SLEEP_REQUEST=12-25
rem Same cookie settings as start_gallery_dl.bat. No password needed.
rem ==================================

echo.
echo ========================================
echo   Update following list only
echo ========================================
echo   target : %TARGET%
echo   list   : %LIST%
echo.
echo  - Be logged in to instagram.com in %BROWSER%, or put cookies.txt in this folder.
echo  - Close %BROWSER% completely first.
echo  - Existing lines are kept, including # excluded ones. Only new accounts are added.
echo.
pause

set PY=
where python >nul 2>nul
if not errorlevel 1 set PY=python
if "%PY%"=="" (
  where py >nul 2>nul
  if not errorlevel 1 set PY=py
)
if "%PY%"=="" (
  echo [ERROR] Python is not installed. Install it from https://www.python.org/downloads/
  pause
  exit /b 1
)

%PY% -m pip show gallery-dl >nul 2>nul
if errorlevel 1 %PY% -m pip install -U gallery-dl

set AUTH=--cookies-from-browser %BROWSER%
if exist "%COOKIES%" set AUTH=--cookies "%COOKIES%"
echo Login source: %AUTH%

%PY% -m gallery_dl %AUTH% --sleep-request %SLEEP_REQUEST% -g "https://www.instagram.com/%TARGET%/following/" > following_raw.txt
%PY% merge_following.py "%LIST%" following_raw.txt %TARGET%

echo.
pause
