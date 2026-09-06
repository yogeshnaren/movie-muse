"""Role contracts, structured output, fallback, prompts, and fine-tuned routes."""

from __future__ import annotations

import pytest

from movie_muse.model_router.api import (
    PromptImmutableError,
    RoleContractDeniedError,
    StructuredOutputError,
)


def test_role_contract_mismatch_denied(router_stack, request_factory) -> None:
    with pytest.raises(RoleContractDeniedError):
        router_stack.router.route(
            request_factory(
                capability="calculate_production",
                role_contract="actor",
                quality_tier="fast",
            )
        )
    with pytest.raises(RoleContractDeniedError):
        router_stack.router.route(
            request_factory(
                capability="calculate_production",
                role_contract="audience",
                quality_tier="fast",
            )
        )
    decision = router_stack.router.route(
        request_factory(
            capability="calculate_production",
            role_contract="production_analyst",
            quality_tier="fast",
        )
    )
    assert decision.role_contract == "production_analyst"


def test_structured_output_invalid_fails_closed(router_stack, request_factory) -> None:
    schema = {
        "type": "object",
        "required": ["this_field_is_never_produced"],
        "additionalProperties": True,
        "properties": {"this_field_is_never_produced": {"type": "string"}},
    }
    request = request_factory(structured_output=schema)
    quote = router_stack.router.quote(request)
    with pytest.raises(StructuredOutputError):
        router_stack.router.execute(request, quote_id=quote.id)


def test_fallback_to_allowed_provider_only(router_stack, request_factory, monkeypatch) -> None:
    monkeypatch.delenv("MOVIE_MUSE_REMOTE_MODEL_BASE_URL", raising=False)
    decision = router_stack.router.route(
        request_factory(
            capability="remote_preferred",
            role_contract="expert",
            quality_tier="standard",
            cost_budget=5.0,
        )
    )
    assert decision.provider == "deterministic_double"
    assert decision.fallback_from == "remote_http"
    assert "fallback" in decision.reason


def test_prompt_registry_is_immutable(router_stack, request_factory) -> None:
    first = router_stack.router.register_prompt("scene.intro", "1.0.0", "Hello {{input}}")
    again = router_stack.router.register_prompt("scene.intro", "1.0.0", "Hello {{input}}")
    assert first.digest == again.digest
    with pytest.raises(PromptImmutableError):
        router_stack.router.register_prompt("scene.intro", "1.0.0", "Different template")
    request = request_factory(prompt_id="scene.intro", prompt_version="1.0.0")
    decision = router_stack.router.route(request)
    assert decision.prompt_id == "scene.intro"
    assert decision.prompt_version == "1.0.0"


def test_fine_tuned_adapter_is_a_route(router_stack, request_factory) -> None:
    registered = router_stack.router.register_fine_tuned_adapter(
        "script_suggestions_v1",
        base_provider="deterministic_double",
        model="ft-script-v1",
        model_version="ft-1.0.0",
    )
    assert registered["kind"] == "fine_tuned"
    decision = router_stack.router.route(
        request_factory(
            capability="script_suggest",
            role_contract="executor",
            quality_tier="standard",
        )
    )
    assert decision.provider_kind == "fine_tuned"
    assert decision.adapter_id == "script_suggestions_v1"
    quote = router_stack.router.quote(
        request_factory(
            capability="script_suggest",
            role_contract="executor",
            quality_tier="standard",
        )
    )
    result = router_stack.router.execute(
        request_factory(
            capability="script_suggest",
            role_contract="executor",
            quality_tier="standard",
        ),
        quote_id=quote.id,
    )
    assert result.provenance.adapter_id == "script_suggestions_v1"
    assert "fine_tuned" in result.provenance.method
