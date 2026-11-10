@echo off
setlocal
REM ECLIPSE Ensemble Dashboard - double-click convenience launcher.
REM Usage: run_dashboard.bat [folder_with_eclipse_runs]   (default: repo folder)
set "FOLDER=%~1"
if "%FOLDER%"=="" set "FOLDER=%~dp0."
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher "py" not found. Install Python 3 from python.org ^(tick "py launcher"^).
  pause & exit /b 1
)
py -3 -c "import resdata, plotly" >nul 2>nul
if errorlevel 1 (
  echo Installing dependencies ^(one-time^)...
  py -3 -m pip install -r "%~dp0requirements.txt"
)
py -3 "%~dp0build_dashboard.py" "%FOLDER%" -o "%~dp0dashboard.html"
if errorlevel 1 ( pause & exit /b 1 )
start "" "%~dp0dashboard.html"
endlocal
