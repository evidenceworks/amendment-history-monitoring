from pathlib import Path
import csv,hashlib,sys
ROOT=Path(__file__).resolve().parents[1]
def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()
def verify(manifest):
    rows=list(csv.DictReader((ROOT/manifest).open(newline="",encoding="utf-8")))
    bad=[]
    for r in rows:
        p=ROOT/r["path"]
        if not p.is_file(): bad.append((r["path"],"MISSING")); continue
        if str(p.stat().st_size)!=r["bytes"]: bad.append((r["path"],"SIZE")); continue
        if sha(p)!=r["sha256"]: bad.append((r["path"],"SHA256"))
    if bad:
        print("FAIL")
        for x in bad: print(x[0],x[1])
        return 1
    print(f"PASS: {len(rows)} files verified")
    return 0

if __name__=="__main__": sys.exit(verify("verification/science_manifest.csv"))
