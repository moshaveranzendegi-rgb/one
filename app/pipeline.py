from __future__ import annotations

import json
import os
import shutil
import traceback
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

from app import db
from app.config import JOBS_DIR, OUTPUTS_DIR
from app.services.audio import make_tts, media_duration, normalize_audio, transcribe_audio
from app.services.avatar import generate_avatar
from app.services.engine_selection import resolve_engine_mode
from app.services.body_completion import complete_body
from app.services.render import finalize_video
from app.services.runtime import get_runtime_status
from app.services.scene import composite_scene
from app.services.wardrobe import apply_layer


def _log(job_dir: Path, message: str) -> None:
    with (job_dir / "pipeline.log").open("a", encoding="utf-8") as log:
        log.write(f"[{datetime.now().isoformat(timespec='seconds')}] {message}\n")


def _progress(job_id: str, job_dir: Path, value: int, message: str) -> None:
    db.update_job(job_id, progress=value, message=message)
    _log(job_dir, message)


def _environment_prompt(form: dict[str, Any]) -> str:
    style_map = {
        "professional": "professional presenter speaking naturally to camera, relaxed shoulders and clear deliberate hand gestures",
        "advertising": "confident product presenter with expressive but controlled gestures, energetic natural delivery",
        "educational": "warm teacher explaining a topic, calm head movement, clear hand gestures and friendly expression",
        "motivational": "engaging motivational speaker, expressive posture and natural purposeful gestures",
        "news": "credible news presenter, composed posture, restrained gestures, direct eye contact",
        "story": "expressive storyteller, emotionally appropriate facial expression and natural body language",
    }
    style = style_map.get(form.get("style", "professional"), style_map["professional"])
    movement = form.get("movement", "natural")
    extra = {
        "natural": "balanced natural full upper-body and arm motion, subtle head movement, preserve identity, realistic lip sync to the supplied speech",
        "expressive": "clearly visible but realistic arm and hand gestures, facial expression and head motion synchronized with speech, no exaggerated motion",
        "subtle": "subtle body sway, small hand gestures and gentle head movement while speaking, identity consistent",
    }.get(movement, "natural realistic speaking motion")
    context = str(form.get("scenario", "")).strip()
    context = context[:900].replace("@@", " ")
    return f"Photorealistic real person presenter, preserve the identity and facial appearance of the reference image. {style}. {extra}. Full coherent body motion; both hands anatomically plausible; stable camera; realistic lighting; no captions, no text, no logos. Spoken context: {context}"


def _check_image(path: Path, label: str) -> None:
    try:
        with Image.open(path) as img:
            img.verify()
    except Exception as exc:
        raise RuntimeError(f"فایل تصویر «{label}» خوانده نمی‌شود. یک JPG یا PNG معتبر انتخاب کن.") from exc


def run_job(job_id: str) -> None:
    job = db.get_job(job_id)
    if not job:
        return
    job_dir = Path(job["input_dir"])
    form = job["form"]
    try:
        db.update_job(job_id, status="running", progress=1, message="آماده‌سازی پروژه")
        status = get_runtime_status()
        ffmpeg = status["ffmpeg"]["path"]
        if not status["ffmpeg"]["ready"] or not ffmpeg:
            raise RuntimeError("FFmpeg نصب نیست یا مسیر آن نامعتبر است. ابتدا FFmpeg را نصب کن یا مسیر RS_AI_FFMPEG را تنظیم کن.")
        engine_info = status.get("avatar_engine", {})
        detected_engine = engine_info.get("id", "none")
        requested_engine = form.get("engine_mode", "auto")
        engine = resolve_engine_mode(requested_engine, detected_engine)
        if engine == "cloud" and (form.get("body_mode") == "complete" or (form.get("clothing_mode") == "custom" and any(form.get("garments", {}).get(k) for k in ("upper", "lower", "onepiece")))):
            raise RuntimeError("در مسیر GPU ابری آزمایشی، تکمیل بدن و تعویض لباس خودکار نیست. ابتدا «حفظ قاب موجود» و «لباس فعلی حفظ شود» را انتخاب کن.")
        if engine == "sadtalker_cpu":
            if form.get("body_mode") == "complete":
                raise RuntimeError("تکمیل بدن به مدل جداگانه نیاز دارد و در حالت SadTalker CPU فعال نیست؛ حالت بدن را روی «حفظ قاب موجود» بگذار.")
            garments = form.get("garments", {})
            if form.get("clothing_mode") == "custom" and any(garments.get(k) for k in ("upper", "lower", "onepiece")):
                raise RuntimeError("تعویض لباس با موتور GPU جداگانه انجام می‌شود و در حالت SadTalker CPU فعال نیست.")
        avatar = Path(form["files"]["avatar"])
        _check_image(avatar, "آواتار")
        environment = Path(form["files"]["environment"]) if form["files"].get("environment") else None
        if environment:
            _check_image(environment, "محیط")
        engine_label = {"omniavatar": "OmniAvatar GPU", "sadtalker_cpu": "SadTalker CPU (چهره و سر)", "cloud": "بستهٔ انتقال به GPU ابری"}.get(engine, "موتور آواتار")
        _progress(job_id, job_dir, 8, f"موتور انتخاب‌شده: {engine_label}")

        audio_file = job_dir / "spoken.mp3"
        subtitle_path: Path | None = None
        if form.get("subtitles"):
            subtitle_path = job_dir / "captions.srt"
        if form["audio_source"] == "tts":
            _progress(job_id, job_dir, 15, "تبدیل سناریو به گفتار")
            tts_backend = make_tts(
                form["scenario"], form["language"], form["voice"], audio_file, subtitle_path, ffmpeg
            )
            _log(job_dir, f"TTS backend selected: {tts_backend}")
            if tts_backend != "edge-tts":
                _progress(job_id, job_dir, 18, f"صدای جایگزین فعال شد: {tts_backend}")
        else:
            original = Path(form["files"]["audio"])
            if not original.exists():
                raise RuntimeError("فایل صدای آپلودشده پیدا نشد.")
            audio_file = original
            if subtitle_path:
                _progress(job_id, job_dir, 15, "تبدیل گفتار به زیرنویس زمان‌دار")
                transcribe_audio(audio_file, form["language"], subtitle_path)
        model_audio = job_dir / "audio_model_16k.wav"
        duration = normalize_audio(audio_file, model_audio, ffmpeg)
        if duration > 180.5:
            raise RuntimeError(f"مدت صدا {duration/60:.1f} دقیقه است؛ سقف این نسخه ۳ دقیقه است. صدا را کوتاه کن.")
        if duration < 0.5:
            raise RuntimeError("صدای ورودی خیلی کوتاه است.")
        _progress(job_id, job_dir, 24, f"مدت صدا: {duration:.1f} ثانیه")

        current_avatar = avatar
        if form.get("body_mode") == "complete":
            completed = job_dir / "avatar_fullbody.png"
            _progress(job_id, job_dir, 30, "تکمیل اختیاری بدن با مدل inpainting")
            current_avatar = complete_body(current_avatar, completed, job_dir)

        if form.get("clothing_mode") == "custom":
            garments = form.get("garments", {})
            layers = [("upper", "tops"), ("lower", "bottoms"), ("onepiece", "one-pieces")]
            for index, (key, category) in enumerate(layers):
                garment_data = garments.get(key)
                if not garment_data:
                    continue
                garment_path = Path(garment_data["path"])
                _check_image(garment_path, f"لباس {key}")
                if key == "onepiece" and (garments.get("upper") or garments.get("lower")):
                    raise RuntimeError("لباس یک‌تکه با بالاتنه/پایین‌تنه هم‌زمان قابل استفاده نیست.")
                _progress(job_id, job_dir, 34 + index * 5, f"تطبیق لباس: {key}")
                current_avatar = apply_layer(
                    current_avatar, garment_path, job_dir / f"wardrobe_{key}", category,
                    garment_data.get("photo_type", "model"), job_dir,
                )

        scene_image = job_dir / "scene_reference.png"
        _progress(job_id, job_dir, 48, "ترکیب آواتار با محیط انتخابی")
        composite_scene(current_avatar, environment, scene_image, form["video_ratio"])
        prompt = _environment_prompt(form)
        if engine == "cloud":
            _progress(job_id, job_dir, 60, "آماده‌سازی بستهٔ امن برای اجرای اختیاری روی GPU ابری")
            package_path = job_dir / "RS-ai-cloud-package.zip"
            manifest = {
                "app": "RS-ai", "job_id": job_id, "purpose": "avatar-motion-cloud-handoff",
                "audio_duration_seconds": duration, "language": form["language"],
                "video_ratio": form["video_ratio"], "video_format": form["video_format"],
                "subtitles_requested": bool(subtitle_path),
                "privacy_note": "This package contains the reference image and speech audio. Upload it to a cloud GPU only if you consent to that transfer."
            }
            with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(scene_image, "reference.png")
                archive.write(model_audio, "speech_16k.wav")
                archive.writestr("prompt.txt", prompt)
                archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
                if subtitle_path and subtitle_path.is_file():
                    archive.write(subtitle_path, "captions.srt")
            db.update_job(job_id, status="awaiting_cloud", progress=65, message="بسته آماده است؛ دانلود کن و فقط در صورت رضایت، در نشست GPU ابری اجرا کن.")
            _log(job_dir, f"CLOUD_PACKAGE_READY: {package_path}")
            return
        raw_video = generate_avatar(
            scene_image, model_audio, prompt, job_dir,
            lambda v, m: _progress(job_id, job_dir, v, m),
            engine=engine,
        )

        output_dir_raw = str(form.get("output_directory", "")).strip()
        output_dir = Path(output_dir_raw).expanduser() if output_dir_raw else OUTPUTS_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"RS-ai_{job_id[:8]}_{timestamp}.{form['video_format']}"
        _progress(job_id, job_dir, 80, "همگام‌سازی صدا، اندازه‌بندی و خروجی نهایی")
        final = finalize_video(raw_video, audio_file, subtitle_path, form["video_ratio"], form["video_format"], output_path, ffmpeg)
        manifest = {
            "app": "RS-ai",
            "job_id": job_id,
            "status": "completed",
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "language": form["language"],
            "duration_seconds": duration,
            "resolution": form["video_ratio"],
            "output_format": form["video_format"],
            "subtitles_burned_in": bool(subtitle_path),
            "source_audio": str(audio_file),
            "avatar_engine": "OmniAvatar 1.3B" if engine == "omniavatar" else "SadTalker CPU",
            "output": str(final),
            "notes": (
                ["OmniAvatar output is upscaled from its configured generation size to the selected social-media preset."]
                if engine == "omniavatar"
                else [
                    "SadTalker CPU mainly animates facial expression, lips and head; body and hand gestures are not fully generated.",
                    "The 256px CPU output is upscaled to the selected social-media preset; old CPUs may require substantial processing time.",
                ]
            ),
        }
        (job_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        db.update_job(job_id, status="completed", progress=100, message="ویدئو با موفقیت ساخته شد", output_path=str(final), error=None)
        _log(job_dir, f"FINISHED: {final}")
    except Exception as exc:
        message = str(exc) or exc.__class__.__name__
        try:
            db.update_job(job_id, status="failed", progress=100, message="ساخت ناموفق بود", error=message)
            _log(job_dir, "FAILED: " + message)
            (job_dir / "error.txt").write_text(message + "\n\n" + traceback.format_exc(), encoding="utf-8")
        except Exception:
            pass
