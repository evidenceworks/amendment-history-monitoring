# Amendment history as lifecycle monitoring information

This repository contains the code, compact analysis data, figures and reference outputs for a study of whether dated regulatory amendment history adds useful monitoring information at a fixed lifecycle checkpoint.

## Reproduce or inspect the study

For most readers, the two Colab notebooks are enough.

**Quick check** — [open in Colab](https://colab.research.google.com/github/evidenceworks/amendment-history-monitoring/blob/main/notebooks/quick_check.ipynb)

Checks the repository, compact data, headline reference results and Figures 1–4. It does not fit models and does not require R.

**Core reproduction** — [open in Colab](https://colab.research.google.com/github/evidenceworks/amendment-history-monitoring/blob/main/notebooks/core_reproduction.ipynb)

Starts from `data/analysis.csv.gz`, rebuilds the development-only preprocessing, fits M0, M_any, M_count and M1, recomputes the main point results and draws 500 paired evaluation-BIN loss resamples.

Readers who want to start from the archived NYC source rather than the compact data can use the [full source audit](full-audit.md). That route uses archived revision 3408 and reruns source processing, the primary analysis, S1–S6 and the representation checks, then compares the rebuilt outputs with the packaged reference results.

## Analysis data

`data/analysis.csv.gz` is a deterministic 19-column pre-model dataset with 198,284 rows: 131,311 development, 33,126 validation 2023 and 33,847 validation 2024. The 24,431 mature-2024 roots are a nested subset.

The file contains no fitted coefficients, serialized models or fixed predictions. Its schema and provenance are stored alongside it.

The underlying source is NYC DOB NOW: Build – Job Application Filings (`w9ak-ipjd`), archived revision 3408: 956,139 rows, 827,461,297 bytes and SHA-256 `f910c1fde198fedb764ba9d6310d9234af7940f7fcfd3cc8bdf2f03974bec418`.

The raw CSV is not included in this repository.

## Run locally

With the pinned Python and R environment active:

```bash
python verification/verify_science.py
python scripts/quick_check.py
python scripts/run_core.py --output /new/empty/core-output --rscript Rscript
python verification/verify_core.py --output /new/empty/core-output
```

Core fits the four model variants before comparing fresh outputs with the reference results. Comparisons use `atol=1e-10` and `rtol=0`. The complete S1–S6 rerun is part of the [full source audit](full-audit.md).

## Repository contents

The repository includes the analysis code, compact data, retained primary replicate arrays, reference results and figures. It does not include the 827 MB raw CSV, fixed predictions, serialized models, fitted design matrices, submission files or unpublished review material.

Code written for the project is licensed under MIT. Original documentation, figures and aggregate outputs are licensed under CC BY 4.0. NYC source data and source-derived records keep their source terms and are not relicensed here. See [`LICENSE`](LICENSE), [`LICENSES/`](LICENSES/) and [`source.md`](source.md).

The study is retrospective and predictive within one city. Recorded signoff is treated as an administrative milestone rather than physical completion, intervention benefit or deployment readiness.
