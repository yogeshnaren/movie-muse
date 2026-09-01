#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

python_version="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' \
  || { echo "Python 3.11+ is required (found ${python_version})" >&2; exit 1; }

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required for the frontend toolchain" >&2
  exit 1
fi

python3 -m pip install --upgrade pip
python3 -m pip install -r "${REPO_ROOT}/requirements-dev.txt"
python3 -m pip install -r "${REPO_ROOT}/backend/requirements.txt"

(cd "${REPO_ROOT}/frontend" && npm ci)

python3 "${REPO_ROOT}/scripts/validate_handoff.py"
echo "BOOTSTRAP=PASS python=${python_version}"
