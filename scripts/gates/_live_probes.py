#!/usr/bin/env python3
"""Fail-closed live/sandbox probes for required_for_final EXT gates.

Contract pytest is not live PASS. Unset or unreachable providers are not
skipped and do not satisfy MOVIE_MUSE_PROTOTYPE_VERIFICATION=PASS. A YAML
stamp without a successful probe is also insufficient: verify_all runs this
module before accepting ledger EXT PASS.
"""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable

from movie_muse.adapters.google_meet.api import GOOGLE_MEET_SANDBOX_ENV, require_google_meet_sandbox
from movie_muse.adapters.zoom.api import ZOOM_SANDBOX_ENV, require_zoom_sandbox
from movie_muse.fdx.api import require_final_draft
from movie_muse.model_router.api import (
    ModelRequest,
    ProviderUnavailableError,
    RemoteProviderAdapter,
    RoutingDecision,
)
from movie_muse.storyboard.api import IMAGE_PROVIDER_ENV, require_image_provider
from movie_muse.video_previs.api import VIDEO_PROVIDER_ENV, require_video_provider

DELIVERY_CHANNEL_ENV = "MOVIE_MUSE_DELIVERY_CHANNEL_BASE_URL"
INSURANCE_PARTNER_ENV = "MOVIE_MUSE_INSURANCE_PARTNER_BASE_URL"
PROBE_TIMEOUT_S = 8.0

REQUIRED_LIVE_GATES = (
    "EXT-FDX-FINAL-DRAFT",
    "EXT-REMOTE-MODEL",
    "EXT-ZOOM-SANDBOX",
    "EXT-GOOGLE-MEET-SANDBOX",
    "EXT-IMAGE-PROVIDER",
    "EXT-VIDEO-PROVIDER",
    "EXT-DELIVERY-CHANNEL",
    "EXT-INSURANCE-PARTNER",
)


class LiveProbeError(RuntimeError):
    """A required live/sandbox probe failed closed."""


def _http_probe(url: str, gate_id: str) -> None:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=PROBE_TIMEOUT_S) as response:
            response.read(512)
    except urllib.error.HTTPError as exc:
        if exc.code >= 500:
            raise LiveProbeError(
                f"{gate_id} live endpoint returned HTTP {exc.code}"
            ) from exc
    except urllib.error.URLError as exc:
        raise LiveProbeError(f"{gate_id} live endpoint unreachable: {exc}") from exc


def probe_final_draft() -> None:
    require_final_draft()


def probe_remote_model() -> None:
    adapter = RemoteProviderAdapter(timeout_s=PROBE_TIMEOUT_S)
    request = ModelRequest(
        capability="generate_text",
        data_classification="public",
        latency_budget_ms=5000,
        cost_budget=5.0,
        offline_required=False,
        context_tokens=16,
        structured_output=True,
        quality_tier="premium",
        role_contract="executor",
        project_id="proj_live_probe",
        actor_id="act_live_probe",
        acl_epoch=0,
        permission_snapshot_id="snap_live_probe",
        input={"text": "live-probe"},
    )
    decision = RoutingDecision(
        id="rtd_live_probe",
        provider="remote_http",
        model="remote-generic-v1",
        reason="live-probe",
        policy_version="1.0.0",
        capability="generate_text",
        classification="public",
        offline=False,
        cost_quote_id="qte_live_probe",
        prompt_id="builtin.default",
        prompt_version="1.0.0",
        provider_kind="remote",
        model_version="remote-1.0.0",
        timestamp="2026-09-01T00:00:00Z",
        paid=True,
        estimated_cost=1.5,
        role_contract="executor",
    )
    try:
        result = adapter.invoke(request, decision, "live probe")
    except ProviderUnavailableError as exc:
        raise LiveProbeError(f"EXT-REMOTE-MODEL fail-closed: {exc}") from exc
    if "chain_of_thought" in result.output:
        raise LiveProbeError("EXT-REMOTE-MODEL returned chain_of_thought")


def probe_zoom() -> None:
    _http_probe(require_zoom_sandbox(), "EXT-ZOOM-SANDBOX")


def probe_google_meet() -> None:
    _http_probe(require_google_meet_sandbox(), "EXT-GOOGLE-MEET-SANDBOX")


def probe_image_provider() -> None:
    _http_probe(require_image_provider(), "EXT-IMAGE-PROVIDER")


def probe_video_provider() -> None:
    _http_probe(require_video_provider(), "EXT-VIDEO-PROVIDER")


def _require_env(name: str, gate_id: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise LiveProbeError(f"{name} is unset; {gate_id} stays NOT_RUN (fail-closed)")
    return value


def probe_delivery_channel() -> None:
    _http_probe(_require_env(DELIVERY_CHANNEL_ENV, "EXT-DELIVERY-CHANNEL"), "EXT-DELIVERY-CHANNEL")


def probe_insurance_partner() -> None:
    _http_probe(
        _require_env(INSURANCE_PARTNER_ENV, "EXT-INSURANCE-PARTNER"),
        "EXT-INSURANCE-PARTNER",
    )


PROBES: tuple[tuple[str, Callable[[], None]], ...] = (
    ("EXT-FDX-FINAL-DRAFT", probe_final_draft),
    ("EXT-REMOTE-MODEL", probe_remote_model),
    ("EXT-ZOOM-SANDBOX", probe_zoom),
    ("EXT-GOOGLE-MEET-SANDBOX", probe_google_meet),
    ("EXT-IMAGE-PROVIDER", probe_image_provider),
    ("EXT-VIDEO-PROVIDER", probe_video_provider),
    ("EXT-DELIVERY-CHANNEL", probe_delivery_channel),
    ("EXT-INSURANCE-PARTNER", probe_insurance_partner),
)

ENV_NAMES = (
    "MOVIE_MUSE_FINAL_DRAFT_BIN",
    "MOVIE_MUSE_REMOTE_MODEL_BASE_URL",
    ZOOM_SANDBOX_ENV,
    GOOGLE_MEET_SANDBOX_ENV,
    IMAGE_PROVIDER_ENV,
    VIDEO_PROVIDER_ENV,
    DELIVERY_CHANNEL_ENV,
    INSURANCE_PARTNER_ENV,
)


def probe_all() -> list[str]:
    missing: list[str] = []
    for gate_id, probe in PROBES:
        try:
            probe()
        except Exception:
            missing.append(gate_id)
    return missing


def main() -> int:
    missing = probe_all()
    if missing:
        print(
            "MOVIE_MUSE_PROTOTYPE_VERIFICATION=NOT_READY missing_live_gates="
            + ",".join(missing),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
