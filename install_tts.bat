@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Run install_windows.bat first.&pause&exit /b 1)
call ".venv\Scripts\activate.bat"
python -m pip install -r requirements.txt || goto :error
echo TTS package installed. It needs internet when generating speech.
pause
exit /b 0
:error
echo TTS installation failed.
pause
exit /b 1
