"""Resume RAM using smaller independently retried ranges."""
import concurrent.futures as cf
import hashlib
import json
import time
from pathlib import Path
import requests
from download_ram_parallel import SIZE, SHA256, URL, TARGET

folder=TARGET.parent/"chunks"
folder.mkdir(exist_ok=True)
manifest=folder/"manifest.json"
if manifest.exists():
    plan=json.loads(manifest.read_text())
else:
    step=(SIZE+7)//8
    plan=[]
    for i in range(8):
        part=TARGET.with_suffix(f".part{i}")
        saved=part.stat().st_size if part.exists() else 0
        start=i*step+saved
        end=min(SIZE,(i+1)*step)
        for offset in range(start,end,8*1024*1024):
            plan.append({"start":offset,"end":min(end,offset+8*1024*1024)-1,"part":i})
    manifest.write_text(json.dumps(plan))
def fetch(item):
    start,end=item["start"],item["end"]
    path=folder/f"{start}.bin"
    for attempt in range(12):
        saved=path.stat().st_size if path.exists() else 0
        if saved==end-start+1:return path
        try:
            with requests.get(URL,headers={"Range":f"bytes={start+saved}-{end}"},stream=True,timeout=(20,30)) as r:
                r.raise_for_status()
                if r.status_code!=206 or r.headers.get("Content-Range")!=f"bytes {start+saved}-{end}/{SIZE}":
                    raise RuntimeError("Unexpected server byte range")
                with path.open("ab") as f:
                    for chunk in r.iter_content(256*1024):f.write(chunk)
        except requests.RequestException:
            time.sleep(min(attempt+1,5))
    raise RuntimeError(f"Failed range {start}")
with cf.ThreadPoolExecutor(max_workers=32) as pool:
    jobs=[pool.submit(fetch,item) for item in plan]
    base=sum(p.stat().st_size for p in TARGET.parent.glob("*.part[0-7]"))
    while not all(job.done() for job in jobs):
        done=base+sum(p.stat().st_size for p in folder.glob("*.bin"))
        print(f"RAM: {done/1e6:.0f}/{SIZE/1e6:.0f} MB",flush=True)
        time.sleep(15)
    [job.result() for job in jobs]
digest=hashlib.sha256()
combined=TARGET.with_suffix(".assembling")
with combined.open("wb") as out:
    for i in range(8):
        paths=[TARGET.with_suffix(f".part{i}")]+[folder/f'{v["start"]}.bin' for v in plan if v["part"]==i]
        for path in paths:
            if not path.exists():continue
            with path.open("rb") as source:
                while block:=source.read(8*1024*1024):
                    digest.update(block);out.write(block)
if combined.stat().st_size!=SIZE or digest.hexdigest()!=SHA256:raise RuntimeError("RAM checksum mismatch")
combined.replace(TARGET)
print("RAM complete, SHA256 verified.",flush=True)
