@echo off
cd /d "%~dp0"

python --version >nul 2>nul
if not errorlevel 1 goto run_python

py --version >nul 2>nul
if not errorlevel 1 goto run_py

echo Python 3.10 or newer was not found.
echo Install it from https://www.python.org/downloads/
echo and enable "Add python.exe to PATH" during installation.
pause
exit /b 1

:run_python
python app.py
goto end

:run_py
py app.py

:end
if errorlevel 1 pause
