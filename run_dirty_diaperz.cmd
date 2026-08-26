@echo off
setlocal
if "%~1"=="" goto usage
if "%~2"=="" goto usage
if "%~3"=="" goto usage
python scripts\dirty_diaperz_fadr.py --source "%~1" --title "%~2" --out "%~3"
if errorlevel 1 (
  echo.
  echo ERROR: Automation failed with exit code %errorlevel%.
  exit /b %errorlevel%
)
echo Automation complete.
exit /b 0
:usage
echo Usage: %~nx0 "source audio" "song title" "output folder"
exit /b 64
