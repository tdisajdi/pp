@echo off
cd /d "%~dp0"

echo.
echo ========================================
echo   Make cookies.txt from Edge  - no extension needed
echo ========================================
echo.
echo  1. Open Edge and log in to instagram.com with the account you want to use.
echo  2. Press F12 to open the developer tools.
echo  3. Click the tab named Application. If you do not see it, click the arrows to show more tabs.
echo  4. On the left open Storage, then Cookies, then https://www.instagram.com
echo  5. Find the row named sessionid. Double click its Value and copy it with Ctrl+C.
echo  6. Come back here and paste it with a right click. Then press Enter.
echo.
echo  The sessionid works like your login. Never send it to anyone.
echo  Do not log out of Instagram in Edge while downloading, or it stops working.
echo.

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

%PY% make_cookies.py

echo.
pause
