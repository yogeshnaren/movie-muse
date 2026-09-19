#!/usr/bin/env bash
# Unit/property coverage for packages not owned by other named gates.
# tests/release is excluded because it invokes verify_all.sh.
set -euo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec "${SCRIPT_DIR}/_run_pytest.sh" \
  tests/schemas tests/document tests/compiler tests/film_ir \
  tests/identity tests/revisions tests/proposals tests/audit \
  tests/artifacts tests/beats tests/breakdown tests/budget \
  tests/commercial_forecast tests/context tests/continuity \
  tests/creative_intent tests/department_handoff tests/dependencies \
  tests/director tests/fixtures tests/harness tests/impact \
  tests/investor_artifacts tests/meeting_capture tests/policy \
  tests/production_revisions tests/project_memory tests/provenance \
  tests/reference_lens tests/render tests/retrieval tests/room_mode \
  tests/scheduling tests/shot_ir tests/state_engine tests/storyboard \
  tests/ux tests/video_previs tests/visual_language tests/writer_unblock \
  tests/adapters tests/insurance_readiness
