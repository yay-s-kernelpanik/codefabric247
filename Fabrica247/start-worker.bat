@echo off
where py >nul 2>nul
if %errorlevel%==0 (py -3 -m fabrica worker run) else (python -m fabrica worker run)
pause
