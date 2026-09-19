#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec "${SCRIPT_DIR}/_run_pytest.sh" tests/model_router tests/evaluation tests/audience_lab tests/rubric
