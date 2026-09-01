#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)"

python3 "${REPO_ROOT}/scripts/validate_handoff.py"

# This is a fail-closed V2 release-gate starter. Cursor must implement every
# named gate as the corresponding work packages land. Missing gates are a hard
# failure; no placeholder or skip is accepted.
required_gates=(
  "manifest_and_staleness"
  "static_quality_and_boundaries"
  "migrations_backup_and_recovery"
  "unit_and_property"
  "integration_sync_concurrency_and_crash"
  "layout_render_and_fdx"
  "ai_contract_and_evaluation"
  "security_privacy_and_rights"
  "api_mcp_webhooks"
  "web_desktop_and_mobile"
  "external_live_providers"
  "competitive_regressions"
  "golden_path_41_steps"
)

for gate in "${required_gates[@]}"; do
  gate_script="${REPO_ROOT}/scripts/gates/${gate}.sh"
  if [[ ! -x "${gate_script}" ]]; then
    echo "MOVIE_MUSE_PROTOTYPE_VERIFICATION=NOT_READY missing_executable_gate=${gate}" >&2
    exit 1
  fi
  "${gate_script}"
done

# The status gate must have proven that all 47 items and required external
# gates are current PASS for the tested commit/input fingerprints.
echo "MOVIE_MUSE_PROTOTYPE_VERIFICATION=PASS"

