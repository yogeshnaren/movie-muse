"""EXT-REMOTE-MODEL smoke: unset env is fail-closed, never pytest.skip.

If MOVIE_MUSE_REMOTE_MODEL_BASE_URL is unset, invoke() must raise
ProviderUnavailableError. The live gate remains NOT_RUN; this test does not
mark it PASS. When the env is set, one real HTTP round-trip is attempted.
"""

from __future__ import annotations

import os

import pytest

from movie_muse.model_router.api import (
    ModelRequest,
    ProviderUnavailableError,
    RemoteProviderAdapter,
    RoutingDecision,
)

REMOTE_ENV = "MOVIE_MUSE_REMOTE_MODEL_BASE_URL"


def _dummy_request() -> ModelRequest:
    return ModelRequest(
        capability="generate_text",
        data_classification="public",
        latency_budget_ms=5000,
        cost_budget=5.0,
        offline_required=False,
        context_tokens=16,
        structured_output=True,
        quality_tier="premium",
        role_contract="executor",
        project_id="proj_smoke",
        actor_id="act_smoke",
        acl_epoch=0,
        permission_snapshot_id="snap_smoke",
        input={"text": "smoke"},
    )


def _dummy_decision() -> RoutingDecision:
    return RoutingDecision(
        id="rtd_smoke",
        provider="remote_http",
        model="remote-generic-v1",
        reason="smoke",
        policy_version="1.0.0",
        capability="generate_text",
        classification="public",
        offline=False,
        cost_quote_id="qte_smoke",
        prompt_id="builtin.default",
        prompt_version="1.0.0",
        provider_kind="remote",
        model_version="remote-1.0.0",
        timestamp="2026-09-01T00:00:00Z",
        paid=True,
        estimated_cost=1.5,
        role_contract="executor",
    )


def test_remote_smoke_fail_closed_or_live_round_trip() -> None:
    adapter = RemoteProviderAdapter()
    request = _dummy_request()
    decision = _dummy_decision()
    base = os.environ.get(REMOTE_ENV, "").strip()
    if not base:
        with pytest.raises(ProviderUnavailableError):
            adapter.invoke(request, decision, "smoke template")
        return
    result = adapter.invoke(request, decision, "smoke template")
    assert isinstance(result.output, dict)
    assert result.model_version
    assert "chain_of_thought" not in result.output
