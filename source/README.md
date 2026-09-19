# Exact source acquisition and verification

The study analyzed NYC DOB NOW: Build – Job Application Filings (`w9ak-ipjd`), archival revision 3408, dated 12 September 2026. The archived CSV contains 956,139 data rows, is 827,461,297 bytes, and has SHA-256:

`f910c1fde198fedb764ba9d6310d9234af7940f7fcfd3cc8bdf2f03974bec418`

The archival export locator used for the study is:

`https://data.cityofnewyork.us/api/archival.csv?id=w9ak-ipjd&version=3408&method=export`

Before analysis run:

```bash
python scripts/check_source.py /path/to/source.csv
```

A current live export is not numerically interchangeable with the archived revision and is rejected unless its bytes, row count, and SHA-256 are identical. The repository never searches user directories for a source file.
