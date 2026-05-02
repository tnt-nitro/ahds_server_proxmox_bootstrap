@echo off
setlocal
cd /d "%~dp0"

python "geheimnisse_eintragen.py"
if errorlevel 1 (
  echo.
  echo Fehler beim Ausfuehren von geheimnisse_eintragen.py
)

echo.
pause
