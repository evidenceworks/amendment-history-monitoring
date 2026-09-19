# Reproduction environment

The accepted run used Python 3.12.10, the exact package versions in `requirements.txt`, R 4.6.1 and `survival` 3.8-6. Verify an existing environment and selected R executable with:

```bash
python scripts/check_runtime.py --rscript Rscript
```

`setup_python.sh` creates an isolated Python 3.12.10 environment outside the checkout using pinned `uv` 0.12.16, installs the pinned requirements into that environment, verifies its patch version and prints the selected interpreter path. The full notebook uses that same interpreter for guards, reproduction and comparison.

`setup_r.sh` is a bounded Ubuntu/Colab provisioning attempt. It installs R only when an exact 4.6.1 package is available from the configured CRAN Ubuntu repository, installs `survival` 3.8-6 from its CRAN archive, and then invokes the same strict version guard. It exits nonzero rather than substituting another R or package version.
