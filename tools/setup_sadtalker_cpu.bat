@echo off
chcp 65001 >nul
setlocal
title RS ai - نصب موتور آواتار CPU
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_sadtalker_cpu.ps1"
if errorlevel 1 (
  echo.
  echo نصب موتور CPU ناموفق بود. متن خطا را برای بررسی نگه دار.
  pause
  exit /b 1
)
echo.
echo موتور SadTalker CPU نصب شد.
echo RS ai را ببند و دوباره اجرا کن، سپس «وضعیت موتور‌ها» را بررسی کن.
pause
exit /b 0
