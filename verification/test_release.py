"""Test release-payload verification across Git initialization, clone and archive transport."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def run(directory, command):
    result = subprocess.run(command, cwd=directory, text=True, capture_output=True)
    return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def verify_both(directory):
    return {
        "scientific": run(directory, [sys.executable, "verification/verify_science.py"]),
        "snapshot": run(directory, [sys.executable, "verification/verify_release.py"]),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    tests = {}
    with tempfile.TemporaryDirectory(prefix="release_transport_tests_") as temporary:
        temporary = Path(temporary)
        initialized = temporary / "initialized"
        shutil.copytree(ROOT, initialized)
        tests["git_init"] = run(initialized, ["git", "init", "-b", "main"])
        tests["initialized_verifiers"] = verify_both(initialized)
        run(initialized, ["git", "config", "user.name", "Anonymous Reproduction"])
        run(initialized, ["git", "config", "user.email", "anonymous@example.invalid"])
        tests["git_add"] = run(initialized, ["git", "add", "."])
        tests["git_commit"] = run(initialized, ["git", "commit", "-m", "Local transport test"])

        clone = temporary / "clone"
        tests["git_clone"] = run(temporary, ["git", "clone", str(initialized), str(clone)])
        tests["clone_verifiers"] = verify_both(clone)

        archive = temporary / "repository.zip"
        tests["git_archive"] = run(initialized, ["git", "archive", "--format=zip", "-o", str(archive), "HEAD"])
        extracted = temporary / "archive_extracted"
        extracted.mkdir()
        with zipfile.ZipFile(archive) as bundle:
            tests["archive_crc"] = {"bad_member": bundle.testzip()}
            bundle.extractall(extracted)
        tests["archive_verifiers"] = verify_both(extracted)

        unexpected = temporary / "unexpected"
        shutil.copytree(ROOT, unexpected)
        (unexpected / "unexpected_payload.txt").write_text("unexpected\n", encoding="utf-8")
        tests["unexpected_payload"] = run(unexpected, [sys.executable, "verification/verify_release.py"])

        missing = temporary / "missing"
        shutil.copytree(ROOT, missing)
        (missing / "requirements.txt").unlink()
        tests["missing_payload"] = run(missing, [sys.executable, "verification/verify_release.py"])

        altered = temporary / "altered"
        shutil.copytree(ROOT, altered)
        with (altered / "requirements.txt").open("a", encoding="utf-8") as stream:
            stream.write("# altered\n")
        tests["altered_payload"] = run(altered, [sys.executable, "verification/verify_release.py"])

        readme_changed = temporary / "readme_changed"
        shutil.copytree(ROOT, readme_changed)
        with (readme_changed / "README.md").open("a", encoding="utf-8") as stream:
            stream.write("\nTemporary landing-page edit.\n")
        tests["readme_mutable"] = run(readme_changed, [sys.executable, "verification/verify_release.py"])

        source_readme_changed = temporary / "source_readme_changed"
        shutil.copytree(ROOT, source_readme_changed)
        with (source_readme_changed / "source" / "README.md").open("a", encoding="utf-8") as stream:
            stream.write("\nTemporary source-access documentation edit.\n")
        tests["source_readme_mutable"] = run(source_readme_changed, [sys.executable, "verification/verify_release.py"])

        github_metadata = temporary / "github_metadata"
        shutil.copytree(ROOT, github_metadata)
        (github_metadata / ".github").mkdir(exist_ok=True)
        (github_metadata / ".github" / "README_NOTE.md").write_text("GitHub metadata\n", encoding="utf-8")
        tests["github_metadata_mutable"] = run(github_metadata, [sys.executable, "verification/verify_release.py"])

    zero = lambda record: record["returncode"] == 0
    passed = (
        zero(tests["git_init"])
        and zero(tests["initialized_verifiers"]["scientific"])
        and zero(tests["initialized_verifiers"]["snapshot"])
        and zero(tests["git_add"])
        and zero(tests["git_commit"])
        and zero(tests["git_clone"])
        and zero(tests["clone_verifiers"]["scientific"])
        and zero(tests["clone_verifiers"]["snapshot"])
        and zero(tests["git_archive"])
        and tests["archive_crc"]["bad_member"] is None
        and zero(tests["archive_verifiers"]["scientific"])
        and zero(tests["archive_verifiers"]["snapshot"])
        and not zero(tests["unexpected_payload"])
        and not zero(tests["missing_payload"])
        and not zero(tests["altered_payload"])
        and zero(tests["readme_mutable"])
        and zero(tests["source_readme_mutable"])
        and zero(tests["github_metadata_mutable"])
    )
    report = {"status": "PASS" if passed else "FAIL", "tests": tests}
    text = json.dumps(report, indent=2)
    if args.json_out:
        args.json_out.write_text(text + "\n", encoding="utf-8")
    print(text)
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
