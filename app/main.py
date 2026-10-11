from __future__ import annotations
import argparse,os,socket,webbrowser
import uvicorn
from app.config import APP_HOME
from app.security import ACCESS_TOKEN
def _local_ip()->str:
    try:
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:s.connect(("192.0.2.1",80));return str(s.getsockname()[0])
    except OSError:return "IP رایانه"
def main()->None:
    p=argparse.ArgumentParser(description="RS ai local video studio");p.add_argument("--host",default=None);p.add_argument("--port",type=int,default=int(os.getenv("RS_AI_PORT","8765")));p.add_argument("--no-browser",action="store_true");a=p.parse_args()
    lan=os.getenv("RS_AI_BIND_LAN","0").lower() in {"1","true","yes"};host=a.host or ("0.0.0.0" if lan else "127.0.0.1")
    url=f"http://127.0.0.1:{a.port}/#token={ACCESS_TOKEN}"
    print("="*60);print("RS ai · استودیوی محلی ساخت ویدئو");print(f"پوشهٔ داده‌ها: {APP_HOME}");print(f"توکن دسترسی: {APP_HOME/'access.token'}")
    if lan:print(f"نشانی رایانه برای اپ موبایل: http://{_local_ip()}:{a.port}");print("فقط روی شبکهٔ خصوصی و مطمئن اجرا کن.")
    else:print("حالت پیش‌فرض فقط روی همین رایانه قابل دسترسی است.")
    print("برای توقف Ctrl+C را بزن.");print("="*60)
    if not a.no_browser:webbrowser.open(url)
    uvicorn.run("app.api:app",host=host,port=a.port,log_level="info",access_log=False)
if __name__=="__main__":main()
