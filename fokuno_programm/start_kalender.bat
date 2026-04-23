@echo off
cd /d "%~dp0"

python --version >nul 2>&1
if not errorlevel 1 (
  python main.py kalender
  goto fertig
)

py -3 --version >nul 2>&1
if not errorlevel 1 (
  py -3 main.py kalender
  goto fertig
)

echo.
echo [Fehler] Weder "python" noch "py" wurde gefunden.
echo Python installieren und bei der Installation "Add python.exe to PATH" aktivieren,
echo oder die Eingabeaufforderung so starten, dass Python im PATH ist.
echo.

:fertig
echo.
pause
