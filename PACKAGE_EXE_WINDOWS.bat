@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\package_windows_build.ps1"
if errorlevel 1 (echo Packaging failed.&pause&exit /b 1)
echo Windows portable package created in dist-packages.
echo Keep every .partNNN file and the matching .sha256.txt together.
pause
