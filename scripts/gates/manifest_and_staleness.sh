#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

python3 "${REPO_ROOT}/scripts/validate_handoff.py"
export PYTHONPATH="${REPO_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"
python3 "${REPO_ROOT}/scripts/mm_status.py" validate
python3 "${REPO_ROOT}/scripts/mm_status.py" check-scopes
python3 "${REPO_ROOT}/scripts/mm_status.py" runnable
