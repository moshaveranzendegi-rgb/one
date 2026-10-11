#!/usr/bin/env bash
set -euo pipefail
sudo apt-get update
sudo apt-get install -y git python3-venv python3-pip
if [ ! -d /opt/fashn-vton-1.5/.git ]; then
  sudo git clone https://github.com/fashn-AI/fashn-vton-1.5.git /opt/fashn-vton-1.5
  sudo chown -R "$USER":"$USER" /opt/fashn-vton-1.5
fi
cd /opt/fashn-vton-1.5
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -e .
python scripts/download_weights.py --weights-dir ./weights
