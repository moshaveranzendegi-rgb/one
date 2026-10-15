@echo off
setlocal EnableExtensions
set "RS_PORTABLE=%~dp0"
set "RS_ENGINE=%LOCALAPPDATA%\RS-ai\engines\SadTalker"
set "RS_VISION=%LOCALAPPDATA%\RS-ai\engines\Vision"
set "RS_AI_SADTALKER_DIR=%RS_ENGINE%"
if not defined RS_AI_PORT set "RS_AI_PORT=8765"
if defined PYTHONPATH (
  set "PYTHONPATH=%RS_ENGINE%;%PYTHONPATH%"
) else (
  set "PYTHONPATH=%RS_ENGINE%"
)
set "PATH=C:\ffmpeg\bin;%RS_VISION%\.venv\Scripts;%RS_ENGINE%\.venv\Scripts;%PATH%"
cd /d "%RS_PORTABLE%"
if not exist "%RS_PORTABLE%RS-ai.exe" (
  echo RS-ai.exe was not found beside this launcher.
  pause
  exit /b 1
)
if exist "C:\ffmpeg\bin\ffmpeg.exe" set "RS_AI_FFMPEG=C:\ffmpeg\bin\ffmpeg.exe"
if exist "%LOCALAPPDATA%\RS-ai\engines\PiperTTS\run_hidden.vbs" (
  start "" /b "%SystemRoot%\System32\wscript.exe" "%LOCALAPPDATA%\RS-ai\engines\PiperTTS\run_hidden.vbs"
)
where ffmpeg >nul 2>nul
if errorlevel 1 if not exist "C:\ffmpeg\bin\ffmpeg.exe" echo WARNING: FFmpeg not found. Rendering requires FFmpeg.
start "RS ai" "%RS_PORTABLE%RS-ai.exe"
