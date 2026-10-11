from __future__ import annotations
import secrets
from app.config import TOKEN_PATH
def load_or_create_token()->str:
    if TOKEN_PATH.exists():
        value=TOKEN_PATH.read_text(encoding="utf-8").strip()
        if len(value)>=32:return value
    value=secrets.token_urlsafe(36);TOKEN_PATH.parent.mkdir(parents=True,exist_ok=True);TOKEN_PATH.write_text(value+"\n",encoding="utf-8")
    try:TOKEN_PATH.chmod(0o600)
    except OSError:pass
    return value
ACCESS_TOKEN=load_or_create_token()
def token_matches(candidate:str|None)->bool:return bool(candidate) and secrets.compare_digest(candidate,ACCESS_TOKEN)
