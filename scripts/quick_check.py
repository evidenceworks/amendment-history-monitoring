"""Dependency-free integrity and headline-result Quick check."""
from __future__ import annotations
import argparse, csv, gzip, hashlib, json, pathlib, time

ROOT = pathlib.Path(__file__).resolve().parents[1]

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""): h.update(block)
    return h.hexdigest()

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--json-out", type=pathlib.Path); args = parser.parse_args()
    started = time.perf_counter(); data = ROOT / "data/analysis.csv.gz"
    provenance = json.loads((ROOT / "data/provenance.json").read_text(encoding="utf-8"))
    if sha(data) != provenance["compact_sha256"]: raise RuntimeError("compact SHA-256 mismatch")
    canonical = gzip.decompress(data.read_bytes())
    if hashlib.sha256(canonical).hexdigest() != provenance["canonical_csv_sha256"]: raise RuntimeError("canonical CSV mismatch")
    roles = {}; rows = 0
    for row in csv.DictReader(canonical.decode("utf-8").splitlines()):
        rows += 1; roles[row["role"]] = roles.get(row["role"], 0) + 1
    if rows != 198284 or roles != {"development": 131311, "validation_2024": 33847, "validation_2023": 33126}:
        raise RuntimeError("compact counts mismatch")
    primary = ROOT / "results/reference/primary/2023/performance.csv"
    with primary.open(newline="", encoding="utf-8") as stream:
        metrics = {row["metric"]: float(row["estimate"]) for row in csv.DictReader(stream)}
    required = ["M0__IBS", "M1__IBS", "Delta__IBS", "M0__Uno_C_365", "M1__Uno_C_365"]
    if not all(key in metrics for key in required): raise RuntimeError("headline reference keys missing")
    figures = {f"figure{i}.png": sha(ROOT / f"figures/final/figure{i}.png") for i in range(1, 5)}
    report = {"status": "QUICK_CHECK_PASS", "scope": "integrity/reference inspection; no fit or raw reconstruction",
              "rows": rows, "role_counts": roles, "compact_sha256": sha(data),
              "headline_2023": {key: metrics[key] for key in required}, "figure_sha256": figures,
              "elapsed_seconds": time.perf_counter() - started}
    text = json.dumps(report, indent=2)
    if args.json_out: args.json_out.write_text(text + "\n", encoding="utf-8")
    print(text)

if __name__ == "__main__": main()
