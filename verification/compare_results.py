"""Compare a fresh reproduction with the packaged accepted references."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import re
import sys

import numpy as np
import pandas as pd

TOLERANCE = 1e-10


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def primary_target(relative: pathlib.Path) -> pathlib.Path:
    parts = relative.parts
    if parts and parts[0] == "primary":
        parts = parts[1:]
    if parts == ("sensitivities", "s1", "2023", "performance.csv"):
        return pathlib.Path("primary/analysis_results/sensitivity_analyses/S1/validation_2023/performance.csv")
    if parts and parts[0] == "sensitivities":
        sensitivity, population, filename = parts[1].upper(), parts[2], parts[3]
        population_path = {"2023": "validation_2023", "2024_180d": "validation_2024/full_180", "2024_365d": "validation_2024/mature_365"}[population]
        return pathlib.Path("primary/analysis_results/sensitivity_analyses") / sensitivity / population_path / filename
    if parts == ("models", "any_coefficients.csv"):
        return pathlib.Path("primary/analysis_results/sensitivity_analyses/S5/M1/coefficients.csv")
    if parts == ("models", "base_coefficients.csv"):
        return pathlib.Path("primary/analysis_results/primary_models/M0/coefficients.csv")
    if parts == ("models", "history_coefficients.csv"):
        return pathlib.Path("primary/analysis_results/primary_models/M1/coefficients.csv")
    if parts == ("2023", "performance.csv"):
        return pathlib.Path("primary/analysis_results/validation_2023/performance.csv")
    if parts == ("2023", "calibration.csv"):
        return pathlib.Path("primary/analysis_results/validation_2023/calibration.csv")
    if len(parts) == 2 and parts[0] in {"2024_180d", "2024_365d"}:
        return pathlib.Path("primary/analysis_results/validation_2024") / ("full_180" if parts[0] == "2024_180d" else "mature_365") / parts[1]
    raise ValueError(f"unrecognized primary reference: {relative}")


REPRESENTATION_TARGETS = {
    "count_baseline_hazard.csv": "representation/fit/M_count/baseline_cumulative_hazard.csv",
    "count_coefficients.csv": "representation/fit/M_count/coefficients.csv",
    "count_variance.csv": "representation/fit/M_count/variance.csv",
    "count_diagnostics.txt": "representation/fit/M_count/fit_diagnostics.txt",
    "losses.csv": "representation/tables/losses.csv",
    "contrasts.csv": "representation/tables/contrasts.csv",
    "bootstrap.csv": "representation/bootstrap/bootstrap.csv",
    "diagnostics.csv": "representation/diagnostics/diagnostics.csv",
    "calibration.csv": "representation/diagnostics/calibration.csv",
}


def compare_csv(reference: pathlib.Path, reproduced: pathlib.Path) -> dict:
    try:
        left = pd.read_csv(reference)
        right = pd.read_csv(reproduced)
    except Exception as exc:
        return {"status": "MALFORMED", "reason": str(exc), "substantive": True}
    result = {
        "reference_rows": len(left), "reproduced_rows": len(right),
        "reference_columns": list(left.columns), "reproduced_columns": list(right.columns),
        "maximum_absolute_difference": 0.0, "failed_metrics": [],
    }
    if left.shape != right.shape or list(left.columns) != list(right.columns):
        result.update(status="FAIL", reason="shape or column mismatch", substantive=True)
        return result
    maximum = 0.0
    failures = []
    for column in left.columns:
        a, b = left[column], right[column]
        an, bn = pd.to_numeric(a, errors="coerce"), pd.to_numeric(b, errors="coerce")
        numeric = (a.notna().sum() == an.notna().sum() and b.notna().sum() == bn.notna().sum())
        if numeric:
            av, bv = an.to_numpy(float), bn.to_numpy(float)
            same_nan = np.array_equal(np.isnan(av), np.isnan(bv))
            finite = np.isfinite(av) & np.isfinite(bv)
            diff = float(np.max(np.abs(av[finite] - bv[finite]))) if finite.any() else 0.0
            maximum = max(maximum, diff)
            if not same_nan or not np.allclose(av, bv, atol=TOLERANCE, rtol=0, equal_nan=True):
                failures.append({"metric": column, "maximum_absolute_difference": diff})
        else:
            av = a.fillna("<NA>").astype(str).to_numpy()
            bv = b.fillna("<NA>").astype(str).to_numpy()
            if not np.array_equal(av, bv):
                failures.append({"metric": column, "reason": "string/category mismatch"})
    result["maximum_absolute_difference"] = maximum
    result["failed_metrics"] = failures
    result["status"] = "FAIL" if failures else "PASS"
    result["substantive"] = bool(failures)
    return result


def diagnostic_fields(path: pathlib.Path) -> dict[str, str]:
    fields = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r"^(formula|warnings|iterations|loglik|observations|events)\s+(.*)$", line)
        if match:
            fields[match.group(1)] = match.group(2).strip()
    return fields


def compare_diagnostics(reference: pathlib.Path, reproduced: pathlib.Path) -> dict:
    try:
        left, right = diagnostic_fields(reference), diagnostic_fields(reproduced)
    except Exception as exc:
        return {"status": "MALFORMED", "reason": str(exc), "substantive": True}
    failed = []
    maximum = 0.0
    for key in ("formula", "warnings", "iterations", "observations", "events"):
        if left.get(key) != right.get(key):
            failed.append({"metric": key, "reference": left.get(key), "reproduced": right.get(key)})
    try:
        a = np.asarray([float(x) for x in left.get("loglik", "").split(",")])
        b = np.asarray([float(x) for x in right.get("loglik", "").split(",")])
        maximum = float(np.max(np.abs(a - b))) if a.shape == b.shape and a.size else math.inf
        if a.shape != b.shape or not np.allclose(a, b, atol=TOLERANCE, rtol=0):
            failed.append({"metric": "loglik", "maximum_absolute_difference": maximum})
    except Exception as exc:
        failed.append({"metric": "loglik", "reason": str(exc)})
    metadata_equal = sha256(reference) == sha256(reproduced)
    return {
        "status": "FAIL" if failed else "PASS", "substantive": bool(failed),
        "failed_metrics": failed, "maximum_absolute_difference": maximum,
        "runtime_metadata_equal": metadata_equal,
        "runtime_metadata_note": "Full sessionInfo text may differ by path/platform; scientific fit fields are compared above.",
    }


def check_fit(reproduced_root: pathlib.Path, relative: str) -> dict:
    fit = reproduced_root / relative
    required = [fit / "FIT_STATUS.txt", fit / "fit_diagnostics.txt", fit / "coefficients.csv", fit / "baseline_cumulative_hazard.csv"]
    missing = [str(p.relative_to(reproduced_root)) for p in required if not p.is_file()]
    if missing:
        return {"status": "MISSING", "substantive": True, "missing": missing}
    fields = diagnostic_fields(fit / "fit_diagnostics.txt")
    bad_warning = bool(re.search(r"infinite|did not converge|ran out", fields.get("warnings", ""), re.I))
    passed = (fit / "FIT_STATUS.txt").read_text(errors="replace").strip() == "PASS"
    return {"status": "PASS" if passed and not bad_warning else "FAIL", "substantive": not (passed and not bad_warning), "diagnostic_fields": fields}


def keyed_values(left: pd.DataFrame, right: pd.DataFrame, keys: list[str], values: list[str]) -> dict:
    required = set(keys + values)
    if not required.issubset(left.columns) or not required.issubset(right.columns):
        return {"status": "MALFORMED", "substantive": True, "reason": "required key/value columns absent"}
    left = left[keys + values].copy()
    right = right[keys + values].copy()
    if left.duplicated(keys).any() or right.duplicated(keys).any():
        return {"status": "FAIL", "substantive": True, "reason": "duplicate semantic key"}
    left_keys = set(map(tuple, left[keys].itertuples(index=False, name=None)))
    right_keys = set(map(tuple, right[keys].itertuples(index=False, name=None)))
    if left_keys != right_keys:
        return {"status": "FAIL", "substantive": True, "reason": "missing or unexpected semantic key", "left_only": sorted(left_keys-right_keys), "right_only": sorted(right_keys-left_keys)}
    merged = left.merge(right, on=keys, suffixes=("_left", "_right"), validate="one_to_one")
    maximum = 0.0
    failures = []
    for value in values:
        a = pd.to_numeric(merged[f"{value}_left"], errors="raise").to_numpy(float)
        b = pd.to_numeric(merged[f"{value}_right"], errors="raise").to_numpy(float)
        difference = float(np.max(np.abs(a-b))) if len(a) else 0.0
        maximum = max(maximum, difference)
        if not np.allclose(a, b, atol=TOLERANCE, rtol=0, equal_nan=True):
            failures.append({"metric": value, "maximum_absolute_difference": difference})
    return {"status": "FAIL" if failures else "PASS", "substantive": bool(failures), "keys": len(merged), "maximum_absolute_difference": maximum, "failed_metrics": failures}


def load_csv(path: pathlib.Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def figure_crosswalk_records(reproduced: pathlib.Path, repository_root: pathlib.Path) -> list[dict]:
    records = []
    figure_root = repository_root / "figures/data"
    designated = {
        ("2023", "IBS_0_365", "M_any - M_base"),
        ("2023", "IBS_0_365", "M_count - M_any"),
        ("2023", "IBS_0_365", "M_history - M_count"),
        ("full_2024", "Brier_180", "M_any - M_base"),
        ("full_2024", "Brier_180", "M_count - M_any"),
        ("full_2024", "Brier_180", "M_history - M_count"),
    }
    keys = ["population", "loss", "contrast"]
    values = ["estimate", "percentile_2_5", "percentile_97_5"]
    try:
        fresh_source = load_csv(reproduced / "representation/figure/representation_comparison_figure_source.csv")
        fresh_pairs = load_csv(reproduced / "representation/tables/contrasts.csv")
        packaged = load_csv(figure_root / "figure4.csv")
        for frame_name, frame in (("fresh figure source", fresh_source), ("fresh paired contrasts", fresh_pairs), ("packaged Figure 4 source", packaged)):
            frame_keys = set(map(tuple, frame[keys].itertuples(index=False, name=None))) if set(keys).issubset(frame.columns) else set()
            if frame_name == "fresh paired contrasts":
                frame_keys &= designated
            valid = frame_keys == designated and not frame[frame[keys].apply(tuple, axis=1).isin(designated)].duplicated(keys).any()
            records.append({"artifact_class": "figure_4_semantic_keys", "artifact": frame_name, "status": "PASS" if valid else "FAIL", "substantive": not valid, "keys": len(frame_keys)})
        selected_pairs = fresh_pairs[fresh_pairs[keys].apply(tuple, axis=1).isin(designated)]
        records.append({"artifact_class": "figure_4_fresh_to_results", **keyed_values(fresh_source, selected_pairs, keys, values)})
        records.append({"artifact_class": "figure_4_fresh_to_packaged", **keyed_values(fresh_source, packaged, keys, values)})
    except Exception as exc:
        records.append({"artifact_class": "figure_4_crosswalk", "status": "MALFORMED", "substantive": True, "reason": str(exc)})

    try:
        score = load_csv(figure_root / "figure2_scores.csv")
        failures = []
        maximum = 0.0
        for row in score.itertuples(index=False):
            if row.specification_id == "Primary":
                base = reproduced / "primary/analysis_results"
                prefix = pathlib.Path()
            else:
                base = reproduced / "primary/analysis_results/sensitivity_analyses"
                prefix = pathlib.Path(row.specification_id)
            if row.assessment_id == "2023_primary":
                path = base / prefix / "validation_2023/performance.csv"
                metric = "Delta__IBS"
            else:
                path = base / prefix / "validation_2024/full_180/performance.csv"
                metric = "Delta__BS_180"
            source = load_csv(path)
            match = source[source.metric == metric]
            if len(match) != 1:
                failures.append({"specification": row.specification_id, "assessment": row.assessment_id, "reason": "metric row count"})
                continue
            for public, fresh in (("estimate", "estimate"), ("ci_low", "percentile_2_5"), ("ci_high", "percentile_97_5")):
                difference = abs(float(getattr(row, public))-float(match.iloc[0][fresh]))
                maximum = max(maximum, difference)
                if difference > TOLERANCE:
                    failures.append({"specification": row.specification_id, "assessment": row.assessment_id, "metric": public, "difference": difference})
        records.append({"artifact_class": "figure_2_score_crosswalk", "status": "FAIL" if failures else "PASS", "substantive": bool(failures), "rows": len(score), "maximum_absolute_difference": maximum, "failures": failures})
    except Exception as exc:
        records.append({"artifact_class": "figure_2_score_crosswalk", "status": "MALFORMED", "substantive": True, "reason": str(exc)})

    try:
        workload = load_csv(figure_root / "figure2_workload.csv")
        failures = []
        mappings = {
            "actual_allocation": ("M0__realized_review_fraction", 4, "estimate"),
            "flagged_roots_per_model": ("M0__flagged", 0, "estimate"),
            "m0_persisters_per_100": ("M0__persisters_per_100_reviews", 2, "estimate"),
            "m1_persisters_per_100": ("M1__persisters_per_100_reviews", 2, "estimate"),
            "yield_difference": ("Delta__persisters_per_100_reviews", 2, "estimate"),
            "yield_ci_low": ("Delta__persisters_per_100_reviews", 2, "percentile_2_5"),
            "yield_ci_high": ("Delta__persisters_per_100_reviews", 2, "percentile_97_5"),
        }
        for row in workload.itertuples(index=False):
            relative = "validation_2023/performance.csv" if row.assessment_id == "2023_primary" else "validation_2024/full_180/performance.csv"
            source = load_csv(reproduced / "primary/analysis_results" / relative)
            for public, (metric, places, field) in mappings.items():
                match = source[source.metric == metric]
                if len(match) != 1 or not np.isclose(round(float(match.iloc[0][field]), places), float(getattr(row, public)), atol=10**(-(places+4)), rtol=0):
                    failures.append({"assessment": row.assessment_id, "field": public, "metric": metric})
        records.append({"artifact_class": "figure_2_workload_crosswalk", "status": "FAIL" if failures else "PASS", "substantive": bool(failures), "rows": len(workload), "rounding": "allocation 4 decimals; counts 0; rates and intervals 2", "failures": failures})
    except Exception as exc:
        records.append({"artifact_class": "figure_2_workload_crosswalk", "status": "MALFORMED", "substantive": True, "reason": str(exc)})

    try:
        packaged = load_csv(figure_root / "figure3.csv")
        fresh = []
        for assessment, relative in (("2023/365", "validation_2023/calibration.csv"), ("Full 2024/180", "validation_2024/full_180/calibration.csv")):
            frame = load_csv(reproduced / "primary/analysis_results" / relative)
            frame = frame[((frame.horizon == 365) if assessment == "2023/365" else (frame.horizon == 180))].copy()
            frame["assessment"] = assessment
            fresh.append(frame)
        fresh = pd.concat(fresh, ignore_index=True)
        records.append({"artifact_class": "figure_3_calibration_crosswalk", **keyed_values(packaged, fresh, ["assessment", "model", "horizon", "decile"], ["n", "predicted_persistence", "observed_persistence"])})
    except Exception as exc:
        records.append({"artifact_class": "figure_3_calibration_crosswalk", "status": "MALFORMED", "substantive": True, "reason": str(exc)})

    figure_output = reproduced / "figure_reproduction/figures"
    for number in range(1, 5):
        for suffix in ("pdf", "png", "svg", "tif"):
            path = figure_output / f"figure{number}.{suffix}"
            present = path.is_file() and path.stat().st_size > 0
            records.append({"artifact_class": "figure_render_presence", "artifact": path.name, "status": "PASS" if present else "MISSING", "substantive": not present})
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reproduced", required=True, type=pathlib.Path)
    parser.add_argument("--reference", required=True, type=pathlib.Path)
    parser.add_argument("--json-out", type=pathlib.Path)
    args = parser.parse_args()
    reproduced, reference = args.reproduced.resolve(), args.reference.resolve()
    records = []

    for ref in sorted(reference.rglob("*")):
        if not ref.is_file() or ref.relative_to(reference).parts[0] not in {"primary", "sensitivities", "models"}:
            continue
        rel = primary_target(ref.relative_to(reference))
        target = reproduced / rel
        record = {"artifact_class": "primary_or_registered_sensitivity", "reference": str(ref), "reproduced": str(target)}
        if not target.is_file():
            record.update(status="MISSING", substantive=True, reason="reproduced artifact absent")
        else:
            record.update(reference_sha256=sha256(ref), reproduced_sha256=sha256(target))
            record.update(compare_csv(ref, target))
        records.append(record)

    for name, relname in sorted(REPRESENTATION_TARGETS.items()):
        ref, target = reference / "representation" / name, reproduced / relname
        record = {"artifact_class": "representation_audit", "reference": str(ref), "reproduced": str(target)}
        if not ref.is_file() or not target.is_file():
            record.update(status="MISSING", substantive=True, reason="reference or reproduced artifact absent")
        elif ref.suffix == ".csv":
            record.update(reference_sha256=sha256(ref), reproduced_sha256=sha256(target))
            record.update(compare_csv(ref, target))
        else:
            record.update(reference_sha256=sha256(ref), reproduced_sha256=sha256(target))
            record.update(compare_diagnostics(ref, target))
        records.append(record)

    for label, rel in {
        "M0_fit": "primary/analysis_results/primary_models/M0",
        "M1_fit": "primary/analysis_results/primary_models/M1",
        "M_count_fit": "representation/fit/M_count",
    }.items():
        records.append({"artifact_class": "fit_status_and_diagnostics", "artifact": label, **check_fit(reproduced, rel)})

    records.extend(figure_crosswalk_records(reproduced, reference.parents[1]))

    failed = [r for r in records if r.get("substantive")]
    report = {
        "status": "PASS" if not failed else "FAIL",
        "strict_absolute_tolerance": TOLERANCE,
        "relative_tolerance": 0,
        "reproduced_root": str(reproduced),
        "reference_root": str(reference),
        "artifact_classes_checked": sorted({r["artifact_class"] for r in records}),
        "artifacts_checked": len(records),
        "substantive_failures": len(failed),
        "maximum_absolute_difference": max((r.get("maximum_absolute_difference", 0.0) for r in records if math.isfinite(r.get("maximum_absolute_difference", 0.0))), default=0.0),
        "records": records,
    }
    output = json.dumps(report, indent=2, ensure_ascii=False)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(output + "\n", encoding="utf-8")
    # Keep the machine-readable file UTF-8 while remaining printable on the
    # legacy Windows cp1252 console used by the packaged route.
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
