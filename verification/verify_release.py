"""Verify the checksummed release payload while allowing mutable GitHub-facing docs."""
from pathlib import Path
import csv
import hashlib
import sys

ROOT = Path(__file__).resolve().parents[1]
MUTABLE_FILES = {"README.md", "CITATION.cff", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md"}
MUTABLE_PREFIXES = (".github/",)


def is_mutable_public_path(path):
    value = path.as_posix() if isinstance(path, Path) else str(path)
    return value in MUTABLE_FILES or value.startswith(MUTABLE_PREFIXES)


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify(manifest):
    rows = list(csv.DictReader((ROOT / manifest).open(newline="", encoding="utf-8")))
    bad = []
    expected = {row["path"] for row in rows}
    for row in rows:
        path = ROOT / row["path"]
        if not path.is_file():
            bad.append((row["path"], "MISSING"))
            continue
        if str(path.stat().st_size) != row["bytes"]:
            bad.append((row["path"], "SIZE"))
            continue
        if sha(path) != row["sha256"]:
            bad.append((row["path"], "SHA256"))

    manifest_path = (ROOT / manifest).resolve()
    actual = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.resolve() != manifest_path
        and ".git" not in path.relative_to(ROOT).parts
        and "__pycache__" not in path.relative_to(ROOT).parts
        and path.suffix != ".pyc"
        and not is_mutable_public_path(path.relative_to(ROOT))
    }
    for path in sorted(actual - expected):
        bad.append((path, "UNMANIFESTED"))
    for path in sorted(expected - actual):
        if not any(item[0] == path for item in bad):
            bad.append((path, "MISSING"))

    if bad:
        print("FAIL")
        for item in bad:
            print(item[0], item[1])
        return 1
    print(f"PASS: {len(rows)} files verified")
    return 0


if __name__ == "__main__":
    sys.exit(verify("verification/release_manifest.csv"))
