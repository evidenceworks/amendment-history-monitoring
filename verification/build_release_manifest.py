"""Build the release-payload manifest.

The GitHub landing-page README and future GitHub-only metadata are intentionally
mutable and are not part of the checksummed reproduction payload.
"""
from pathlib import Path
import csv
import hashlib

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "verification/release_manifest.csv"
MUTABLE_FILES = {"README.md", "CITATION.cff", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md"}
MUTABLE_PREFIXES = (".github/",)


def is_mutable_public_path(rel):
    path = rel.as_posix()
    return path in MUTABLE_FILES or path.startswith(MUTABLE_PREFIXES)


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


rows = []
for path in sorted(ROOT.rglob("*")):
    rel = path.relative_to(ROOT)
    if (
        not path.is_file()
        or path == OUT
        or ".git" in rel.parts
        or "__pycache__" in rel.parts
        or path.suffix == ".pyc"
        or is_mutable_public_path(rel)
    ):
        continue
    rows.append((rel.as_posix(), path.stat().st_size, sha(path)))

with OUT.open("w", newline="", encoding="utf-8") as stream:
    writer = csv.writer(stream)
    writer.writerow(["path", "bytes", "sha256"])
    writer.writerows(rows)
print(f"wrote {len(rows)} rows")
