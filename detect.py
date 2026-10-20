"""RAM image tags -> Grounding DINO bounding boxes."""
import argparse
import gc
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("HF_HOME", str(ROOT / ".cache" / "huggingface"))
sys.path.insert(0, str(ROOT / "vendor" / "recognize-anything"))

import torch
from PIL import Image, ImageDraw, ImageOps
from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--labels", help="Optional comma-separated English labels; skips RAM")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--box-threshold", type=float, default=0.30)
    parser.add_argument("--text-threshold", type=float, default=0.25)
    args = parser.parse_args()
    if not args.image.is_file():
        parser.error(f"Image not found: {args.image}")
    device = "cuda" if args.device == "auto" and torch.cuda.is_available() else args.device
    if device == "auto":
        device = "cpu"
    if device == "cuda" and not torch.cuda.is_available():
        parser.error("CUDA is unavailable; use --device cpu")
    torch.set_num_threads(min(8, os.cpu_count() or 4))
    started = time.perf_counter()
    image = ImageOps.exif_transpose(Image.open(args.image)).convert("RGB")
    if args.labels is None:
        from ram import get_transform, inference_ram
        from ram.models import ram
        checkpoint = ROOT / "models" / "ram" / "ram_swin_large_14m.pth"
        if not checkpoint.is_file():
            parser.error("Models missing. Run download_models.py first.")
        print(f"RAM tagging on {device}...", flush=True)
        model = ram(pretrained=str(checkpoint), image_size=384, vit="swin_l",
                    text_encoder_type=str(ROOT / "models" / "bert"))
        model.eval().to(device)
        tensor = get_transform(image_size=384)(image).unsqueeze(0).to(device)
        with torch.inference_mode():
            english, _ = inference_ram(tensor, model)
        tags = [tag.strip() for tag in english.split("|") if tag.strip()]
        del tensor, model
        gc.collect()
        if device == "cuda":
            torch.cuda.empty_cache()
    else:
        tags = [tag.strip().lower() for tag in args.labels.split(",") if tag.strip()]
    tags = list(dict.fromkeys(tags))
    print("Tags:", " | ".join(tags), flush=True)
    detections = []
    if tags:
        print(f"Grounding DINO on {device}...", flush=True)
        path = ROOT / "models" / "grounding-dino-tiny"
        processor = AutoProcessor.from_pretrained(path, local_files_only=True)
        model = AutoModelForZeroShotObjectDetection.from_pretrained(
            path, local_files_only=True).eval().to(device)
        # Process every tag, splitting long prompts to respect the text token limit.
        chunks, current = [], []
        for tag in tags:
            candidate = ". ".join(current + [tag]) + "."
            if len(processor.tokenizer(candidate)["input_ids"]) > 200 and current:
                chunks.append(current)
                current = []
            current.append(tag)
        if current:
            chunks.append(current)
        for chunk in chunks:
            inputs = processor(images=image, text=". ".join(chunk) + ".",
                               return_tensors="pt").to(device)
            with torch.inference_mode():
                outputs = model(**inputs)
            result = processor.post_process_grounded_object_detection(
                outputs, inputs.input_ids, box_threshold=args.box_threshold,
                text_threshold=args.text_threshold, target_sizes=[(image.height, image.width)])[0]
            for box, score, label in zip(result["boxes"], result["scores"], result["labels"]):
                detections.append({"label": label, "score": round(score.item(), 4),
                                   "box_xyxy": [round(x, 2) for x in box.tolist()]})
    args.output.mkdir(parents=True, exist_ok=True)
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)
    for detection in detections:
        box = detection["box_xyxy"]
        draw.rectangle(box, outline="#00ff88", width=3)
        label = f'{detection["label"]} {detection["score"]:.2f}'
        x, y = max(0, box[0]), max(0, box[1] - 14)
        draw.text((x, y), label, fill="black", stroke_width=1, stroke_fill="#00ff88")
    image_path = args.output / f"{args.image.stem}_boxes.jpg"
    json_path = args.output / f"{args.image.stem}_detections.json"
    annotated.save(image_path, quality=95)
    elapsed = round(time.perf_counter() - started, 2)
    json_path.write_text(json.dumps({
        "image": str(args.image.resolve()), "size": list(image.size), "device": device,
        "tags": tags, "detections": detections, "seconds": elapsed
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Detected {len(detections)} boxes in {elapsed}s\nImage: {image_path}\nJSON: {json_path}")

if __name__ == "__main__":
    main()
