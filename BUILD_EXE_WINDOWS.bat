@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo First run INSTALL_RS-ai.bat.&pause&exit /b 1)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\build_windows.ps1"
if errorlevel 1 (echo Build failed. Keep the error output above.&pause&exit /b 1)
echo Build folder: dist\RS-ai
pause
