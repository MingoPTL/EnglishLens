"""RAM confidence extraction and detection association without loading weights."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine


class TinyRAM:
    def __init__(self, fail=False):
        self.fc = torch.nn.Identity()
        self.tag_list = ["bottle", "book", "phone"]
        self.class_threshold = torch.tensor([.71, .90, .80])
        self.calls = 0
        self.fail = fail

    def generate_tag(self, image):
        self.calls += 1
        logits = self.fc(image).squeeze(-1)
        if self.fail:
            raise RuntimeError("tagging failed")
        labels = [name for name, keep in zip(
            self.tag_list, (logits.sigmoid() > self.class_threshold)[0]) if keep]
        return [" | ".join(labels)], [""]


class RAMConfidenceTests(unittest.TestCase):
    def test_scores_are_sigmoid_of_same_pass_and_rejected_labels_are_absent(self):
        model = TinyRAM()
        logits = torch.tensor([[[2.1972246], [1.0], [2.2]]])
        tags, scores = engine.infer_ram_with_scores(logits, model)
        self.assertEqual(model.calls, 1)
        self.assertEqual(tags, "bottle | phone")
        self.assertAlmostEqual(scores["bottle"]["score"], .9, places=6)
        self.assertAlmostEqual(scores["bottle"]["threshold"], .71, places=6)
        self.assertNotIn("book", scores)
        self.assertEqual(len(model.fc._forward_hooks), 0)

    def test_capture_hook_is_removed_after_error(self):
        model = TinyRAM(fail=True)
        with self.assertRaisesRegex(RuntimeError, "tagging failed"):
            engine.infer_ram_with_scores(torch.zeros(1, 3, 1), model)
        self.assertEqual(len(model.fc._forward_hooks), 0)

    def test_detection_only_uses_exact_ram_label_and_manual_has_no_ram_score(self):
        class Inputs(dict):
            def to(self, device):
                return self

            input_ids = None

        class Processor:
            def tokenizer(self, prompt):
                return {"input_ids": [1, 2]}

            def __call__(self, **kwargs):
                return Inputs()

            def post_process_grounded_object_detection(self, *args, **kwargs):
                return [{"boxes": torch.tensor([[1., 2., 3., 4.]] * 2),
                         "scores": torch.tensor([.4, .5]),
                         "labels": ["bottle", "bottles"]}]

        subject = engine.Engine()
        subject.device = "cpu"
        subject.ram = object()
        subject.transform = lambda image: torch.zeros(3, 4, 4)
        subject.processor = Processor()
        subject.dino = lambda **kwargs: object()
        image = SimpleNamespace(width=20, height=10, size=(20, 10))
        with patch.object(engine, "model_status", return_value={"dino": True, "ram": True}), \
             patch.object(engine, "infer_ram_with_scores", return_value=(
                 "bottle", {"bottle": {"score": .93456, "threshold": .71}})) as tagging:
            result = subject.infer(image, "auto", "", .3)
            self.assertEqual(result["detections"][0]["ram_score"], .93456)
            self.assertEqual(result["detections"][0]["ram_threshold"], .71)
            self.assertIsNone(result["detections"][1]["ram_score"])
            tagging.assert_called_once()
            manual = subject.infer(image, "manual", "bottle", .3)
            self.assertEqual(manual["ram_scores"], {})
            self.assertTrue(all(d["ram_score"] is None for d in manual["detections"]))
            tagging.assert_called_once()


if __name__ == "__main__":
    unittest.main()
