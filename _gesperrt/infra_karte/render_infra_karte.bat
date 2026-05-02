@echo off

setlocal

cd /d "%~dp0"



python render_infra_karte.py

set EXITCODE=%ERRORLEVEL%



if %EXITCODE% neq 0 (

  echo.

  echo Fehler beim Rendern ^(Exit %EXITCODE%^).

  echo Pruefen: Python im PATH? Liegt daten.json im gleichen Ordner?

  pause

  exit /b %EXITCODE%

)



echo.

echo Fertig: infra_karte.html wurde erzeugt ^(gleicher Ordner wie diese BAT^).

echo.

pause

endlocal

exit /b 0

