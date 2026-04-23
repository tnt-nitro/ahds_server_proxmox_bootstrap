@echo off
cd /d "%~dp0"

python --version >nul 2>&1
if not errorlevel 1 (
  python main.py app
  goto fertig
)

py -3 --version >nul 2>&1
if not errorlevel 1 (
  py -3 main.py app
  goto fertig
)

echo.
echo [Fehler] Weder "python" noch "py" wurde gefunden.
echo.

:fertig
echo.
pause
