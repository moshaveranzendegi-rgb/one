@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title RS ai - Installer
set "INSTALL_DIR=%LOCALAPPDATA%\Programs\RS-ai"
if /I not "%~1"=="--installed" (
  for %%I in ("%~dp0.") do set "SOURCE_DIR=%%~fI"
  for %%I in ("%INSTALL_DIR%") do set "TARGET_DIR=%%~fI"
  if /I not "%SOURCE_DIR%"=="%TARGET_DIR%" (
    echo Installing RS ai to: %INSTALL_DIR%
    if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%" || goto :copyerror
    robocopy "%SOURCE_DIR%" "%INSTALL_DIR%" /E /R:2 /W:1 /XD .git .venv __pycache__ .pytest_cache .mypy_cache .ruff_cache data outputs logs dist build dist-packages node_modules /XF *.pyc *.pyo *.sqlite3 *.db
    if errorlevel 8 goto :copyerror
  )
  call "%INSTALL_DIR%\INSTALL_RS-ai.bat" --installed
  exit /b %ERRORLEVEL%
)
cd /d "%INSTALL_DIR%"
echo ================================================================
echo                  RS ai - نصب کننده ویندوز
echo ================================================================
set "PY_CMD="
where py >nul 2>nul
if not errorlevel 1 (
  py -3.11 --version >nul 2>nul
  if not errorlevel 1 set "PY_CMD=py -3.11"
  if not defined PY_CMD (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>nul
    if not errorlevel 1 set "PY_CMD=py -3"
  )
)
if not defined PY_CMD (
  where python >nul 2>nul
  if not errorlevel 1 (
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>nul
    if not errorlevel 1 set "PY_CMD=python"
  )
)
if not defined PY_CMD (
  echo Python 3.11 or newer was not found.
  where winget >nul 2>nul
  if not errorlevel 1 (
    echo Trying to install Python 3.11 using Windows Package Manager...
    winget install --id Python.Python.3.11 --exact --scope user --silent --accept-package-agreements --accept-source-agreements
    echo Close this window and run INSTALL_RS-ai.bat again if installation succeeded.
  ) else (
    echo Install Python 3.11 from https://www.python.org/downloads/windows/
  )
  pause
  exit /b 1
)
echo Python interpreter: %PY_CMD%
%PY_CMD% --version || goto :error
if not exist ".venv\Scripts\python.exe" (
  echo Creating isolated Python environment...
  %PY_CMD% -m venv .venv || goto :error
)
call ".venv\Scripts\activate.bat" || goto :error
echo Updating pip build tools...
python -m pip install --disable-pip-version-check --upgrade pip setuptools wheel || goto :error
echo Installing RS ai dependencies...
python -m pip install --disable-pip-version-check -r requirements.txt || goto :error
echo Verifying source and basic tests...
python -m compileall -q app tools tests || goto :error
python -m unittest discover -s tests -v || goto :error
if exist "C:\ffmpeg\bin\ffmpeg.exe" (
  set "RS_AI_FFMPEG=C:\ffmpeg\bin\ffmpeg.exe"
) else (
  where ffmpeg >nul 2>nul
  if errorlevel 1 echo WARNING: FFmpeg is missing. Rendering requires FFmpeg.
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\RS ai.lnk'); $s.TargetPath='%INSTALL_DIR%\RUN_RS-ai.bat'; $s.WorkingDirectory='%INSTALL_DIR%'; $s.IconLocation='%SystemRoot%\System32\SHELL32.dll,14'; $s.Save()" >nul 2>nul
echo.
echo RS ai base setup completed.
echo Installed in: %INSTALL_DIR%
echo Desktop shortcut: RS ai
echo Next: run RUN_RS-ai.bat or the desktop shortcut.
echo IMPORTANT: OmniAvatar model weights are not bundled; compatible NVIDIA GPU and WSL2 are required.
pause
exit /b 0
:copyerror
echo Could not copy RS ai into %INSTALL_DIR%. Close the app and retry.
pause
exit /b 1
:error
echo INSTALLATION FAILED. Copy the error above before asking for help.
pause
exit /b 1
