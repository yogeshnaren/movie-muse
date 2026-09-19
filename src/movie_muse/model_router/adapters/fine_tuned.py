"""Fine-tuned adapter: registered adapter id plus a base route."""

from __future__ import annotations

from movie_muse.model_router.adapters.fixtures import canned_output
from movie_muse.model_router.errors import AdapterNotFoundError
from movie_muse.model_router.types import AdapterResult, ModelRequest, RoutingDecision


class FineTunedAdapter:
    def invoke(
        self,
        request: ModelRequest,
        decision: RoutingDecision,
        prompt_template: str,
    ) -> AdapterResult:
        if not decision.adapter_id:
            raise AdapterNotFoundError("fine-tuned route missing adapter_id")
        del prompt_template
        output = canned_output(request.capability, source=f"fine_tuned:{decision.adapter_id}")
        return AdapterResult(
            output=output,
            model_version=decision.model_version,
            input_tokens=max(1, request.context_tokens // 3 or 1),
            output_tokens=20,
            actual_cost=decision.estimated_cost,
            method=f"fine_tuned:{decision.adapter_id}",
            assumptions=("fine_tuned_adapter_route", "not_a_separate_architecture"),
            uncertainty="adapter_stub",
        )
