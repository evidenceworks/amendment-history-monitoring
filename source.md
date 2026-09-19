# Source rights, attribution and minimized derivative

The source is NYC Department of Buildings / NYC Open Data, **DOB NOW: Build – Job Application Filings**, dataset `w9ak-ipjd`, archival revision 3408. The retained authority has 956,139 rows, 827,461,297 bytes and SHA-256 `f910c1fde198fedb764ba9d6310d9234af7940f7fcfd3cc8bdf2f03974bec418`.

`data/analysis.csv.gz` is a minimized deterministic derivative built by the documented raw-to-cohort pipeline and `scripts/build_data.py`. It replaces original root and BIN strings with order-preserving opaque identifiers, retains the original queue-tie rank, and includes only the 19 pre-model fields needed for bounded Core and compact-route verification. The Full source audit itself starts from exact raw revision 3408 rather than from this compact object. These opaque identifiers are not described as irreversibly anonymized.

The [NYC Open Data Technical Standards Manual](https://opendata.cityofnewyork.us/wp-content/uploads/NYC_OpenData_TechnicalStandardsManual.pdf) states that published datasets are public resources available without restriction or licensing requirements. This repository nevertheless preserves the provider, dataset ID, archival revision, source identity and transformation attribution. It does not claim ownership of or apply the repository's MIT or CC BY licenses to the NYC source or source-derived records. Users remain responsible for applicable provider notices and access conditions.

Author-created code is licensed under MIT. Author-created documentation, original figures and aggregate outputs are licensed under CC BY 4.0. See `LICENSES/`.

For the optional end-to-end source-level reproduction, including the complete S1–S6 rerun, see [`full-audit.md`](full-audit.md).
