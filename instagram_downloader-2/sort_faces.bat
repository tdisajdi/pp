@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem ============ settings ============
set PHOTO_DIR=instagram_downloads\instagram
rem ==================================

echo.
echo ========================================
echo   Face sorting
echo ========================================
echo   folder: %PHOTO_DIR%
echo.
echo  Each account folder gets three sub folders:
echo    single_face : exactly 1 face
echo    multi_face  : 2 or more faces
echo    no_face     : no face
echo  Photos are moved, never deleted.
echo.
pause

if not exist "%PHOTO_DIR%" (
  echo.
  echo [ERROR] Folder not found: %PHOTO_DIR%
  echo Download photos first with start_gallery_dl.bat.
  pause
  exit /b 1
)

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

%PY% -m pip show mediapipe >nul 2>nul
if errorlevel 1 (
  echo Installing mediapipe and opencv. This can take a few minutes...
  %PY% -m pip install -U mediapipe opencv-python-headless
  if errorlevel 1 (
    echo.
    echo [ERROR] Install failed. mediapipe may not support your Python version.
    echo Try Python 3.11 or 3.12 from https://www.python.org/downloads/
    pause
    exit /b 1
  )
)

%PY% instagram_downloader.py --sort-faces "%PHOTO_DIR%"

echo.
echo Done. Open %PHOTO_DIR%\ACCOUNT\single_face and the other folders.
pause
