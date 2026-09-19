#!/usr/bin/env bash
# Run named-gate pytest with live/sandbox env vars unset in the child process.
# Contract tests may pop those vars; isolation keeps later live probes honest.
set -euo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
LIVE_ENV_VARS=(
  MOVIE_MUSE_FINAL_DRAFT_BIN
  MOVIE_MUSE_REMOTE_MODEL_BASE_URL
  MOVIE_MUSE_ZOOM_SANDBOX_BASE_URL
  MOVIE_MUSE_GOOGLE_MEET_SANDBOX_BASE_URL
  MOVIE_MUSE_IMAGE_PROVIDER_BASE_URL
  MOVIE_MUSE_VIDEO_PROVIDER_BASE_URL
  MOVIE_MUSE_DELIVERY_CHANNEL_BASE_URL
  MOVIE_MUSE_INSURANCE_PARTNER_BASE_URL
)
unset_args=()
for name in "${LIVE_ENV_VARS[@]}"; do
  unset_args+=(-u "${name}")
done
exec env "${unset_args[@]}" "${SCRIPT_DIR}/_run_pytest.sh" "$@"
