"""Mutate a passing Core output and prove the verifier fails closed."""
from __future__ import annotations
import argparse, json, pathlib, shutil, subprocess, sys, tempfile
import pandas as pd

ROOT=pathlib.Path(__file__).resolve().parents[1]
def verify(path):return subprocess.run([sys.executable,str(ROOT/"verification/verify_core.py"),"--output",str(path)],capture_output=True,text=True)
def main():
    parser=argparse.ArgumentParser();parser.add_argument("--passing-output",required=True,type=pathlib.Path);parser.add_argument("--json-out",type=pathlib.Path);args=parser.parse_args()
    tests={"pristine":verify(args.passing_output.resolve()).returncode==0}
    with tempfile.TemporaryDirectory(prefix="core_negative_") as temporary:
        base=pathlib.Path(temporary)
        cases={}
        for name in ["missing_output","duplicate_key","altered_metric_status","wrong_replicate_count","missing_model"]:
            path=base/name;shutil.copytree(args.passing_output,path);cases[name]=path
        (cases["missing_output"]/"results/core_summary.csv").unlink()
        summary=pd.read_csv(cases["duplicate_key"]/"results/core_summary.csv");pd.concat([summary,summary.iloc[[0]]]).to_csv(cases["duplicate_key"]/"results/core_summary.csv",index=False)
        comparison=json.loads((cases["altered_metric_status"]/"results/scientific_comparison.json").read_text());comparison["representation_pairs"]["status"]="FAIL";(cases["altered_metric_status"]/"results/scientific_comparison.json").write_text(json.dumps(comparison))
        boot=pd.read_csv(cases["wrong_replicate_count"]/"results/fresh_500_loss_bootstrap.csv.gz");boot=boot[~((boot.population=="validation_2023")&(boot.replicate==500))];boot.to_csv(cases["wrong_replicate_count"]/"results/fresh_500_loss_bootstrap.csv.gz",index=False)
        fit=json.loads((cases["missing_model"]/"fit_parity_receipt.json").read_text());fit["models"].remove("M_any");(cases["missing_model"]/"fit_parity_receipt.json").write_text(json.dumps(fit))
        for name,path in cases.items():tests[name]=verify(path).returncode!=0
    report={"status":"PASS" if all(tests.values()) else "FAIL","tests":tests}
    text=json.dumps(report,indent=2)
    if args.json_out:args.json_out.write_text(text+"\n",encoding="utf-8")
    print(text);raise SystemExit(0 if all(tests.values()) else 1)
if __name__=="__main__":main()
