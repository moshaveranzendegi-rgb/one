from __future__ import annotations

import json
import os
import socket
import tempfile
import threading
import time
import wave
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOME = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "RS-ai" / "engines" / "PiperTTS"
MODEL = HOME / "voices" / "fa_IR-amir-medium.onnx"
CONFIG = HOME / "voices" / "fa_IR-amir-medium.onnx.json"
LOG = HOME / "piper-server.log"
HOST = "127.0.0.1"
PORT = 8767
ALLOWED_ORIGINS = {"http://127.0.0.1:8765", "http://localhost:8765"}
_voice = None
_voice_lock = threading.Lock()


def log(message: str) -> None:
    try:
        with LOG.open("a", encoding="utf-8") as stream:
            stream.write(f"{datetime.now().isoformat(timespec='seconds')} {message}\n")
    except OSError:
        pass


class Handler(BaseHTTPRequestHandler):
    server_version = "RSaiOfflineTTS/1.0"

    def log_message(self, format_string, *args):
        return

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        return origin in ALLOWED_ORIGINS

    def _cors(self) -> None:
        origin = self.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _json(self, status: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        if not self._origin_allowed():
            self._json(403, {"error": "Origin not allowed"})
            return
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_GET(self):
        if self.path != "/health":
            self._json(404, {"error": "Not found"})
            return
        self._json(200, {
            "ok": True,
            "engine": "Piper TTS",
            "language": "fa",
            "model_ready": MODEL.is_file() and CONFIG.is_file(),
        })

    def do_POST(self):
        if self.path != "/synthesize":
            self._json(404, {"error": "Not found"})
            return
        if not self._origin_allowed():
            self._json(403, {"error": "Only the local RS ai app may call this service"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > 128_000:
            self._json(413, {"error": "Invalid request size"})
            return
        try:
            request = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json(400, {"error": "Invalid JSON"})
            return

        language = str(request.get("language", "fa")).lower()
        text = str(request.get("text", "")).strip()
        if language not in {"fa", "fa-ir", "fa_ir"}:
            self._json(400, {"error": "The offline voice currently supports Persian (fa) only."})
            return
        if not text or len(text) > 12_000:
            self._json(400, {"error": "Enter Persian text between 1 and 12000 characters."})
            return
        if not MODEL.is_file() or not CONFIG.is_file():
            self._json(503, {"error": "Persian offline TTS model is not installed yet."})
            return

        global _voice
        try:
            with _voice_lock:
                if _voice is None:
                    from piper import PiperVoice
                    _voice = PiperVoice.load(MODEL, config_path=CONFIG, use_cuda=False)

            fd, temp_name = tempfile.mkstemp(prefix="rs-ai-piper-", suffix=".wav", dir=str(HOME))
            os.close(fd)
            path = Path(temp_name)
            try:
                with wave.open(str(path), "wb") as wav_file:
                    # Piper 1.8.0 sets framerate before channels; wave.Wave_write
                    # rejects that order on Python 3.13 with "# channels not specified".
                    # Set the mono PCM format first and let Piper write audio frames only.
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(_voice.config.sample_rate)
                    _voice.synthesize_wav(text, wav_file, set_wav_format=False)
                payload = path.read_bytes()
            finally:
                path.unlink(missing_ok=True)

            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Content-Disposition", 'attachment; filename="rs-ai-fa.wav"')
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
        except Exception as exc:
            log(f"synthesis failed: {type(exc).__name__}: {exc}")
            self._json(500, {"error": "Offline Persian speech synthesis failed. Check piper-server.log."})


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def already_running() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((HOST, PORT)) == 0


if __name__ == "__main__":
    HOME.mkdir(parents=True, exist_ok=True)
    if already_running():
        raise SystemExit(0)
    server = Server((HOST, PORT), Handler)
    log(f"started on {HOST}:{PORT}; Persian model exists={MODEL.is_file()}")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        log("stopped")

[executed on device: DESKTOP-AG001JD (75030569-cef4-42ce-a3e2-0085550df642)]
