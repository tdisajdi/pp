@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"

rem ===== settings =====
set BROWSER=chrome
set LIST=following_lilillliilu.txt
rem ====================

echo ========================================
echo   Instagram download (gallery-dl)
echo   browser cookies: %BROWSER%
echo   list: %LIST%
echo ========================================
echo.
echo - Log in to instagram.com in %BROWSER% first.
echo - Close %BROWSER% completely before running (cookie file is locked while open).
echo - Re-run this file any time: already downloaded posts are skipped.
echo.
pause

where gallery-dl >nul 2>nul
if errorlevel 1 (
  echo gallery-dl not found. Installing...
  python -m pip install -U gallery-dl
)

set /a N=0
for /f "usebackq eol=# tokens=*" %%u in ("%LIST%") do (
  set /a N+=1
  echo.
  echo [!N!] %%u
  gallery-dl --cookies-from-browser %BROWSER% --download-archive gallery_dl_archive.sqlite3 --sleep-request 6-12 -o videos=false -d instagram_downloads "https://www.instagram.com/%%u/"
)

echo.
echo ----------------------------------------
echo Done. Files are in: %cd%\instagram_downloads\instagram\
pause
