"""Fail-closed verifier for a completed compact Core output directory."""
from __future__ import annotations
import argparse, json, pathlib
import pandas as pd

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--output", required=True, type=pathlib.Path); parser.add_argument("--json-out", type=pathlib.Path); args=parser.parse_args()
    root=args.output.resolve(); failures=[]
    def load(name):
        path=root/name
        if not path.is_file(): failures.append(f"missing:{name}"); return None
        try:return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc: failures.append(f"malformed:{name}:{exc}"); return None
    fit=load("fit_parity_receipt.json"); runtime=load("runtime_receipt.json"); comparison=load("results/scientific_comparison.json")
    if fit and (fit.get("status")!="PASS" or set(fit.get("models",[]))!={"M0","M_any","M_count","M1"}): failures.append("fit_contract")
    if runtime and runtime.get("status")!="CORE_LOCAL_PASS": failures.append("runtime_status")
    if comparison:
        def walk(value):
            if isinstance(value,dict):
                if "status" in value and value["status"]!="PASS": failures.append("comparison_status")
                for child in value.values(): walk(child)
        walk(comparison)
    try:
        summary=pd.read_csv(root/"results/core_summary.csv")
        required={"population","model_or_contrast","metric","estimate","origin"}
        if not required.issubset(summary.columns) or summary.duplicated(["population","model_or_contrast","metric"]).any(): failures.append("summary_keys")
        allowed={"fresh_fit_point","fresh_500_loss_bootstrap","retained_500_interval_reconstruction"}
        if not set(summary.origin)<=allowed: failures.append("summary_origin")
        boot=pd.read_csv(root/"results/fresh_500_loss_bootstrap.csv.gz")
        counts=boot.groupby("population").replicate.nunique().to_dict()
        if counts!={"full_2024":500,"mature_2024":500,"validation_2023":500}: failures.append("fresh_bootstrap_counts")
    except Exception as exc: failures.append(f"table_error:{exc}")
    report={"status":"PASS" if not failures else "FAIL","failures":failures}
    text=json.dumps(report,indent=2)
    if args.json_out: args.json_out.write_text(text+"\n",encoding="utf-8")
    print(text); raise SystemExit(0 if not failures else 1)
if __name__=="__main__": main()
