"""Download the official RAM checkpoint in parallel byte ranges; verify SHA256."""
import concurrent.futures
import hashlib
from pathlib import Path
import shutil
import time
import requests

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "models/ram/ram_swin_large_14m.pth"
URL = "https://huggingface.co/xinyu1205/recognize_anything_model/resolve/main/ram_swin_large_14m.pth"
SIZE = 5625634877
SHA256 = "15c729c793af28b9d107c69f85836a1356d76ea830d4714699fb62e55fcc08ed"
WORKERS = 8

def get_part(index):
    step = (SIZE + WORKERS - 1) // WORKERS
    start, end = index * step, min(SIZE, (index + 1) * step) - 1
    part = TARGET.with_suffix(f".part{index}")
    for attempt in range(8):
        saved = part.stat().st_size if part.exists() else 0
        if saved == end - start + 1:
            return part
        if saved > end - start + 1:
            raise RuntimeError("Invalid partial file size")
        try:
            with requests.get(URL, headers={"Range": f"bytes={start + saved}-{end}"},
                              stream=True, timeout=(30, 60)) as response:
                response.raise_for_status()
                if response.status_code != 206:
                    raise RuntimeError("Server does not support partial downloads")
                expected = f"bytes {start + saved}-{end}/{SIZE}"
                if response.headers.get("Content-Range") != expected:
                    raise RuntimeError("Server returned unexpected byte range")
                with part.open("ab") as out:
                    for chunk in response.iter_content(1024 * 1024):
                        out.write(chunk)
            if part.stat().st_size == end - start + 1:
                return part
        except requests.RequestException as error:
            print(f"Part {index}: retry {attempt + 1}: {type(error).__name__}", flush=True)
            time.sleep(2)
    raise RuntimeError(f"Failed to download part {index}")

def main():
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    if TARGET.exists():
        print("RAM checkpoint already present.", flush=True)
        return
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        pending = [pool.submit(get_part, i) for i in range(WORKERS)]
        while not all(job.done() for job in pending):
            count = sum(p.stat().st_size for p in TARGET.parent.glob("*.part[0-7]"))
            print(f"RAM download: {count / 1e6:.0f}/{SIZE / 1e6:.0f} MB", flush=True)
            time.sleep(15)
        parts = [job.result() for job in pending]
    combined = TARGET.with_suffix(".assembling")
    digest = hashlib.sha256()
    with combined.open("wb") as out:
        for part in parts:
            with part.open("rb") as source:
                while chunk := source.read(8 * 1024 * 1024):
                    digest.update(chunk)
                    out.write(chunk)
    if digest.hexdigest() != SHA256:
        raise RuntimeError("RAM checkpoint checksum mismatch")
    combined.replace(TARGET)
    for part in parts:
        part.unlink()
    previous = TARGET.with_suffix(TARGET.suffix + ".part")
    if previous.exists():
        previous.unlink()
    print("RAM downloaded; SHA256 verified.", flush=True)

if __name__ == "__main__":
    main()
