@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0deployment\VectorNext.ps1" -Action Start
if errorlevel 1 pause
