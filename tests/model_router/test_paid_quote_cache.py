"""Paid authorization, preflight quotes, usage, and cache."""

from __future__ import annotations

import pytest

from movie_muse.authorization.api import AuthorizationError
from movie_muse.identity.api import Role


def test_paid_execute_requires_run_paid_provider_viewer_denied(
    router_stack, request_factory, member_factory, monkeypatch
) -> None:
    monkeypatch.setenv("MOVIE_MUSE_REMOTE_MODEL_BASE_URL", "https://example.invalid/v1")
    viewer = member_factory(Role.VIEWER)
    paid = request_factory(
        quality_tier="premium",
        cost_budget=5.0,
        actor_id=viewer.actor_id,
        acl_epoch=router_stack.epoch,
        permission_snapshot_id=router_stack.snapshot,
    )
    quote = router_stack.router.quote(paid)
    assert quote.paid
    assert quote.estimated_cost > 0
    with pytest.raises(AuthorizationError):
        router_stack.router.execute(paid, quote_id=quote.id)


def test_owner_quoted_then_authorized_paid_execute(
    router_stack, request_factory, monkeypatch
) -> None:
    monkeypatch.setenv("MOVIE_MUSE_REMOTE_MODEL_BASE_URL", "https://example.invalid/v1")
    paid = request_factory(quality_tier="premium", cost_budget=5.0)
    quote = router_stack.router.quote(paid)
    assert quote.paid
    result = router_stack.router.execute(paid, quote_id=quote.id)
    assert result.quote_id == quote.id
    assert result.usage.estimated_cost == quote.estimated_cost
    assert result.usage.actual_cost == 1.25
    assert result.cache_hit is False
    assert "chain_of_thought" not in result.to_dict()
    assert result.provenance.provider == "remote_http"
    assert result.provenance.policy_version == "1.0.0"
    assert router_stack.http.calls


def test_preflight_quote_then_actual_usage_recorded(router_stack, request_factory) -> None:
    request = request_factory()
    quote = router_stack.router.quote(request)
    assert quote.estimated_cost == 0.0
    assert quote.paid is False
    result = router_stack.router.execute(request, quote_id=quote.id)
    usage = router_stack.router.list_usage()
    assert usage[-1].quote_id == quote.id
    assert usage[-1].actual_cost == result.usage.actual_cost
    assert usage[-1].estimated_cost == quote.estimated_cost


def test_cache_hit_on_identical_accepted_request(router_stack, request_factory) -> None:
    request = request_factory(input={"text": "identical cache probe"})
    first_quote = router_stack.router.quote(request)
    first = router_stack.router.execute(request, quote_id=first_quote.id)
    assert first.cache_hit is False
    second_quote = router_stack.router.quote(request)
    second = router_stack.router.execute(request, quote_id=second_quote.id)
    assert second.cache_hit is True
    assert second.output == first.output
    assert second.usage.actual_cost == 0.0
    assert second.provenance.model_version == first.provenance.model_version
