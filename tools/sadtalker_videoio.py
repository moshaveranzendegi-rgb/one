import os
import shutil
import subprocess
import uuid

import cv2


def load_video_to_cv2(input_path):
    video_stream = cv2.VideoCapture(input_path)
    full_frames = []
    while True:
        still_reading, frame = video_stream.read()
        if not still_reading:
            video_stream.release()
            break
        full_frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    return full_frames


def _ffmpeg_executable():
    """Resolve FFmpeg reliably even when a frozen Windows app was launched directly."""
    candidates = [
        os.environ.get("RS_AI_FFMPEG"),
        shutil.which("ffmpeg"),
        r"C:\\ffmpeg\\bin\\ffmpeg.exe" if os.name == "nt" else None,
    ]
    for candidate in candidates:
        if not candidate:
            continue
        candidate = os.path.expandvars(os.path.expanduser(candidate))
        if os.path.isfile(candidate):
            return candidate
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise FileNotFoundError(
        "FFmpeg executable was not found. Set RS_AI_FFMPEG or add C:\\ffmpeg\\bin to PATH."
    )


def _run_ffmpeg(executable, arguments):
    completed = subprocess.run(
        [executable, *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "No FFmpeg diagnostic output").strip()
        raise RuntimeError("FFmpeg failed (exit %s): %s" % (completed.returncode, detail[-4000:]))


def save_video_with_watermark(video, audio, save_path, watermark=False):
    executable = _ffmpeg_executable()
    output_dir = os.path.dirname(os.path.abspath(save_path))
    os.makedirs(output_dir, exist_ok=True)
    temp_file = os.path.join(output_dir, ".sadtalker-" + str(uuid.uuid4()) + ".mp4")

    try:
        _run_ffmpeg(executable, [
            "-y", "-hide_banner", "-loglevel", "error",
            "-i", os.path.abspath(video),
            "-i", os.path.abspath(audio),
            "-vcodec", "copy", temp_file,
        ])
        if not os.path.isfile(temp_file) or os.path.getsize(temp_file) == 0:
            raise RuntimeError("FFmpeg returned without creating the temporary MP4.")

        if watermark is False:
            os.replace(temp_file, save_path)
            return

        try:
            import webui
            from modules import paths
            watermark_path = os.path.join(
                paths.script_path, "extensions", "SadTalker", "docs", "sadtalker_logo.png"
            )
        except Exception:
            dir_path = os.path.dirname(os.path.realpath(__file__))
            watermark_path = os.path.abspath(
                os.path.join(dir_path, "..", "..", "docs", "sadtalker_logo.png")
            )

        if not os.path.isfile(watermark_path):
            raise FileNotFoundError("SadTalker watermark image was not found: " + watermark_path)

        _run_ffmpeg(executable, [
            "-y", "-hide_banner", "-loglevel", "error",
            "-i", temp_file,
            "-i", watermark_path,
            "-filter_complex", "[1]scale=100:-1[wm];[0][wm]overlay=(main_w-overlay_w)-10:10",
            save_path,
        ])
        if not os.path.isfile(save_path) or os.path.getsize(save_path) == 0:
            raise RuntimeError("FFmpeg did not create the watermarked MP4.")
    finally:
        if os.path.isfile(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass
