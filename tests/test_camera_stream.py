"""Local MJPEG integration checks. No phone, model loading or Internet required."""
import io
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app


class Phone(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=phone")
        self.end_headers()
        try:
            deadline = time.monotonic()
            index = 0
            while True:
                image = Image.new("RGB", (640, 480), (index % 255, 70, 90))
                ImageDraw.Draw(image).text((30, 30), f"Frame {index}", fill="white")
                output = io.BytesIO()
                image.save(output, "JPEG")
                frame = output.getvalue()
                self.wfile.write(b"--phone\r\nContent-Type: image/jpeg\r\n"
                                 + f"Content-Length: {len(frame)}\r\n\r\n".encode()
                                 + frame + b"\r\n")
                self.wfile.flush()
                index += 1
                deadline += 1 / 30
                time.sleep(max(0, deadline - time.monotonic()))
        except OSError:
            pass

    def log_message(self, *_):
        pass


def serve(handler, port=0):
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_port}"


def next_frame(response):
    assert response.raw.readline().strip() == b"--englishlens"
    headers = {}
    while line := response.raw.readline().strip():
        name, value = line.split(b":", 1)
        headers[name.lower()] = value.strip()
    frame = response.raw.read(int(headers[b"content-length"]))
    assert response.raw.read(2) == b"\r\n"
    assert frame.startswith(b"\xff\xd8") and frame.endswith(b"\xff\xd9")
    return frame


class CameraStreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = requests.Session()
        cls.client.trust_env = False
        cls.phone, cls.phone_url = serve(Phone)
        cls.server, cls.url = serve(app.Handler)

    @classmethod
    def tearDownClass(cls):
        app.camera.stop()
        cls.client.close()
        for server in (cls.phone, cls.server):
            server.shutdown()
            server.server_close()

    def setUp(self):
        app.camera.start(self.phone_url)
        self.assertIsNotNone(app.camera.wait_frame(-1, app.camera.generation))

    def tearDown(self):
        app.camera.stop()

    def test_stream_keeps_source_rate_and_snapshot_available(self):
        started = time.monotonic()
        for _ in range(15):
            self.client.get(self.url + "/api/frame", timeout=2).raise_for_status()
            time.sleep(.08)
        polling_fps = 15 / (time.monotonic() - started)
        with self.client.get(self.url + "/api/stream", stream=True, timeout=3) as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn("multipart/x-mixed-replace", response.headers["Content-Type"])
            next_frame(response)
            started = time.monotonic()
            frames = [next_frame(response) for _ in range(45)]
            fps = 45 / (time.monotonic() - started)
            self.assertGreater(fps, 24)
            self.assertGreater(fps, polling_fps * 1.7)
            self.assertGreater(len(set(frames)), 35)
            snapshot = self.client.get(self.url + "/api/frame", timeout=2)
            self.assertEqual(Image.open(io.BytesIO(snapshot.content)).size, (640, 480))
            status = self.client.get(self.url + "/api/status", timeout=2).json()
            self.assertGreater(status["camera"]["fps"], 24)
            print(f"\nSynthetic source 30 FPS -> old polling {polling_fps:.1f} FPS; "
                  f"MJPEG {fps:.1f} FPS", flush=True)

    def test_reader_handles_split_markers_and_publishes_without_filling_chunk(self):
        camera = app.Camera()
        event = threading.Event()
        response = MagicMock()
        response.__enter__.return_value = response
        response.status_code = 200
        chunks = iter([b"--phone\r\n\xff", b"\xd8first\xff", b"\xd9\xff\xd8latest\xff\xd9"])

        def read_available(*_, **__):
            try:
                return next(chunks)
            except StopIteration:
                # Leave the stream open after a tiny JPEG; a full chunk never arrives.
                event.wait(2)
                return b""

        response.raw.read1.side_effect = read_available
        with patch.object(app.requests, "get", return_value=response):
            with camera.lock:
                camera.state = "connecting"
                camera.stop_event = event
            reader = threading.Thread(target=camera.read, args=("http://phone/video", event, 0))
            reader.start()
            try:
                self.assertEqual(camera.wait_frame(-1, 0, timeout=.5),
                                 (2, b"\xff\xd8latest\xff\xd9"))
            finally:
                camera.stop()
                reader.join(1)
            self.assertFalse(reader.is_alive())

    def test_disconnect_closes_stream_and_reconnect_is_fresh(self):
        with self.client.get(self.url + "/api/stream", stream=True, timeout=2) as response:
            next_frame(response)
            disconnected = self.client.post(self.url + "/api/camera/disconnect", json={}, timeout=2)
            self.assertEqual(disconnected.status_code, 200)
            self.assertLess(len(response.raw.read()), 100_000)
        self.assertEqual(app.camera.status()["state"], "disconnected")
        app.camera.start(self.phone_url)
        with self.client.get(self.url + "/api/stream", stream=True, timeout=2) as response:
            self.assertEqual(response.status_code, 200)
            next_frame(response)

    def test_slow_consumer_gets_latest_and_stop_wakes_waiter(self):
        camera = app.Camera()
        with camera.changed:
            camera.state = "connected"
            camera.frame = b"newest"
            camera.updated = time.monotonic()
            camera.sequence = 100
        self.assertEqual(camera.wait_frame(1, 0), (100, b"newest"))
        results = []
        waiter = threading.Thread(target=lambda: results.append(camera.wait_frame(100, 0)))
        waiter.start()
        camera.stop()
        waiter.join(1)
        self.assertFalse(waiter.is_alive())
        self.assertEqual(results, [None])

    def test_disconnected_stream_returns_503(self):
        app.camera.stop()
        response = self.client.get(self.url + "/api/stream", timeout=2)
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    if "--serve" in sys.argv:
        phone, phone_url = serve(Phone)
        server, url = serve(app.Handler, 7861)
        print(f"UI: {url} | Phone IP: 127.0.0.1 | Phone port: {phone.server_port}", flush=True)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            app.camera.stop()
            phone.shutdown()
            server.shutdown()
    else:
        unittest.main()
