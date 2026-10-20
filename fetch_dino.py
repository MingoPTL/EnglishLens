import os
from pathlib import Path
ROOT = Path(__file__).resolve().parent
os.environ["HF_HOME"] = str(ROOT / ".cache/huggingface")
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "60"
from huggingface_hub import snapshot_download
snapshot_download("IDEA-Research/grounding-dino-tiny",local_dir=ROOT/"models/grounding-dino-tiny",
                  allow_patterns=["*.json","*.txt","*.safetensors"],max_workers=2)
snapshot_download("google-bert/bert-base-uncased",local_dir=ROOT/"models/bert",
                  allow_patterns=["config.json","tokenizer_config.json","tokenizer.json","vocab.txt"],max_workers=2)
print("Grounding DINO and BERT tokenizer ready.",flush=True)
