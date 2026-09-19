"""Confirm exact-runtime guards fail closed on controlled lock mismatches."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def run(directory, rscript):
    result = subprocess.run([sys.executable, "scripts/check_runtime.py", "--rscript", rscript], cwd=directory, text=True, capture_output=True)
    return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rscript", default="Rscript")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    tests = {"correct_runtime": run(ROOT, args.rscript)}
    with tempfile.TemporaryDirectory(prefix="runtime_negative_tests_") as temporary:
        temporary = Path(temporary)
        cases = {
            "wrong_python": ("python", "0.0.0"),
            "wrong_r": ("r", "0.0.0"),
            "wrong_survival": ("survival", "0.0-0"),
            "missing_package": ("missing", "package-that-does-not-exist"),
        }
        for name, (kind, value) in cases.items():
            case = temporary / name; shutil.copytree(ROOT, case)
            lock_path = case / "environment/environment.json"
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            if kind == "python": lock["python"] = value
            elif kind == "r": lock["r"] = value
            elif kind == "survival": lock["r_packages"]["survival"] = value
            else: lock["python_packages"][value] = "1.0.0"
            lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
            tests[name] = run(case, args.rscript)
    passed = tests["correct_runtime"]["returncode"] == 0 and all(tests[name]["returncode"] != 0 for name in tests if name != "correct_runtime")
    report = {"status": "PASS" if passed else "FAIL", "tests": tests}
    text = json.dumps(report, indent=2)
    if args.json_out: args.json_out.write_text(text + "\n", encoding="utf-8")
    print(text)
    raise SystemExit(0 if passed else 1)

if __name__ == "__main__":
    main()
