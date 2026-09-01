"""Fail-closed errors for model routing."""

from __future__ import annotations


class ModelRouterError(Exception):
    """Base class for honest model-router failures."""


class AiOffError(ModelRouterError):
    """Project-level or capability-level AI is disabled."""


class CapabilityDisabledError(AiOffError):
    """The requested capability is disabled in policy."""


class RoleContractDeniedError(ModelRouterError):
    """Capability is not permitted for the declared AI role contract."""


class ClassificationDeniedError(ModelRouterError):
    """No allowed provider may handle the request classification."""


class ConsentRequiredError(ModelRouterError):
    """The data classification requires consent that was not granted."""


class OfflineRouteDeniedError(ModelRouterError):
    """Offline/airplane mode forbids the only remaining providers."""


class BudgetExceededError(ModelRouterError):
    """No provider fits the request cost or latency budget."""


class ProviderUnavailableError(ModelRouterError):
    """A selected provider is unset, missing, or unreachable."""


class LocalRuntimeMissingError(ProviderUnavailableError):
    """Local-model runtime is not configured."""


class StructuredOutputError(ModelRouterError):
    """Adapter output failed JSON Schema validation or contained chain-of-thought."""


class PromptImmutableError(ModelRouterError):
    """An existing prompt id+version cannot be rewritten."""


class PromptNotFoundError(ModelRouterError):
    """The requested prompt version is not in the registry."""


class QuoteNotFoundError(ModelRouterError):
    """execute() was given an unknown or mismatched cost quote."""


class RouteNotFoundError(ModelRouterError):
    """Policy produced no legal route for the request."""


class AdapterNotFoundError(ModelRouterError):
    """A fine-tuned or named adapter is not registered."""


class StaleAuthorizationError(ModelRouterError):
    """ACL epoch or permission snapshot on the request is stale."""
