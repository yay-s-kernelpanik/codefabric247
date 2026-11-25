@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)"
  if errorlevel 1 goto oldpython
  py -3 -m fabrica hub init
) else (
  where python >nul 2>nul
  if errorlevel 1 goto nopython
  python -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)"
  if errorlevel 1 goto oldpython
  python -m fabrica hub init
)
if errorlevel 1 echo No se pudo inicializar el Hub.
echo.
echo Para iniciarlo: py -3 -m fabrica hub serve --host 0.0.0.0 --port 8765
echo No publiques HTTP directamente en Internet; usa VPN privada o HTTPS.
pause
goto end
:nopython
echo No se encontro Python 3.9 o superior.
goto end
:oldpython
echo Fabrica247 requiere Python 3.9 o superior.
:end
pause
