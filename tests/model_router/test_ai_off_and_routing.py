"""Auditable routing, project/capability AI-off, and non-AI authoring."""

from __future__ import annotations

import pytest

from movie_muse.model_router.api import AiOffError, CapabilityDisabledError, ConsentRequiredError, ModelRequest, ModelRouter
from movie_muse.schemas.api import ChangeSet, ChangeSetOperation, OperationType, new_id


def _update_heading(stack, text: str):
    heading = stack.document.blocks[0]
    change = ChangeSet(
        id=new_id("change_set"),
        base_revision_id=stack.revisions.canon_head_id(),
        author_actor_id=stack.owner.id,
        created_at="2026-09-01T00:00:00Z",
        operations=(
            ChangeSetOperation(
                id="op-0",
                order=0,
                op_type=OperationType.UPDATE_BLOCK,
                target_id=heading.id,
                payload={"text": text},
            ),
        ),
    )
    return stack.revisions.apply_change_set(change, actor_id=stack.owner.id)


def _request(stack, **overrides) -> ModelRequest:
    values = {
        "capability": "generate_text",
        "data_classification": "public",
        "latency_budget_ms": 5000,
        "cost_budget": 5.0,
        "offline_required": False,
        "context_tokens": 128,
        "structured_output": True,
        "quality_tier": "fast",
        "role_contract": "executor",
        "project_id": stack.project.id,
        "actor_id": stack.owner.id,
        "acl_epoch": stack.epoch,
        "permission_snapshot_id": stack.snapshot,
        "input": {"text": "Write a scene heading."},
        "consent_granted": True,
    }
    values.update(overrides)
    return ModelRequest(**values)


def test_route_records_auditable_decision(router_stack, request_factory) -> None:
    decision = router_stack.router.route(request_factory())
    payload = decision.to_dict()
    for key in (
        "provider",
        "model",
        "reason",
        "policy_version",
        "capability",
        "classification",
        "offline",
        "cost_quote_id",
    ):
        assert key in payload
        assert payload[key] is not None
    assert "chain_of_thought" not in payload
    assert decision.provider == "deterministic_double"
    assert decision.policy_version == "1.0.0"
    quote = router_stack.router.get_quote(decision.cost_quote_id)
    assert quote.provider == decision.provider


def test_project_ai_off_denies_generation_but_revision_service_saves(ai_off_stack) -> None:
    assert ai_off_stack.project.ai_off
    with pytest.raises(AiOffError):
        ai_off_stack.router.route(_request(ai_off_stack))
    ack = _update_heading(ai_off_stack, "INT. ROUTER LAB - NIGHT")
    assert ack.revision_id
    loaded = ai_off_stack.revisions.load_revision(ack.revision_id)
    assert loaded.blocks[0].text == "INT. ROUTER LAB - NIGHT"


def test_confidential_without_consent_fails_closed(router_stack, request_factory) -> None:
    with pytest.raises(ConsentRequiredError):
        router_stack.router.route(
            request_factory(
                data_classification="confidential",
                consent_granted=False,
                quality_tier="fast",
            )
        )


def test_capability_disabled_denies_generation(router_stack, request_factory) -> None:
    request = request_factory(
        capability="disabled_capability",
        role_contract="expert",
        quality_tier="fast",
    )
    with pytest.raises(CapabilityDisabledError):
        router_stack.router.route(request)


def test_ai_off_does_not_require_model_router_for_revisions(router_stack) -> None:
    ack = _update_heading(router_stack, "INT. ROUTER LAB - CONTINUOUS")
    assert ack.revision_id != router_stack.document.base_revision_id
    assert isinstance(router_stack.router, ModelRouter)
