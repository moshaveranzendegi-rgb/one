from __future__ import annotations

import os
import shutil
import shlex
import subprocess
from pathlib import Path

from app.config import APP_HOME


def _wsl_path(path: Path, wsl: str, distro: str) -> str:
    result = subprocess.run([wsl, "-d", distro, "--", "wslpath", "-a", str(path.resolve())], capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise RuntimeError(f"مسیر ورودی برای WSL قابل تبدیل نیست: {result.stderr.strip()}")
    return result.stdout.strip()


def _generate_omniavatar(image_path: Path, audio_path: Path, prompt: str, job_dir: Path, progress=None) -> Path:
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


def _generate_sadtalker_cpu(image_path: Path, audio_path: Path, job_dir: Path, progress=None) -> Path:
    """Animate a full-frame portrait with CPU inference; mainly face/lips/head, not full-body gestures."""
    root = Path(os.getenv("RS_AI_SADTALKER_DIR", str(APP_HOME / "engines" / "SadTalker"))).expanduser().resolve()
    python = root / ".venv" / "Scripts" / "python.exe"
    inference = root / "inference.py"
    checkpoint_dir = root / "checkpoints"
    needed = [
        python, inference,
        checkpoint_dir / "SadTalker_V0.0.2_256.safetensors",
        checkpoint_dir / "mapping_00109-model.pth.tar",
    ]
    missing = [str(path) for path in needed if not path.is_file()]
    if missing:
        raise RuntimeError(
            "موتور SadTalker CPU یا وزن‌های آن نصب نیست. فایل tools\\setup_sadtalker_cpu.bat را اجرا کن. "
            "فایل‌های مفقود: " + ", ".join(missing[:4])
        )

    result_dir = (job_dir / "sadtalker_results").resolve()
    result_dir.mkdir(parents=True, exist_ok=True)
    command = [
        str(python), str(inference),
        "--driven_audio", str(audio_path.resolve()),
        "--source_image", str(image_path.resolve()),
        "--result_dir", str(result_dir),
        "--checkpoint_dir", str(checkpoint_dir),
        "--cpu", "--size", "256", "--batch_size", "1", "--preprocess", "full",
    ]
    if progress:
        progress(55, "SadTalker در حال متحرک‌سازی چهره و سر روی CPU است؛ روی پردازندهٔ قدیمی ممکن است زمان‌بر باشد.")
    try:
        result = subprocess.run(
            command, cwd=str(root), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=10_800,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("اجرای SadTalker بیش از ۳ ساعت طول کشید و متوقف شد. ابتدا یک صدای کوتاه‌تر آزمایش کن.") from exc
    log_text = (result.stdout or "") + "\n--- stderr ---\n" + (result.stderr or "")
    (job_dir / "sadtalker.log").write_text(log_text, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError("SadTalker نتوانست ویدئو بسازد؛ جزئیات در sadtalker.log قرار دارد. " + log_text[-3500:])

    outputs = sorted((p for p in result_dir.rglob("*.mp4") if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)
    if not outputs:
        raise RuntimeError("SadTalker بدون گزارش خطا پایان یافت، اما MP4 خروجی پیدا نشد؛ sadtalker.log را بررسی کن.")
    generated = outputs[0]
    if generated.stat().st_size < 20_000:
        raise RuntimeError("فایل خروجی SadTalker خیلی کوچک یا ناقص است.")
    stable = job_dir / "avatar_motion_raw.mp4"
    shutil.copy2(generated, stable)
    return stable


def generate_avatar(
    image_path: Path,
    audio_path: Path,
    prompt: str,
    job_dir: Path,
    progress=None,
    engine: str = "omniavatar",
) -> Path:
    """Run the engine explicitly selected by runtime hardware/model checks."""
    if engine == "omniavatar":
        return _generate_omniavatar(image_path, audio_path, prompt, job_dir, progress)
    if engine == "sadtalker_cpu":
        return _generate_sadtalker_cpu(image_path, audio_path, job_dir, progress)
    raise RuntimeError(
        "هیچ موتور آواتاری آماده نیست. روی سیستم بدون GPU انویدیا، "
        "tools\\setup_sadtalker_cpu.bat را اجرا کن."
    )
