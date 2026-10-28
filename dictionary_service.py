"""Dictionary lookup cache; fixed upstream URL, bounded words and timeout."""
import re
import threading
import time
from urllib.parse import quote
import requests
from translation_service import translate_vi

cache = {}
lock = threading.Lock()

def lookup(word):
    word = word.strip().lower()
    if len(word) > 80 or not re.fullmatch(r"[a-z]+(?:[ '\-][a-z]+)*", word):
        return 400, {"error": "Từ tra cứu không hợp lệ."}
    with lock:
        saved = cache.get(word)
        if saved and time.monotonic() - saved[0] < 86400:
            return saved[1], saved[2]
    try:
        response = requests.get(
            "https://api.dictionaryapi.dev/api/v2/entries/en/" + quote(word, safe=""),
            timeout=(3, 8))
        if response.status_code == 404:
            status, data = 404, {"error": "Từ điển chưa có mục từ này."}
        elif response.status_code == 200:
            status, data = 200, response.json()
            if not isinstance(data, list) or not data:
                return 502, {"error": "Từ điển chưa có dữ liệu hợp lệ."}
        else:
            return 503, {"error": "Từ điển đang không phản hồi. Vui lòng thử lại."}
    except (requests.RequestException, ValueError):
        return 503, {"error": "Không kết nối được từ điển. Kiểm tra Internet rồi thử lại."}
    with lock:
        if len(cache) >= 128:
            cache.pop(next(iter(cache)))
        cache[word] = time.monotonic(), status, data
    return status, data

audio_cache = {}
def audio(word):
    from urllib.parse import urlsplit
    word = word.strip().lower()
    status, entries = lookup(word)
    if status != 200:
        return status, entries, "application/json"
    with lock:
        saved = audio_cache.get(word)
        if saved:
            return 200, saved[0], saved[1]
    urls = []
    for entry in entries:
        for phonetic in entry.get("phonetics", []):
            url = phonetic.get("audio", "")
            if url.startswith("//"):
                url = "https:" + url
            parsed = urlsplit(url)
            if parsed.scheme == "https" and parsed.hostname in {
                    "api.dictionaryapi.dev", "ssl.gstatic.com", "upload.wikimedia.org"}:
                urls.append(url)
    for url in list(dict.fromkeys(urls))[:2]:
        try:
            with requests.get(url, timeout=(3, 5), stream=True) as response:
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "").split(";")[0]
                if not content_type.startswith("audio/"):
                    continue
                chunks, length = [], 0
                for chunk in response.iter_content(65536):
                    length += len(chunk)
                    if length > 4 * 1024 * 1024:
                        raise ValueError("Audio too large")
                    chunks.append(chunk)
                data = b"".join(chunks)
                if not data:
                    continue
            with lock:
                if len(audio_cache) >= 32:
                    audio_cache.pop(next(iter(audio_cache)))
                audio_cache[word] = data, content_type
            return 200, data, content_type
        except (requests.RequestException, ValueError):
            continue
    return 503, {"error": "Không tải được audio cho từ này."}, "application/json"

translation_cache = {}

def vocabulary(word):
    """Combine Vietnamese translation with a dictionary sense and its example."""
    word = word.strip().lower()
    if len(word) > 80 or not re.fullmatch(r"[a-z]+(?:[ '\-][a-z]+)*", word):
        return 400, {"error": "Nhập từ hoặc cụm từ tiếng Anh (tối đa 80 ký tự)."}
    result = {"word": word, "meaning": "", "definition": "", "example": "",
              "phonetic": "", "warnings": [], "translationSource": "", "dictionarySource": ""}
    with lock:
        saved = translation_cache.get(word)
    if saved and time.monotonic() - saved[0] < 86400:
        result["meaning"] = saved[1]
    else:
        try:
            translated = translate_vi(word)
            if not translated:
                raise ValueError('Argos returned an empty translation')
            result["meaning"] = translated
            with lock:
                if len(translation_cache) >= 128:
                    translation_cache.pop(next(iter(translation_cache)))
                translation_cache[word] = time.monotonic(), result["meaning"]
        except Exception:
            result["warnings"].append("Chưa dịch được bằng Argos Translate. Kiểm tra cài đặt và chạy setup_argos.py rồi thử lại.")
    if result["meaning"]:
        result["translationSource"] = "Argos Translate"
    status, entries = lookup(word)
    if status == 200:
        senses = [d for e in entries for m in e.get("meanings", []) for d in m.get("definitions", []) if d.get("definition")]
        sense = next((d for d in senses if d.get("example")), senses[0] if senses else {})
        result["definition"] = sense.get("definition", "")
        result["example"] = sense.get("example", "")
        result["phonetic"] = next((e["phonetic"] for e in entries if e.get("phonetic")), "") or next((p["text"] for e in entries for p in e.get("phonetics", []) if p.get("text")), "")
        result["dictionarySource"] = "Free Dictionary API"
        if not result["example"]:
            result["warnings"].append("Từ điển chưa cung cấp câu ví dụ cho từ này.")
    else:
        result["warnings"].append("Chưa lấy được định nghĩa và ví dụ từ từ điển. Có thể thử Lấy lại API.")
    return 200, result
