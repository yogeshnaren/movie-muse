"""Public surface of ``movie_muse.model_router``.

Other modules must import this surface rather than model_router internals.
Provider HTTP lives behind adapters in this package; extraction packages must
not import provider SDKs.

Environment:
- ``MOVIE_MUSE_REMOTE_MODEL_BASE_URL`` — required for live remote invoke
- ``MOVIE_MUSE_REMOTE_MODEL_API_KEY`` — optional bearer token (never logged)
- ``MOVIE_MUSE_LOCAL_MODEL_RUNTIME`` — required for local adapter invoke

EXT-REMOTE-MODEL stays NOT_RUN until a real configured provider is available.
Unset remote env fails closed with ProviderUnavailableError (not skipped).
"""

from __future__ import annotations

from movie_muse.model_router.adapters.local import LOCAL_RUNTIME_ENV, local_runtime_configured
from movie_muse.model_router.adapters.remote import (
    REMOTE_API_KEY_ENV,
    REMOTE_BASE_URL_ENV,
    HttpClient,
    RemoteProviderAdapter,
    UrllibHttpClient,
    remote_base_url,
)
from movie_muse.model_router.errors import (
    AdapterNotFoundError,
    AiOffError,
    BudgetExceededError,
    CapabilityDisabledError,
    ClassificationDeniedError,
    ConsentRequiredError,
    LocalRuntimeMissingError,
    ModelRouterError,
    OfflineRouteDeniedError,
    PromptImmutableError,
    PromptNotFoundError,
    ProviderUnavailableError,
    QuoteNotFoundError,
    RoleContractDeniedError,
    RouteNotFoundError,
    StaleAuthorizationError,
    StructuredOutputError,
)
from movie_muse.model_router.policy import (
    default_policy_dir,
    evaluate_route,
    load_model_policy,
)
from movie_muse.model_router.service import ModelRouter, env_local_configured, env_remote_configured
from movie_muse.model_router.storage import INDEX_META_KEY
from movie_muse.model_router.types import (
    AdapterResult,
    CostQuote,
    DataClassification,
    ExecutionResult,
    ModelPolicy,
    ModelProvenance,
    ModelRequest,
    PromptVersion,
    ProviderKind,
    QualityTier,
    RoleContract,
    RouteChoice,
    RouteConstraints,
    RoutingDecision,
    UsageRecord,
)

__all__ = [
    "INDEX_META_KEY",
    "LOCAL_RUNTIME_ENV",
    "REMOTE_API_KEY_ENV",
    "REMOTE_BASE_URL_ENV",
    "AdapterNotFoundError",
    "AdapterResult",
    "AiOffError",
    "BudgetExceededError",
    "CapabilityDisabledError",
    "ClassificationDeniedError",
    "ConsentRequiredError",
    "CostQuote",
    "DataClassification",
    "ExecutionResult",
    "HttpClient",
    "LocalRuntimeMissingError",
    "ModelPolicy",
    "ModelProvenance",
    "ModelRequest",
    "ModelRouter",
    "ModelRouterError",
    "OfflineRouteDeniedError",
    "PromptImmutableError",
    "PromptNotFoundError",
    "PromptVersion",
    "ProviderKind",
    "ProviderUnavailableError",
    "QualityTier",
    "QuoteNotFoundError",
    "RemoteProviderAdapter",
    "RoleContract",
    "RoleContractDeniedError",
    "RouteChoice",
    "RouteConstraints",
    "RouteNotFoundError",
    "RoutingDecision",
    "StaleAuthorizationError",
    "StructuredOutputError",
    "UrllibHttpClient",
    "UsageRecord",
    "default_policy_dir",
    "env_local_configured",
    "env_remote_configured",
    "evaluate_route",
    "load_model_policy",
    "local_runtime_configured",
    "remote_base_url",
]
