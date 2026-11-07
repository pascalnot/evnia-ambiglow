@echo off
rem Starts Evnia Ambiglow in the tray. The first run sets up a Python environment.
cd /d "%~dp0"
if not exist .venv\Scripts\pythonw.exe (
    echo First run: setting up Python environment, this takes a minute...
    py -3 -m venv .venv || (echo Python 3.10+ is required: https://www.python.org/downloads/ & pause & exit /b 1)
    .venv\Scripts\python.exe -m pip install -q --disable-pip-version-check -r requirements.txt || (pause & exit /b 1)
)
start "" .venv\Scripts\pythonw.exe EvniaAmbiglow.pyw %*
