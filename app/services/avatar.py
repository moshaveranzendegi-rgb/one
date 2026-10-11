from __future__ import annotations

import os
import shutil
import shlex
import subprocess
from pathlib import Path


def _wsl_path(path: Path, wsl: str, distro: str) -> str:
    result = subprocess.run([wsl, "-d", distro, "--", "wslpath", "-a", str(path.resolve())], capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise RuntimeError(f"مسیر ورودی برای WSL قابل تبدیل نیست: {result.stderr.strip()}")
    return result.stdout.strip()


def generate_avatar(image_path: Path, audio_path: Path, prompt: str, job_dir: Path, progress=None) -> Path:
    wsl = os.getenv("RS_AI_WSL", "wsl.exe")
    distro = os.getenv("RS_AI_WSL_DISTRO", "Ubuntu")
    omni_dir = os.getenv("RS_AI_OMNIAVATAR_DIR", "/opt/OmniAvatar")
    image_wsl = _wsl_path(image_path, wsl, distro)
    audio_wsl = _wsl_path(audio_path, wsl, distro)
    input_file = job_dir / f"infer_samples_{job_dir.name}.txt"
    cleaned_prompt = " ".join(prompt.replace("@@", " ").split()).replace("\n", " ")
    input_file.write_text(f"{cleaned_prompt}@@{image_wsl}@@{audio_wsl}\n", encoding="utf-8")
    input_wsl = _wsl_path(input_file, wsl, distro)
    # Quote every externally-derived path for Bash. Windows profile names can contain
    # apostrophes; naïve single-quoting breaks commands and can alter argument parsing.
    command = (
        f"cd {shlex.quote(omni_dir)} && "
        f"source .venv/bin/activate && "
        f"torchrun --standalone --nproc_per_node=1 scripts/inference.py "
        f"--config configs/inference_1.3B.yaml --input_file {shlex.quote(input_wsl)}"
    )
    if progress:
        progress(55, "در حال تولید آواتار متحرک با OmniAvatar؛ این مرحله به GPU و مدل‌های نصب‌شده نیاز دارد.")
    result = subprocess.run([wsl, "-d", distro, "--", "bash", "-lc", command], capture_output=True, text=True, timeout=10_800)
    (job_dir / "omniavatar.log").write_text((result.stdout or "") + "\n--- stderr ---\n" + (result.stderr or ""), encoding="utf-8", errors="replace")
    if result.returncode:
        tail = (result.stderr or result.stdout or "")[-3000:]
        raise RuntimeError("OmniAvatar نتوانست ویدئوی متحرک بسازد. عکس ثابت جایگزین نمی‌شود. مطمئن شو WSL2، دسترسی GPU و مدل ۱٫۳B آماده‌اند. " + tail)
    # Official OmniAvatar stores results under demo_out/<model-name>/res_.../result_000.mp4.
    output_pattern = f"*/res_infer_samples_{job_dir.name}_*/result_000.mp4"
    find_command = (
        f"cd {shlex.quote(omni_dir)} && find \"$PWD/demo_out\" -type f "
        f"-path {shlex.quote(output_pattern)} -printf '%T@ %p\\n' 2>/dev/null "
        "| sort -nr | head -n 1 | cut -d' ' -f2-"
    )
    root_path = subprocess.run([wsl, "-d", distro, "--", "bash", "-lc", find_command], capture_output=True, text=True, timeout=30)
    if root_path.returncode or not root_path.stdout.strip():
        raise RuntimeError("OmniAvatar با موفقیت برگشت، اما فایل result_000.mp4 پیدا نشد؛ لاگ omniavatar.log را بررسی کن.")
    generated_wsl = root_path.stdout.strip()
    generated_win = subprocess.run([wsl, "-d", distro, "--", "wslpath", "-w", generated_wsl], capture_output=True, text=True, timeout=15)
    if generated_win.returncode:
        raise RuntimeError("تبدیل مسیر ویدئوی تولیدشده از WSL به Windows شکست خورد.")
    generated_path = Path(generated_win.stdout.strip())
    if not generated_path.exists() or generated_path.stat().st_size < 20_000:
        raise RuntimeError("فایل ویدئوی تولیدشده وجود ندارد یا ناقص است.")
    # Copy from the shared Windows/WSL folder so later stages never reference a moving demo_out folder.
    stable = job_dir / "avatar_motion_raw.mp4"
    shutil.copy2(generated_path, stable)
    return stable
