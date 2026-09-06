"""Policy YAML/JSON contracts for capabilities, consent, and role tables."""

from __future__ import annotations

from movie_muse.model_router.api import load_model_policy


def test_consent_required_for_confidential_and_restricted() -> None:
    policy = load_model_policy()
    assert policy.consent_required_for["confidential"] is True
    assert policy.consent_required_for["restricted"] is True
    assert policy.consent_required_for["public"] is False


def test_actor_and_audience_cannot_calculate_in_policy() -> None:
    policy = load_model_policy()
    assert "calculate_production" in policy.role_contracts["actor"].may_not
    assert "calculate_production" in policy.role_contracts["audience"].may_not
    assert "calculate_production" in policy.role_contracts["production_analyst"].capabilities
    assert "propose_structured_ops" in policy.role_contracts["executor"].capabilities
    assert "retrieve" in policy.role_contracts["expert"].may
    assert "propose_alternatives" in policy.role_contracts["divergence"].may


def test_cache_policy_names_reuse_key_parts() -> None:
    policy = load_model_policy()
    assert policy.cache_enabled is True
    parts = policy.extra["cache"]["key_parts"]
    assert parts == [
        "capability",
        "input_hash",
        "policy_version",
        "prompt_version",
        "model",
    ]
