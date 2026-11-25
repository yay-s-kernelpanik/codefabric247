@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)"
  if errorlevel 1 goto oldpython
  py -3 -m fabrica setup --edition windows-heavy
) else (
  where python >nul 2>nul
  if errorlevel 1 goto nopython
  python -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)"
  if errorlevel 1 goto oldpython
  python -m fabrica setup --edition windows-heavy
)
if errorlevel 1 echo La instalacion no se completo. Revisa el mensaje anterior.
goto end
:nopython
echo No se encontro Python 3.9 o superior. Instalalo para tu usuario y volve a ejecutar.
goto end
:oldpython
echo Fabrica247 requiere Python 3.9 o superior.
:end
echo.
pause
