from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path


def _wsl_path(path: Path, wsl_executable: str, distro: str) -> str:
    result = subprocess.run([wsl_executable, "-d", distro, "--", "wslpath", "-a", str(path.resolve())], capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise RuntimeError(f"تبدیل مسیر برای WSL شکست خورد: {result.stderr.strip()}")
    return result.stdout.strip()


def apply_layer(person_path: Path, garment_path: Path, output_dir: Path, category: str, photo_type: str, job_dir: Path) -> Path:
    wsl = os.getenv("RS_AI_WSL", "wsl.exe")
    distro = os.getenv("RS_AI_WSL_DISTRO", "Ubuntu")
    fashn_dir = os.getenv("RS_AI_FASHN_DIR", "/opt/fashn-vton-1.5")
    venv_python = f"{fashn_dir}/.venv/bin/python"
    if photo_type not in {"model", "flat-lay"}:
        raise RuntimeError("نوع عکس لباس معتبر نیست.")
    if category not in {"tops", "bottoms", "one-pieces"}:
        raise RuntimeError("دستهٔ لباس توسط موتور مجازی پشتیبانی نمی‌شود.")
    person_wsl = _wsl_path(person_path, wsl, distro)
    garment_wsl = _wsl_path(garment_path, wsl, distro)
    output_wsl = _wsl_path(output_dir, wsl, distro)
    script = (
        f"cd {shlex.quote(fashn_dir)} && {shlex.quote(venv_python)} "
        f"examples/basic_inference.py --weights-dir ./weights "
        f"--person-image {shlex.quote(person_wsl)} "
        f"--garment-image {shlex.quote(garment_wsl)} "
        f"--category {shlex.quote(category)} "
        f"--garment-photo-type {shlex.quote(photo_type)} "
        f"--output-dir {shlex.quote(output_wsl)} --num-timesteps 30"
    )
    result = subprocess.run([wsl, "-d", distro, "--", "bash", "-lc", script], capture_output=True, text=True, timeout=1800)
    (job_dir / f"wardrobe-{category}.log").write_text((result.stdout or "") + "\n--- stderr ---\n" + (result.stderr or ""), encoding="utf-8", errors="replace")
    output = output_dir / "output_00.png"
    if result.returncode or not output.exists():
        tail = (result.stderr or result.stdout or "")[-1600:]
        raise RuntimeError("موتور تعویض لباس خروجی معتبر نساخت. بررسی کن FASHN VTON و وزن‌های آن نصب باشند. " + tail)
    stable = output_dir / f"person_after_{category.replace('-', '_')}.png"
    output.replace(stable)
    return stable
