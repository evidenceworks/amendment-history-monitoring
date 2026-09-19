# Full source audit

The Quick and Core notebooks are the normal reviewer route. This page documents the optional **Full source audit** for readers who want to trace the analysis from the exact archived NYC DOB source through the complete registered analysis and final parity checks.

This route is intentionally separate from the normal Core timing claim. It requires the exact raw CSV, which is not distributed in this repository, and it can take substantially longer than Core. No fixed runtime is claimed here.

## What you need

Use the exact archived source analyzed by the study:

- NYC DOB NOW: Build – Job Application Filings
- dataset: `w9ak-ipjd`
- archival revision: `3408`
- rows: `956,139`
- bytes: `827,461,297`
- SHA-256: `f910c1fde198fedb764ba9d6310d9234af7940f7fcfd3cc8bdf2f03974bec418`

Source acquisition and verification are described in [`source/README.md`](source/README.md). The repository does not substitute a current live export for revision 3408.

Use the pinned environment documented in [`environment/README.md`](environment/README.md) and `environment/environment.json`. The accepted toolchain is Python 3.12.10, the package versions in `requirements.txt`, R 4.6.1 and `survival` 3.8-6.

Before a full run, the source can be checked directly:

```bash
python scripts/check_source.py /path/to/w9ak-ipjd_version_3408.csv
```

## Two source-level operations

### Rebuild the compact analysis object

To independently rebuild the deterministic 19-column compact object from the exact raw source, use:

```bash
python scripts/build_data.py \
  --source /path/to/w9ak-ipjd_version_3408.csv \
  --output /new/empty/compact-build \
  --rscript Rscript
```

This command verifies revision 3408 before reading it, runs the ingest/cohort/audit/pre-model pipeline, exports canonical CSV bytes and deterministic gzip, and checks schema, row, value, map, design, ordering, weight-stream and queue parity. It does **not** fit the study models or rerun S1–S6.

### Run the complete source audit

For the end-to-end source-level reproduction, use:

```bash
python reproduce.py \
  --source /path/to/w9ak-ipjd_version_3408.csv \
  --output /new/empty/full-reproduction \
  --rscript Rscript
```

The output directory must not already exist.

`reproduce.py` performs the following sequence:

1. verifies the repository science manifest;
2. verifies the pinned Python/R runtime;
3. verifies the raw source identity;
4. reconstructs the raw-source cohort, audit ledgers and prepared analysis data;
5. fits the primary M0 and M1 models, evaluates the registered validation populations and runs proportional-hazards diagnostics;
6. reruns all six registered sensitivities S1–S6;
7. reproduces the post-primary base → any → count → history representation audit;
8. regenerates Figures 1–4 from their packaged source tables in an isolated output tree;
9. runs the strict comparator between the fresh source-level outputs and `results/reference/`.

The final comparison is written to:

```text
full-reproduction/parity_comparison.json
```

The main output tree also contains:

```text
full-reproduction/
    primary/
    representation/
    figure_reproduction/
    parity_comparison.json
```

## What S1–S6 do

The six sensitivities are implemented in `src/analysis.py`. The descriptions below are deliberately mechanical so the documentation does not add interpretations that are absent from the code.

| Sensitivity | Implemented change |
|---|---|
| **S1** | Reuses the primary predictions and produces the registered S1/discordance evaluation; it does not refit the primary models. |
| **S2** | Restricts the analysis rows to `no_observed_S == 1`, refits M0 and M1, and reevaluates the validation populations. |
| **S3** | Excludes development roots whose first-permit year is 2020 or 2021, then refits M0 and M1. |
| **S4** | Keeps the primary M0 and refits M1 with the explicit `PAA_count_1`, `PAA_count_2` and `PAA_count_3plus` count representation. |
| **S5** | Keeps the primary M0 and refits M1 with the binary `PAA_any` representation. This is the binary-any representation also fitted as M_any in Core. |
| **S6** | Restricts the development sample to first-permit years 2021–2022, keeps the validation populations, then refits M0 and M1. |

The full source route also regenerates source exclusion and duplicate ledgers, malformed-sibling accounting, contributor-level timing checks, prepared-cohort invariants, proportional-hazards diagnostics and the complete source-to-interval reconstruction used by the registered analysis.

## How this differs from Core

Core starts from the packaged compact object and is intentionally bounded. It freshly fits M0, M_any, M_count and M1 and performs the principal evaluation/representation checks needed for routine reproduction.

The Full source audit starts from the exact 827 MB raw revision and exercises the broader source-to-analysis pipeline, including the full S1–S6 set and raw-source audit ledgers. It is therefore an optional audit route rather than the expected reviewer path.

## Interpreting success or failure

A successful command exits without error after the strict comparator completes. `parity_comparison.json` records the detailed comparisons. A source hash mismatch, runtime mismatch, failed model fit, failed audit invariant or substantive comparator mismatch causes the pipeline to stop rather than silently substituting a different input or environment.

For source rights and the minimized derivative, see [`source.md`](source.md).
