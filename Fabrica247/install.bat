@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)"
  if errorlevel 1 goto oldpython
  py -3 -m fabrica setup --edition windows
  goto result
)
where python >nul 2>nul
if %errorlevel%==0 (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)"
  if errorlevel 1 goto oldpython
  python -m fabrica setup --edition windows
  goto result
)
echo No encuentro Python 3.9 o superior. Instala Python para tu usuario y activa la opcion de agregarlo al PATH.
echo No hace falta ejecutar este instalador como administrador.
goto end
:oldpython
echo Fabrica247 requiere Python 3.9 o superior.
:result
if errorlevel 1 echo La instalacion no se completo. Revisa el mensaje anterior.
:end
echo.
pause
