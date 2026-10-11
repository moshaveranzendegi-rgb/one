@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Run install_windows.bat first.&pause&exit /b 1)
call ".venv\Scripts\activate.bat"
python -m pip install -r requirements-vision.txt || goto :error
echo Background-removal dependency installed.
pause
exit /b 0
:error
echo Image dependency installation failed.
pause
exit /b 1
