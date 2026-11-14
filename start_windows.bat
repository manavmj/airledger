@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
    set "AIRLEDGER_PYTHON=py -3"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Install Python 3.11 or newer from https://www.python.org/downloads/
        echo Enable "Add Python to PATH" during installation, then run this file again.
        pause
        exit /b 1
    )
    set "AIRLEDGER_PYTHON=python"
)
if not exist ".venv\Scripts\python.exe" (
    %AIRLEDGER_PYTHON% -m venv .venv
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" scripts\run_local.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo.
echo AirLedger could not start. Copy the error above so it can be diagnosed.
pause
exit /b 1
