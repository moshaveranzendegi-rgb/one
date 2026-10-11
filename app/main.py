from __future__ import annotations
import argparse
import os
import socket
import sys
import webbrowser
import uvicorn
from app.config import APP_HOME
from app.security import ACCESS_TOKEN

def _configure_console() -> None:
    # Windows consoles may default to cp1252/cp437. The app prints Persian messages,
    # so explicitly use UTF-8 and replace characters only if the terminal cannot render them.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass

def _local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("192.0.2.1", 80))
            return str(sock.getsockname()[0])
    except OSError:
        return "IP رایانه"

def main() -> None:
    _configure_console()
    parser = argparse.ArgumentParser(description="RS ai local video studio")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=int(os.getenv("RS_AI_PORT", "8765")))
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    lan = os.getenv("RS_AI_BIND_LAN", "0").lower() in {"1", "true", "yes"}
    host = args.host or ("0.0.0.0" if lan else "127.0.0.1")
    local_url = f"http://127.0.0.1:{args.port}/#token={ACCESS_TOKEN}"
    print("=" * 60)
    print("RS ai · استودیوی محلی ساخت ویدئو")
    print(f"پوشهٔ داده‌ها: {APP_HOME}")
    print(f"توکن دسترسی: {APP_HOME / 'access.token'}")
    if lan:
        print(f"نشانی رایانه برای اپ موبایل: http://{_local_ip()}:{args.port}")
        print("فقط روی شبکهٔ خصوصی و مطمئن اجرا کن.")
    else:
        print("حالت پیش‌فرض فقط روی همین رایانه قابل دسترسی است.")
    print("برای توقف Ctrl+C را بزن.")
    print("=" * 60)
    if not args.no_browser:
        webbrowser.open(local_url)
    uvicorn.run("app.api:app", host=host, port=args.port, log_level="info", access_log=False)

if __name__ == "__main__":
    main()
