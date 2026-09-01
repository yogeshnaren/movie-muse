"""In-process local-model stub. Does not call the network."""

from __future__ import annotations

import os

from movie_muse.model_router.adapters.fixtures import canned_output
from movie_muse.model_router.errors import LocalRuntimeMissingError
from movie_muse.model_router.types import AdapterResult, ModelRequest, RoutingDecision

LOCAL_RUNTIME_ENV = "MOVIE_MUSE_LOCAL_MODEL_RUNTIME"


def local_runtime_configured(env_name: str = LOCAL_RUNTIME_ENV) -> bool:
    value = os.environ.get(env_name, "").strip()
    return bool(value)


class LocalModelAdapter:
    def __init__(self, runtime_env: str = LOCAL_RUNTIME_ENV) -> None:
        self.runtime_env = runtime_env

    def invoke(
        self,
        request: ModelRequest,
        decision: RoutingDecision,
        prompt_template: str,
    ) -> AdapterResult:
        del prompt_template
        if not local_runtime_configured(self.runtime_env):
            raise LocalRuntimeMissingError(
                f"local model runtime missing ({self.runtime_env} is unset)"
            )
        output = canned_output(request.capability, source="local_stub")
        return AdapterResult(
            output=output,
            model_version=decision.model_version,
            input_tokens=max(1, request.context_tokens // 2 or 1),
            output_tokens=24,
            actual_cost=0.01,
            method="local_in_process_stub",
            assumptions=("local_stub", "no_network"),
            uncertainty="stubbed_local_runtime",
        )
