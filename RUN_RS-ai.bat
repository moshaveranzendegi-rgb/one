@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Please run INSTALL_RS-ai.bat first.&pause&exit /b 1)
if exist "C:\ffmpeg\bin\ffmpeg.exe" set "RS_AI_FFMPEG=C:\ffmpeg\bin\ffmpeg.exe"
call ".venv\Scripts\activate.bat"
python -m app.main
pause
