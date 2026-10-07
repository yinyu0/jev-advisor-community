@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" tools\advisor_demo.py
if errorlevel 1 pause
