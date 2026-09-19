"""Verify the exact archival source before analysis."""
import argparse, hashlib, pathlib, sys
EXPECTED_BYTES=827_461_297
EXPECTED_ROWS=956_139
EXPECTED_SHA256="f910c1fde198fedb764ba9d6310d9234af7940f7fcfd3cc8bdf2f03974bec418"
def inspect(path):
    path=pathlib.Path(path)
    if not path.is_file(): raise ValueError(f"source does not exist: {path}")
    size=path.stat().st_size; h=hashlib.sha256(); rows=-1
    with path.open("rb") as f:
        rows=sum(1 for line in f if not h.update(line)) - 1
    digest=h.hexdigest()
    if (size,rows,digest)!=(EXPECTED_BYTES,EXPECTED_ROWS,EXPECTED_SHA256):
        raise ValueError("source rejected: expected archival revision 3408 (size, row count, and SHA-256 must all match)")
    return {"bytes":size,"rows":rows,"sha256":digest}
def main():
    p=argparse.ArgumentParser(); p.add_argument("source",type=pathlib.Path); a=p.parse_args()
    try:r=inspect(a.source)
    except ValueError as e: print(f"FAIL: {e}",file=sys.stderr); raise SystemExit(1)
    print(f"PASS: archival revision 3408 verified ({r['rows']} rows; {r['bytes']} bytes)")
if __name__=="__main__": main()
