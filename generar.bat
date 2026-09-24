@echo off
cd /d "%~dp0"
python interfaz.py
if errorlevel 1 pause
