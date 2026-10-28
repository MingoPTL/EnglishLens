"""Project-local Argos English -> Vietnamese translation (CPU, no network)."""
import os
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ['ARGOS_PACKAGES_DIR'] = str(ROOT / 'models' / 'argos')
os.environ.setdefault('XDG_DATA_HOME', str(ROOT / '.cache' / 'argos-data'))
os.environ.setdefault('XDG_CACHE_HOME', str(ROOT / '.cache'))
os.environ['ARGOS_DEVICE_TYPE'] = 'cpu'
os.environ['ARGOS_MODEL_PROVIDER'] = 'OPENNMT'
_translation = None
_lock = threading.Lock()

def translate_vi(text):
    global _translation
    with _lock:
        if _translation is None:
            import argostranslate.translate
            languages = argostranslate.translate.get_installed_languages()
            source = next((language for language in languages if language.code == 'en'), None)
            target = next((language for language in languages if language.code == 'vi'), None)
            if not source or not target:
                raise RuntimeError('Chưa có model Argos Anh–Việt. Chạy setup_argos.py.')
            _translation = source.get_translation(target)
            if _translation is None:
                raise RuntimeError('Không tìm thấy model Argos Anh–Việt.')
            # SentencePiece's native file loader cannot open some Windows Unicode
            # paths. Python reads the same installed model safely as bytes.
            import sentencepiece
            tokenizer = _translation.underlying.pkg.tokenizer
            tokenizer.processor = sentencepiece.SentencePieceProcessor(
                model_proto=tokenizer.model_file.read_bytes())
        return _translation.translate(text).strip()
