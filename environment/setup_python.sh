#!/usr/bin/env bash
set -euo pipefail

UV_VERSION=0.12.16
PYTHON_VERSION=3.12.10
PYTHON_ENV=/content/reproduction-python-3.12.10

rm -rf "$PYTHON_ENV"

echo "[python-bootstrap] installing uv==$UV_VERSION with host Python: $(python3 --version 2>&1)"
python3 -m pip install --disable-pip-version-check --quiet --upgrade "uv==$UV_VERSION"

# Resolve the console-script directory belonging to the same host Python that
# performed the pip installation. This avoids accidentally selecting an older
# uv already present elsewhere on PATH.
UV_BIN="$(python3 - <<'PY'
import os, sysconfig
print(os.path.join(sysconfig.get_path('scripts'), 'uv'))
PY
)"
if [ ! -x "$UV_BIN" ]; then
  UV_BIN="$(command -v uv || true)"
fi
if [ -z "$UV_BIN" ] || [ ! -x "$UV_BIN" ]; then
  echo "Pinned uv $UV_VERSION was not found after host-pip bootstrap." >&2
  exit 3
fi

UV_REPORTED="$($UV_BIN --version 2>&1)"
UV_ACTUAL="$(printf '%s\n' "$UV_REPORTED" | awk '{print $2}' | head -n 1)"
echo "[python-bootstrap] uv executable: $UV_BIN"
echo "[python-bootstrap] uv version: $UV_REPORTED"
if [ "$UV_ACTUAL" != "$UV_VERSION" ]; then
  echo "Unexpected uv version: $UV_REPORTED (expected semantic version $UV_VERSION)" >&2
  exit 4
fi

echo "[python-bootstrap] installing Python $PYTHON_VERSION"
"$UV_BIN" python install "$PYTHON_VERSION"

echo "[python-bootstrap] creating controlled environment at $PYTHON_ENV"
"$UV_BIN" venv --python "$PYTHON_VERSION" "$PYTHON_ENV"

echo "[python-bootstrap] installing pinned requirements"
"$UV_BIN" pip install --python "$PYTHON_ENV/bin/python" -r requirements.txt

CONTROLLED_VERSION="$($PYTHON_ENV/bin/python -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
if [ "$CONTROLLED_VERSION" != "$PYTHON_VERSION" ]; then
  echo "Controlled Python mismatch: $CONTROLLED_VERSION (expected $PYTHON_VERSION)" >&2
  exit 5
fi

echo "[python-bootstrap] PASS controlled Python $CONTROLLED_VERSION"
printf '%s\n' "$PYTHON_ENV/bin/python"
