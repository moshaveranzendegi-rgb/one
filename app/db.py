from __future__ import annotations
import json,sqlite3
from datetime import datetime,timezone
from typing import Any
from app.config import DB_PATH
def utc_now()->str:return datetime.now(timezone.utc).isoformat(timespec="seconds")
def _connect()->sqlite3.Connection:
    c=sqlite3.connect(DB_PATH,timeout=30);c.row_factory=sqlite3.Row;return c
def init_db()->None:
    with _connect() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("""CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,status TEXT NOT NULL,progress INTEGER NOT NULL DEFAULT 0,message TEXT NOT NULL DEFAULT '',form_json TEXT NOT NULL,input_dir TEXT NOT NULL,output_path TEXT,error TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)""")
def create_job(job_id:str,form:dict[str,Any],input_dir:str)->None:
    n=utc_now()
    with _connect() as c:c.execute("INSERT INTO jobs(id,status,progress,message,form_json,input_dir,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",(job_id,"queued",0,"در صف ساخت",json.dumps(form,ensure_ascii=False),input_dir,n,n))
def update_job(job_id:str,**fields:Any)->None:
    p={k:v for k,v in fields.items() if k in {"status","progress","message","output_path","error"}}
    if not p:return
    p["updated_at"]=utc_now()
    with _connect() as c:c.execute("UPDATE jobs SET "+", ".join(f"{k}=?" for k in p)+" WHERE id=?",list(p.values())+[job_id])
def get_job(job_id:str)->dict[str,Any]|None:
    with _connect() as c:r=c.execute("SELECT * FROM jobs WHERE id=?",(job_id,)).fetchone()
    if not r:return None
    d=dict(r);d["form"]=json.loads(d.pop("form_json"));return d
def list_jobs(limit:int=20)->list[dict[str,Any]]:
    with _connect() as c:rows=c.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",(limit,)).fetchall()
    result=[]
    for r in rows:
        d=dict(r);d["form"]=json.loads(d.pop("form_json"));result.append(d)
    return result
def count_jobs_today()->int:
    today=utc_now()[:10]
    with _connect() as c:r=c.execute("SELECT COUNT(*) n FROM jobs WHERE substr(created_at,1,10)=? AND status!='cancelled'",(today,)).fetchone()
    return int(r["n"] or 0)
init_db()
