from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.config import APP_HOME


def _command_version(command: list[str], timeout: int = 3) -> tuple[bool, str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        line = (result.stdout or result.stderr).strip().splitlines()
        return result.returncode == 0, line[0][:160] if line else "installed"
    except (OSError, subprocess.TimeoutExpired):
        return False, "not found"


def get_runtime_status() -> dict[str, Any]:
    ffmpeg = os.getenv("RS_AI_FFMPEG") or shutil.which("ffmpeg")
    if not ffmpeg and os.name == "nt":
        candidate = Path(r"C:\ffmpeg\bin\ffmpeg.exe")
        if candidate.exists():
            ffmpeg = str(candidate)
    ffmpeg_ok = bool(ffmpeg and Path(ffmpeg).exists()) if ffmpeg else False
    ffmpeg_version = "not found"
    subtitles_filter = False
    if ffmpeg_ok:
        ok, text = _command_version([str(ffmpeg), "-version"])
        ffmpeg_version = text if ok else "unavailable"
        try:
            filters = subprocess.run([str(ffmpeg), "-hide_banner", "-filters"], capture_output=True, text=True, timeout=5)
            subtitles_filter = " subtitles " in (filters.stdout or "") or " subtitles=" in (filters.stdout or "")
        except (OSError, subprocess.TimeoutExpired):
            pass

    wsl = shutil.which("wsl.exe") or shutil.which("wsl")
    wsl_ok = bool(wsl)
    wsl_gpu = False
    omni_ready = False
    fashn_ready = False
    body_ready = False
    wsl_message = "WSL2 not detected"
    if wsl_ok:
        distro = os.getenv("RS_AI_WSL_DISTRO", "Ubuntu")
        wsl_gpu, gpu_text = _command_version([str(wsl), "-d", distro, "--", "bash", "-lc", "nvidia-smi -L"], timeout=8)
        omni_dir = os.getenv("RS_AI_OMNIAVATAR_DIR", "/opt/OmniAvatar")
        checks = [
            "scripts/inference.py",
            "pretrained_models/OmniAvatar-1.3B/pytorch_model.pt",
            "pretrained_models/wav2vec2-base-960h",
            "pretrained_models/Wan2.1-T2V-1.3B/diffusion_pytorch_model.safetensors",
            "pretrained_models/Wan2.1-T2V-1.3B/models_t5_umt5-xxl-enc-bf16.pth",
            "pretrained_models/Wan2.1-T2V-1.3B/Wan2.1_VAE.pth",
        ]
        model_check = " && ".join(f"test -e {shlex.quote(omni_dir.rstrip('/') + '/' + item)}" for item in checks)
        omni_ready, _ = _command_version([str(wsl), "-d", distro, "--", "bash", "-lc", model_check], timeout=4)
        fashn_dir = os.getenv("RS_AI_FASHN_DIR", "/opt/fashn-vton-1.5")
        weights_path = fashn_dir.rstrip("/") + "/weights"
        fashn_check = f"test -n \"$(find {shlex.quote(weights_path)} -maxdepth 2 -type f -name '*.safetensors' -print -quit 2>/dev/null)\""
        fashn_ready, _ = _command_version([str(wsl), "-d", distro, "--", "bash", "-lc", fashn_check], timeout=4)
        body_ready, _ = _command_version([str(wsl), "-d", distro, "--", "bash", "-lc", "test -f /opt/rs-ai-body-ready"], timeout=3)
        wsl_message = gpu_text if wsl_gpu else "WSL2 موجود است، اما GPU انویدیا از داخل آن تأیید نشد"

    try:
        import edge_tts  # noqa: F401
        tts_ready = True
    except ImportError:
        tts_ready = False
    try:
        import rembg  # noqa: F401
        rembg_ready = True
    except ImportError:
        rembg_ready = False
    try:
        import faster_whisper  # noqa: F401
        whisper_ready = True
    except ImportError:
        whisper_ready = False

    return {
        "app_home": str(APP_HOME),
        "ffmpeg": {"ready": ffmpeg_ok, "path": str(ffmpeg or ""), "version": ffmpeg_version, "subtitle_filter": subtitles_filter},
        "wsl": {"ready": wsl_ok, "gpu_ready": wsl_gpu, "message": wsl_message},
        "omniavatar": {"ready": omni_ready},
        "fashn": {"ready": fashn_ready},
        "body_completion": {"ready": body_ready},
        "tts": {"ready": tts_ready},
        "background_removal": {"ready": rembg_ready},
        "transcription": {"ready": whisper_ready},
        "daily_jobs": 20,
        "is_windows": os.name == "nt",
    }
