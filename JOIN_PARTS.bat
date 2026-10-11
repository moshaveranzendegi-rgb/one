@echo off
setlocal
cd /d "%~dp0"
echo RS ai - join split installer parts
echo Keep files NAME.part001, NAME.part002, ... and NAME.sha256.txt in this folder.
echo Do not rename or skip parts.
echo.
set /p BASE=Enter the base filename without .part001 or .zip:
if not defined BASE exit /b 1
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\JOIN_PARTS.ps1" -BaseName "%BASE%"
if errorlevel 1 (echo Joining failed. Check missing parts and SHA-256 file.&pause&exit /b 1)
echo Reassembly and hash check completed.
pause
