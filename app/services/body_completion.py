from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

from app.config import PROJECT_ROOT


def complete_body(image_path: Path, output_path: Path, job_dir: Path) -> Path:
    """Run an explicit inpainting stage in WSL2; never silently keep a cropped torso."""
    wsl = os.getenv("RS_AI_WSL", "wsl.exe")
    distro = os.getenv("RS_AI_WSL_DISTRO", "Ubuntu")
    tools_dir = os.getenv("RS_AI_WSL_TOOLS_DIR", "/opt/rs-ai-tools")
    src = subprocess.run([wsl, "-d", distro, "--", "wslpath", "-a", str(image_path.resolve())], capture_output=True, text=True, timeout=15)
    dst = subprocess.run([wsl, "-d", distro, "--", "wslpath", "-a", str(output_path.resolve())], capture_output=True, text=True, timeout=15)
    if src.returncode or dst.returncode:
        raise RuntimeError("مسیر تصویر برای تکمیل بدن در WSL قابل تبدیل نیست.")
    script_path = PROJECT_ROOT / "tools" / "complete_body.py"
    script_wsl = subprocess.run([wsl, "-d", distro, "--", "wslpath", "-a", str(script_path.resolve())], capture_output=True, text=True, timeout=15)
    if script_wsl.returncode:
        raise RuntimeError("فایل موتور تکمیل بدن در WSL قابل دسترسی نیست.")
    python_wsl = f"{tools_dir.rstrip('/')}/.venv/bin/python"
    command = (
        f"test -x {shlex.quote(python_wsl)} && {shlex.quote(python_wsl)} "
        f"{shlex.quote(script_wsl.stdout.strip())} "
        f"--input {shlex.quote(src.stdout.strip())} "
        f"--output {shlex.quote(dst.stdout.strip())}"
    )
    result = subprocess.run([wsl, "-d", distro, "--", "bash", "-lc", command], capture_output=True, text=True, timeout=1800)
    (job_dir / "body-completion.log").write_text((result.stdout or "") + "\n--- stderr ---\n" + (result.stderr or ""), encoding="utf-8", errors="replace")
    if result.returncode or not output_path.exists():
        tail = (result.stderr or result.stdout or "")[-1600:]
        raise RuntimeError("تکمیل بدن اجرا نشد یا مدل inpainting نصب نیست. برای نصب اختیاری، tools/setup_body_wsl.sh را اجرا کن. " + tail)
    return output_path
