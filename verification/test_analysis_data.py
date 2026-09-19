"""Positive and mutation tests for compact/Core trust boundaries."""
from __future__ import annotations
import copy, json, pathlib, shutil, sys, tempfile
import numpy as np, pandas as pd

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"scripts"),str(ROOT/"src")]
import build_data as compact
import run_core as core

checks={}
def reject(name,fn):
    try:fn()
    except Exception:checks[name]=True
    else:raise AssertionError("mutation accepted: "+name)

df,provenance=core.load_compact(ROOT/"data/analysis.csv.gz",ROOT/"data/provenance.json")
checks["valid_compact"]=True
def mutated(column,value,row=0):
    changed=df.copy();changed.loc[row,column]=value;compact.validate_compact(changed)
reject("duplicate_root",lambda:mutated("root_id",df.root_id.iloc[1]))
reject("duplicate_tie",lambda:mutated("tie_order",int(df.tie_order.iloc[1])))
reject("role_shift",lambda:mutated("role","validation_2023"))
reject("date_shift",lambda:mutated("first_permit","2029-01-01"))
dev=int(np.flatnonzero((df.role=="development").to_numpy())[0]);reject("S1_leakage",lambda:mutated("s1_loc_issued",1,dev))
s2=int(np.flatnonzero((df.no_observed_S==1).to_numpy())[0]);reject("S2_conflict",lambda:mutated("S_filed",1,s2))
reject("wrong_schema",lambda:compact.validate_compact(df.assign(extra=1)))
bad=copy.deepcopy(provenance);bad["compact_sha256"]="0"*64
with tempfile.TemporaryDirectory(prefix="compact_negative_") as temporary:
    bad_path=pathlib.Path(temporary)/"provenance.json";bad_path.write_text(json.dumps(bad),encoding="utf-8")
    reject("wrong_provenance",lambda:core.load_compact(ROOT/"data/analysis.csv.gz",bad_path))
features,_=compact.original_frames(df);maps=core.fit_maps(features[features.role=="development"].copy());designs=core.validation_designs(features,maps,"validation_2023")
checks["design_widths"]={k:v.shape[1] for k,v in designs.items()}=={"M0":20,"M_any":21,"M_count":23,"M1":26}
wrong=designs["M1"][:,::-1];checks["wrong_design_detected"]=not np.array_equal(wrong[:,:20],designs["M0"])
retained=pd.read_csv(ROOT/"data/primary_bootstrap.csv.gz");checks["retained_exact_counts"]=retained.groupby("population").replicate.nunique().eq(500).all()
duplicate=pd.concat([retained,retained.iloc[[0]]],ignore_index=True)
checks["duplicate_replicate_detected"]=bool(duplicate.duplicated(["population","replicate"]).any())
authority=core.expected_fit_paths(ROOT/"results/reference",None)
checks["authority_set_exact"] = set(authority)==set(core.MODEL_ORDER)
checks["authority_paths_resolve"] = all(path.is_file() for path in authority.values())
performance_paths={
    "validation_2023": ROOT/"results/reference/primary/2023/performance.csv",
    "full_2024": ROOT/"results/reference/primary/2024_180d/performance.csv",
    "mature_2024": ROOT/"results/reference/primary/2024_365d/performance.csv",
}
checks["performance_paths_resolve"] = all(path.is_file() for path in performance_paths.values())
core.preflight_repository(ROOT/"results/reference")
checks["preflight_pristine"] = True
with tempfile.TemporaryDirectory(prefix="core_preflight_negative_") as temporary:
    reference_copy=pathlib.Path(temporary)/"reference"
    shutil.copytree(ROOT/"results/reference", reference_copy)
    (reference_copy/"models/base_coefficients.csv").unlink()
    reject("missing_authority_preflight", lambda: core.preflight_repository(reference_copy))
checks={k:bool(v) for k,v in checks.items()};assert all(checks.values()),checks
print(json.dumps({"status":"PASS","checks":checks,"count":len(checks)},indent=2))
