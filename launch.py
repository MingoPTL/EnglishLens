"""Start EnglishLens independently of the launcher window and reopen safely."""
import argparse
import ctypes
import json
import msvcrt
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def ready(url):
    try:
        # A local app must remain reachable even when Windows has a proxy enabled.
        client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with client.open(url + "/api/status", timeout=2) as response:
            data = json.load(response)
        return isinstance(data.get("models"), dict) and "camera" in data and "phase" in data
    except Exception:
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    url = f"http://127.0.0.1:{args.port}"
    output = ROOT / "outputs"
    output.mkdir(exist_ok=True)
    lock_path = output / f"launcher-{args.port}.lock"
    # Serialize simultaneous double-clicks so only one server is started.
    with lock_path.open("a+b") as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0")
            lock.flush()
        deadline = time.monotonic() + 45
        while True:
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("App đang khởi động. Vui lòng thử lại sau vài giây.")
                time.sleep(.3)
        try:
            if ready(url):
                print("Reusing running EnglishLens:", url, flush=True)
            else:
                python = ROOT / ".venv-ram/Scripts/python.exe"
                if not python.is_file():
                    raise RuntimeError("Không tìm thấy môi trường Python của EnglishLens.")
                with (output / f"server-{args.port}.log").open("ab") as log:
                    process = subprocess.Popen(
                        [str(python), "-u", str(ROOT / "app.py"), "--port", str(args.port)],
                        cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_BREAKAWAY_FROM_JOB,
                    )
                deadline = time.monotonic() + 30
                while not ready(url):
                    if process.poll() is not None:
                        raise RuntimeError(f"Không khởi động được app. Xem outputs/server-{args.port}.log.")
                    if time.monotonic() >= deadline:
                        raise RuntimeError("App khởi động chậm. Vui lòng mở lại sau vài giây.")
                    time.sleep(.3)
                print("Started EnglishLens:", url, flush=True)
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
    if not args.no_open:
        webbrowser.open(url)

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        if "--no-open" in sys.argv:
            print(str(error), file=sys.stderr)
        else:
            ctypes.windll.user32.MessageBoxW(0, str(error), "EnglishLens", 0x10)
        sys.exit(1)
