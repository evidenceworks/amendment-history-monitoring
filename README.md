# Amendment history as lifecycle monitoring information

This repository contains the code, compact derived data, aggregate results and figures for a study of whether dated regulatory amendment history adds monitoring information at a fixed lifecycle checkpoint.

## Reproduction

### Quick check

[Open in Colab](https://colab.research.google.com/github/evidenceworks/amendment-history-monitoring/blob/main/notebooks/quick_check.ipynb)

Runs from the packaged repository and checks package integrity, compact-data identity, headline results and Figures 1–4. The check runs in Python.

### Core reproduction

[Open in Colab](https://colab.research.google.com/github/evidenceworks/amendment-history-monitoring/blob/main/notebooks/core_reproduction.ipynb)

Starts from `data/analysis.csv.gz`, rebuilds the development-only preprocessing, fits M0, M_any, M_count and M1, recomputes the main point results and generates 500 paired evaluation-BIN loss resamples.

### Full source audit

[See the full source audit guide](full-audit.md)

Starts from the archived NYC DOB source at revision 3408 and rebuilds the source-to-analysis path. It reruns the primary analysis and S1–S6, reproduces the representation checks and compares the rebuilt outputs with the packaged reference results. The guide gives the source identity, environment, commands and expected outputs.

## Compact analysis object

`data/analysis.csv.gz` is a deterministic 19-column pre-model dataset with 198,284 rows: 131,311 development, 33,126 validation 2023 and 33,847 validation 2024. The 24,431 mature-2024 roots are a nested subset.

No fitted matrices, coefficients, serialized models or fixed predictions are stored in this file. Its schema and provenance are documented in the adjacent files.

The source data come from NYC DOB NOW: Build – Job Application Filings (`w9ak-ipjd`), archived revision 3408: 956,139 rows, 827,461,297 bytes and SHA-256 `f910c1fde198fedb764ba9d6310d9234af7940f7fcfd3cc8bdf2f03974bec418`.

## Local reproduction

With the pinned Python and R environment active:

```bash
python verification/verify_science.py
python scripts/quick_check.py
python scripts/run_core.py --output /new/empty/core-output --rscript Rscript
python verification/verify_core.py --output /new/empty/core-output
```

Core compares fresh calculations after all four model fits. Numerical comparisons use `atol=1e-10` and `rtol=0`. The complete S1–S6 rerun is covered in the [Full source audit](full-audit.md).

## Repository contents

The repository includes the analysis code, compact minimized derivative, retained primary replicate arrays, reference results and figures.

The 827 MB raw CSV, fixed predictions, serialized models, fitted design matrices, submission documents and unpublished review material are not stored here.

## Licensing

Licensing is summarized in the root [`LICENSE`](LICENSE) file.

Original code is licensed under MIT. Original documentation, figures and aggregate outputs are licensed under CC BY 4.0. NYC source data and source-derived records remain under their source terms and are not relicensed here. See [`source.md`](source.md) and [`LICENSES/`](LICENSES/).

## Study scope

The study is retrospective, based on one city and designed for prediction rather than causal inference. Recorded signoff is treated as an administrative milestone rather than physical completion, intervention benefit or deployment readiness.
