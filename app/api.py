from __future__ import annotations
import json
import os
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from fastapi import BackgroundTasks, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from app import db
from app.config import JOBS_DIR, OUTPUTS_DIR, STATIC_DIR
from app.pipeline import run_job
from app.security import ACCESS_TOKEN, token_matches
from app.services.runtime import get_runtime_status
from app.services.render import finalize_video
from app.validation import RESOLUTIONS, validate_form

app=FastAPI(title="RS ai",docs_url=None,redoc_url=None)
app.mount("/static",StaticFiles(directory=STATIC_DIR),name="static")

def _require_token(candidate:str|None)->None:
    if not token_matches(candidate):
        raise HTTPException(status_code=401,detail="توکن دسترسی معتبر نیست. برنامه را از RUN_RS-ai.bat باز کن یا توکن نصب را وارد کن.")

def _suffix(upload:UploadFile,fallback:str)->str:
    suffix=Path(upload.filename or "").suffix.lower()
    return suffix if suffix and suffix[1:].isalnum() and len(suffix)<=10 else fallback

def _ffmpeg_path()->str:
    candidate=os.getenv("RS_AI_FFMPEG") or shutil.which("ffmpeg")
    if not candidate and os.name=="nt":
        fallback=Path(r"C:\ffmpeg\bin\ffmpeg.exe")
        if fallback.is_file():candidate=str(fallback)
    return str(candidate) if candidate and Path(candidate).is_file() else ""

async def _save_upload(upload:UploadFile,dest:Path,max_bytes:int=120*1024*1024)->Path:
    total=0; dest.parent.mkdir(parents=True,exist_ok=True)
    try:
        with dest.open("wb") as stream:
            while True:
                chunk=await upload.read(1024*1024)
                if not chunk:break
                total+=len(chunk)
                if total>max_bytes:raise HTTPException(status_code=413,detail=f"حجم فایل از سقف مجاز {max_bytes//(1024*1024)} مگابایت بیشتر است.")
                stream.write(chunk)
    finally:await upload.close()
    if not total:
        dest.unlink(missing_ok=True);raise HTTPException(status_code=400,detail="فایل آپلودشده خالی است.")
    return dest

@app.get("/",response_class=HTMLResponse)
async def index()->HTMLResponse:
    path=STATIC_DIR/"index.html"
    if not path.is_file():raise HTTPException(status_code=500,detail="رابط کاربری پیدا نشد.")
    return HTMLResponse(path.read_text(encoding="utf-8"))

@app.get("/api/health")
async def health()->dict[str,Any]:
    return {"ok":True,"app":"RS-ai","version":"0.4.3","auth_required":True}

@app.get("/api/status")
async def status(x_rs_ai_token:str|None=Header(default=None))->dict[str,Any]:
    _require_token(x_rs_ai_token);return get_runtime_status()

@app.get("/api/jobs")
async def jobs(x_rs_ai_token:str|None=Header(default=None))->dict[str,Any]:
    _require_token(x_rs_ai_token)
    items=[{k:v for k,v in item.items() if k not in {"form","input_dir"}} for item in db.list_jobs(20)]
    return {"items":items,"today_count":db.count_jobs_today()}

@app.get("/api/jobs/{job_id}")
async def job_status(job_id:str,x_rs_ai_token:str|None=Header(default=None))->dict[str,Any]:
    _require_token(x_rs_ai_token);item=db.get_job(job_id)
    if not item:raise HTTPException(status_code=404,detail="پروژه پیدا نشد.")
    public={k:v for k,v in item.items() if k not in {"form","input_dir"}}
    public["download_url"]=f"/api/jobs/{job_id}/download" if item.get("status")=="completed" else None
    return public

@app.get("/api/jobs/{job_id}/download")
async def download_job(job_id:str,x_rs_ai_token:str|None=Header(default=None))->FileResponse:
    _require_token(x_rs_ai_token);item=db.get_job(job_id)
    if not item or item.get("status")!="completed" or not item.get("output_path"):raise HTTPException(status_code=404,detail="فایل نهایی هنوز آماده نیست.")
    path=Path(item["output_path"]).resolve()
    if not path.is_file():raise HTTPException(status_code=404,detail="فایل خروجی روی دیسک پیدا نشد.")
    return FileResponse(path,filename=path.name,media_type="video/mp4")

@app.get("/api/jobs/{job_id}/cloud-package")
async def download_cloud_package(job_id:str,x_rs_ai_token:str|None=Header(default=None))->FileResponse:
    _require_token(x_rs_ai_token)
    item=db.get_job(job_id)
    if not item or item.get("status")!="awaiting_cloud":
        raise HTTPException(status_code=404,detail="بستهٔ GPU ابری برای این پروژه آماده نیست.")
    path=Path(item["input_dir"])/"RS-ai-cloud-package.zip"
    if not path.is_file():
        raise HTTPException(status_code=404,detail="بستهٔ GPU ابری روی دیسک پیدا نشد.")
    return FileResponse(path,filename=f"RS-ai-cloud-{job_id[:8]}.zip",media_type="application/zip")

@app.post("/api/jobs/{job_id}/cloud-result")
async def import_cloud_result(
    job_id:str,
    video:UploadFile=File(...),
    x_rs_ai_token:str|None=Header(default=None),
)->dict[str,Any]:
    _require_token(x_rs_ai_token)
    item=db.get_job(job_id)
    if not item or item.get("status")!="awaiting_cloud":
        raise HTTPException(status_code=409,detail="این پروژه منتظر خروجی GPU ابری نیست.")
    if Path(video.filename or "").suffix.lower()!=".mp4":
        await video.close()
        raise HTTPException(status_code=400,detail="فایل خروجی GPU باید MP4 باشد.")
    job_dir=Path(item["input_dir"])
    raw_path=await _save_upload(video,job_dir/"cloud_avatar_motion.mp4",max_bytes=500*1024*1024)
    ffmpeg=_ffmpeg_path()
    if not ffmpeg:
        raise HTTPException(status_code=500,detail="FFmpeg پیدا نشد؛ مسیر RS_AI_FFMPEG یا C:\\ffmpeg\\bin\\ffmpeg.exe را بررسی کن.")
    ffprobe=Path(ffmpeg).with_name("ffprobe.exe" if ffmpeg.lower().endswith(".exe") else "ffprobe")
    probe_exe=str(ffprobe) if ffprobe.is_file() else (shutil.which("ffprobe") or "ffprobe")
    try:
        probe=subprocess.run([probe_exe,"-v","error","-show_entries","stream=codec_type","-of","csv=p=0",str(raw_path)],capture_output=True,text=True,timeout=30)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise HTTPException(status_code=400,detail="بررسی فایل MP4 ناموفق بود؛ مطمئن شو FFprobe همراه FFmpeg نصب است.") from exc
    if probe.returncode or "video" not in set((probe.stdout or "").splitlines()) or raw_path.stat().st_size<20_000:
        raise HTTPException(status_code=400,detail="فایل ارسالی ویدئوی معتبر نیست یا ناقص است.")
    form=item["form"]
    audio_path=job_dir/"spoken.mp3" if form.get("audio_source")=="tts" else Path(form.get("files",{}).get("audio",""))
    if not audio_path.is_file():
        raise HTTPException(status_code=400,detail="صدای اصلی پروژه پیدا نشد؛ این پروژه را دوباره آماده کن.")
    subtitle_path=job_dir/"captions.srt" if form.get("subtitles") and (job_dir/"captions.srt").is_file() else None
    output_dir_raw=str(form.get("output_directory","")).strip()
    output_dir=Path(output_dir_raw).expanduser() if output_dir_raw else OUTPUTS_DIR
    output_dir.mkdir(parents=True,exist_ok=True)
    timestamp=datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path=output_dir/f"RS-ai_{job_id[:8]}_{timestamp}.{form.get('video_format','mp4')}"
    db.update_job(job_id,status="running",progress=80,message="پردازش خروجی GPU ابری و همگام‌سازی صدا")
    try:
        final=finalize_video(raw_path,audio_path,subtitle_path,form["video_ratio"],form["video_format"],output_path,ffmpeg)
    except Exception as exc:
        db.update_job(job_id,status="awaiting_cloud",progress=65,message="پردازش فایل ابری ناموفق بود؛ فایل MP4 معتبر دیگری وارد کن.",error=str(exc))
        raise HTTPException(status_code=400,detail="پردازش خروجی ابری شکست خورد: "+str(exc)[-1200:]) from exc
    db.update_job(job_id,status="completed",progress=100,message="ویدئوی GPU ابری نهایی شد",output_path=str(final),error=None)
    return {"id":job_id,"status":"completed","output_path":str(final),"download_url":f"/api/jobs/{job_id}/download"}

@app.post("/api/jobs")
async def create_job(
    background_tasks:BackgroundTasks,
    x_rs_ai_token:str|None=Header(default=None),
    avatar:UploadFile=File(...), environment:UploadFile|None=File(default=None), audio:UploadFile|None=File(default=None),
    garment_upper:UploadFile|None=File(default=None), garment_lower:UploadFile|None=File(default=None), garment_onepiece:UploadFile|None=File(default=None),
    garment_upper_type:str=Form(default="model"),garment_lower_type:str=Form(default="model"),garment_onepiece_type:str=Form(default="model"),
    scenario:str=Form(default=""),language:str=Form(default="fa"),voice:str=Form(default="fa-IR-DilaraNeural"),audio_source:str=Form(default="tts"),
    body_mode:str=Form(default="keep"),clothing_mode:str=Form(default="current"),style:str=Form(default="professional"),movement:str=Form(default="natural"),
    engine_mode:str=Form(default="cloud"),subtitles:bool=Form(default=True),video_ratio:str=Form(default="9:16"),video_format:str=Form(default="mp4"),
    output_directory:str=Form(default=""),daily_limit:str=Form(default="20"),
)->dict[str,Any]:
    _require_token(x_rs_ai_token)
    if not avatar.filename:raise HTTPException(status_code=400,detail="عکس آواتار را انتخاب کن.")
    if audio_source=="upload" and (audio is None or not audio.filename):raise HTTPException(status_code=400,detail="روش صدای آپلودی انتخاب شده اما فایل صدا انتخاب نشده است.")
    if audio_source=="tts" and not scenario.strip():raise HTTPException(status_code=400,detail="برای تولید صدا از متن، سناریو را وارد کن.")
    if clothing_mode=="current" and any(f and f.filename for f in (garment_upper,garment_lower,garment_onepiece)):raise HTTPException(status_code=400,detail="وقتی لباس فعلی انتخاب شده، ورودی لباس جدید را پاک کن.")
    job_id=uuid.uuid4().hex;job_dir=JOBS_DIR/job_id;job_dir.mkdir(parents=True,exist_ok=True)
    files={"avatar":str(await _save_upload(avatar,job_dir/("avatar"+_suffix(avatar,".png"))))}
    if environment and environment.filename:files["environment"]=str(await _save_upload(environment,job_dir/("environment"+_suffix(environment,".jpg"))))
    if audio_source=="upload" and audio and audio.filename:files["audio"]=str(await _save_upload(audio,job_dir/("uploaded_audio"+_suffix(audio,".wav"))))
    garments={}
    if clothing_mode=="custom":
        for key,upload,photo_type in [("upper",garment_upper,garment_upper_type),("lower",garment_lower,garment_lower_type),("onepiece",garment_onepiece,garment_onepiece_type)]:
            if upload and upload.filename:
                if photo_type not in {"model","flat-lay"}:raise HTTPException(status_code=400,detail=f"نوع عکس لباس {key} معتبر نیست.")
                garments[key]={"path":str(await _save_upload(upload,job_dir/(f"garment_{key}"+_suffix(upload,".png")))),"photo_type":photo_type}
    form={"scenario":scenario.strip(),"language":language,"voice":voice,"audio_source":audio_source,"body_mode":body_mode,"clothing_mode":clothing_mode,"garments":garments,"style":style,"movement":movement,"engine_mode":engine_mode,"subtitles":bool(subtitles),"video_ratio":video_ratio,"video_format":video_format.lower(),"output_directory":output_directory.strip(),"daily_limit":daily_limit,"files":files}
    errors=validate_form(form)
    if errors:raise HTTPException(status_code=400,detail=" ".join(errors))
    if daily_limit=="20" and db.count_jobs_today()>=20:raise HTTPException(status_code=429,detail="سقف روزانهٔ ۲۰ پروژه پر شده است.")
    db.create_job(job_id,form,str(job_dir));background_tasks.add_task(run_job,job_id)
    return {"id":job_id,"status":"queued","message":"پروژه در صف ساخت قرار گرفت."}

@app.exception_handler(HTTPException)
async def http_exception_handler(request:Request,exc:HTTPException)->JSONResponse:
    detail=exc.detail if isinstance(exc.detail,str) else json.dumps(exc.detail,ensure_ascii=False)
    return JSONResponse(status_code=exc.status_code,content={"detail":detail})
