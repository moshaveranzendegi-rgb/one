from __future__ import annotations

import subprocess
from pathlib import Path

from app.validation import RESOLUTIONS

CODECS = {
    "mp4": ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"],
    "mov": ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "192k"],
    "mkv": ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "192k"],
    "webm": ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-c:a", "libopus", "-b:a", "128k"],
    "avi": ["-c:v", "mpeg4", "-q:v", "3", "-c:a", "libmp3lame", "-q:a", "2"],
}


def _escape_filter_path(path: Path) -> str:
    # Escape characters special to FFmpeg filter syntax, notably Windows drive colons.
    value = path.resolve().as_posix().replace("'", r"\'").replace(":", r"\:")
    return value


def finalize_video(raw_video: Path, source_audio: Path, subtitles: Path | None, ratio: str, output_format: str, output_path: Path, ffmpeg: str) -> Path:
    width, height = RESOLUTIONS[ratio]
    # Blur-fill preserves the entire presenter instead of cropping feet/head; this is upscaled from 480p AI output.
    vf = (
        f"split[bg][fg];"
        f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},boxblur=24:12[bg2];"
        f"[fg]scale={width}:{height}:force_original_aspect_ratio=decrease[fg2];"
        f"[bg2][fg2]overlay=(W-w)/2:(H-h)/2,setsar=1,fps=25"
    )
    if subtitles:
        sub_path = _escape_filter_path(subtitles)
        # libass performs Unicode shaping for Persian/Arabic where available.
        vf += f",subtitles='{sub_path}':force_style='FontName=Tahoma,FontSize=26,Outline=2,Shadow=0,Alignment=2,MarginV=52,PrimaryColour=&H00FFFFFF'"
    vf += "[outv]"
    args = ["-hide_banner", "-loglevel", "error", "-y", "-i", str(raw_video), "-i", str(source_audio), "-filter_complex", vf, "-map", "[outv]", "-map", "1:a:0", "-shortest", *CODECS[output_format], str(output_path)]
    result = subprocess.run([ffmpeg, *args], capture_output=True, text=True, timeout=10_800)
    if result.returncode:
        detail = (result.stderr or "")[-2000:]
        if subtitles and ("No such filter: 'subtitles'" in detail or "subtitles" in detail.lower() and "filter" in detail.lower()):
            raise RuntimeError("نسخهٔ FFmpeg فیلتر زیرنویس ندارد. یک build از FFmpeg با libass نصب کن؛ ویدئو بدون زیرنویس تحویل داده نمی‌شود.")
        raise RuntimeError("ساخت فایل نهایی و همگام‌سازی صدا شکست خورد: " + detail)
    if not output_path.exists() or output_path.stat().st_size < 5_000:
        raise RuntimeError("فایل نهایی تولید نشده یا ناقص است.")
    ffprobe = Path(ffmpeg).with_name("ffprobe.exe" if ffmpeg.lower().endswith(".exe") else "ffprobe")
    probe = subprocess.run(
        [str(ffprobe) if ffprobe.exists() else "ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(output_path)],
        capture_output=True, text=True, timeout=30,
    )
    stream_types = set((probe.stdout or "").splitlines())
    if probe.returncode or "video" not in stream_types or "audio" not in stream_types:
        raise RuntimeError("اعتبارسنجی فایل خروجی تأیید نکرد که هم صدا و هم تصویر در آن وجود دارد.")
    return output_path
