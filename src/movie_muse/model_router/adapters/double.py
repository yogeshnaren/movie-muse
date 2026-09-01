"""Deterministic fixture adapter. Never opens a network connection."""

from __future__ import annotations

from movie_muse.model_router.adapters.fixtures import canned_output
from movie_muse.model_router.types import AdapterResult, ModelRequest, RoutingDecision


class DeterministicDoubleAdapter:
    def invoke(
        self,
        request: ModelRequest,
        decision: RoutingDecision,
        prompt_template: str,
    ) -> AdapterResult:
        del prompt_template
        output = canned_output(request.capability, source="deterministic_fixture")
        return AdapterResult(
            output=output,
            model_version=decision.model_version,
            input_tokens=max(1, request.context_tokens // 4 or 1),
            output_tokens=16,
            actual_cost=0.0,
            method="deterministic_fixture",
            assumptions=("fixture", "no_network"),
            uncertainty="none",
        )
