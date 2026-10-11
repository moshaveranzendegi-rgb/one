@echo off
setlocal
cd /d "%~dp0\.."
echo RS ai - OmniAvatar 1.3B setup in WSL2
echo This downloads large model weights. Allow 20-30 GB free disk space and a compatible NVIDIA GPU.
wsl --status >nul 2>nul
if errorlevel 1 (echo WSL is not ready. Install WSL2 and Ubuntu first.&pause&exit /b 1)
wsl -d Ubuntu -- bash -lc "sudo apt-get update && sudo apt-get install -y git python3-venv python3-pip ffmpeg" || goto :error
wsl -d Ubuntu -- bash -lc "if [ ! -d /opt/OmniAvatar/.git ]; then sudo git clone https://github.com/Omni-Avatar/OmniAvatar /opt/OmniAvatar; sudo chown -R $USER:$USER /opt/OmniAvatar; fi" || goto :error
wsl -d Ubuntu -- bash -lc "cd /opt/OmniAvatar && python3 -m venv .venv && source .venv/bin/activate && python -m pip install --upgrade pip setuptools wheel && pip install torch==2.4.0 torchvision==0.19.0 torchaudio==2.4.0 --index-url https://download.pytorch.org/whl/cu124 && pip install -r requirements.txt" || goto :error
wsl -d Ubuntu -- bash -lc "cd /opt/OmniAvatar && source .venv/bin/activate && pip install -U 'huggingface_hub[cli]' && mkdir -p pretrained_models && hf download Wan-AI/Wan2.1-T2V-1.3B --local-dir pretrained_models/Wan2.1-T2V-1.3B && hf download facebook/wav2vec2-base-960h --local-dir pretrained_models/wav2vec2-base-960h && hf download OmniAvatar/OmniAvatar-1.3B --local-dir pretrained_models/OmniAvatar-1.3B" || goto :error
echo Setup commands completed. Confirm model files and engine status before generating.
pause
exit /b 0
:error
echo Model setup failed. GPU drivers, WSL2, disk space or model access may be the cause.
pause
exit /b 1
