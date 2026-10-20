"""Download DINO first using resumable HTTP ranges."""
import os
from pathlib import Path
import requests
import download_ram_parallel as downloader
ROOT = Path(__file__).resolve().parent
os.environ["HF_HOME"] = str(ROOT / ".cache/huggingface")
os.environ["HF_HUB_DISABLE_XET"] = "1"
downloader.TARGET = ROOT / "models/grounding-dino-tiny/model.safetensors"
downloader.URL = "https://huggingface.co/IDEA-Research/grounding-dino-tiny/resolve/main/model.safetensors"
with requests.get(downloader.URL,stream=True,timeout=(30,60)) as response:
    response.raise_for_status()
    downloader.SIZE = int(response.headers["Content-Length"])
downloader.SHA256 = "1a2412ef99bd74bcd3c2a246fa1e48581f8889a1300c9051974741314fc042f3"
print(f"Grounding DINO: {downloader.SIZE / 1e6:.0f} MB",flush=True)
downloader.main()
# Small configuration files were already fetched; complete both tokenizers.
from huggingface_hub import snapshot_download
snapshot_download("IDEA-Research/grounding-dino-tiny",local_dir=ROOT/"models/grounding-dino-tiny",
                  allow_patterns=["*.json","*.txt"],max_workers=2)
snapshot_download("google-bert/bert-base-uncased",local_dir=ROOT/"models/bert",
                  allow_patterns=["config.json","tokenizer_config.json","tokenizer.json","vocab.txt"],max_workers=2)
print("DINO ready.",flush=True)
