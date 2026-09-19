#!/usr/bin/env bash
set -euo pipefail

. /etc/os-release
case "${VERSION_CODENAME:-}" in
  jammy|noble) ;;
  *) echo "Unsupported Ubuntu release for the bounded R provisioning attempt: ${VERSION_CODENAME:-unknown}" >&2; exit 2 ;;
esac

if command -v Rscript >/dev/null 2>&1 && \
   Rscript -e 'quit(status=as.integer(!(as.character(getRversion())=="4.6.1" && as.character(packageVersion("survival"))=="3.8.6")))'; then
  echo "Exact R 4.6.1 and survival 3.8-6 are already available."
  "${REPRO_PYTHON:-python}" scripts/check_runtime.py --rscript Rscript
  exit 0
fi

apt-get update
apt-get install -y --no-install-recommends ca-certificates curl gnupg build-essential fonts-liberation
curl -fsSL https://cloud.r-project.org/bin/linux/ubuntu/marutter_pubkey.asc -o /etc/apt/trusted.gpg.d/cran_ubuntu_key.asc
echo "deb https://cloud.r-project.org/bin/linux/ubuntu ${VERSION_CODENAME}-cran40/" > /etc/apt/sources.list.d/cran-r.list
apt-get update
R_APT_VERSION="$(apt-cache madison r-base-core | awk '$3 ~ /^4[.]6[.]1([.-]|$)/ {print $3; exit}')"
if [ -z "$R_APT_VERSION" ]; then
  echo "Exact R 4.6.1 is unavailable from the configured CRAN Ubuntu repository; refusing substitution." >&2
  exit 3
fi
apt-get install -y --no-install-recommends "r-base-core=${R_APT_VERSION}" "r-base-dev=${R_APT_VERSION}"
Rscript -e 'install.packages("https://cran.r-project.org/src/contrib/Archive/survival/survival_3.8-6.tar.gz", repos=NULL, type="source")'
"${REPRO_PYTHON:-python}" scripts/check_runtime.py --rscript Rscript
