"""Provider adapter protocol. Adapters live only in this package."""

from __future__ import annotations

from typing import Protocol

from movie_muse.model_router.types import AdapterResult, ModelRequest, RoutingDecision


class ProviderAdapter(Protocol):
    def invoke(
        self,
        request: ModelRequest,
        decision: RoutingDecision,
        prompt_template: str,
    ) -> AdapterResult: ...
