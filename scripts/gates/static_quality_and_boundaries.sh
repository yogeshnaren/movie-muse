#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

export PYTHONPATH="${REPO_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"

python3 -m ruff check src tests scripts backend
python3 -m mypy
python3 -m pytest tests/architecture tests/security tests/toolchain backend/tests
python3 "${REPO_ROOT}/scripts/mm_status.py" boundaries
python3 "${REPO_ROOT}/scripts/mm_status.py" secrets
