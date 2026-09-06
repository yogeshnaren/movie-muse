"""Policy files exist and choose double vs local vs remote from constraints."""

from __future__ import annotations

from pathlib import Path

from movie_muse.model_router.api import (
    RouteConstraints,
    default_policy_dir,
    evaluate_route,
    load_model_policy,
)


def test_policy_directory_contains_required_yaml() -> None:
    directory = default_policy_dir()
    for name in (
        "policy.yaml",
        "capabilities.yaml",
        "providers.yaml",
        "consent.yaml",
        "classification.yaml",
        "budgets.yaml",
        "cache.yaml",
        "role_contracts.yaml",
    ):
        assert (directory / name).is_file()
    policy = load_model_policy(directory)
    assert policy.version == "1.0.0"
    assert "generate_text" in policy.capabilities
    assert policy.providers["remote_http"].paid
    assert policy.providers["deterministic_double"].offline
    assert Path(directory).as_posix().endswith("policy/models")


def test_fast_tier_chooses_deterministic_double() -> None:
    policy = load_model_policy()
    choice = evaluate_route(
        policy,
        RouteConstraints(
            capability="generate_text",
            classification="public",
            offline_required=False,
            cost_budget=5.0,
            latency_budget_ms=5000,
            quality_tier="fast",
            context_tokens=128,
            role_contract="executor",
            remote_available=True,
            local_available=True,
        ),
    )
    assert choice.provider_id == "deterministic_double"
    assert choice.provider_kind == "double"


def test_standard_online_with_local_runtime_chooses_local() -> None:
    policy = load_model_policy()
    choice = evaluate_route(
        policy,
        RouteConstraints(
            capability="generate_text",
            classification="public",
            offline_required=False,
            cost_budget=5.0,
            latency_budget_ms=5000,
            quality_tier="standard",
            context_tokens=128,
            role_contract="executor",
            remote_available=True,
            local_available=True,
        ),
    )
    assert choice.provider_id == "local_stub"
    assert choice.provider_kind == "local"


def test_premium_public_budget_chooses_remote() -> None:
    policy = load_model_policy()
    choice = evaluate_route(
        policy,
        RouteConstraints(
            capability="generate_text",
            classification="public",
            offline_required=False,
            cost_budget=5.0,
            latency_budget_ms=5000,
            quality_tier="premium",
            context_tokens=128,
            role_contract="executor",
            remote_available=True,
            local_available=True,
        ),
    )
    assert choice.provider_id == "remote_http"
    assert choice.paid
    assert choice.provider_kind == "remote"


def test_restricted_classification_does_not_choose_remote() -> None:
    policy = load_model_policy()
    choice = evaluate_route(
        policy,
        RouteConstraints(
            capability="generate_text",
            classification="restricted",
            offline_required=False,
            cost_budget=5.0,
            latency_budget_ms=5000,
            quality_tier="premium",
            context_tokens=128,
            role_contract="executor",
            remote_available=True,
            local_available=True,
        ),
    )
    assert choice.provider_kind != "remote"
    assert choice.provider_id in {"local_stub", "finetune_script_adapter", "deterministic_double"}


def test_offline_required_never_selects_remote() -> None:
    policy = load_model_policy()
    choice = evaluate_route(
        policy,
        RouteConstraints(
            capability="generate_text",
            classification="public",
            offline_required=True,
            cost_budget=5.0,
            latency_budget_ms=5000,
            quality_tier="premium",
            context_tokens=128,
            role_contract="executor",
            remote_available=True,
            local_available=True,
        ),
    )
    assert choice.provider_kind != "remote"
    assert choice.offline


def test_low_cost_budget_selects_double() -> None:
    policy = load_model_policy()
    choice = evaluate_route(
        policy,
        RouteConstraints(
            capability="generate_text",
            classification="public",
            offline_required=False,
            cost_budget=0.0,
            latency_budget_ms=5000,
            quality_tier="standard",
            context_tokens=128,
            role_contract="executor",
            remote_available=True,
            local_available=True,
        ),
    )
    assert choice.provider_id == "deterministic_double"
    assert choice.estimated_cost == 0.0
