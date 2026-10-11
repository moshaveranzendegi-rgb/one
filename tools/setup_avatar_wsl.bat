@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0\.."
title RS ai - OmniAvatar 1.3B Setup

echo ================================================================
echo RS ai - نصب موتور اصلی آواتار متحرک
echo این مرحله حدود 20 تا 30 گیگابایت فضای خالی و اینترنت پایدار می‌خواهد.
echo ================================================================
echo.

where wsl >nul 2>nul
if errorlevel 1 (
  echo WSL پیدا نشد. PowerShell را با دسترسی Administrator باز کن و اجرا کن:
  echo   wsl --install -d Ubuntu
  echo سپس رایانه را راه‌اندازی مجدد کن و این فایل را دوباره اجرا کن.
  goto :fail
)

wsl -d Ubuntu -- bash -lc "test -f /etc/os-release" >nul 2>nul
if errorlevel 1 (
  echo توزیع Ubuntu در WSL پیدا نشد.
  echo در PowerShell با دسترسی Administrator اجرا کن:
  echo   wsl --install -d Ubuntu
  echo بعد از نصب Ubuntu و ساخت کاربر لینوکس، این فایل را دوباره اجرا کن.
  goto :fail
)

echo [1/5] بررسی دسترسی GPU از داخل WSL2...
wsl -d Ubuntu -- bash -lc "nvidia-smi -L"
if errorlevel 1 (
  echo.
  echo GPU انویدیا از داخل WSL قابل استفاده نیست؛ مدل‌ها را دانلود نمی‌کنم
  echo تا بی‌دلیل ده‌ها گیگابایت اینترنت و فضای دیسک مصرف نشود.
  echo در ویندوز دستور nvidia-smi را بررسی کن و درایور NVIDIA با پشتیبانی WSL را نصب کن.
  echo در صورت نداشتن GPU سازگار NVIDIA، این موتور روی این رایانه اجرا نمی‌شود.
  goto :fail
)

echo.
echo فضای آزاد Ubuntu:
wsl -d Ubuntu -- bash -lc "df -h /"
echo.

echo [2/5] نصب ابزارهای موردنیاز و دریافت سورس رسمی OmniAvatar...
wsl -d Ubuntu -- bash -lc "sudo apt-get update && sudo apt-get install -y git python3-venv python3-pip ffmpeg" 
if errorlevel 1 goto :fail

wsl -d Ubuntu -- bash -lc "if [ -e /opt/OmniAvatar ] && [ ! -d /opt/OmniAvatar/.git ]; then echo '/opt/OmniAvatar exists but is not a Git repository; inspect that folder before retrying.' >&2; exit 2; fi; if [ ! -d /opt/OmniAvatar/.git ]; then sudo git clone https://github.com/Omni-Avatar/OmniAvatar /opt/OmniAvatar || exit 3; fi; sudo chown -R $USER:$USER /opt/OmniAvatar"
if errorlevel 1 goto :fail

echo.
echo [3/5] نصب PyTorch سازگار با CUDA و وابستگی‌های OmniAvatar...
wsl -d Ubuntu -- bash -lc "cd /opt/OmniAvatar && python3 -m venv .venv && source .venv/bin/activate && python -m pip install --upgrade pip setuptools wheel && pip install torch==2.4.0 torchvision==0.19.0 torchaudio==2.4.0 --index-url https://download.pytorch.org/whl/cu124 && pip install -r requirements.txt"
if errorlevel 1 goto :fail

echo.
echo بررسی می‌کنم PyTorch هم GPU را می‌بیند؛ اگر نه، دانلود مدل‌ها را شروع نمی‌کنم...
wsl -d Ubuntu -- bash -lc "cd /opt/OmniAvatar && source .venv/bin/activate && python -c 'import torch; print(torch.__version__); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CUDA GPU NOT AVAILABLE"); assert torch.cuda.is_available(), "PyTorch cannot access the WSL GPU"'"
if errorlevel 1 goto :fail

echo.
echo [4/5] دانلود وزن‌های رسمی مدل‌های 1.3B، Wav2Vec و OmniAvatar...
echo دانلود ممکن است طول بکشد؛ پنجره را نبند.
wsl -d Ubuntu -- bash -lc "cd /opt/OmniAvatar && source .venv/bin/activate && pip install -U 'huggingface_hub[cli]' && mkdir -p pretrained_models && hf download Wan-AI/Wan2.1-T2V-1.3B --local-dir pretrained_models/Wan2.1-T2V-1.3B && hf download facebook/wav2vec2-base-960h --local-dir pretrained_models/wav2vec2-base-960h && hf download OmniAvatar/OmniAvatar-1.3B --local-dir pretrained_models/OmniAvatar-1.3B"
if errorlevel 1 goto :fail

echo.
echo [5/5] بررسی فایل‌های ضروری مدل و مسیر اتصال...
wsl -d Ubuntu -- bash -lc "cd /opt/OmniAvatar && test -f scripts/inference.py && test -f configs/inference_1.3B.yaml && test -f pretrained_models/Wan2.1-T2V-1.3B/diffusion_pytorch_model.safetensors && test -f pretrained_models/Wan2.1-T2V-1.3B/models_t5_umt5-xxl-enc-bf16.pth && test -f pretrained_models/Wan2.1-T2V-1.3B/Wan2.1_VAE.pth && test -f pretrained_models/wav2vec2-base-960h/config.json && test -f pretrained_models/OmniAvatar-1.3B/pytorch_model.pt"
if errorlevel 1 (
  echo.
  echo بعضی فایل‌های لازم پیدا نشدند. اتصال هنوز تأیید نشده است.
  echo این فایل را دوباره اجرا کن تا دانلودهای ناقص ادامه پیدا کنند.
  goto :fail
)

echo.
echo موفق: فایل‌های اصلی مدل پیدا شدند و PyTorch به GPU دسترسی دارد.
echo اکنون برنامه RS ai را اجرا کن و در بخش «وضعیت موتور‌ها» OmniAvatar را بررسی کن.
echo این بررسی نصب مدل است؛ تولید نمونه ویدئوی فارسی باید جداگانه آزمایش شود.
pause
exit /b 0

:fail
echo.
echo نصب موتور به پایان موفق نرسید؛ متن خطای بالا را نگه دار.
echo هیچ خروجی ساختگی یا عکس ثابت به جای ویدئوی متحرک تحویل داده نمی‌شود.
pause
exit /b 1
