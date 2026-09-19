"""Airplane/offline routes and honest remote unavailability."""

from __future__ import annotations

import pytest

from movie_muse.model_router.adapters.local import LocalModelAdapter
from movie_muse.model_router.api import (
    ClassificationDeniedError,
    LocalRuntimeMissingError,
    ModelRequest,
    ProviderUnavailableError,
    RemoteProviderAdapter,
    RoutingDecision,
)


def test_airplane_denies_remote_and_allows_double(router_stack, request_factory) -> None:
    router_stack.workspace.set_airplane_mode(True)
    decision = router_stack.router.route(request_factory(quality_tier="premium", cost_budget=5.0))
    assert decision.provider_kind != "remote"
    assert decision.offline
    assert decision.provider in {"deterministic_double", "local_stub", "finetune_script_adapter"}


def test_offline_required_allows_double(router_stack, request_factory) -> None:
    decision = router_stack.router.route(request_factory(offline_required=True, quality_tier="fast"))
    assert decision.provider == "deterministic_double"
    assert decision.offline


def test_unavailable_remote_fails_honestly(router_stack, request_factory, monkeypatch) -> None:
    monkeypatch.delenv("MOVIE_MUSE_REMOTE_MODEL_BASE_URL", raising=False)
    with pytest.raises(ProviderUnavailableError):
        router_stack.router.route(
            request_factory(
                capability="remote_only",
                role_contract="expert",
                quality_tier="premium",
                cost_budget=5.0,
            )
        )


def test_remote_adapter_unset_env_raises_without_network(monkeypatch) -> None:
    monkeypatch.delenv("MOVIE_MUSE_REMOTE_MODEL_BASE_URL", raising=False)
    adapter = RemoteProviderAdapter()
    dummy_request = ModelRequest(
        capability="generate_text",
        data_classification="public",
        latency_budget_ms=1000,
        cost_budget=5.0,
        offline_required=False,
        context_tokens=8,
        structured_output=True,
        quality_tier="premium",
        role_contract="executor",
        project_id="proj_dummy",
        actor_id="act_dummy",
        acl_epoch=0,
        permission_snapshot_id="snap",
    )
    dummy_decision = RoutingDecision(
        id="rtd_dummy",
        provider="remote_http",
        model="remote-generic-v1",
        reason="test",
        policy_version="1.0.0",
        capability="generate_text",
        classification="public",
        offline=False,
        cost_quote_id="qte_dummy",
        prompt_id="builtin.default",
        prompt_version="1.0.0",
        provider_kind="remote",
        model_version="remote-1.0.0",
        timestamp="2026-09-01T00:00:00Z",
        paid=True,
        estimated_cost=1.5,
        role_contract="executor",
    )
    with pytest.raises(ProviderUnavailableError, match="unset"):
        adapter.invoke(dummy_request, dummy_decision, "template")


def test_restricted_cannot_fallback_to_disallowed_remote(
    router_stack, request_factory, monkeypatch
) -> None:
    monkeypatch.setenv("MOVIE_MUSE_REMOTE_MODEL_BASE_URL", "https://example.invalid")
    with pytest.raises(ClassificationDeniedError):
        router_stack.router.route(
            request_factory(
                capability="restricted_remote_only",
                role_contract="expert",
                data_classification="restricted",
                quality_tier="premium",
                consent_granted=True,
            )
        )


def test_local_adapter_missing_runtime_fails_honestly(monkeypatch) -> None:
    monkeypatch.delenv("MOVIE_MUSE_LOCAL_MODEL_RUNTIME", raising=False)
    adapter = LocalModelAdapter()
    dummy_request = ModelRequest(
        capability="generate_text",
        data_classification="public",
        latency_budget_ms=1000,
        cost_budget=5.0,
        offline_required=True,
        context_tokens=8,
        structured_output=True,
        quality_tier="standard",
        role_contract="executor",
        project_id="proj_dummy",
        actor_id="act_dummy",
        acl_epoch=0,
        permission_snapshot_id="snap",
    )
    dummy_decision = RoutingDecision(
        id="rtd_local",
        provider="local_stub",
        model="local-stub-v1",
        reason="test",
        policy_version="1.0.0",
        capability="generate_text",
        classification="public",
        offline=True,
        cost_quote_id="qte_local",
        prompt_id="builtin.default",
        prompt_version="1.0.0",
        provider_kind="local",
        model_version="stub-1.0.0",
        timestamp="2026-09-01T00:00:00Z",
        paid=False,
        estimated_cost=0.01,
        role_contract="executor",
    )
    with pytest.raises(LocalRuntimeMissingError, match="unset"):
        adapter.invoke(dummy_request, dummy_decision, "template")
