# Exact source acquisition and verification

NYC DOB NOW: Build – Job Application Filings (`w9ak-ipjd`), archival revision 3408

Dataset page:

`https://data.cityofnewyork.us/d/w9ak-ipjd`

Archived revision 3408:

`https://data.cityofnewyork.us/api/archival.csv?id=w9ak-ipjd&version=3408&method=export`  
(last retrieved on 14 September 2026)

Data.gov catalog:

`https://catalog.data.gov/dataset/dob-now-build-job-application-filings`

The archived CSV contains 956,139 data rows, is 827,461,297 bytes, and has SHA-256:

`f910c1fde198fedb764ba9d6310d9234af7940f7fcfd3cc8bdf2f03974bec418`

Before analysis run:

```bash
python scripts/check_source.py /path/to/source.csv
```

A current live export is not numerically interchangeable with the archived revision and is rejected unless its bytes, row count, and SHA-256 are identical. The repository never searches user directories for a source file.

For the complete raw-source reproduction after acquiring and verifying this exact archive, see [`../full-audit.md`](../full-audit.md).
