@echo off
setlocal
cd /d "%~dp0"
set "CADOS_VENV=%LOCALAPPDATA%\Cados\.venv"
if exist "%CADOS_VENV%\Scripts\python.exe" goto install
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if errorlevel 1 (
  echo CADOS benoetigt Python 3.11 oder neuer mit dem Python Launcher.
  echo Bitte Python installieren und diesen Starter erneut oeffnen.
  pause
  exit /b 1
)
py -3 -m venv "%CADOS_VENV%"
if errorlevel 1 goto error
:install
"%CADOS_VENV%\Scripts\python.exe" -m pip install -e "%CD%"
if errorlevel 1 goto error
"%CADOS_VENV%\Scripts\python.exe" -m cados
if errorlevel 1 goto error
exit /b 0
:error
echo CADOS konnte nicht gestartet werden. Bitte die Fehlermeldung oben pruefen.
pause
exit /b 1
