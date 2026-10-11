@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0RS-ai.exe" (echo RS-ai.exe was not found beside this launcher.&pause&exit /b 1)
if exist "C:\ffmpeg\bin\ffmpeg.exe" set "RS_AI_FFMPEG=C:\ffmpeg\bin\ffmpeg.exe"
where ffmpeg >nul 2>nul
if errorlevel 1 if not exist "C:\ffmpeg\bin\ffmpeg.exe" echo WARNING: FFmpeg not found. The UI opens, but video rendering requires FFmpeg.
start "RS ai" "%~dp0RS-ai.exe"
