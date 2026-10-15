from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

VOICE_DEFAULTS = {
    "fa": "fa-IR-DilaraNeural",
    "en": "en-US-JennyNeural",
    "ru": "ru-RU-SvetlanaNeural",
}

# Mana Persian Piper voice: pinned model, downloaded on first offline fallback.
_MANA_REVISION = "737756257ce0c614f9147a48ce2936ffc0e24cd6"
_MANA_MODEL_BYTES = 63_531_379
_MANA_MODEL_SHA256 = "e390c0e74ba71fd97c49ba662ee0c6e1724b462ba2d4561698af4f564840f126"
_MANA_BASE_URL = f"https://huggingface.co/MahtaFetrat/Mana-Persian-Piper/resolve/{_MANA_REVISION}"


def _download_voice_file(
    url: str,
    destination: Path,
    *,
    max_bytes: int,
    expected_bytes: int | None = None,
    expected_sha256: str | None = None,
    require_json: bool = False,
) -> None:
    """Download a model/config safely to a temporary file, verify it, then atomically replace."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".download")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "RS-ai/0.4.9 (Persian voice setup)"},
    )
    last_error: Exception | None = None
    for attempt in range(2):
        digest = hashlib.sha256()
        total = 0
        try:
            with urllib.request.urlopen(request, timeout=20) as response, partial.open("wb") as stream:
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    total += len(block)
                    if total > max_bytes:
                        raise RuntimeError(f"Voice asset exceeded safe download limit ({max_bytes} bytes).")
                    stream.write(block)
                    digest.update(block)
            if expected_bytes is not None and total != expected_bytes:
                raise RuntimeError(f"Voice model size mismatch: got {total}, expected {expected_bytes} bytes.")
            if expected_sha256 and digest.hexdigest().lower() != expected_sha256.lower():
                raise RuntimeError("Voice model SHA-256 verification failed.")
            if total < 100:
                raise RuntimeError("Voice asset download was unexpectedly small.")
            if require_json:
                parsed = json.loads(partial.read_text(encoding="utf-8"))
                if not isinstance(parsed, dict):
                    raise RuntimeError("Voice configuration JSON is not an object.")
            os.replace(partial, destination)
            return
        except Exception as exc:
            last_error = exc
            partial.unlink(missing_ok=True)
            if attempt == 0:
                time.sleep(0.5)
    raise RuntimeError(f"Could not download/verify {destination.name}: {last_error}") from last_error


def _ensure_mana_voice(voices_dir: Path) -> tuple[Path, Path]:
    model = voices_dir / "fa_IR-mana-medium.onnx"
    config = voices_dir / "fa_IR-mana-medium.onnx.json"

    def valid_model() -> bool:
        if not model.is_file() or model.stat().st_size != _MANA_MODEL_BYTES:
            return False
        digest = hashlib.sha256()
        with model.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest().lower() == _MANA_MODEL_SHA256

    if not valid_model():
        _download_voice_file(
            f"{_MANA_BASE_URL}/fa_IR-mana-medium.onnx?download=true",
            model,
            max_bytes=80_000_000,
            expected_bytes=_MANA_MODEL_BYTES,
            expected_sha256=_MANA_MODEL_SHA256,
        )
    config_valid = False
    if config.is_file():
        try:
            config_valid = isinstance(json.loads(config.read_text(encoding="utf-8")), dict)
        except (OSError, UnicodeError, json.JSONDecodeError):
            config_valid = False
    if not config_valid:
        _download_voice_file(
            f"{_MANA_BASE_URL}/fa_IR-mana-medium.onnx.json?download=true",
            config,
            max_bytes=200_000,
            require_json=True,
        )
    return model, config


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
        raise RuntimeError("موتور صدای Edge TTS نصب نیست.") from exc
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
        raise RuntimeError("تولید صدای Edge TTS ناموفق بود؛ سرویس صدا پاسخ معتبر نداد.")
    if subtitles_path:
        groups = _group_word_boundaries(words)
        if groups:
            write_srt(groups, subtitles_path)


def _caption_chunks(text: str) -> list[str]:
    tokens = re.split(r"\s+", text.strip())
    chunks: list[str] = []
    active: list[str] = []
    for token in tokens:
        if not token:
            continue
        if active and (len(active) >= 7 or len(" ".join(active)) + len(token) + 1 > 44):
            chunks.append(" ".join(active))
            active = []
        active.append(token)
        if len(active) >= 3 and re.search(r"[.!?؟،؛,:]$", token):
            chunks.append(" ".join(active))
            active = []
    if active:
        chunks.append(" ".join(active))
    return chunks


def _write_fallback_subtitles(
    text: str,
    audio_path: Path,
    subtitles_path: Path | None,
    ffmpeg: str | None,
) -> None:
    if not subtitles_path:
        return
    chunks = _caption_chunks(text)
    if not chunks:
        return
    duration = 0.0
    if ffmpeg:
        try:
            duration = media_duration(audio_path, ffmpeg)
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError):
            duration = 0.0
    if duration <= 0:
        # Last-resort estimate only used if ffprobe itself is unavailable.
        duration = max(1.0, len(text) / 12.0)
    weights = [max(1, len(chunk)) for chunk in chunks]
    total_weight = sum(weights)
    entries: list[tuple[float, float, str]] = []
    cursor = 0.0
    for index, (chunk, weight) in enumerate(zip(chunks, weights)):
        end = duration if index == len(chunks) - 1 else cursor + duration * weight / total_weight
        entries.append((cursor, end, chunk))
        cursor = end
    write_srt(entries, subtitles_path)


def _piper_length_scale() -> float:
    """A modest faster speech rate for the offline Persian voice; configurable for testing."""
    try:
        value = float(os.getenv("RS_AI_PIPER_LENGTH_SCALE", "0.92"))
    except (TypeError, ValueError):
        value = 0.92
    return max(0.80, min(1.15, value))


def _piper_fallback(
    text: str,
    audio_path: Path,
    subtitles_path: Path | None,
    ffmpeg: str | None,
) -> str:
    """Prefer the Mana Persian voice; fall back to the installed Amir voice if unavailable."""
    app_data = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    engine_dir = app_data / "RS-ai" / "engines" / "PiperTTS"
    piper = engine_dir / ".venv" / "Scripts" / "piper.exe"
    voices_dir = engine_dir / "voices"
    if not piper.is_file():
        raise RuntimeError("برنامهٔ Piper نصب نیست؛ ابتدا موتور TTS آفلاین را نصب کن.")

    mana_error: Exception | None = None
    voice_name = "fa_IR-mana-medium"
    try:
        model, config = _ensure_mana_voice(voices_dir)
    except Exception as exc:
        mana_error = exc
        voice_name = "fa_IR-amir-medium"
        model = voices_dir / "fa_IR-amir-medium.onnx"
        config = voices_dir / "fa_IR-amir-medium.onnx.json"
        if not all(path.is_file() for path in (model, config)):
            raise RuntimeError(
                "مدل فارسی Mana دانلود/اعتبارسنجی نشد و مدل قدیمی Amir هم نصب نیست. "
                f"جزئیات مدل Mana: {exc}"
            ) from exc

    encoder = ffmpeg or os.getenv("RS_AI_FFMPEG") or shutil.which("ffmpeg")
    if not encoder and os.name == "nt":
        candidate = Path(r"C:\ffmpeg\bin\ffmpeg.exe")
        if candidate.is_file():
            encoder = str(candidate)
    if not encoder:
        raise RuntimeError("برای تبدیل صدای آفلاین Piper به MP3، FFmpeg پیدا نشد.")
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    timeout = max(120, min(900, 60 + int(len(text) * 0.3)))
    with tempfile.TemporaryDirectory(prefix="rsai-piper-", dir=str(audio_path.parent)) as temp:
        text_file = Path(temp) / "speech.txt"
        wav_file = Path(temp) / "speech.wav"
        text_file.write_text(text, encoding="utf-8")
        result = subprocess.run(
            [
                str(piper), "--model", str(model), "--config", str(config),
                "--length_scale", str(_piper_length_scale()),
                "--input_file", str(text_file), "--output_file", str(wav_file),
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, check=False, cwd=str(engine_dir),
        )
        if result.returncode != 0 or not wav_file.is_file() or wav_file.stat().st_size < 1024:
            detail = (result.stderr or result.stdout or "Piper هیچ صدایی تولید نکرد").strip()[-500:]
            raise RuntimeError("ساخت صدای آفلاین فارسی ناموفق بود: " + detail)
        _run_ffmpeg(
            str(encoder),
            ["-i", str(wav_file), "-vn", "-codec:a", "libmp3lame", "-q:a", "4", str(audio_path)],
        )
    if not audio_path.is_file() or audio_path.stat().st_size < 1024:
        raise RuntimeError("فایل MP3 خروجی Piper ساخته نشد.")
    _write_fallback_subtitles(text, audio_path, subtitles_path, str(encoder))
    if mana_error:
        return f"{voice_name}; Mana unavailable ({type(mana_error).__name__})"
    return voice_name


def _gtts_fallback(
    text: str,
    language: str,
    audio_path: Path,
    subtitles_path: Path | None,
    ffmpeg: str | None,
) -> None:
    """Use Google Translate TTS for English/Russian if Edge TTS is refusing connections."""
    if language not in {"en", "ru"}:
        raise RuntimeError("Google TTS جایگزین مناسبی برای این زبان نیست.")
    try:
        from gtts import gTTS
    except ImportError as exc:
        raise RuntimeError("بستهٔ جایگزین gTTS نصب نیست.") from exc
    gTTS(text=text, lang=language, slow=False).save(str(audio_path))
    if not audio_path.is_file() or audio_path.stat().st_size < 1024:
        raise RuntimeError("سرویس جایگزین گفتار فایل صوتی معتبر نداد.")
    _write_fallback_subtitles(text, audio_path, subtitles_path, ffmpeg)


def make_tts(
    text: str,
    language: str,
    voice: str,
    audio_path: Path,
    subtitles_path: Path | None,
    ffmpeg: str | None = None,
) -> str:
    language = (language or "fa").lower().split("-")[0]
    selected_voice = voice or VOICE_DEFAULTS.get(language, VOICE_DEFAULTS["fa"])
    try:
        asyncio.run(_edge_tts_stream(text, selected_voice, audio_path, subtitles_path))
        return "edge-tts"
    except Exception as edge_error:
        # A failed WebSocket may have left an incomplete MP3/SRT behind.
        audio_path.unlink(missing_ok=True)
        if subtitles_path:
            subtitles_path.unlink(missing_ok=True)
        edge_error_name = type(edge_error).__name__
        if language not in {"fa", "en", "ru"}:
            raise RuntimeError(
                f"سرویس Microsoft Edge TTS برای زبان {language} شکست خورد و جایگزینی تنظیم نشده است."
            ) from edge_error

        try:
            if language == "fa":
                # Google Translate TTS does not support Persian; use a Persian Piper model.
                voice_used = _piper_fallback(text, audio_path, subtitles_path, ffmpeg)
                return f"piper-{voice_used} (offline fallback; Edge TTS={edge_error_name})"
            _gtts_fallback(text, language, audio_path, subtitles_path, ffmpeg)
            return f"gTTS-{language} (online fallback; Edge TTS={edge_error_name})"
        except Exception as fallback_error:
            audio_path.unlink(missing_ok=True)
            if subtitles_path:
                subtitles_path.unlink(missing_ok=True)
            raise RuntimeError(
                "سرویس Microsoft Edge TTS شکست خورد و جایگزین گفتار نیز ناموفق بود: "
                f"{fallback_error}. راه موقت: منبع صدا را روی «آپلود فایل صوتی» بگذار."
            ) from fallback_error


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
