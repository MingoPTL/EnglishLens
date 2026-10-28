"""EnglishLens local camera UI. Bind only to this computer."""
import argparse
import io
import ipaddress
import json
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

import requests
from PIL import Image, UnidentifiedImageError
from engine import Engine, model_status
from dictionary_service import lookup, audio, vocabulary

ROOT = Path(__file__).resolve().parent
engine = Engine()
inference_lock = threading.Lock()

def camera_url(ip, port):
    address = ipaddress.ip_address(str(ip).strip())
    if address.version != 4 or not address.is_private or address.is_unspecified or address.is_multicast:
        raise ValueError("Nhập địa chỉ IPv4 nội bộ hiển thị trên DroidCam, ví dụ 192.168.1.10.")
    port = int(port)
    if not 1 <= port <= 65535:
        raise ValueError("Cổng phải từ 1 đến 65535.")
    return f"http://{address}:{port}/video"

class Camera:
    def __init__(self):
        self.lock = threading.Lock()
        self.changed = threading.Condition(self.lock)
        self.stop_event = None
        self.frame = None
        self.updated = 0
        self.state = "disconnected"
        self.error = ""
        self.generation = 0
        self.sequence = 0
        self.frame_times = deque(maxlen=120)

    def stop(self):
        with self.lock:
            if self.stop_event:
                self.stop_event.set()
            self.generation += 1
            self.frame = None
            self.updated = 0
            self.state = "disconnected"
            self.error = ""
            self.frame_times.clear()
            self.changed.notify_all()

    def start(self, url):
        self.stop()
        with self.lock:
            generation = self.generation
            event = self.stop_event = threading.Event()
            self.state = "connecting"
        threading.Thread(target=self.read, args=(url, event, generation), daemon=True).start()

    def read(self, url, event, generation):
        try:
            with requests.get(url, stream=True, timeout=(5, 6), allow_redirects=False) as response:
                if response.status_code != 200:
                    raise ValueError(f"DroidCam trả về HTTP {response.status_code}. Kiểm tra IP, cổng và app.")
                data = bytearray()
                # Read available bytes without waiting for a fixed-size chunk to fill.
                while not event.is_set():
                    chunk = response.raw.read1(64 * 1024, decode_content=True)
                    if not chunk:
                        break
                    if event.is_set():
                        return
                    data.extend(chunk)
                    latest = None
                    received = 0
                    while True:
                        start = data.find(b"\xff\xd8")
                        end = data.find(b"\xff\xd9", start + 2) if start >= 0 else -1
                        if start < 0 or end < 0:
                            break
                        latest = bytes(data[start:end+2])
                        del data[:end+2]
                        received += 1
                    if latest is not None:
                        with self.lock:
                            if generation != self.generation:
                                return
                            self.frame = latest
                            self.updated = time.monotonic()
                            self.state = "connected"
                            self.sequence += received
                            self.frame_times.extend([self.updated] * received)
                            self.changed.notify_all()
                    if len(data) > 8 * 1024 * 1024:
                        raise ValueError("Luồng không đúng định dạng MJPEG của DroidCam.")
                if not event.is_set():
                    raise ValueError("Luồng camera đã kết thúc. Mở DroidCam và kết nối lại.")
        except Exception as error:
            with self.lock:
                if generation == self.generation and not event.is_set():
                    self.state = "error"
                    self.error = str(error) if isinstance(error, ValueError) else (
                        "Không nhận được hình. Kiểm tra IP/cổng, cùng Wi-Fi và giữ DroidCam đang mở.")
                    self.frame = None
                    self.changed.notify_all()

    def wait_frame(self, sequence, generation, timeout=6):
        """Wait for a newer frame; slow viewers skip frames instead of queuing them."""
        with self.changed:
            self.changed.wait_for(lambda: self.generation != generation
                                  or self.state in ("disconnected", "error")
                                  or (self.frame is not None and self.sequence != sequence), timeout)
            if (self.generation != generation or self.state != "connected"
                    or self.frame is None or self.sequence == sequence
                    or time.monotonic() - self.updated >= 6):
                return None
            return self.sequence, self.frame

    def status(self):
        with self.lock:
            age = time.monotonic() - self.updated if self.updated else None
            times = [stamp for stamp in self.frame_times if time.monotonic() - stamp < 2]
            fps = (len(times) - 1) / (times[-1] - times[0]) if len(times) > 1 and times[-1] > times[0] else 0
            return {"state": self.state, "error": self.error, "frame_age": age,
                    "fps": round(fps, 1)}

camera = Camera()

class Handler(BaseHTTPRequestHandler):
    disable_nagle_algorithm = True

    def stream_camera(self):
        with camera.lock:
            generation = camera.generation
        current = camera.wait_frame(-1, generation)
        if current is None:
            return self.json(503, {"error": "Chưa có hình từ camera."})
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=englishlens")
        self.send_header("Cache-Control", "no-store, no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        self.connection.settimeout(3)
        try:
            while current is not None:
                sequence, frame = current
                header = (f"--englishlens\r\nContent-Type: image/jpeg\r\n"
                          f"Content-Length: {len(frame)}\r\n\r\n").encode("ascii")
                self.wfile.write(header + frame + b"\r\n")
                self.wfile.flush()
                current = camera.wait_frame(sequence, generation)
        except (OSError, TimeoutError):
            pass

    def send_bytes(self, status, data, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def json(self, status, data):
        self.send_bytes(status, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/status":
            self.json(200, {"models": model_status(), "camera": camera.status(),
                            "phase": engine.phase, "busy": inference_lock.locked(),
                            "device": engine.device})
        elif path == "/api/pronunciation":
            word = parse_qs(urlsplit(self.path).query).get("word", [""])[0]
            code, data, mime = audio(word)
            if code == 200:
                self.send_bytes(code, data, mime)
            else:
                self.json(code, data)
        elif path == "/api/vocabulary":
            word = parse_qs(urlsplit(self.path).query).get("word", [""])[0]
            code, data = vocabulary(word)
            self.json(code, data)
        elif path == "/api/dictionary":
            word = parse_qs(urlsplit(self.path).query).get("word", [""])[0]
            code, data = lookup(word)
            self.json(code, data)
        elif path == "/api/frame":
            with camera.lock:
                frame = camera.frame
                age = time.monotonic() - camera.updated
            if frame and age < 6:
                self.send_bytes(200, frame, "image/jpeg")
            else:
                self.json(503, {"error": "Chưa có hình từ camera."})
        elif path == "/api/stream":
            self.stream_camera()
        elif path == "/api/sample":
            self.send_bytes(200, (ROOT / "vendor/recognize-anything/images/demo/demo1.jpg").read_bytes(), "image/jpeg")
        elif path in ["/", "/app.js", "/vocabulary.js", "/style.css"]:
            name = {"/": "index.html", "/app.js": "app.js", "/vocabulary.js": "vocabulary.js", "/style.css": "style.css"}[path]
            mime = {"/": "text/html", "/app.js": "text/javascript", "/vocabulary.js": "text/javascript", "/style.css": "text/css"}[path]
            self.send_bytes(200, (ROOT / "web" / name).read_bytes(), mime + "; charset=utf-8")
        else:
            self.json(404, {"error": "Not found"})

    def do_POST(self):
        # Browser calls must come from this local UI; no cross-origin camera control.
        origin = self.headers.get("Origin")
        if origin and urlsplit(origin).netloc != self.headers.get("Host"):
            return self.json(403, {"error": "Origin không hợp lệ."})
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 4 * 1024 * 1024:
                return self.json(413, {"error": "Ảnh hoặc yêu cầu quá lớn (tối đa 4 MB)."})
            body = self.rfile.read(length)
            parsed = urlsplit(self.path)
            if parsed.path == "/api/camera/connect":
                data = json.loads(body)
                camera.start(camera_url(data.get("ip", ""), data.get("port", 4747)))
                return self.json(200, {"ok": True})
            if parsed.path == "/api/camera/disconnect":
                camera.stop()
                return self.json(200, {"ok": True})
            if parsed.path != "/api/infer":
                return self.json(404, {"error": "Not found"})
            query = parse_qs(parsed.query)
            mode = query.get("mode", ["manual"])[0]
            if mode not in ["manual", "auto"]:
                raise ValueError("Chế độ không hợp lệ.")
            labels = query.get("labels", [""])[0]
            if len(labels) > 500 or (mode == "manual" and not labels.strip()):
                raise ValueError("Nhập tên vật thể tiếng Anh, ngăn cách bằng dấu phẩy (tối đa 500 ký tự).")
            threshold = float(query.get("threshold", [".3"])[0])
            if not 0.05 <= threshold <= 0.95:
                raise ValueError("Ngưỡng không hợp lệ.")
            image = Image.open(io.BytesIO(body))
            if image.width * image.height > 12_000_000:
                raise ValueError("Ảnh quá lớn.")
            image = image.convert("RGB")
            image.thumbnail((960, 960))
            if not inference_lock.acquire(blocking=False):
                return self.json(409, {"error": "AI đang xử lý một ảnh. Vui lòng chờ."})
            try:
                result = engine.infer(image, mode, labels, threshold)
                self.json(200, result)
            finally:
                inference_lock.release()
        except (ValueError, TypeError, UnidentifiedImageError) as error:
            self.json(400, {"error": str(error)})
        except Exception as error:
            print(f"Inference error: {type(error).__name__}: {error}", flush=True)
            self.json(500, {"error": "AI gặp lỗi. Xem cửa sổ chạy EnglishLens để biết chi tiết."})

    def log_message(self, format, *args):
        if not self.path.startswith(("/api/status", "/api/frame", "/api/stream")):
            super().log_message(format, *args)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--open", action="store_true", help="Open the local UI in your browser")
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"EnglishLens: http://127.0.0.1:{args.port}", flush=True)
    if args.open:
        import webbrowser
        threading.Timer(1, lambda: webbrowser.open(f"http://127.0.0.1:{args.port}")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        camera.stop()
        server.server_close()
