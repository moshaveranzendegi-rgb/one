from __future__ import annotations

import asyncio
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

VOICE_DEFAULTS = {
    "fa": "fa-IR-DilaraNeural",
    "en": "en-US-JennyNeural",
    "ru": "ru-RU-SvetlanaNeural",
}


@dataclass
class AudioResult:
    source_path: Path
    model_wav_path: Path
    subtitle_path: Path | None
    duration_seconds: float
    warnings: list[str]


def _timestamp(seconds: float) -> str:
    seconds = max(0.0, seconds)
    total_ms = int(round(seconds * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


def write_srt(entries: list[tuple[float, float, str]], path: Path) -> None:
    lines: list[str] = []
    index = 1
    for start, end, text in entries:
        text = re.sub(r"\s+", " ", str(text)).strip()
        if not text:
            continue
        start = max(0.0, float(start))
        end = max(start + 0.25, float(end))
        lines.extend([str(index), f"{_timestamp(start)} --> {_timestamp(end)}", text, ""])
        index += 1
    if index == 1:
        raise RuntimeError("زیرنویس زمان‌دار تولید نشد.")
    path.write_text("\n".join(lines), encoding="utf-8-sig")


def _word_boundary_from_event(message: dict) -> tuple[float, float, str] | None:
    """Convert a current edge-tts WordBoundary stream event into seconds + word text."""
    if message.get("type") != "WordBoundary":
        return None
    start = float(message.get("offset", 0)) / 10_000_000
    duration = float(message.get("duration", 0)) / 10_000_000
    word = str(message.get("text", "")).strip()
    if not word:
        return None
    return start, start + max(0.0, duration), word


def _group_word_boundaries(words: list[tuple[float, float, str]]) -> list[tuple[float, float, str]]:
    groups: list[tuple[float, float, str]] = []
    active: list[tuple[float, float, str]] = []
    for word in words:
        active.append(word)
        value = word[2]
        duration = active[-1][1] - active[0][0]
        boundary = bool(re.search(r"[.!?؟،؛,:]$", value))
        if len(active) >= 7 or duration >= 3.8 or (boundary and len(active) >= 3):
            groups.append((active[0][0], active[-1][1] + 0.12, " ".join(x[2] for x in active).strip()))
            active = []
    if active:
        groups.append((active[0][0], active[-1][1] + 0.12, " ".join(x[2] for x in active).strip()))
    return groups


async def _edge_tts_stream(text: str, voice: str, audio_path: Path, subtitles_path: Path | None) -> None:
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError("موتور صدای رایگان Edge TTS نصب نیست. فایل install_tts.bat را اجرا کن؛ این موتور برای تبدیل متن به صدا به اینترنت نیاز دارد.") from exc
    # Explicitly request word events; the Edge TTS default may emit sentence boundaries only.
    communicate = edge_tts.Communicate(text=text, voice=voice, boundary="WordBoundary")
    words: list[tuple[float, float, str]] = []
    with audio_path.open("wb") as out:
        async for message in communicate.stream():
            if message.get("type") == "audio":
                out.write(message["data"])
            elif message.get("type") == "WordBoundary":
                timing = _word_boundary_from_event(message)
                if timing:
                    words.append(timing)
    if not audio_path.exists() or audio_path.stat().st_size < 1024:
        raise RuntimeError("تولید صدای گفتار ناموفق بود؛ سرویس صدا پاسخ معتبر نداد.")
    if subtitles_path:
        groups = _group_word_boundaries(words)
        write_srt(groups, subtitles_path)


def make_tts(text: str, language: str, voice: str, audio_path: Path, subtitles_path: Path | None) -> None:
    asyncio.run(_edge_tts_stream(text, voice or VOICE_DEFAULTS[language], audio_path, subtitles_path))


def _run_ffmpeg(ffmpeg: str, args: list[str]) -> None:
    result = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", *args], capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError("تبدیل صدا با FFmpeg شکست خورد: " + (result.stderr or "خطای ناشناخته")[-1200:])


def normalize_audio(source: Path, destination: Path, ffmpeg: str) -> float:
    _run_ffmpeg(ffmpeg, ["-i", str(source), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(destination)])
    return media_duration(source, ffmpeg)


def media_duration(path: Path, ffmpeg: str) -> float:
    ffprobe = Path(ffmpeg).with_name("ffprobe.exe" if ffmpeg.lower().endswith(".exe") else "ffprobe")
    executable = str(ffprobe) if ffprobe.exists() else "ffprobe"
    result = subprocess.run([executable, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)], capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError("مدت فایل صدا قابل تشخیص نیست؛ FFprobe را بررسی کن.")
    try:
        duration = float(result.stdout.strip())
    except ValueError as exc:
        raise RuntimeError("مدت فایل صدا نامعتبر است.") from exc
    if duration <= 0:
        raise RuntimeError("مدت صدا صفر است.")
    return duration


def transcribe_audio(audio_path: Path, language: str, subtitles_path: Path) -> None:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("برای زیرنویس دقیقِ صدای آپلودشده، ماژول Whisper نصب نیست. ابتدا install_captions.bat را اجرا کن؛ ساخت ویدئو بدون زیرنویس جعلی متوقف شد.") from exc
    # CPU int8 is the most compatible default. Users can configure a GPU model later if needed.
    try:
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, info = model.transcribe(str(audio_path), language=language, vad_filter=True, word_timestamps=False)
        entries = [(seg.start, seg.end, seg.text.strip()) for seg in segments if seg.text.strip()]
        if not entries:
            raise RuntimeError("از صدای ورودی متنی قابل استفاده برای زیرنویس پیدا نشد.")
        write_srt(entries, subtitles_path)
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"رونویسی صدا برای زیرنویس شکست خورد: {exc}") from exc
