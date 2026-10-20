"""Persistent local RAM / Grounding DINO inference."""
import gc
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("HF_HOME", str(ROOT / ".cache/huggingface"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
sys.path.insert(0, str(ROOT / "vendor/recognize-anything"))
RAM_BYTES = 5625634877

def infer_ram_with_scores(image, model):
    """Capture tagging logits from the same RAM pass that selects the labels."""
    import torch
    captured = []
    handle = model.fc.register_forward_hook(
        lambda _module, _inputs, output: captured.append(output.detach()))
    try:
        with torch.inference_mode():
            tags, _ = model.generate_tag(image)
    finally:
        handle.remove()
    probabilities = captured[0].squeeze(-1).sigmoid()[0].cpu().tolist()
    thresholds = model.class_threshold.cpu().tolist()
    selected = {label.strip() for label in tags[0].split("|") if label.strip()}
    scores = {str(label).strip().lower(): {
        "score": probabilities[index], "threshold": thresholds[index]}
        for index, label in enumerate(model.tag_list) if str(label).strip() in selected}
    return tags[0], scores

def model_status():
    ram_file = ROOT / "models/ram/ram_swin_large_14m.pth"
    dino_dir = ROOT / "models/grounding-dino-tiny"
    ram_ok = ram_file.is_file() and ram_file.stat().st_size == RAM_BYTES
    bert_ok = (ROOT / "models/bert/vocab.txt").is_file()
    dino_ok = all((dino_dir / f).is_file() for f in [
        "config.json", "preprocessor_config.json", "tokenizer_config.json",
        "vocab.txt", "model.safetensors"])
    progress = max(
        sum(p.stat().st_size for p in (ROOT / "models/ram").glob("*.part[0-7]")),
        sum(p.stat().st_size for p in (ROOT / "models/ram").glob("*.pth.part")),
        sum(p.stat().st_size for p in (ROOT / "models/ram").glob(".cache/huggingface/download/*.incomplete")),
        RAM_BYTES if ram_ok else 0,
    )
    return {"ram": ram_ok and bert_ok, "dino": dino_ok,
            "ram_download_mb": round(progress / 1e6), "ram_total_mb": round(RAM_BYTES / 1e6),
            "dino_download_mb": round(max(sum(p.stat().st_size for p in dino_dir.glob("*.part[0-7]")),
            sum(p.stat().st_size for p in dino_dir.glob(".cache/huggingface/download/*.incomplete"))) / 1e6)}

class Engine:
    def __init__(self):
        self.ram = self.dino = self.processor = self.transform = None
        self.phase = "idle"
        self.device = None

    def infer(self, image, mode, labels, threshold):
        import torch
        from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
        if self.device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            torch.set_num_threads(min(8, os.cpu_count() or 4))
        ready = model_status()
        if not ready["dino"] or (mode == "auto" and not ready["ram"]):
            raise ValueError("Model chưa tải xong. Bạn vẫn có thể xem camera trực tiếp.")
        started = time.perf_counter()
        try:
            ram_scores = {}
            if mode == "auto":
                if self.ram is None:
                    self.phase = "loading_ram"
                    from ram.models import ram
                    from ram import get_transform
                    self.ram = ram(pretrained=str(ROOT / "models/ram/ram_swin_large_14m.pth"),
                                   image_size=384, vit="swin_l",
                                   text_encoder_type=str(ROOT / "models/bert"))
                    # Captioning modules are unused for generate_tag; keep the tagging path.
                    del self.ram.text_decoder
                    del self.ram.tag_encoder
                    self.ram.eval().to(self.device)
                    self.transform = get_transform(image_size=384)
                    gc.collect()
                self.phase = "tagging"
                tags, ram_scores = infer_ram_with_scores(
                    self.transform(image).unsqueeze(0).to(self.device), self.ram)
                labels = [x.strip() for x in tags.split("|") if x.strip()]
            else:
                labels = [x.strip().lower() for x in labels.split(",") if x.strip()]
            labels = list(dict.fromkeys(labels))
            if not labels:
                return {"tags": [], "detections": [], "mode": mode, "ram_scores": ram_scores,
                        "seconds": round(time.perf_counter()-started, 2),
                        "device": self.device, "size": list(image.size)}
            if self.dino is None:
                self.phase = "loading_dino"
                folder = ROOT / "models/grounding-dino-tiny"
                self.processor = AutoProcessor.from_pretrained(folder, local_files_only=True)
                self.processor.image_processor.size = {"shortest_edge": 480, "longest_edge": 800}
                self.dino = AutoModelForZeroShotObjectDetection.from_pretrained(
                    folder, local_files_only=True).eval().to(self.device)
            self.phase = "detecting"
            chunks, current = [], []
            for label in labels:
                prompt = ". ".join(current + [label]) + "."
                if len(self.processor.tokenizer(prompt)["input_ids"]) > 200 and current:
                    chunks.append(current)
                    current = []
                current.append(label)
            if current:
                chunks.append(current)
            detections = []
            for chunk in chunks:
                inputs = self.processor(images=image, text=". ".join(chunk)+".", return_tensors="pt").to(self.device)
                with torch.inference_mode():
                    output = self.dino(**inputs)
                result = self.processor.post_process_grounded_object_detection(
                    output, inputs.input_ids, box_threshold=threshold, text_threshold=0.25,
                    target_sizes=[(image.height, image.width)])[0]
                for box, score, label in zip(result["boxes"], result["scores"], result["labels"]):
                    # DINO can decode a phrase that differs from RAM's original label.
                    # Only attach a RAM score for an exact label match, never a guess.
                    ram_match = ram_scores.get(label.strip().lower())
                    detections.append({"label": label, "score": round(score.item(), 3),
                                       "ram_score": ram_match["score"] if ram_match else None,
                                       "ram_threshold": ram_match["threshold"] if ram_match else None,
                                       "box": [round(v, 2) for v in box.tolist()]})
            return {"tags": labels, "detections": detections, "mode": mode, "ram_scores": ram_scores,
                    "seconds": round(time.perf_counter()-started, 2),
                    "device": self.device, "size": list(image.size)}
        except torch.cuda.OutOfMemoryError:
            self.ram = self.dino = self.processor = None
            gc.collect()
            torch.cuda.empty_cache()
            raise ValueError("GPU thiếu bộ nhớ. Tắt ứng dụng dùng GPU hoặc chọn chế độ nhập nhãn.")
        finally:
            self.phase = "idle"
