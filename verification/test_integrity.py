"""Run verifier and source-guard negative tests on disposable repository copies."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def run(directory, command):
    result = subprocess.run(command, cwd=directory, text=True, capture_output=True)
    return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-source", required=True, type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    py = sys.executable
    tests = {}
    with tempfile.TemporaryDirectory(prefix="repository_verifier_tests_") as temp_name:
        temp = Path(temp_name)

        pristine = temp / "pristine"; shutil.copytree(ROOT, pristine)
        tests["pristine_scientific"] = run(pristine, [py, "verification/verify_science.py"])
        tests["pristine_snapshot"] = run(pristine, [py, "verification/verify_release.py"])

        modified = temp / "modified"; shutil.copytree(ROOT, modified)
        aggregate = modified / "results/reference/models/base_coefficients.csv"
        aggregate.write_bytes(aggregate.read_bytes() + b"\n")
        tests["modified_science"] = run(modified, [py, "verification/verify_science.py"])

        missing = temp / "missing"; shutil.copytree(ROOT, missing)
        (missing / "results/reference/models/base_coefficients.csv").unlink()
        tests["missing_science"] = run(missing, [py, "verification/verify_science.py"])

        documentation = temp / "documentation"; shutil.copytree(ROOT, documentation)
        science_before = digest(documentation / "verification/science_manifest.csv")
        readme = documentation / "README.md"
        readme.write_text(readme.read_text(encoding="utf-8") + "\nDocumentation-only verification edit.\n", encoding="utf-8")
        tests["readme_scientific"] = run(documentation, [py, "verification/verify_science.py"])
        tests["readme_snapshot_before_regeneration"] = run(documentation, [py, "verification/verify_release.py"])
        tests["snapshot_regeneration"] = run(documentation, [py, "verification/build_release_manifest.py"])
        tests["readme_snapshot_after_regeneration"] = run(documentation, [py, "verification/verify_release.py"])
        tests["readme_scientific_after_regeneration"] = run(documentation, [py, "verification/verify_science.py"])
        science_after = digest(documentation / "verification/science_manifest.csv")
        tests["scientific_manifest_unchanged"] = {"value": science_before == science_after}

        wrong = temp / "wrong_source.csv"; wrong.write_text("not,the,archived,source\n", encoding="utf-8")
        tests["wrong_source"] = run(ROOT, [py, "scripts/check_source.py", str(wrong)])
        tests["exact_source"] = run(ROOT, [py, "scripts/check_source.py", str(args.exact_source.resolve())])

    expected = {
        "pristine_scientific": 0, "pristine_snapshot": 0,
        "modified_science": "nonzero", "missing_science": "nonzero",
        "readme_scientific": 0, "readme_snapshot_before_regeneration": "nonzero",
        "snapshot_regeneration": 0, "readme_snapshot_after_regeneration": 0,
        "readme_scientific_after_regeneration": 0, "wrong_source": "nonzero", "exact_source": 0,
    }
    passed = tests["scientific_manifest_unchanged"]["value"]
    for name, want in expected.items():
        got = tests[name]["returncode"]
        passed = passed and (got == want if isinstance(want, int) else got != 0)
    report = {"status": "PASS" if passed else "FAIL", "tests": tests}
    text = json.dumps(report, indent=2)
    if args.json_out:
        args.json_out.write_text(text + "\n", encoding="utf-8")
    print(text)
    raise SystemExit(0 if passed else 1)

if __name__ == "__main__":
    main()
