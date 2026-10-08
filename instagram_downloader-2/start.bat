@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   Instagram Downloader
echo ========================================
echo.
echo  1. Download from following list
echo  2. Get following list
echo  3. Download one profile
echo  4. Sort faces (1 / 2+ / none)
echo  5. Custom command
echo  0. Exit
echo.
set /p choice="Select (0-5): "

if "%choice%"=="1" goto from_file
if "%choice%"=="2" goto following
if "%choice%"=="3" goto profile
if "%choice%"=="4" goto sort
if "%choice%"=="5" goto custom
if "%choice%"=="0" goto end
goto end

:from_file
echo.
set /p fname="List file name (ex: following_xxx.txt): "
if "%fname%"=="" goto end
python instagram_downloader.py --from-file "%fname%"
goto done

:following
echo.
set /p uid="Instagram ID: "
if "%uid%"=="" goto end
python instagram_downloader.py --following "%uid%"
goto done

:profile
echo.
set /p uid="Instagram ID: "
if "%uid%"=="" goto end
python instagram_downloader.py --profile "%uid%"
goto done

:sort
python instagram_downloader.py --sort-faces
goto done

:custom
echo.
echo Example: --from-file list.txt --max 30
echo Example: --profile username --video
set /p args="Arguments: "
if "%args%"=="" goto end
python instagram_downloader.py %args%
goto done

:done
echo.
echo ----------------------------------------
pause

:end
