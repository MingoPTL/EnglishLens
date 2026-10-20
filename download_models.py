"""Download official checkpoints to the project, with progress and resume."""
import os
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parent
os.environ.setdefault("HF_HOME", str(ROOT / ".cache" / "huggingface"))
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
import requests
from huggingface_hub import snapshot_download

def download(url, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        print(f"Already downloaded: {destination.name}", flush=True)
        return
    partial = destination.with_suffix(destination.suffix + ".part")
    for attempt in range(5):
        offset = partial.stat().st_size if partial.exists() else 0
        try:
            print(f"Downloading {destination.name}, resuming at {offset / 1e6:.0f} MB", flush=True)
            with requests.get(url, headers={"Range": f"bytes={offset}-"} if offset else {},
                              stream=True, timeout=(30, 60)) as response:
                response.raise_for_status()
                if offset and response.status_code != 206:
                    offset = 0
                total = offset + int(response.headers.get("Content-Length", 0))
                count, report = offset, time.monotonic()
                with partial.open("ab" if offset else "wb") as target:
                    for chunk in response.iter_content(1024 * 1024):
                        if not chunk:
                            continue
                        target.write(chunk)
                        count += len(chunk)
                        if time.monotonic() - report > 10:
                            print(f"{destination.name}: {count/1e6:.0f}/{total/1e6:.0f} MB", flush=True)
                            report = time.monotonic()
                if total and count != total:
                    raise IOError(f"Incomplete download: {count}/{total}")
            partial.replace(destination)
            return
        except (requests.RequestException, IOError) as error:
            if attempt == 4:
                raise
            print(f"Retrying: {error}", flush=True)
            time.sleep(3)

download("https://huggingface.co/xinyu1205/recognize_anything_model/resolve/main/ram_swin_large_14m.pth",
         ROOT / "models" / "ram" / "ram_swin_large_14m.pth")
snapshot_download("google-bert/bert-base-uncased", local_dir=ROOT / "models" / "bert",
                  allow_patterns=["config.json", "tokenizer.json", "tokenizer_config.json", "vocab.txt"])
snapshot_download("IDEA-Research/grounding-dino-tiny",
                  local_dir=ROOT / "models" / "grounding-dino-tiny",
                  allow_patterns=["*.json", "*.txt", "*.safetensors"])
print("All models downloaded.", flush=True)
