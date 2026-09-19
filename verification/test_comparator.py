"""Exercise semantic figure/source and render-presence failures on disposable fixtures."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "results/reference"

def primary_target(relative):
    parts = relative.parts
    if parts and parts[0] == "primary": parts = parts[1:]
    if parts and parts[0] == "sensitivities":
        population = {"2023": "validation_2023", "2024_180d": "validation_2024/full_180", "2024_365d": "validation_2024/mature_365"}[parts[2]]
        return Path("primary/analysis_results/sensitivity_analyses") / parts[1].upper() / population / parts[3]
    if parts == ("models", "base_coefficients.csv"): return Path("primary/analysis_results/primary_models/M0/coefficients.csv")
    if parts == ("models", "history_coefficients.csv"): return Path("primary/analysis_results/primary_models/M1/coefficients.csv")
    if parts == ("models", "any_coefficients.csv"): return Path("primary/analysis_results/sensitivity_analyses/S5/M1/coefficients.csv")
    if parts == ("2023", "performance.csv"): return Path("primary/analysis_results/validation_2023/performance.csv")
    if parts == ("2023", "calibration.csv"): return Path("primary/analysis_results/validation_2023/calibration.csv")
    if len(parts) == 2 and parts[0] in {"2024_180d", "2024_365d"}:
        return Path("primary/analysis_results/validation_2024") / ("full_180" if parts[0] == "2024_180d" else "mature_365") / parts[1]
    raise ValueError(relative)

representation_targets = {
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

def copy_file(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)

def build_fixture(path):
    for source in sorted(REFERENCE.rglob("*")):
        if source.is_file() and source.relative_to(REFERENCE).parts[0] in {"primary", "sensitivities", "models"}:
            copy_file(source, path / primary_target(source.relative_to(REFERENCE)))
    for name, relative in representation_targets.items():
        copy_file(REFERENCE / "representation" / name, path / relative)
    diagnostic = "formula fixture\nwarnings \niterations 1\nloglik 0,0\nobservations 1\nevents 1\n"
    for model in ("M0", "M1"):
        fit = path / f"primary/analysis_results/primary_models/{model}"
        fit.mkdir(parents=True, exist_ok=True)
        (fit / "FIT_STATUS.txt").write_text("PASS\n", encoding="utf-8")
        (fit / "fit_diagnostics.txt").write_text(diagnostic, encoding="utf-8")
        if not (fit / "coefficients.csv").exists():
            (fit / "coefficients.csv").write_text("column,coefficient\nx,0\n", encoding="utf-8")
        (fit / "baseline_cumulative_hazard.csv").write_text("time,hazard\n0,0\n", encoding="utf-8")
    (path / "representation/fit/M_count").mkdir(parents=True, exist_ok=True)
    (path / "representation/fit/M_count/FIT_STATUS.txt").write_text("PASS\n", encoding="utf-8")
    copy_file(ROOT / "figures/data/figure4.csv", path / "representation/figure/representation_comparison_figure_source.csv")
    figures = path / "figure_reproduction/figures"; figures.mkdir(parents=True)
    for number in range(1, 5):
        for suffix in ("pdf", "png", "svg", "tif"):
            (figures / f"figure{number}.{suffix}").write_bytes(b"render fixture\n")

def run_fixture(path, report_path):
    command = [sys.executable, str(ROOT / "verification/compare_results.py"), "--reproduced", str(path), "--reference", str(REFERENCE), "--json-out", str(report_path)]
    result = subprocess.run(command, text=True, capture_output=True)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return {"returncode": result.returncode, "status": report["status"], "substantive_failures": report["substantive_failures"], "failed_classes": [record.get("artifact_class") for record in report["records"] if record.get("substantive")]}

def mutate_csv(path, operation):
    table = pd.read_csv(path)
    if operation == "wrong_estimate": table.loc[0, "estimate"] += 1
    elif operation == "wrong_ci": table.loc[0, "percentile_2_5"] -= 1
    elif operation == "duplicate_key": table = pd.concat([table, table.iloc[[0]]], ignore_index=True)
    elif operation == "missing_key": table = table.iloc[1:].copy()
    elif operation == "wrong_contrast_key": table.loc[0, "contrast"] = "unexpected contrast"
    table.to_csv(path, index=False)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    tests = {}
    with tempfile.TemporaryDirectory(prefix="comparator_negative_tests_") as temporary:
        temporary = Path(temporary)
        baseline = temporary / "baseline"; baseline.mkdir(); build_fixture(baseline)
        tests["baseline"] = run_fixture(baseline, temporary / "baseline.json")
        for operation in ("wrong_estimate", "wrong_ci", "duplicate_key", "missing_key", "wrong_contrast_key"):
            case = temporary / operation; shutil.copytree(baseline, case)
            mutate_csv(case / "representation/figure/representation_comparison_figure_source.csv", operation)
            tests[operation] = run_fixture(case, temporary / f"{operation}.json")
        case = temporary / "missing_figure_output"; shutil.copytree(baseline, case)
        (case / "figure_reproduction/figures/figure1.pdf").unlink()
        tests["missing_figure_output"] = run_fixture(case, temporary / "missing_figure_output.json")
    passed = tests["baseline"]["returncode"] == 0 and all(tests[name]["returncode"] != 0 for name in tests if name != "baseline")
    report = {"status": "PASS" if passed else "FAIL", "tests": tests}
    text = json.dumps(report, indent=2)
    if args.json_out:
        args.json_out.write_text(text + "\n", encoding="utf-8")
    print(text)
    raise SystemExit(0 if passed else 1)

if __name__ == "__main__":
    main()
