"""Exit nonzero unless the exact accepted Python and R environment is active."""
import importlib.metadata
import argparse
import json
import pathlib
import platform
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--rscript", default="Rscript", help="Rscript executable to verify")
parser.add_argument("--json-out", type=pathlib.Path)
args = parser.parse_args()
lock = json.loads((ROOT / "environment/environment.json").read_text(encoding="utf-8"))
errors = []
python_version = ".".join(map(str, sys.version_info[:3]))
if python_version != lock["python"]:
    errors.append(f"Python {python_version}; expected {lock['python']}")
for package, expected in lock["python_packages"].items():
    try:
        actual = importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        errors.append(f"{package} missing; expected {expected}")
        continue
    if actual != expected:
        errors.append(f"{package} {actual}; expected {expected}")
try:
    r_process = subprocess.run(
        [args.rscript, "-e", "cat(as.character(getRversion()), '\\n', as.character(packageVersion('survival')), '\\n', sep='')"],
        check=True, capture_output=True, text=True,
    )
    output = r_process.stdout.splitlines()
    r_version, survival_version = output[-2:]
    if r_version != lock["r"]:
        errors.append(f"R {r_version}; expected {lock['r']}")
    expected_survival = lock["r_packages"]["survival"].replace("-", ".")
    if survival_version != expected_survival:
        errors.append(f"survival {survival_version}; expected {lock['r_packages']['survival']}")
except Exception as exc:
    errors.append(f"R runtime check failed: {exc}")
if errors:
    print("RUNTIME CHECK FAIL")
    print("\n".join(errors))
    raise SystemExit(1)
receipt = {
    "status": "RUNTIME_CHECK_PASS", "python": python_version,
    "python_packages": {name: importlib.metadata.version(name) for name in lock["python_packages"]},
    "r": r_version, "r_packages": {"survival_runtime": survival_version, "survival_accepted_label": lock["r_packages"]["survival"]},
    "platform": platform.platform(), "machine": platform.machine(),
    "openblas_num_threads": __import__("os").environ.get("OPENBLAS_NUM_THREADS"),
    "omp_num_threads": __import__("os").environ.get("OMP_NUM_THREADS"),
}
if args.json_out:
    args.json_out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print("RUNTIME CHECK PASS")
