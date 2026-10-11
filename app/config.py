from __future__ import annotations
import os, sys
from pathlib import Path
PROJECT_ROOT=Path(sys._MEIPASS) if getattr(sys,"frozen",False) and hasattr(sys,"_MEIPASS") else Path(__file__).resolve().parents[1]
def _default_home()->Path:
    override=os.getenv("RS_AI_HOME")
    if override:return Path(override).expanduser().resolve()
    if os.name=="nt":return Path(os.getenv("LOCALAPPDATA",str(Path.home()/"AppData"/"Local")))/"RS-ai"
    return Path.home()/".local"/"share"/"rs-ai"
APP_HOME=_default_home();DATA_DIR=APP_HOME/"data";JOBS_DIR=DATA_DIR/"jobs";OUTPUTS_DIR=APP_HOME/"outputs";LOGS_DIR=APP_HOME/"logs";DB_PATH=DATA_DIR/"jobs.sqlite3";TOKEN_PATH=APP_HOME/"access.token";STATIC_DIR=PROJECT_ROOT/"web"
for p in (APP_HOME,DATA_DIR,JOBS_DIR,OUTPUTS_DIR,LOGS_DIR):p.mkdir(parents=True,exist_ok=True)
