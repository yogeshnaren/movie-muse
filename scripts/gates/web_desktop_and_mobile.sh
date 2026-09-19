#!/usr/bin/env bash
# Platform pytest plus frontend vitest smoke. Missing node_modules is fail-closed.
set -euo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/../.." && pwd)"
"${SCRIPT_DIR}/_run_pytest.sh" tests/platforms tests/hosts
cd "${REPO_ROOT}/frontend"
if [[ ! -x node_modules/.bin/vitest ]]; then
  echo "MOVIE_MUSE_PROTOTYPE_VERIFICATION=NOT_READY missing_frontend_vitest" >&2
  exit 1
fi
./node_modules/.bin/vitest --run
