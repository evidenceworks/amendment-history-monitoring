# Advanced source and Deep reproduction

The normal reviewer route is the Quick and Core notebooks. This guide is for source auditors.

## Rebuild the compact object from the exact source

Activate the exact environment in `environment/environment.json`, then run:

```bash
python scripts/build_data.py \
  --source /path/to/w9ak-ipjd_version_3408.csv \
  --output /new/empty/compact-build \
  --rscript Rscript
```

The command verifies revision 3408 before reading it, runs the unchanged ingest/cohort/audit/pre-model pipeline, exports canonical CSV bytes and deterministic gzip (`mtime=0`, empty embedded filename), and fails on schema, row, value, map, design, ordering, weight-stream or queue parity errors. It does not run S1–S6 or fit a model.

The accepted source identity is 956,139 rows, 827,461,297 bytes, SHA-256 `f910c1fde198fedb764ba9d6310d9234af7940f7fcfd3cc8bdf2f03974bec418`.

## Complete Deep audit

The original CLI remains available:

```bash
python reproduce.py \
  --source /path/to/w9ak-ipjd_version_3408.csv \
  --output /new/empty/full-reproduction \
  --rscript Rscript
```

This slower route reconstructs the raw cohort and source audit, fits the primary models, reruns S1–S6, performs the full registered bootstrap work, reproduces representation outputs and figures, and runs the strict comparator. It is not part of the normal Core timing claim.

Deep-only scope includes the complete S1–S6 interval tables, source exclusion and duplicate ledgers, contributor-level timing audit, malformed-sibling accounting, PH diagnostics, and complete source-to-interval reconstruction. Core verifies retained sensitivity references without claiming those analyses were freshly rerun.
