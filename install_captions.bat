@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Run install_windows.bat first.&pause&exit /b 1)
call ".venv\Scripts\activate.bat"
python -m pip install -r requirements-captions.txt || goto :error
echo Whisper captioning package installed. Its speech model downloads on first use.
pause
exit /b 0
:error
echo Caption dependency installation failed.
pause
exit /b 1
