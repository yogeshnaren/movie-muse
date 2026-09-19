#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec "${SCRIPT_DIR}/_run_pytest.sh" tests/control_plane tests/privacy tests/rights tests/authorization tests/observability
