"""Build and verify the deterministic 19-column compact object.

The bounded vertical-slice route starts from the accepted cohort frames.
The public raw route first executes the unchanged source guard and raw-to-cohort
code, then exports the same compact bytes.  No model is fitted here.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from preprocess import apply_maps, fit_maps  # noqa: E402
from queue_utils import cluster_draw, queue_order, queue_selected, tie  # noqa: E402

SOURCE_SHA = "f910c1fde198fedb764ba9d6310d9234af7940f7fcfd3cc8bdf2f03974bec418"
FEATURE_SHA = "ee402fef19784a7a4e4bbb4042875fe6334a02250dc5b831bb16250f7c633f26"
OUTCOME_SHA = "e76c9bae38d11d9b7b1cc9ddc60e28c561096b35378d671b1d5f11d6aa814790"
ROLES = ("development", "validation_2023", "validation_2024")
COLUMNS = [
    "root_id", "cluster_id", "tie_order", "role", "first_permit",
    "borough", "review", "building", "filing_to_F", "approval_to_F",
    "S_filed", "S_approved", "S_review_diversity", "paa_category",
    "paa_recency", "no_observed_S", "duration", "event", "s1_loc_issued",
]
STRING_COLUMNS = {
    "root_id", "cluster_id", "role", "first_permit", "borough", "review",
    "building", "paa_category",
}
DTYPES = {name: ("string" if name in STRING_COLUMNS else "Int64") for name in COLUMNS}
OPTIONAL = {"review", "building", "approval_to_F", "S_review_diversity", "paa_recency", "s1_loc_issued"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256_path(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_compact(df: pd.DataFrame, production: bool = True) -> None:
    require(list(df.columns) == COLUMNS, "exact ordered 19-column schema required")
    require(len(df) > 0, "empty compact object")
    require(df.root_id.is_monotonic_increasing and not df.root_id.duplicated().any(), "root order/uniqueness failure")
    require(df.root_id.str.fullmatch(r"R\d{9}").fillna(False).all(), "invalid root_id")
    require(df.cluster_id.str.fullmatch(r"C\d{9}").fillna(False).all(), "invalid cluster_id")
    require(df.tie_order.notna().all() and not df.tie_order.duplicated().any(), "tie_order must be unique")
    require(set(df.tie_order.astype(int)) == set(range(1, len(df) + 1)), "tie_order must be a complete rank")
    for column in COLUMNS:
        require(column in OPTIONAL or df[column].notna().all(), f"missing mandatory field {column}")
    require(set(df.role) == set(ROLES), "unexpected or missing role")
    first = pd.to_datetime(df.first_permit, format="%Y-%m-%d", errors="raise")
    landmark = first + pd.Timedelta(days=365)
    dev = df.role == "development"
    require(((first[dev].dt.year >= 2017) & (first[dev].dt.year <= 2022)).all(), "development year mismatch")
    require((landmark[dev] < pd.Timestamp("2023-12-31")).all(), "nonpositive development window")
    require((first[df.role == "validation_2023"].dt.year == 2023).all(), "2023 role mismatch")
    require((first[df.role == "validation_2024"].dt.year == 2024).all(), "2024 role mismatch")
    end = pd.Series(pd.Timestamp("2026-09-12"), index=df.index)
    end.loc[dev] = pd.concat(
        [landmark[dev] + pd.Timedelta(days=365), pd.Series(pd.Timestamp("2023-12-31"), index=landmark[dev].index)], axis=1
    ).min(axis=1)
    potential = (end - landmark).dt.days
    require(((df.duration > 0) & (df.duration <= potential)).all(), "duration outside information window")
    require((df.loc[df.event == 0, "duration"] == potential[df.event == 0]).all(), "nonevent duration mismatch")
    require(df.event.isin([0, 1]).all(), "event must be binary")
    require(df.paa_category.isin(["0", "1", "2", "3"]).all(), "invalid PAA category")
    exposed = df.paa_category != "0"
    require(df.loc[~exposed, "paa_recency"].isna().all(), "unexposed recency must be empty")
    require(df.loc[exposed, "paa_recency"].notna().all(), "exposed recency is missing")
    require((df.S_approved <= df.S_filed).all(), "S approvals exceed S filings")
    require(df.no_observed_S.isin([0, 1]).all(), "invalid S2 flag")
    require((df.loc[df.no_observed_S == 1, "S_filed"] == 0).all(), "S2 flag conflict")
    require(df.loc[dev, "s1_loc_issued"].isna().all(), "development S1 leakage")
    require(df.loc[~dev, "s1_loc_issued"].isin([0, 1]).all(), "validation S1 label missing")
    if production:
        require(df.role.value_counts().to_dict() == {
            "development": 131311, "validation_2023": 33126, "validation_2024": 33847,
        }, "authoritative role counts mismatch")
        require(int(((df.role == "validation_2024") & (first <= pd.Timestamp("2024-09-12"))).sum()) == 24431,
                "mature-2024 count mismatch")


def read_frames(features_path: pathlib.Path, outcomes_path: pathlib.Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    feature_dtype = {"root": str, "bin": str, "role": str, "quarter": str, "paa_category": str, "first_permit": str, "landmark": str}
    outcome_dtype = {"root": str, "role": str, "landmark": str, "status_for_S1": str}
    features = pd.read_csv(features_path, dtype=feature_dtype)
    outcomes = pd.read_csv(outcomes_path, dtype=outcome_dtype).fillna({"status_for_S1": ""})
    require(features.root.tolist() == outcomes.root.tolist(), "feature/outcome root order mismatch")
    return features, outcomes


def from_accepted_frames(features: pd.DataFrame, outcomes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    mask = features.role.isin(ROLES)
    f = features.loc[mask].copy()
    o = outcomes.loc[mask].copy()
    order = np.argsort(f.root.astype(str).to_numpy(), kind="stable")
    f = f.iloc[order].reset_index(drop=True)
    o = o.iloc[order].reset_index(drop=True)
    require(not f.root.duplicated().any(), "duplicate accepted root")
    bins = sorted(f.bin.astype(str).unique())
    bin_map = {value: f"C{i + 1:09d}" for i, value in enumerate(bins)}
    tie_hashes = f.root.astype(str).map(tie).to_numpy()
    require(len(set(tie_hashes)) == len(f), "queue tie hash collision")
    tie_rank = np.empty(len(f), dtype=np.int64)
    tie_rank[np.argsort(tie_hashes, kind="stable")] = np.arange(1, len(f) + 1)
    compact = pd.DataFrame({
        "root_id": [f"R{i + 1:09d}" for i in range(len(f))],
        "cluster_id": f.bin.astype(str).map(bin_map),
        "tie_order": tie_rank,
        "role": f.role,
        "first_permit": f.first_permit,
        "borough": f.borough,
        "review": f.review,
        "building": f.building,
        "filing_to_F": f.filing_to_F,
        "approval_to_F": f.approval_to_F,
        "S_filed": f.S_filed,
        "S_approved": f.S_approved,
        "S_review_diversity": f.S_review_diversity,
        "paa_category": f.paa_category,
        "paa_recency": f.paa_recency,
        "no_observed_S": f.no_observed_S,
        "duration": o.duration,
        "event": o.event,
        "s1_loc_issued": np.where(f.role == "development", pd.NA, (o.status_for_S1 == "LOC Issued").astype(int)),
    })[COLUMNS].astype(DTYPES)
    validate_compact(compact)
    mapping = pd.DataFrame({"root": f.root, "root_id": compact.root_id, "bin": f.bin, "cluster_id": compact.cluster_id,
                            "original_tie_sha256": tie_hashes, "tie_order": tie_rank})
    return compact, mapping


def original_frames(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    validate_compact(df)
    f = df[["role", "first_permit", "borough", "review", "building", "filing_to_F", "approval_to_F", "S_filed",
            "S_approved", "S_review_diversity", "paa_category", "paa_recency", "no_observed_S"]].copy()
    f.insert(0, "bin", df.cluster_id)
    f.insert(0, "root", df.root_id)
    first = pd.to_datetime(f.first_permit)
    landmark = first + pd.Timedelta(days=365)
    f["landmark"] = landmark.dt.strftime("%Y-%m-%d")
    f["year_centered"] = first.dt.year - 2020
    f["quarter"] = first.dt.quarter.astype(str)
    f["paa_90"] = ((f.paa_category != "0") & (f.paa_recency <= 90)).fillna(False).astype(int)
    f["mature_2024"] = ((f.role == "validation_2024") & (first <= pd.Timestamp("2024-09-12"))).astype(int)
    for name in ["filing_to_F", "approval_to_F", "S_filed", "S_approved", "S_review_diversity", "paa_recency"]:
        f[name] = f[name].to_numpy(dtype=float, na_value=np.nan)
    for name in ["borough", "review", "building", "paa_category"]:
        f[name] = f[name].astype(object).where(f[name].notna(), np.nan)
    dev = f.role == "development"
    end = pd.Series(pd.Timestamp("2026-09-12"), index=df.index)
    end.loc[dev] = pd.concat(
        [landmark[dev] + pd.Timedelta(days=365), pd.Series(pd.Timestamp("2023-12-31"), index=landmark[dev].index)], axis=1
    ).min(axis=1)
    observed = (landmark + pd.to_timedelta(df.duration.astype(int), unit="D")).dt.strftime("%Y-%m-%d").where(df.event == 1, "")
    status = np.where(dev, "", np.where(df.s1_loc_issued.astype("Int64").fillna(0) == 1, "LOC Issued", ""))
    o = pd.DataFrame({"root": df.root_id, "role": df.role, "landmark": f.landmark,
                      "observation_end": end.dt.strftime("%Y-%m-%d"), "duration": df.duration.astype(int),
                      "event": df.event.astype(int), "observed_signoff": observed, "status_for_S1": status})
    return f, o


def canonical_bytes(df: pd.DataFrame) -> bytes:
    validate_compact(df)
    return df.astype(DTYPES).to_csv(index=False, lineterminator="\n", na_rep="").encode("utf-8")


def gzip_bytes(data: bytes) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", filename="", mtime=0, compresslevel=6) as stream:
        stream.write(data)
    return buffer.getvalue()


def schema_payload() -> dict:
    return {
        "schema_version": "analysis-ready-19-v1",
        "columns": [{"name": name, "type": DTYPES[name], "nullable": name in OPTIONAL} for name in COLUMNS],
        "predictor_columns": COLUMNS[3:16],
        "outcome_only_columns": ["duration", "event", "s1_loc_issued"],
        "identifier_columns": ["root_id", "cluster_id", "tie_order"],
        "notes": {
            "paa_category": "0, 1, 2, or 3 where 3 means 3+",
            "approval_to_F": "signed days; negative values are valid",
            "paa_recency": "missing only for category 0; values above 365 are valid",
            "s1_loc_issued": "missing in development; binary in validation",
        },
    }


def compare_values(original: pd.DataFrame, rebuilt: pd.DataFrame, columns: list[str]) -> dict:
    result = {}
    for name in columns:
        a, b = original[name].reset_index(drop=True), rebuilt[name].reset_index(drop=True)
        if pd.api.types.is_numeric_dtype(a) or pd.api.types.is_numeric_dtype(b):
            equal = np.array_equal(pd.to_numeric(a, errors="coerce").to_numpy(float),
                                   pd.to_numeric(b, errors="coerce").to_numpy(float), equal_nan=True)
        else:
            equal = np.array_equal(a.fillna("").astype(str).to_numpy(), b.fillna("").astype(str).to_numpy())
        result[name] = bool(equal)
    return result


def parity_receipt(compact: pd.DataFrame, mapping: pd.DataFrame, source_f: pd.DataFrame, source_o: pd.DataFrame,
                   prepared: pathlib.Path | None, primary: pathlib.Path | None) -> dict:
    mask = source_f.role.isin(ROLES)
    sf = source_f.loc[mask].copy().sort_values("root", kind="stable").reset_index(drop=True)
    so = source_o.loc[mask].copy().set_index("root").loc[sf.root].reset_index()
    rf, ro = original_frames(compact)
    feature_columns = ["role", "first_permit", "landmark", "borough", "review", "building", "year_centered", "quarter",
                       "filing_to_F", "approval_to_F", "S_filed", "S_approved", "S_review_diversity", "paa_category",
                       "paa_recency", "paa_90", "no_observed_S", "mature_2024"]
    outcome_columns = ["role", "landmark", "observation_end", "duration", "event", "observed_signoff"]
    value_parity = {**{f"feature.{k}": v for k, v in compare_values(sf, rf, feature_columns).items()},
                    **{f"outcome.{k}": v for k, v in compare_values(so, ro, outcome_columns).items()}}
    s1_original = np.where(sf.role == "development", pd.NA, (so.status_for_S1.fillna("") == "LOC Issued").astype(int))
    value_parity["outcome.s1_loc_issued"] = bool(np.array_equal(
        pd.array(s1_original, dtype="Int64").to_numpy(dtype=float, na_value=np.nan),
        compact.s1_loc_issued.to_numpy(dtype=float, na_value=np.nan), equal_nan=True))
    failed_value_columns = [name for name, passed in value_parity.items() if not passed]
    require(not failed_value_columns, "source-to-compact row/value parity failed: " + ", ".join(failed_value_columns))
    require(mapping.root.tolist() == sf.root.tolist(), "root order mapping mismatch")
    require(mapping.bin.tolist() == sf.bin.astype(str).tolist(), "BIN order mapping mismatch")
    role_counts = {str(k): int(v) for k, v in compact.role.value_counts().items()}
    paa_counts = {str(role): {str(k): int(v) for k, v in part.paa_category.value_counts().sort_index().items()}
                  for role, part in compact.groupby("role", sort=False)}
    overlap = {
        role: int(len(set(sf.loc[sf.role == "development", "bin"]) & set(sf.loc[sf.role == role, "bin"])))
        for role in ("validation_2023", "validation_2024")
    }
    require(overlap == {"validation_2023": 8682, "validation_2024": 7663}, "BIN overlap mismatch")
    receipt = {
        "status": "PASS", "rows": len(compact), "role_counts": role_counts, "paa_counts": paa_counts,
        "mature_2024": int(((compact.role == "validation_2024") & (compact.first_permit <= "2024-09-12")).sum()),
        "development_BIN_overlap": overlap,
        "approval_to_F_min_max": [int(compact.approval_to_F.min()), int(compact.approval_to_F.max())],
        "paa_recency_min_max": [int(compact.paa_recency.min()), int(compact.paa_recency.max())],
        "source_value_columns": value_parity,
        "root_order_mapping_sha256": sha256_bytes("\n".join(mapping.root + "," + mapping.root_id).encode()),
        "cluster_order_mapping_sha256": sha256_bytes("\n".join(mapping.bin + "," + mapping.cluster_id).encode()),
    }
    rebuilt_maps = fit_maps(rf[rf.role == "development"].copy())
    receipt["design_columns"] = {}
    receipt["design_sha256"] = {}
    receipt["accepted_design_parity"] = {}
    accepted_maps = json.loads((prepared / "preprocessing_maps.json").read_text()) if prepared else None
    if accepted_maps:
        left = dict(accepted_maps); right = dict(rebuilt_maps)
        left.pop("fit_roots", None); right.pop("fit_roots", None)
        require(left == right, "development-only preprocessing maps mismatch")
        receipt["preprocessing_maps_exact_except_opaque_roots"] = True
    for role in ROLES:
        part = rf[rf.role == role].copy()
        x0, x1, n0, n1, _ = apply_maps(part, rebuilt_maps)
        require((x0.shape[1], x1.shape[1]) == (20, 26), f"unexpected design width for {role}")
        receipt["design_columns"][role] = {"M0": n0, "M1": n1}
        receipt["design_sha256"][role] = {"M0": sha256_bytes(x0.tobytes()), "M1": sha256_bytes(x1.tobytes())}
        if prepared:
            a0 = np.load(prepared / f"{role}_M0.npy")
            a1 = np.load(prepared / f"{role}_M1.npy")
            require(np.array_equal(a0, x0) and np.array_equal(a1, x1), f"accepted matrix parity failed for {role}")
            receipt["accepted_design_parity"][role] = True
    receipt["shared_M0_bytes"] = all(
        apply_maps(rf[rf.role == role], rebuilt_maps)[0].tobytes() ==
        np.ascontiguousarray(apply_maps(rf[rf.role == role], rebuilt_maps)[1][:, :20]).tobytes()
        for role in ROLES
    )
    require(receipt["shared_M0_bytes"], "shared M0 block mismatch")
    weight_checks = {}
    queue_checks = {}
    for population, mask in {
        "validation_2023": rf.role == "validation_2023",
        "full_2024": rf.role == "validation_2024",
        "mature_2024": (rf.role == "validation_2024") & (rf.mature_2024 == 1),
    }.items():
        source_part = sf.loc[mask.to_numpy()].reset_index(drop=True)
        compact_part = compact.loc[mask.to_numpy()].reset_index(drop=True)
        old_rng = np.random.Generator(np.random.PCG64(20260916))
        new_rng = np.random.Generator(np.random.PCG64(20260916))
        old_h, new_h = hashlib.sha256(), hashlib.sha256()
        for _ in range(500):
            old_w = cluster_draw(source_part.bin.astype(str).to_numpy(), old_rng)
            new_w = cluster_draw(compact_part.cluster_id.astype(str).to_numpy(), new_rng)
            require(np.array_equal(old_w, new_w), f"bootstrap weight mismatch: {population}")
            old_h.update(old_w.astype(np.int32).tobytes()); new_h.update(new_w.astype(np.int32).tobytes())
        weight_checks[population] = {"all_500_equal": True, "weight_stream_sha256": old_h.hexdigest()}
        if primary:
            pred_role = "validation_2023" if population == "validation_2023" else "validation_2024"
            arrays = np.load(primary / "predictions" / f"{pred_role}.npz")
            index = {root: i for i, root in enumerate(arrays["roots"].astype(str))}
            positions = np.array([index[root] for root in source_part.root.astype(str)])
            horizon = 365 if population != "full_2024" else 180
            scores = arrays["M1"][positions, horizon]
            old_order = queue_order(source_part.root.to_numpy(), source_part.landmark.to_numpy(), scores)
            new_order = np.lexsort((compact_part.tie_order.to_numpy(int), -scores, source_part.landmark.to_numpy()))
            require(np.array_equal(old_order, new_order), f"queue tie order mismatch: {population}")
            old_selected = queue_selected(source_part.root.to_numpy(), source_part.landmark.to_numpy(), scores, order=old_order)
            new_selected = queue_selected(compact_part.root_id.to_numpy(), source_part.landmark.to_numpy(), scores, order=new_order)
            require(np.array_equal(old_selected, new_selected), f"queue selection mismatch: {population}")
            queue_checks[population] = {"order_equal": True, "selection_equal": True,
                                        "selected": int(old_selected.sum())}
    receipt["bootstrap_weight_parity"] = weight_checks
    receipt["queue_tie_parity"] = queue_checks
    return receipt


def run_raw_builder(source: pathlib.Path, build_area: pathlib.Path, rscript: str) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path, pathlib.Path]:
    subprocess.run([sys.executable, str(ROOT / "scripts/check_source.py"), str(source)], check=True, cwd=ROOT)
    results, work = build_area / "analysis_results", build_area / "working_data"
    results.mkdir(parents=True); work.mkdir()
    shutil.copytree(ROOT / "src", results / "src")
    shutil.copytree(ROOT / "config", results / "config")
    for name in ("cohort_reconstruction", "prepared_cohort"):
        (results / name).mkdir()
    env = dict(os.environ, REPRO_OUTPUT=str(results), REPRO_WORK=str(work), REPRO_SOURCE=str(source),
               REPRO_RSCRIPT=rscript, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    for script in ("ingest.py", "cohort.py", "audit.py", "prepare.py"):
        subprocess.run([sys.executable, str(results / "src" / script)], check=True, env=env)
    return (results / "cohort_reconstruction/event_time_features.csv",
            results / "cohort_reconstruction/outcomes_separate.csv", results / "prepared_cohort", results)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source", type=pathlib.Path, help="exact revision-3408 raw CSV")
    group.add_argument("--features", type=pathlib.Path, help="accepted event_time_features.csv")
    parser.add_argument("--outcomes", type=pathlib.Path)
    parser.add_argument("--accepted-prepared", type=pathlib.Path)
    parser.add_argument("--accepted-primary", type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--mapping-output-dir", type=pathlib.Path)
    parser.add_argument("--rscript", default="Rscript")
    args = parser.parse_args()
    start = time.perf_counter()
    output = args.output.resolve()
    require(not output.exists(), "output directory must not already exist")
    output.mkdir(parents=True)
    raw_build_area = None
    if args.source:
        require(not args.outcomes, "--outcomes is only used with --features")
        require(sha256_path(args.source.resolve()) == SOURCE_SHA, "raw source SHA-256 mismatch")
        raw_build_area = output / "raw_builder_workspace"
        features_path, outcomes_path, prepared, _ = run_raw_builder(args.source.resolve(), raw_build_area, args.rscript)
    else:
        require(args.outcomes is not None, "--outcomes is required with --features")
        features_path, outcomes_path = args.features.resolve(), args.outcomes.resolve()
        require(sha256_path(features_path) == FEATURE_SHA, "accepted feature frame SHA-256 mismatch")
        require(sha256_path(outcomes_path) == OUTCOME_SHA, "accepted outcome frame SHA-256 mismatch")
        prepared = args.accepted_prepared.resolve() if args.accepted_prepared else None
    features, outcomes = read_frames(features_path, outcomes_path)
    compact, mapping = from_accepted_frames(features, outcomes)
    receipt = parity_receipt(compact, mapping, features, outcomes, prepared,
                             args.accepted_primary.resolve() if args.accepted_primary else None)
    canonical = canonical_bytes(compact)
    compressed = gzip_bytes(canonical)
    schema = schema_payload()
    schema_bytes = (json.dumps(schema, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    (output / "analysis.csv.gz").write_bytes(compressed)
    (output / "schema.json").write_bytes(schema_bytes)
    receipt_bytes = (json.dumps(receipt, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    (output / "compact_parity.json").write_bytes(receipt_bytes)
    provenance = {
        "status": "REAL_DATA_PARITY_PASS", "schema_version": schema["schema_version"],
        "dataset_id": "w9ak-ipjd", "source_revision": 3408, "source_rows": 956139,
        "source_bytes": 827461297, "source_sha256": SOURCE_SHA,
        "source_archive_url": "https://data.cityofnewyork.us/api/archival.csv?id=w9ak-ipjd&version=3408&method=export",
        "accepted_feature_frame_sha256": sha256_path(features_path),
        "accepted_outcome_frame_sha256": sha256_path(outcomes_path),
        "builder_sha256": sha256_path(pathlib.Path(__file__)),
        "configuration_sha256": sha256_path(ROOT / "src/config.json"),
        "compact_sha256": sha256_bytes(compressed), "canonical_csv_sha256": sha256_bytes(canonical),
        "schema_sha256": sha256_bytes(schema_bytes), "compact_parity_receipt_sha256": sha256_bytes(receipt_bytes),
        "rows": len(compact), "columns": COLUMNS,
        "role_counts": {str(k): int(v) for k, v in compact.role.value_counts().items()},
        "mature_2024_roots": receipt["mature_2024"],
        "ordering": "sorted normalized original root; monotone BIN relabeling; retained original queue-tie rank",
        "compression": "gzip level 6; mtime=0; empty embedded filename",
        "build_mode": "raw_revision_3408" if args.source else "accepted_input_vertical_slice",
        "elapsed_seconds": time.perf_counter() - start,
    }
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    if args.mapping_output_dir:
        args.mapping_output_dir.mkdir(parents=True, exist_ok=True)
        mapping.to_csv(args.mapping_output_dir / "original_to_opaque_mapping.csv", index=False)
    if raw_build_area:
        try:
            shutil.rmtree(raw_build_area / "working_data")
        except OSError:
            # A synchronized Windows filesystem may transiently retain a SQLite handle after the
            # child exits.  Cleanup is non-scientific and must not invalidate
            # already-written, hash-verified compact output.
            provenance["temporary_working_data_cleanup"] = "deferred"
    print(json.dumps({"status": "PASS", **provenance}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
