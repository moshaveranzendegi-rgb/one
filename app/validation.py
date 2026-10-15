from __future__ import annotations
from pathlib import Path
from typing import Any
ALLOWED_VIDEO_FORMATS={"mp4","mov","mkv","webm","avi"}
RESOLUTIONS={"9:16":(1080,1920),"4:5":(1080,1350),"1:1":(1080,1080),"16:9":(1920,1080),"4:3":(1440,1080),"3:4":(1080,1440)}
LANGUAGES={"fa","en","ru"}
VOICES={"fa":{"fa-IR-DilaraNeural","fa-IR-FaridNeural"},"en":{"en-US-JennyNeural","en-US-GuyNeural"},"ru":{"ru-RU-SvetlanaNeural","ru-RU-DmitryNeural"}}
GARMENT_CATEGORIES={"upper":"tops","lower":"bottoms","onepiece":"one-pieces"}
def validate_form(form:dict[str,Any])->list[str]:
    e=[]
    if not str(form.get("scenario","")).strip() and form.get("audio_source")!="upload":e.append("متن سناریو خالی است.")
    if form.get("language") not in LANGUAGES:e.append("زبان خروجی معتبر نیست.")
    if form.get("video_ratio") not in RESOLUTIONS:e.append("ابعاد ویدئو معتبر نیست.")
    if str(form.get("video_format","")).lower() not in ALLOWED_VIDEO_FORMATS:e.append("فرمت خروجی معتبر نیست.")
    if form.get("audio_source") not in {"tts","upload"}:e.append("روش صدا معتبر نیست.")
    if form.get("body_mode") not in {"keep","complete"}:e.append("حالت تکمیل بدن معتبر نیست.")
    if form.get("clothing_mode") not in {"current","custom"}:e.append("حالت لباس معتبر نیست.")
    if form.get("engine_mode","auto") not in {"cloud","auto","cpu"}:e.append("مسیر تولید آواتار معتبر نیست.")
    g=form.get("garments") or {}
    if form.get("clothing_mode")=="current" and any(g.values()):e.append("وقتی لباس فعلی انتخاب شده، ورودی لباس‌های جدید باید خالی باشد.")
    if g.get("onepiece") and (g.get("upper") or g.get("lower")):e.append("لباس یک‌تکه را نمی‌توان هم‌زمان با بالاتنه یا پایین‌تنه اعمال کرد.")
    if form.get("audio_source")=="tts" and form.get("voice") not in VOICES.get(form.get("language"),set()):e.append("صدای انتخاب‌شده با زبان خروجی سازگار نیست.")
    if form.get("daily_limit","20") not in {"20","unlimited"}:e.append("محدودیت روزانه معتبر نیست.")
    out=str(form.get("output_directory","")).strip()
    if "\x00" in out or len(out)>500:e.append("مسیر پوشهٔ خروجی معتبر نیست.")
    return e
def safe_suffix(filename:str|None,fallback:str)->str:
    s=Path(filename or "").suffix.lower();return s if s and len(s)<=10 and s[1:].isalnum() else fallback
