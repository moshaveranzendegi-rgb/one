from __future__ import annotations
import json
import uuid
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
from app.validation import RESOLUTIONS, validate_form

app=FastAPI(title="RS ai",docs_url=None,redoc_url=None)
app.mount("/static",StaticFiles(directory=STATIC_DIR),name="static")

def _require_token(candidate:str|None)->None:
    if not token_matches(candidate):
        raise HTTPException(status_code=401,detail="توکن دسترسی معتبر نیست. برنامه را از RUN_RS-ai.bat باز کن یا توکن نصب را وارد کن.")

def _suffix(upload:UploadFile,fallback:str)->str:
    suffix=Path(upload.filename or "").suffix.lower()
    return suffix if suffix and suffix[1:].isalnum() and len(suffix)<=10 else fallback

async def _save_upload(upload:UploadFile,dest:Path,max_bytes:int=120*1024*1024)->Path:
    total=0; dest.parent.mkdir(parents=True,exist_ok=True)
    try:
        with dest.open("wb") as stream:
            while True:
                chunk=await upload.read(1024*1024)
                if not chunk:break
                total+=len(chunk)
                if total>max_bytes:raise HTTPException(status_code=413,detail="حجم یکی از فایل‌ها بیشتر از ۱۲۰ مگابایت است.")
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
    return {"ok":True,"app":"RS-ai","version":"0.2.0","auth_required":True}

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

@app.post("/api/jobs")
async def create_job(
    background_tasks:BackgroundTasks,
    x_rs_ai_token:str|None=Header(default=None),
    avatar:UploadFile=File(...), environment:UploadFile|None=File(default=None), audio:UploadFile|None=File(default=None),
    garment_upper:UploadFile|None=File(default=None), garment_lower:UploadFile|None=File(default=None), garment_onepiece:UploadFile|None=File(default=None),
    garment_upper_type:str=Form(default="model"),garment_lower_type:str=Form(default="model"),garment_onepiece_type:str=Form(default="model"),
    scenario:str=Form(default=""),language:str=Form(default="fa"),voice:str=Form(default="fa-IR-DilaraNeural"),audio_source:str=Form(default="tts"),
    body_mode:str=Form(default="keep"),clothing_mode:str=Form(default="current"),style:str=Form(default="professional"),movement:str=Form(default="natural"),
    subtitles:bool=Form(default=True),video_ratio:str=Form(default="9:16"),video_format:str=Form(default="mp4"),
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
    form={"scenario":scenario.strip(),"language":language,"voice":voice,"audio_source":audio_source,"body_mode":body_mode,"clothing_mode":clothing_mode,"garments":garments,"style":style,"movement":movement,"subtitles":bool(subtitles),"video_ratio":video_ratio,"video_format":video_format.lower(),"output_directory":output_directory.strip(),"daily_limit":daily_limit,"files":files}
    errors=validate_form(form)
    if errors:raise HTTPException(status_code=400,detail=" ".join(errors))
    if daily_limit=="20" and db.count_jobs_today()>=20:raise HTTPException(status_code=429,detail="سقف روزانهٔ ۲۰ پروژه پر شده است.")
    db.create_job(job_id,form,str(job_dir));background_tasks.add_task(run_job,job_id)
    return {"id":job_id,"status":"queued","message":"پروژه در صف ساخت قرار گرفت."}

@app.exception_handler(HTTPException)
async def http_exception_handler(request:Request,exc:HTTPException)->JSONResponse:
    detail=exc.detail if isinstance(exc.detail,str) else json.dumps(exc.detail,ensure_ascii=False)
    return JSONResponse(status_code=exc.status_code,content={"detail":detail})
