@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py -3 -m fabrica hub serve --host 127.0.0.1 --port 8765) else (python -m fabrica hub serve --host 127.0.0.1 --port 8765)
pause
