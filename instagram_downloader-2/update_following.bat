@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem ============ settings ============
set TARGET=lilillliilu
set LOGIN_ID=lilillliilu
rem TARGET   = the account whose following list you want.
rem LOGIN_ID = the Instagram account to log in with. A saved session is reused after the first time.
rem ==================================

echo.
echo ========================================
echo   Update following list
echo ========================================
echo   target account : %TARGET%
echo   login account  : %LOGIN_ID%
echo.
echo  - Existing lines in following_%TARGET%.txt are kept, including # excluded ones.
echo  - Only newly followed accounts are added at the bottom.
echo  - First time only: type the password. Nothing shows while typing, press Enter.
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
  echo.
  echo [ERROR] Python is not installed. Install it from https://www.python.org/downloads/
  pause
  exit /b 1
)

%PY% -m pip show instaloader >nul 2>nul
if errorlevel 1 (
  echo Installing instaloader...
  %PY% -m pip install -U instaloader
  if errorlevel 1 (
    echo [ERROR] Failed to install instaloader.
    pause
    exit /b 1
  )
)

%PY% instagram_downloader.py --following %TARGET% --login %LOGIN_ID%

echo.
pause
