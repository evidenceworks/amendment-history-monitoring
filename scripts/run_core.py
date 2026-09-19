"""Run the accepted four-fit compact-data Core reproduction.

This runner never reads expected coefficients or metrics until all four new
models have been fitted. ``--fit-only`` is the bounded vertical-slice check;
the default continues through Core evaluation and fresh loss resampling.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

# The accepted launcher fixed both thread variables to one before NumPy was
# imported.  This is required for exact dot-product/tie behavior, not merely
# for speed or memory use.
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from build_data import COLUMNS, DTYPES, original_frames, sha256_path, validate_compact  # noqa: E402
from preprocess import apply_maps, fit_maps, ordered_rank  # noqa: E402
from queue_utils import queue_selected  # noqa: E402

# evaluate.py only needs REPRO_SOURCE because its historical module imports the
# raw-route path constants.  Core never opens this value.
os.environ.setdefault("REPRO_SOURCE", str(ROOT / "data/analysis.csv.gz"))
from evaluate import auc_setup, auc_weighted, calibration, predict_curve  # noqa: E402

TOLERANCE = 1e-10
MODEL_ORDER = ("M0", "M_any", "M_count", "M1")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_compact(path: pathlib.Path, provenance_path: pathlib.Path) -> tuple[pd.DataFrame, dict]:
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    body = path.read_bytes()
    require(hashlib.sha256(body).hexdigest() == provenance["compact_sha256"], "compact byte hash mismatch")
    canonical = gzip.decompress(body)
    require(hashlib.sha256(canonical).hexdigest() == provenance["canonical_csv_sha256"], "canonical CSV hash mismatch")
    frame = pd.read_csv(path, dtype=DTYPES, keep_default_na=False, na_values=[""])
    validate_compact(frame)
    require(list(frame.columns) == provenance["columns"] == COLUMNS, "compact schema/provenance mismatch")
    return frame, provenance


def write_design(path: pathlib.Path, matrix: np.ndarray) -> None:
    np.savetxt(path, matrix, delimiter=",", header=",".join(f"x{i + 1}" for i in range(matrix.shape[1])),
               comments="", fmt="%.17g")


def fit_model(rscript: str, design: pathlib.Path, outcomes: pathlib.Path, destination: pathlib.Path) -> float:
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="core_r_ascii_") as scratch_name:
        scratch = pathlib.Path(scratch_name)
        shutil.copy2(design, scratch / "design.csv")
        shutil.copy2(outcomes, scratch / "outcomes.csv")
        subprocess.run([rscript, str(ROOT / "src/fit_cox.R"), str(scratch / "design.csv"),
                        str(scratch / "outcomes.csv"), str(scratch / "fit")], check=True)
        shutil.copytree(scratch / "fit", destination)
    require((destination / "FIT_STATUS.txt").read_text().strip() == "PASS", f"fit failed: {destination.name}")
    return time.perf_counter() - started


def compare_csv_numeric(actual: pathlib.Path, expected: pathlib.Path) -> dict:
    left, right = pd.read_csv(actual), pd.read_csv(expected)
    require(list(left.columns) == list(right.columns) and left.shape == right.shape,
            f"shape/column mismatch: {actual.name} vs {expected}")
    maximum = 0.0
    for column in left.columns:
        a, b = pd.to_numeric(left[column], errors="coerce"), pd.to_numeric(right[column], errors="coerce")
        if a.notna().sum() == left[column].notna().sum() and b.notna().sum() == right[column].notna().sum():
            av, bv = a.to_numpy(float), b.to_numpy(float)
            require(np.array_equal(np.isnan(av), np.isnan(bv)), f"finite pattern mismatch: {column}")
            finite = np.isfinite(av) & np.isfinite(bv)
            difference = float(np.max(np.abs(av[finite] - bv[finite]))) if finite.any() else 0.0
            maximum = max(maximum, difference)
            require(np.allclose(av, bv, atol=TOLERANCE, rtol=0, equal_nan=True),
                    f"numeric mismatch {column}: {difference}")
        else:
            require(np.array_equal(left[column].fillna("").astype(str), right[column].fillna("").astype(str)),
                    f"text mismatch: {column}")
    return {"status": "PASS", "maximum_absolute_difference": maximum,
            "actual_sha256": sha256_path(actual), "expected_sha256": sha256_path(expected)}


def expected_fit_paths(reference_root: pathlib.Path, accepted_results: pathlib.Path | None) -> dict[str, pathlib.Path]:
    paths = {
        "M0": reference_root / "models/base_coefficients.csv",
        "M1": reference_root / "models/history_coefficients.csv",
        "M_count": reference_root / "representation/count_coefficients.csv",
    }
    packaged_any = reference_root / "models/any_coefficients.csv"
    if packaged_any.is_file():
        paths["M_any"] = packaged_any
    elif accepted_results:
        paths["M_any"] = accepted_results / "sensitivity_analyses/S5/M1/coefficients.csv"
    return paths


def preflight_repository(reference_root: pathlib.Path, retained_path: pathlib.Path | None = None) -> None:
    """Reject an incomplete public package before any model fit starts."""
    data_root = ROOT / "data"
    require((data_root / "analysis.csv.gz").is_file(), "preflight: compact data missing")
    require((data_root / "provenance.json").is_file(), "preflight: compact provenance missing")
    retained = retained_path or (data_root / "primary_bootstrap.csv.gz")
    require(retained.is_file(), "preflight: retained bootstrap missing")
    authorities = expected_fit_paths(reference_root, None)
    require(set(authorities) == set(MODEL_ORDER), "preflight: authority set must be exactly M0, M_any, M_count, M1")
    for model, path in authorities.items():
        require(path.is_file(), f"preflight: missing coefficient authority {model}: {path}")
    performance = {
        "validation_2023": reference_root / "primary/2023/performance.csv",
        "full_2024": reference_root / "primary/2024_180d/performance.csv",
        "mature_2024": reference_root / "primary/2024_365d/performance.csv",
    }
    for population, path in performance.items():
        require(path.is_file(), f"preflight: missing performance authority {population}: {path}")
    for name in ("figure1.csv", "figure2_scores.csv", "figure2_workload.csv", "figure3.csv", "figure4.csv"):
        require((ROOT / "figures/data" / name).is_file(), f"preflight: missing figure source {name}")
    require(set(performance) == {"validation_2023", "full_2024", "mature_2024"}, "preflight: performance populations mismatch")


def prepare_designs(compact: pd.DataFrame, output: pathlib.Path) -> tuple[pd.DataFrame, pd.DataFrame, dict, dict[str, np.ndarray]]:
    features, outcomes = original_frames(compact)
    train = features[features.role == "development"].copy()
    labels = outcomes[outcomes.role == "development"].reset_index(drop=True)
    maps = fit_maps(train)
    x0, x1, n0, n1, _ = apply_maps(train, maps)
    xany = np.column_stack([x0, (train.paa_category.astype(str) != "0").to_numpy(float)])
    any_names = n0 + ["PAA_any"]
    keep, removed = ordered_rank(xany, any_names, preserve=len(n0))
    require(keep == list(range(xany.shape[1])) and not removed, "M_any rank contract failed")
    count_names = n0 + ["PAA_count_1", "PAA_count_2", "PAA_count_3plus"]
    count_indices = [n1.index(name) for name in count_names]
    xcount = x1[:, count_indices]
    matrices = {"M0": x0, "M_any": xany, "M_count": xcount, "M1": x1}
    expected_widths = {"M0": 20, "M_any": 21, "M_count": 23, "M1": 26}
    require({name: matrix.shape[1] for name, matrix in matrices.items()} == expected_widths, "design widths mismatch")
    require(all(np.array_equal(matrix[:, :20], x0) for matrix in matrices.values()), "shared M0 block mismatch")
    design_dir = output / "design"
    design_dir.mkdir()
    for name, matrix in matrices.items():
        write_design(design_dir / f"development_{name}.csv", matrix)
    labels.to_csv(design_dir / "development_outcomes.csv", index=False)
    (design_dir / "preprocessing_maps.json").write_text(json.dumps(maps, indent=2) + "\n", encoding="utf-8")
    (design_dir / "formulas.json").write_text(json.dumps({
        "M0": n0, "M_any": any_names, "M_count": count_names, "M1": n1,
        "likelihood": "R survival::coxph; Efron; unpenalized; no intercept",
    }, indent=2) + "\n", encoding="utf-8")
    return features, outcomes, maps, matrices


def fit_vertical_slice(compact: pd.DataFrame, output: pathlib.Path, rscript: str,
                       reference_root: pathlib.Path, accepted_results: pathlib.Path | None) -> tuple[dict, dict, dict]:
    preflight_repository(reference_root)
    features, outcomes, maps, matrices = prepare_designs(compact, output)
    fits = output / "fits"
    fits.mkdir()
    timings = {}
    for model in MODEL_ORDER:
        timings[model] = fit_model(rscript, output / f"design/development_{model}.csv",
                                   output / "design/development_outcomes.csv", fits / model)
    expected = expected_fit_paths(reference_root, accepted_results)
    require(set(expected) == set(MODEL_ORDER), "accepted coefficient authority missing for one or more models")
    comparison = {model: compare_csv_numeric(fits / model / "coefficients.csv", expected[model]) for model in MODEL_ORDER}
    receipt = {
        "status": "PASS", "tolerance": {"atol": TOLERANCE, "rtol": 0},
        "models": list(MODEL_ORDER), "design_widths": {name: matrix.shape[1] for name, matrix in matrices.items()},
        "design_names": json.loads((output / "design/formulas.json").read_text()),
        "shared_M0_byte_identical": True, "coefficient_comparison": comparison,
        "fit_seconds": timings,
    }
    (output / "fit_parity_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt, {"features": features, "outcomes": outcomes, "maps": maps}, matrices


def validation_designs(features: pd.DataFrame, maps: dict, role: str) -> dict[str, np.ndarray]:
    part = features[features.role == role].copy()
    x0, x1, n0, n1, _ = apply_maps(part, maps)
    xany = np.column_stack([x0, (part.paa_category.astype(str) != "0").to_numpy(float)])
    count_names = n0 + ["PAA_count_1", "PAA_count_2", "PAA_count_3plus"]
    xcount = x1[:, [n1.index(name) for name in count_names]]
    return {"M0": x0, "M_any": xany, "M_count": xcount, "M1": x1}


def paired_loss_replicates(clusters: np.ndarray, losses: np.ndarray, replicates: int = 500,
                           seed: int = 20260916) -> np.ndarray:
    values = np.asarray(losses, dtype=np.float64)
    labels, inverse = np.unique(np.asarray(clusters, dtype=str), return_inverse=True)
    require(values.ndim == 2 and len(values) == len(inverse) and np.isfinite(values).all(),
            "finite aligned root-loss matrix required")
    rng = np.random.Generator(np.random.PCG64(seed))
    result = np.empty((replicates, values.shape[1]), dtype=float)
    for replicate in range(replicates):
        weights = np.bincount(rng.integers(0, len(labels), len(labels)), minlength=len(labels))[inverse]
        result[replicate] = weights @ values / weights.sum()
    return result


def point_uno_pair(rscript: str, output: pathlib.Path, duration: np.ndarray, event: np.ndarray,
                   first: np.ndarray, second: np.ndarray, tau: int, label: str) -> tuple[float, float]:
    work = output / "uno_point"
    work.mkdir(exist_ok=True)
    result = work / f"{label}.result.csv"
    with tempfile.TemporaryDirectory(prefix="core_uno_ascii_") as scratch_name:
        scratch = pathlib.Path(scratch_name); data = scratch / "input.csv"; weights = scratch / "weights.int32"
        scratch_result = scratch / "result.csv"
        pd.DataFrame({"time": np.where(event, duration, float(tau + 1)), "event": event.astype(int),
                      "risk0": 1 - first[:, tau], "risk1": 1 - second[:, tau]}).to_csv(data, index=False)
        weights.write_bytes(b"")
        subprocess.run([rscript, str(ROOT / "src/concordance_bootstrap.R"), str(data), str(weights), str(tau), "0", str(scratch_result)],
                       check=True)
        shutil.copy2(scratch_result, result)
    row = pd.read_csv(result).iloc[0]
    return float(row.M0), float(row.M1)


def queue_order_from_rank(days: np.ndarray, scores: np.ndarray, tie_rank: np.ndarray) -> np.ndarray:
    return np.lexsort((np.asarray(tie_rank, dtype=np.int64), -np.asarray(scores, dtype=float), np.asarray(days, dtype=str)))


def primary_metrics(model_curves: dict[str, np.ndarray], duration: np.ndarray, event: np.ndarray,
                    roots: np.ndarray, days: np.ndarray, tie_rank: np.ndarray, horizons: list[int], ibs: bool,
                    uno: dict[str, float], workload: bool) -> tuple[dict, list[dict], dict[str, np.ndarray]]:
    grid = np.arange(366)
    ycurve = ((~event[:, None]) | (duration[:, None] > grid[None, :])).astype(float)
    point, deciles, loss_vectors = {}, [], {}
    for model, survival in model_curves.items():
        loss = (ycurve - survival) ** 2
        if ibs:
            loss_vectors[f"{model}__IBS_0_365"] = np.trapezoid(loss[:, :366], dx=1, axis=1) / 365
            point[f"{model}__IBS"] = float(loss_vectors[f"{model}__IBS_0_365"].mean())
        for horizon in horizons:
            y = ycurve[:, horizon]
            loss_vectors[f"{model}__Brier_{horizon}"] = loss[:, horizon]
            point[f"{model}__BS_{horizon}"] = float(loss[:, horizon].mean())
            point[f"{model}__AUC_{horizon}"] = float(auc_weighted(auc_setup(y, survival[:, horizon]), np.ones(len(y))))
            cal = calibration(y, survival[:, horizon], np.ones(len(y)))
            for name, value in zip(("mean_calibration_bias", "offset_intercept", "joint_intercept", "slope"), cal):
                point[f"{model}__{name}_{horizon}"] = float(value)
            cuts = np.quantile(survival[:, horizon], np.linspace(0, 1, 11), method="linear")
            group = np.searchsorted(cuts[1:-1], survival[:, horizon], side="left") + 1
            for decile in range(1, 11):
                selected = group == decile
                deciles.append({"model": model, "horizon": horizon, "decile": decile, "n": int(selected.sum()),
                                "predicted_persistence": float(survival[selected, horizon].mean()) if selected.any() else np.nan,
                                "observed_persistence": float(y[selected].mean()) if selected.any() else np.nan})
        if workload:
            horizon = max(horizons); y = ycurve[:, horizon]
            order = queue_order_from_rank(days, survival[:, horizon], tie_rank)
            selected = queue_selected(roots, days, survival[:, horizon], order=order)
            flagged = int(selected.sum()); persisters = float(selected @ y); all_persisters = float(y.sum())
            point[f"{model}__flagged"] = flagged
            point[f"{model}__realized_review_fraction"] = flagged / len(y)
            point[f"{model}__persistence_among_flagged"] = persisters / flagged
            point[f"{model}__recall_persisters"] = persisters / all_persisters
            point[f"{model}__persisters_per_100_reviews"] = 100 * persisters / flagged
        if model in uno:
            point[f"{model}__Uno_C_{max(horizons)}"] = uno[model]
    for key in list(point):
        if key.startswith("M0__") and key.replace("M0__", "M1__", 1) in point:
            point["Delta__" + key[4:]] = point[key.replace("M0__", "M1__", 1)] - point[key]
    if ibs:
        point["IBS_relative_reduction_percent"] = 100 * (point["M0__IBS"] - point["M1__IBS"]) / point["M0__IBS"]
    return point, deciles, loss_vectors


def retained_intervals(path: pathlib.Path) -> tuple[pd.DataFrame, dict[tuple[str, str], tuple[float, float, int]]]:
    frame = pd.read_csv(path)
    require(set(frame.population) == {"validation_2023", "full_2024", "mature_2024"}, "retained population mismatch")
    intervals = {}
    for population, part in frame.groupby("population", sort=False):
        require(len(part) == 500 and part.replicate.tolist() == list(range(1, 501)), f"retained replicate mismatch: {population}")
        for column in part.columns[2:]:
            values = pd.to_numeric(part[column], errors="coerce").to_numpy(float)
            finite = np.isfinite(values)
            if finite.any():
                low, high = np.quantile(values[finite], [.025, .975], method="linear")
                intervals[(population, column)] = (float(low), float(high), int(finite.sum()))
    return frame, intervals


def compare_primary_points(points: dict[str, dict], reference_root: pathlib.Path) -> dict:
    paths = {
        "validation_2023": reference_root / "primary/2023/performance.csv",
        "full_2024": reference_root / "primary/2024_180d/performance.csv",
        "mature_2024": reference_root / "primary/2024_365d/performance.csv",
    }
    result = {}
    for population, path in paths.items():
        reference = pd.read_csv(path).set_index("metric")
        maximum = 0.0
        for key, value in points[population].items():
            if key.startswith(("M0__", "M1__", "Delta__")) or key == "IBS_relative_reduction_percent":
                require(key in reference.index, f"missing primary reference key: {population}/{key}")
                difference = abs(float(reference.loc[key, "estimate"]) - float(value))
                maximum = max(maximum, difference)
                require(difference <= TOLERANCE, f"primary point mismatch: {population}/{key}: {difference}")
        result[population] = {"status": "PASS", "maximum_absolute_difference": maximum}
    return result


def run_core_evaluation(compact: pd.DataFrame, context: dict, output: pathlib.Path, rscript: str,
                        retained_path: pathlib.Path, reference_root: pathlib.Path) -> dict:
    features, outcomes, maps = context["features"], context["outcomes"], context["maps"]
    fits = output / "fits"
    _, retained_ci = retained_intervals(retained_path)
    summary_rows, all_bootstrap_rows, all_deciles, representation_abs, representation_pairs = [], [], [], [], []
    point_by_population = {}
    pairs = (("M_any", "M0"), ("M_count", "M_any"), ("M1", "M_count"),
             ("M_count", "M0"), ("M1", "M_any"), ("M1", "M0"))
    specs = [
        ("validation_2023", "validation_2023", None, [180, 365], True, True),
        ("full_2024", "validation_2024", None, [180], False, True),
        ("mature_2024", "validation_2024", "mature", [365], True, False),
    ]
    evaluation_seconds = {}
    for population, role, subset, horizons, ibs, workload in specs:
        phase_start = time.perf_counter()
        role_features = features[features.role == role].copy().reset_index(drop=True)
        role_compact = compact[compact.role == role].copy().reset_index(drop=True)
        role_outcomes = outcomes[outcomes.role == role].copy().reset_index(drop=True)
        designs = validation_designs(features, maps, role)
        curves = {model: predict_curve(matrix, fits / model) for model, matrix in designs.items()}
        if subset == "mature":
            select = role_features.mature_2024.to_numpy(bool)
            role_features = role_features.loc[select].reset_index(drop=True)
            role_compact = role_compact.loc[select].reset_index(drop=True)
            role_outcomes = role_outcomes.loc[select].reset_index(drop=True)
            curves = {model: values[select] for model, values in curves.items()}
        duration = role_outcomes.duration.to_numpy(float); event = role_outcomes.event.to_numpy(bool)
        uno0, uno1 = point_uno_pair(rscript, output, duration, event, curves["M0"], curves["M1"], max(horizons), population)
        points, deciles, losses = primary_metrics(
            curves, duration, event, role_compact.root_id.to_numpy(), role_features.landmark.to_numpy(),
            role_compact.tie_order.to_numpy(int), horizons, ibs, {"M0": uno0, "M1": uno1}, workload,
        )
        point_by_population[population] = points
        all_deciles.extend({"population": population, **row} for row in deciles)
        loss_keys = []
        for model in MODEL_ORDER:
            if ibs: loss_keys.append(f"{model}__IBS_0_365")
            for horizon in horizons: loss_keys.append(f"{model}__Brier_{horizon}")
        matrix = np.column_stack([losses[key] for key in loss_keys])
        replicates = paired_loss_replicates(role_compact.cluster_id.to_numpy(), matrix)
        boot = pd.DataFrame(replicates, columns=loss_keys)
        boot.insert(0, "replicate", np.arange(1, 501)); boot.insert(0, "population", population)
        for first, second in pairs:
            loss_names = (["IBS_0_365"] if ibs else []) + [f"Brier_{h}" for h in horizons]
            for loss_name in loss_names:
                column = f"{first}_minus_{second}__{loss_name}"
                boot[column] = boot[f"{first}__{loss_name}"] - boot[f"{second}__{loss_name}"]
        all_bootstrap_rows.append(boot)
        for key in loss_keys:
            model, loss_name = key.split("__", 1)
            low, high = np.quantile(boot[key], [.025, .975], method="linear")
            estimate = float(losses[key].mean())
            representation_abs.append({"population": "2023" if population == "validation_2023" else population,
                                       "model": "M_base" if model == "M0" else "M_history" if model == "M1" else model,
                                       "loss": loss_name, "estimate": estimate, "percentile_2_5": low,
                                       "percentile_97_5": high, "finite_replicates": 500, "requested_replicates": 500})
            summary_rows.append({"population": population, "model_or_contrast": model, "metric": loss_name,
                                 "horizon": 365 if "365" in loss_name else 180 if "180" in loss_name else 365,
                                 "estimate": estimate, "lower": low, "upper": high, "finite_replicates": 500,
                                 "requested_replicates": 500, "origin": "fresh_500_loss_bootstrap"})
        for first, second in pairs:
            for loss_name in (["IBS_0_365"] if ibs else []) + [f"Brier_{h}" for h in horizons]:
                column = f"{first}_minus_{second}__{loss_name}"
                low, high = np.quantile(boot[column], [.025, .975], method="linear")
                estimate = float(losses[f"{first}__{loss_name}"].mean() - losses[f"{second}__{loss_name}"].mean())
                first_public = "M_base" if first == "M0" else "M_history" if first == "M1" else first
                second_public = "M_base" if second == "M0" else "M_history" if second == "M1" else second
                representation_pairs.append({"population": "2023" if population == "validation_2023" else population,
                                             "loss": loss_name, "contrast": f"{first_public} - {second_public}",
                                             "estimate": estimate, "percentile_2_5": low, "percentile_97_5": high,
                                             "finite_replicates": 500, "requested_replicates": 500,
                                             "orientation": "first model loss minus second model loss; negative favors first"})
        for key, estimate in points.items():
            if (population, key) in retained_ci and not ("BS_" in key or key.endswith("__IBS") or key == "IBS_relative_reduction_percent"):
                low, high, finite = retained_ci[(population, key)]
                summary_rows.append({"population": population, "model_or_contrast": key.split("__")[0],
                                     "metric": key.split("__", 1)[-1], "horizon": max(horizons),
                                     "estimate": estimate, "lower": low, "upper": high, "finite_replicates": finite,
                                     "requested_replicates": 500, "origin": "retained_500_interval_reconstruction"})
            elif not ("BS_" in key or key.endswith("__IBS") or key == "IBS_relative_reduction_percent"):
                summary_rows.append({"population": population, "model_or_contrast": key.split("__")[0],
                                     "metric": key.split("__", 1)[-1], "horizon": max(horizons),
                                     "estimate": estimate, "lower": np.nan, "upper": np.nan, "finite_replicates": 0,
                                     "requested_replicates": 0, "origin": "fresh_fit_point"})
        evaluation_seconds[population] = time.perf_counter() - phase_start
    comparison = {"primary_points": compare_primary_points(point_by_population, reference_root)}
    absdf, pairdf = pd.DataFrame(representation_abs), pd.DataFrame(representation_pairs)
    expected_abs = pd.read_csv(reference_root / "representation/losses.csv")
    expected_pair = pd.read_csv(reference_root / "representation/contrasts.csv")
    for label, actual, expected, keys in (
        ("representation_absolute", absdf, expected_abs, ["population", "model", "loss"]),
        ("representation_pairs", pairdf, expected_pair, ["population", "loss", "contrast"]),
    ):
        actual = actual.sort_values(keys).reset_index(drop=True); expected = expected.sort_values(keys).reset_index(drop=True)
        require(actual[keys].equals(expected[keys]), f"{label} semantic key mismatch")
        maximum = 0.0
        for column in ["estimate", "percentile_2_5", "percentile_97_5"]:
            diff = np.abs(actual[column].to_numpy(float) - expected[column].to_numpy(float))
            maximum = max(maximum, float(diff.max()))
            require(np.all(diff <= TOLERANCE), f"{label}/{column} mismatch: {diff.max()}")
        comparison[label] = {"status": "PASS", "maximum_absolute_difference": maximum}
    results = output / "results"; results.mkdir()
    pd.DataFrame(summary_rows).to_csv(results / "core_summary.csv", index=False, float_format="%.17g")
    pd.concat(all_bootstrap_rows, ignore_index=True, sort=False).to_csv(
        results / "fresh_500_loss_bootstrap.csv.gz", index=False, compression={"method": "gzip", "mtime": 0}, float_format="%.17g")
    pd.DataFrame(all_deciles).to_csv(results / "calibration.csv", index=False, float_format="%.17g")
    absdf.to_csv(results / "losses.csv", index=False, float_format="%.17g")
    pairdf.to_csv(results / "contrasts.csv", index=False, float_format="%.17g")
    (results / "scientific_comparison.json").write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    figure_root = output / "figure_reproduction"
    shutil.copytree(ROOT / "figures/data", figure_root / "data")
    (figure_root / "scripts").mkdir(); shutil.copy2(ROOT / "scripts/make_figures.py", figure_root / "scripts/make_figures.py")
    score = pd.read_csv(figure_root / "data/figure2_scores.csv")
    primary_loss = {
        "2023_primary": ("validation_2023", "Delta__IBS", "2023", "IBS_0_365"),
        "full_2024_corroboration": ("full_2024", "Delta__BS_180", "full_2024", "Brier_180"),
    }
    for assessment, (population, metric, public_population, loss_name) in primary_loss.items():
        row = pairdf[(pairdf.population == public_population) & (pairdf.loss == loss_name) &
                     (pairdf.contrast == "M_history - M_base")].iloc[0]
        select = (score.specification_id == "Primary") & (score.assessment_id == assessment)
        score.loc[select, ["estimate", "ci_low", "ci_high"]] = [point_by_population[population][metric], row.percentile_2_5, row.percentile_97_5]
    score.to_csv(figure_root / "data/figure2_scores.csv", index=False, float_format="%.17g")
    workload_rows=[]
    for population, assessment, horizon in (("validation_2023","2023_primary",365),("full_2024","full_2024_corroboration",180)):
        point=point_by_population[population];low,high,_=retained_ci[(population,"Delta__persisters_per_100_reviews")]
        workload_rows.append({"section":"workload","assessment_id":assessment,"target_horizon":f"{horizon} days",
                              "actual_allocation":point["M0__realized_review_fraction"],"flagged_roots_per_model":point["M0__flagged"],
                              "m0_persisters_per_100":point["M0__persisters_per_100_reviews"],"m1_persisters_per_100":point["M1__persisters_per_100_reviews"],
                              "yield_difference":point["Delta__persisters_per_100_reviews"],"yield_ci_low":low,"yield_ci_high":high})
    pd.DataFrame(workload_rows).to_csv(figure_root / "data/figure2_workload.csv",index=False,float_format="%.17g")
    decdf=pd.DataFrame(all_deciles);fig3=[]
    for population,assessment,horizon in (("validation_2023","2023/365",365),("full_2024","Full 2024/180",180)):
        part=decdf[(decdf.population==population)&(decdf.horizon==horizon)&(decdf.model.isin(["M0","M1"]))].copy()
        part["assessment"]=assessment;fig3.append(part.drop(columns="population"))
    pd.concat(fig3,ignore_index=True).to_csv(figure_root / "data/figure3.csv",index=False,float_format="%.17g")
    packaged4=pd.read_csv(ROOT/"figures/data/figure4.csv")
    keys=["population","loss","contrast"]
    designated=packaged4[keys].drop_duplicates()
    fresh4=designated.merge(pairdf,on=keys,how="left",validate="one_to_one").merge(
        packaged4[keys+["contrast_label","assessment_id","metric_label"]],on=keys,how="left",validate="one_to_one")
    fresh4.to_csv(figure_root / "data/figure4.csv",index=False,float_format="%.17g")
    figure_env = os.environ.copy()
    figure_env["MPLBACKEND"] = "Agg"
    subprocess.run([sys.executable, str(figure_root/"scripts/make_figures.py")],
                   check=True, cwd=figure_root, env=figure_env)
    (figure_root/"CORE_FIGURE_ORIGINS.json").write_text(json.dumps({
        "figure1":"retained_design_schematic","figure2_primary_points_and_intervals":"fresh_fit_point and fresh_500_loss_bootstrap",
        "figure2_workload_intervals":"retained_500_interval_reconstruction","figure2_sensitivities":"reference_verified_not_rerun",
        "figure3":"fresh_fit_point","figure4":"fresh_500_loss_bootstrap"},indent=2)+"\n")
    return {"status": "PASS", "evaluation_seconds": evaluation_seconds, "comparison": comparison,
            "summary_rows": len(summary_rows), "fresh_loss_replicates": 500}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=pathlib.Path, default=ROOT / "data/analysis.csv.gz")
    parser.add_argument("--provenance", type=pathlib.Path, default=ROOT / "data/provenance.json")
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--reference", type=pathlib.Path, default=ROOT / "results/reference")
    parser.add_argument("--retained-bootstrap", type=pathlib.Path,
                        default=ROOT / "data/primary_bootstrap.csv.gz")
    parser.add_argument("--accepted-results", type=pathlib.Path,
                        help="optional accepted analysis-results root for an external M_any reference")
    parser.add_argument("--rscript", default="Rscript")
    parser.add_argument("--fit-only", action="store_true")
    args = parser.parse_args()
    started = time.perf_counter()
    output = args.output.resolve()
    require(not output.exists(), "output directory must not already exist")
    output.mkdir(parents=True)
    compact, provenance = load_compact(args.data.resolve(), args.provenance.resolve())
    receipt, context, _ = fit_vertical_slice(compact, output, args.rscript, args.reference.resolve(),
                                             args.accepted_results.resolve() if args.accepted_results else None)
    evaluation = None if args.fit_only else run_core_evaluation(
        compact, context, output, args.rscript, args.retained_bootstrap.resolve(), args.reference.resolve())
    runtime = {"status": "FIT_ONLY_PASS" if args.fit_only else "CORE_LOCAL_PASS",
               "total_seconds": time.perf_counter() - started, "fit_seconds": receipt["fit_seconds"],
               "compact_sha256": provenance["compact_sha256"], "python": sys.version,
               "rscript": args.rscript, "evaluation": evaluation}
    (output / "runtime_receipt.json").write_text(json.dumps(runtime, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(runtime, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
