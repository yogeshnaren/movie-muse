#!/usr/bin/env bash
# Prove required live/sandbox gates are fail-closed when unconfigured.
# Contract tests are not live PASS. Unset providers are not skipped.
set -euo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"
export PYTHONPATH="${REPO_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"

"${SCRIPT_DIR}/_run_pytest.sh" \
  tests/fdx/test_final_draft_unavailable.py \
  tests/model_router/test_remote_smoke.py \
  tests/adapters/zoom \
  tests/adapters/google_meet \
  tests/storyboard/test_storyboard_boundaries.py \
  tests/video_previs/test_video_previs_boundaries.py \
  tests/insurance_readiness/test_insurance_readiness_boundaries.py \
  tests/correspondence \
  tests/golden_path/test_live_probes.py

python3 "${SCRIPT_DIR}/_live_probes.py"

python3 - <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

import yaml

manifest = yaml.safe_load(Path("movie_muse_build_status.yaml").read_text(encoding="utf-8"))
blocked = [
    str(gate["id"])
    for gate in manifest.get("external_gates", [])
    if gate.get("required_for_final") and gate.get("status") != "PASS"
]
if blocked:
    print(
        "MOVIE_MUSE_PROTOTYPE_VERIFICATION=NOT_READY missing_live_gates="
        + ",".join(blocked),
        file=sys.stderr,
    )
    raise SystemExit(1)
PY
