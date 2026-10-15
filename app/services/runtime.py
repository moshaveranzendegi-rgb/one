from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.config import APP_HOME
from app.services.engine_selection import select_avatar_engine


def _command_version(command: list[str], timeout: int = 3, cwd: str | None = None) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, check=False, cwd=cwd,
        )
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
    # Do not start or probe WSL on Windows systems with no host NVIDIA GPU.
    # On Intel-only PCs, WSL GPU checks cannot succeed and may block status refresh
    # while WSL initializes. This app must remain responsive in its local CPU mode.
    host_nvidia = bool(shutil.which("nvidia-smi"))
    if os.name == "nt" and not host_nvidia:
        wsl_message = "GPU انویدیا روی ویندوز شناسایی نشد؛ OmniAvatar روی این سیستم غیرفعال است."
    elif wsl_ok:
        distro = os.getenv("RS_AI_WSL_DISTRO", "Ubuntu")
        wsl_gpu, gpu_text = _command_version([str(wsl), "-d", distro, "--", "bash", "-lc", "nvidia-smi -L"], timeout=5)
        if wsl_gpu:
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
            omni_ready, _ = _command_version([str(wsl), "-d", distro, "--", "bash", "-lc", model_check], timeout=3)
            fashn_dir = os.getenv("RS_AI_FASHN_DIR", "/opt/fashn-vton-1.5")
            weights_path = fashn_dir.rstrip("/") + "/weights"
            fashn_check = f"test -n \"$(find {shlex.quote(weights_path)} -maxdepth 2 -type f -name '*.safetensors' -print -quit 2>/dev/null)\""
            fashn_ready, _ = _command_version([str(wsl), "-d", distro, "--", "bash", "-lc", fashn_check], timeout=3)
            body_ready, _ = _command_version([str(wsl), "-d", distro, "--", "bash", "-lc", "test -f /opt/rs-ai-body-ready"], timeout=2)
        wsl_message = gpu_text if wsl_gpu else "WSL2 موجود است، اما GPU انویدیا از داخل آن تأیید نشد"

    # Optional local CPU fallback, isolated from the app's Python 3.11 runtime.
    sadtalker_dir = Path(os.getenv("RS_AI_SADTALKER_DIR", str(APP_HOME / "engines" / "SadTalker"))).expanduser()
    sadtalker_python = sadtalker_dir / ".venv" / "Scripts" / "python.exe"
    sadtalker_required = [
        sadtalker_dir / "inference.py",
        sadtalker_dir / "checkpoints" / "SadTalker_V0.0.2_256.safetensors",
        sadtalker_dir / "checkpoints" / "mapping_00109-model.pth.tar",
    ]
    sadtalker_files_ready = sadtalker_python.is_file() and all(p.is_file() for p in sadtalker_required)
    sadtalker_ready = False
    sadtalker_message = "نصب نشده؛ برای رایانهٔ بدون GPU انویدیا، tools\\setup_sadtalker_cpu.bat را اجرا کن"
    if sadtalker_files_ready:
        # Avoid importing inference.py during every status refresh: its transitive imports
        # can trigger heavyweight model downloads and make the UI appear frozen. The setup
        # installer performs the full inference import once; runtime status only checks
        # that the isolated environment contains the essential packages.
        probe = (
            "import importlib.util, sys; "
            "mods=('torch','safetensors','cv2','scipy'); "
            "missing=[m for m in mods if importlib.util.find_spec(m) is None]; "
            "print('Missing modules: '+','.join(missing) if missing else 'SadTalker packages present'); "
            "sys.exit(1 if missing else 0)"
        )
        sadtalker_ready, sadtalker_message = _command_version(
            [str(sadtalker_python), "-c", probe],
            timeout=8,
            cwd=str(sadtalker_dir),
        )
        if not sadtalker_ready:
            sadtalker_message = "فایل‌ها وجود دارند، اما بعضی وابستگی‌های SadTalker ناقص‌اند: " + sadtalker_message

    avatar_engine_id = select_avatar_engine(bool(wsl_gpu and omni_ready), bool(sadtalker_ready))
    avatar_engine_label = {
        "omniavatar": "OmniAvatar GPU",
        "sadtalker_cpu": "SadTalker CPU",
    }.get(avatar_engine_id, "موتور آواتار نصب نیست")

    # Capability checks must be cheap: importing rembg/ONNX Runtime loads large native
    # libraries and made status refreshes sluggish on older CPU-only computers.
    from importlib import util as importlib_util
    from importlib.metadata import PackageNotFoundError, distribution

    try:
        tts_ready = importlib_util.find_spec("edge_tts") is not None
    except (ImportError, ValueError):
        tts_ready = False

    try:
        rembg_available = importlib_util.find_spec("rembg") is not None
        onnx_available = importlib_util.find_spec("onnxruntime") is not None
        distribution("pymatting")  # The frozen build must carry this metadata.
        rembg_ready = bool(rembg_available and onnx_available)
    except (PackageNotFoundError, ImportError, ValueError):
        # A frozen package can contain rembg's Python code without pymatting metadata.
        rembg_ready = False

    try:
        whisper_ready = importlib_util.find_spec("faster_whisper") is not None
    except (ImportError, ValueError):
        whisper_ready = False

    return {
        "app_home": str(APP_HOME),
        "ffmpeg": {"ready": ffmpeg_ok, "path": str(ffmpeg or ""), "version": ffmpeg_version, "subtitle_filter": subtitles_filter},
        "wsl": {"ready": wsl_ok, "gpu_ready": wsl_gpu, "message": wsl_message},
        "omniavatar": {"ready": omni_ready},
        "sadtalker": {"ready": sadtalker_ready, "message": sadtalker_message, "path": str(sadtalker_dir)},
        "avatar_engine": {
            "id": avatar_engine_id or "none",
            "label": avatar_engine_label,
            "ready": avatar_engine_id is not None,
        },
        "fashn": {"ready": fashn_ready},
        "body_completion": {"ready": body_ready},
        "tts": {"ready": tts_ready},
        "background_removal": {"ready": rembg_ready},
        "transcription": {"ready": whisper_ready},
        "daily_jobs": 20,
        "is_windows": os.name == "nt",
    }
