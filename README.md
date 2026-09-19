# Amendment history as lifecycle monitoring information

Code, minimized derived data, aggregate results and figures for the study of whether dated regulatory amendment history adds monitoring information at a fixed lifecycle checkpoint.

The repository provides three reproduction routes: **Quick check + compact-data Core reproduction + optional Deep CLI audit**.

## Normal reviewer route

1. `notebooks/quick_check.ipynb` verifies package integrity, compact source identity, headline accepted results and Figures 1–4. It does not fit models or require R.
2. `notebooks/core_reproduction.ipynb` starts from `data/analysis.csv.gz`, freshly learns development-only preprocessing, fits exactly M0, M_any, M_count and M1 with the accepted R/Efron implementation, recomputes point results, and freshly generates 500 paired evaluation-BIN loss resamples. Other primary intervals are reconstructed from authentic retained replicate arrays and labelled as such.
3. `advanced.md` documents the slower raw revision-3408 source builder and full Deep audit. S1–S6 remain Deep scope except that Core fits the same binary-any model used by S5.

Direct Colab launchers: [Quick check](https://colab.research.google.com/github/evidenceworks/amendment-history-monitoring/blob/main/notebooks/quick_check.ipynb) · [Core reproduction](https://colab.research.google.com/github/evidenceworks/amendment-history-monitoring/blob/main/notebooks/core_reproduction.ipynb)

Quick is designed for inspection without model fitting. Core performs the bounded four-model computation from the compact object. Deep is the slower source-level audit route.

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

The Core runner compares newly computed quantities only after the four fits and uses strict `atol=1e-10, rtol=0` semantics.

## Repository boundary

The repository includes code, the compact minimized derivative, authentic retained primary replicate arrays, aggregate scientific references and accepted figures. It excludes the 827 MB raw CSV, fixed predictions, serialized models, fitted design matrices, submission Office files and unpublished review material.

Licensing is summarized in the root `LICENSE` file. Original code is MIT licensed; original documentation, figures and aggregate outputs are CC BY 4.0. These licenses do not relicense the NYC source or minimized source-derived records; see `source.md` and `LICENSES/`.

The analysis is retrospective, same-city and predictive rather than causal. Recorded signoff is an administrative milestone, not physical completion, intervention benefit or deployment readiness.
