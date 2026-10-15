from __future__ import annotations

import shutil
import sys
from pathlib import Path


def patch_file(path: Path, replacements: list[tuple[str, str, int]]) -> bool:
    if not path.is_file():
        raise FileNotFoundError(f"Required SadTalker file is missing: {path}")

    text = path.read_text(encoding="utf-8-sig")

    # Idempotency: if this engine file already has the RS ai preset, leave it intact.
    if path.name == "inference.py" and "RS_AI_SADTALKER_FPS" in text and "torch.set_num_threads(_CPU_THREADS)" in text:
        return False
    if path.name == "generate_batch.py" and "RS_AI_SADTALKER_FPS" in text:
        return False
    if path.name == "animate.py" and "_rsai_render_fps" in text and "frames * 1000.0 / render_fps" in text:
        return False

    original = text
    for old, new, count in replacements:
        occurrences = text.count(old)
        if occurrences < count:
            raise RuntimeError(
                f"Could not safely patch {path.name}: expected at least "
                f"{count} upstream code section(s), found {occurrences}."
            )
        text = text.replace(old, new, count)

    if text == original:
        return False

    backup = path.with_name(path.name + ".rsai-before-cpu-preset.bak")
    if not backup.exists():
        shutil.copy2(path, backup)

    # Python 3.8 compatible write (the isolated SadTalker runtime is Python 3.8).
    path.write_text(text, encoding="utf-8")
    print(f"PATCHED: {path}")
    return True


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: patch_sadtalker_cpu.py <SadTalker-engine-directory>", file=sys.stderr)
        return 2

    root = Path(sys.argv[1]).expanduser().resolve()
    inference = root / "inference.py"
    generate_batch = root / "src" / "generate_batch.py"
    animate = root / "src" / "facerender" / "animate.py"

    try:
        patch_file(
            inference,
            [
                (
                    "from glob import glob\nimport shutil\nimport torch\nfrom time import  strftime\nimport os, sys, time",
                    '''import os, sys, time
from glob import glob
import shutil
from time import strftime

# RS ai CPU preset for older Intel-only Windows PCs.
_DEFAULT_CPU_THREADS = min(2, os.cpu_count() or 2)
try:
    _CPU_THREADS = max(1, min(4, int(os.environ.get("RS_AI_SADTALKER_CPU_THREADS", _DEFAULT_CPU_THREADS))))
except (TypeError, ValueError):
    _CPU_THREADS = _DEFAULT_CPU_THREADS
os.environ.setdefault("RS_AI_SADTALKER_FPS", "8")
for _thread_env in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_thread_env, str(_CPU_THREADS))

import torch
try:
    torch.set_num_threads(_CPU_THREADS)
    torch.set_num_interop_threads(1)
except RuntimeError:
    pass
print(f"RS ai CPU preset: torch_threads={_CPU_THREADS}, render_fps={os.environ.get('RS_AI_SADTALKER_FPS', '8')}")''',
                    1,
                )
            ],
        )

        patch_file(
            generate_batch,
            [
                (
                    "    syncnet_mel_step_size = 16\n    fps = 25",
                    """    syncnet_mel_step_size = 16
    # Match audio/motion feature sampling to the lower CPU render frame rate.
    try:
        fps = max(8, min(25, int(os.environ.get('RS_AI_SADTALKER_FPS', '8'))))
    except (TypeError, ValueError):
        fps = 8""",
                    1,
                )
            ],
        )

        patch_file(
            animate,
            [
                (
                    "import os\nimport cv2",
                    """import os
import cv2


def _rsai_render_fps():
    try:
        return max(8, min(25, int(os.environ.get('RS_AI_SADTALKER_FPS', '8'))))
    except (TypeError, ValueError):
        return 8
""",
                    1,
                ),
                (
                    "        frame_num = x['frame_num']\n\n        predictions_video = make_animation(",
                    "        frame_num = x['frame_num']\n        render_fps = _rsai_render_fps()\n\n        predictions_video = make_animation(",
                    1,
                ),
                (
                    "imageio.mimsave(path, result,  fps=float(25))",
                    "imageio.mimsave(path, result, fps=float(render_fps))",
                    1,
                ),
                (
                    "end_time = start_time + frames*1/25*1000",
                    "end_time = start_time + frames * 1000.0 / render_fps",
                    1,
                ),
                (
                    "imageio.mimsave(enhanced_path, enhanced_images_gen_with_len, fps=float(25))",
                    "imageio.mimsave(enhanced_path, enhanced_images_gen_with_len, fps=float(render_fps))",
                    2,
                ),
            ],
        )
    except Exception as exc:
        print(f"CPU preset patch failed: {exc}", file=sys.stderr)
        return 1

    required = [
        (inference, "RS_AI_SADTALKER_FPS"),
        (inference, "torch.set_num_threads(_CPU_THREADS)"),
        (generate_batch, "RS_AI_SADTALKER_FPS"),
        (animate, "_rsai_render_fps"),
        (animate, "frames * 1000.0 / render_fps"),
    ]
    for path, marker in required:
        if marker not in path.read_text(encoding="utf-8-sig"):
            print(f"Verification failed: {marker!r} missing in {path}", file=sys.stderr)
            return 1

    print("SUCCESS: RS ai low-resource SadTalker preset is installed (2 CPU threads, 8 FPS by default).")
    print("Note: lower FPS reduces runtime but the mouth/face motion will be less smooth.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

[executed on device: DESKTOP-AG001JD (75030569-cef4-42ce-a3e2-0085550df642)]
