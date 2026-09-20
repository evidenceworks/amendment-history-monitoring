"""Build the non-self-referential manifest of science-critical repository files."""
from pathlib import Path
import csv
import hashlib

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "verification/science_manifest.csv"
PREFIXES = (
    "config/", "data/", "environment/", "figures/final/", "figures/data/",
    "notebooks/", "results/reference/", "scripts/", "source/", "src/",
)
EXPLICIT = {
    "full-audit.md", "source.md", "requirements.txt",
    "reproduce.py", "verification/compare_results.py",
    "verification/verify_science.py",
    "verification/build_science_manifest.py",
    "verification/test_integrity.py",
    "verification/test_comparator.py",
    "verification/test_runtime.py",
    "verification/verify_core.py",
    "verification/test_analysis_data.py",
    "verification/test_core.py",
}

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

rows = []
for path in sorted(ROOT.rglob("*")):
    if not path.is_file() or path == OUT or "__pycache__" in path.parts or path.suffix == ".pyc":
        continue
    rel = path.relative_to(ROOT).as_posix()
    if rel == "source/README.md":
        continue
    if rel in EXPLICIT or rel.startswith(PREFIXES):
        rows.append((rel, path.stat().st_size, sha(path)))
with OUT.open("w", newline="", encoding="utf-8") as stream:
    writer = csv.writer(stream)
    writer.writerow(["path", "bytes", "sha256"])
    writer.writerows(rows)
print(f"wrote {len(rows)} science-critical rows")
