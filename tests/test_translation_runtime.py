"""Opt-in native DLL compatibility checks; requires CUDA and the Argos model."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
TRANSLATE = "from translation_service import translate_vi; assert translate_vi('bottle')"
CONVOLVE = """
import torch
assert torch.cuda.is_available(), 'CUDA is required for this integration test'
with torch.inference_mode():
    layer = torch.nn.Conv2d(3, 8, 3).cuda()
    output = layer(torch.randn(1, 3, 32, 32, device='cuda'))
    torch.cuda.synchronize()
    assert torch.isfinite(output).all().item()
"""


@unittest.skipUnless(os.environ.get('ENGLISHLENS_RUNTIME_TESTS') == '1',
                     'Set ENGLISHLENS_RUNTIME_TESTS=1 with CUDA and Argos installed')
class TranslationRuntimeTests(unittest.TestCase):
    def check_order(self, code):
        # A native DLL mismatch terminates Python, so isolate each load order.
        result = subprocess.run([sys.executable, '-X', 'utf8', '-c', code],
                                cwd=ROOT, capture_output=True, text=True,
                                encoding='utf-8', timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_translation_then_cuda(self):
        self.check_order(TRANSLATE + '\n' + CONVOLVE)

    def test_cuda_then_translation_then_cuda(self):
        self.check_order(CONVOLVE + '\n' + TRANSLATE + '\n' + CONVOLVE)


if __name__ == '__main__':
    unittest.main()
