# Amendment history as lifecycle monitoring information

Code, minimized derived data, aggregate results and figures for the study of whether dated regulatory amendment history adds monitoring information at a fixed lifecycle checkpoint.

The repository has two normal reviewer routes and one optional source-level route:

| Route | Starting point | What it does | Intended use |
|---|---|---|---|
| **Quick check** | Packaged repository | Verifies package integrity, compact-data identity, headline accepted results and Figures 1–4. No model fitting and no R required. | Fast inspection |
| **Core reproduction** | `data/analysis.csv.gz` | Freshly learns development-only preprocessing, fits M0, M_any, M_count and M1, recomputes the principal point results and generates 500 fresh paired evaluation-BIN loss resamples. | Normal computational reproduction |
| **Full source audit** | Exact raw revision 3408 CSV | Reconstructs the source-to-analysis pipeline, reruns the primary analysis and S1–S6, reproduces the representation audit and runs the strict comparator. | Optional source-level audit |

Direct Colab launchers: [Quick check](https://colab.research.google.com/github/evidenceworks/amendment-history-monitoring/blob/main/notebooks/quick_check.ipynb) · [Core reproduction](https://colab.research.google.com/github/evidenceworks/amendment-history-monitoring/blob/main/notebooks/core_reproduction.ipynb)

The Quick and Core notebooks are the normal reviewer path. The **Full source audit** is a local command-line route for readers who have the exact archived raw CSV; it is not a third notebook and has no short runtime claim. See [`full-audit.md`](full-audit.md) for prerequisites, exact commands, the S1–S6 scope and the expected output tree.

## Compact object

`data/analysis.csv.gz` is a deterministic 19-column, pre-model derivative with 198,284 physical rows: 131,311 development, 33,126 validation-2023 and 33,847 validation-2024. The 24,431 mature-2024 roots are a nested subset. It contains no fitted matrix, coefficients, serialized model or fixed prediction authority. Types and provenance are in the adjacent schema and provenance files.

The exact source is NYC DOB NOW: Build – Job Application Filings (`w9ak-ipjd`), archival revision 3408: 956,139 raw rows, 827,461,297 bytes, SHA-256 `f910c1fde198fedb764ba9d6310d9234af7940f7fcfd3cc8bdf2f03974bec418`.

## Local checks

With the exact pinned Python/R toolchain active:

```bash
python verification/verify_science.py
python scripts/quick_check.py
python scripts/run_core.py --output /new/empty/core-output --rscript Rscript
python verification/verify_core.py --output /new/empty/core-output
```

The Core runner compares newly computed quantities only after the four fits and uses strict `atol=1e-10, rtol=0` semantics. Core does not claim to rerun every registered sensitivity: M_any is the same binary-any representation used by S5, while the complete S1–S6 rerun belongs to the Full source audit.

## Repository boundary

The repository includes code, the compact minimized derivative, authentic retained primary replicate arrays, aggregate scientific references and accepted figures. It excludes the 827 MB raw CSV, fixed predictions, serialized models, fitted design matrices, submission Office files and unpublished review material.

Licensing is summarized in the root `LICENSE` file. Original code is MIT licensed; original documentation, figures and aggregate outputs are CC BY 4.0. These licenses do not relicense the NYC source or minimized source-derived records; see `source.md` and `LICENSES/`.

The analysis is retrospective, same-city and predictive rather than causal. Recorded signoff is an administrative milestone, not physical completion, intervention benefit or deployment readiness.
