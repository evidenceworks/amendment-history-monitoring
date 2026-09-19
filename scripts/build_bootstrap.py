"""Package authentic accepted primary replicate arrays in deterministic gzip CSV."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import pathlib

import pandas as pd


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accepted-analysis-results", required=True, type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--provenance-output", required=True, type=pathlib.Path)
    args = parser.parse_args()
    inputs = {
        "validation_2023": args.accepted_analysis_results / "validation_2023/paired_BIN_bootstrap.csv",
        "full_2024": args.accepted_analysis_results / "validation_2024/full_180/paired_BIN_bootstrap.csv",
        "mature_2024": args.accepted_analysis_results / "validation_2024/mature_365/paired_BIN_bootstrap.csv",
    }
    if args.output.exists() or args.provenance_output.exists():
        raise SystemExit("refusing to overwrite retained-bootstrap output")
    frames = []
    source = {}
    for population, path in inputs.items():
        frame = pd.read_csv(path)
        if len(frame) != 500 or frame.replicate.tolist() != list(range(1, 501)):
            raise RuntimeError(f"invalid accepted replicate numbering: {population}")
        if frame.duplicated("replicate").any():
            raise RuntimeError(f"duplicate accepted replicate: {population}")
        frame.insert(0, "population", population)
        frames.append(frame)
        source[population] = {"accepted_relative_path": path.relative_to(args.accepted_analysis_results).as_posix(),
                              "bytes": path.stat().st_size, "sha256": sha(path),
                              "columns": list(frame.columns[1:])}
    union = pd.concat(frames, ignore_index=True, sort=False)
    canonical = union.to_csv(index=False, lineterminator="\n", na_rep="", float_format="%.17g").encode("utf-8")
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", filename="", mtime=0, compresslevel=6) as stream:
        stream.write(canonical)
    body = buffer.getvalue()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(body)
    provenance = {
        "status": "AUTHENTIC_ACCEPTED_PRIMARY_REPLICATES",
        "description": "Retained, not regenerated in Core; point estimates remain freshly computed.",
        "populations": list(inputs), "rows": len(union), "replicates_per_population": 500,
        "source": source, "canonical_csv_sha256": hashlib.sha256(canonical).hexdigest(),
        "gzip_sha256": hashlib.sha256(body).hexdigest(), "gzip_bytes": len(body),
        "quantile": "numpy linear/type-7 over finite accepted values",
    }
    args.provenance_output.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(provenance, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
