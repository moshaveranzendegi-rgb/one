#!/usr/bin/env bash
set -euo pipefail
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip ffmpeg
sudo mkdir -p /opt/rs-ai-tools
sudo chown -R "$USER":"$USER" /opt/rs-ai-tools
cd /opt/rs-ai-tools
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install torch==2.4.0 --index-url https://download.pytorch.org/whl/cu124
pip install diffusers transformers accelerate safetensors pillow
pip install -U 'huggingface_hub[cli]'
hf download stable-diffusion-v1-5/stable-diffusion-inpainting --local-dir /opt/rs-ai-body-model
sudo touch /opt/rs-ai-body-ready
