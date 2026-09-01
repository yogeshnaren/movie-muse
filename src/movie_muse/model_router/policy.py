"""Load and evaluate YAML/JSON model-routing policy."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from movie_muse.model_router.errors import (
    BudgetExceededError,
    CapabilityDisabledError,
    ClassificationDeniedError,
    OfflineRouteDeniedError,
    ProviderUnavailableError,
    RoleContractDeniedError,
    RouteNotFoundError,
)
from movie_muse.model_router.types import (
    CapabilitySpec,
    ModelPolicy,
    ProviderSpec,
    RoleContractSpec,
    RouteChoice,
    RouteConstraints,
)
from movie_muse.toolchain.paths import repo_root

POLICY_FILES = (
    "policy.yaml",
    "capabilities.yaml",
    "providers.yaml",
    "consent.yaml",
    "classification.yaml",
    "budgets.yaml",
    "cache.yaml",
    "role_contracts.yaml",
)


def default_policy_dir(start: Path | None = None) -> Path:
    return repo_root(start) / "policy" / "models"


def _load_mapping(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".json":
        import json

        loaded = json.loads(path.read_text(encoding="utf-8"))
    else:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must contain a mapping")
    return loaded


def load_model_policy(directory: Path | None = None) -> ModelPolicy:
    root = directory or default_policy_dir()
    merged: dict[str, Any] = {}
    for name in POLICY_FILES:
        path = root / name
        if not path.is_file():
            raise FileNotFoundError(f"missing model policy file: {path}")
        merged.update(_load_mapping(path))
    return parse_model_policy(merged)


def parse_model_policy(raw: dict[str, Any]) -> ModelPolicy:
    capabilities_raw = raw.get("capabilities") or {}
    providers_raw = raw.get("providers") or {}
    roles_raw = raw.get("role_contracts") or {}
    classification = raw.get("classification") or {}
    consent = raw.get("consent") or {}
    budgets = raw.get("budgets") or {}
    cache = raw.get("cache") or {}
    preferences = raw.get("quality_tier_preferences") or {}
    capabilities = {
        str(key): CapabilitySpec(
            id=str(key),
            enabled=bool(spec.get("enabled", False)),
            allowed_roles=tuple(str(item) for item in (spec.get("allowed_roles") or ())),
            providers=tuple(str(item) for item in (spec.get("providers") or ())),
            fallbacks=tuple(str(item) for item in (spec.get("fallbacks") or ())),
        )
        for key, spec in capabilities_raw.items()
        if isinstance(spec, dict)
    }
    providers = {
        str(key): ProviderSpec(
            id=str(key),
            kind=str(spec["kind"]),
            model=str(spec["model"]),
            model_version=str(spec["model_version"]),
            paid=bool(spec.get("paid", False)),
            offline=bool(spec.get("offline", False)),
            max_classification=str(spec["max_classification"]),
            estimated_cost=float(spec.get("estimated_cost", 0.0)),
            latency_ms=int(spec.get("latency_ms", 0)),
            quality_tiers=tuple(str(item) for item in (spec.get("quality_tiers") or ())),
            max_context_tokens=int(spec.get("max_context_tokens", 0)),
            adapter_id=str(spec["adapter_id"]) if spec.get("adapter_id") else None,
            base_provider=str(spec["base_provider"]) if spec.get("base_provider") else None,
        )
        for key, spec in providers_raw.items()
        if isinstance(spec, dict)
    }
    roles = {
        str(key): RoleContractSpec(
            id=str(key),
            may=tuple(str(item) for item in (spec.get("may") or ())),
            may_not=tuple(str(item) for item in (spec.get("may_not") or ())),
            capabilities=tuple(str(item) for item in (spec.get("capabilities") or ())),
        )
        for key, spec in roles_raw.items()
        if isinstance(spec, dict)
    }
    ranks_raw = classification.get("ranks") or {}
    consent_for = consent.get("required_for") or {}
    return ModelPolicy(
        version=str(raw.get("version", "0")),
        capabilities=capabilities,
        providers=providers,
        role_contracts=roles,
        classification_ranks={str(key): int(value) for key, value in ranks_raw.items()},
        consent_required_for={str(key): bool(value) for key, value in consent_for.items()},
        quality_tier_preferences={
            str(tier): tuple(str(item) for item in names)
            for tier, names in preferences.items()
            if isinstance(names, list)
        },
        cache_enabled=bool(cache.get("enabled", True)),
        currency=str(budgets.get("currency", "credits")),
        default_prompt_id=str(raw.get("default_prompt_id", "builtin.default")),
        default_prompt_version=str(raw.get("default_prompt_version", "1.0.0")),
        remote_base_url_env=str(raw.get("remote_base_url_env", "MOVIE_MUSE_REMOTE_MODEL_BASE_URL")),
        remote_api_key_env=str(raw.get("remote_api_key_env", "MOVIE_MUSE_REMOTE_MODEL_API_KEY")),
        local_runtime_env=str(raw.get("local_runtime_env", "MOVIE_MUSE_LOCAL_MODEL_RUNTIME")),
        extra={"budgets": budgets, "cache": cache, "consent": consent},
    )


def classification_rank(policy: ModelPolicy, name: str) -> int:
    if name not in policy.classification_ranks:
        raise ClassificationDeniedError(f"unknown data classification: {name}")
    return policy.classification_ranks[name]


def consent_required(policy: ModelPolicy, classification: str) -> bool:
    return bool(policy.consent_required_for.get(classification, True))


def _provider_available(policy: ModelPolicy, spec: ProviderSpec, constraints: RouteConstraints) -> bool:
    if spec.kind == "remote":
        return constraints.remote_available
    if spec.kind == "local":
        return constraints.local_available
    if spec.kind == "fine_tuned":
        base_id = spec.base_provider
        if not base_id or base_id not in policy.providers:
            return False
        return _provider_available(policy, policy.providers[base_id], constraints)
    return True


def provider_rejection_reason(
    policy: ModelPolicy, spec: ProviderSpec, constraints: RouteConstraints
) -> str | None:
    request_rank = classification_rank(policy, constraints.classification)
    provider_rank = classification_rank(policy, spec.max_classification)
    if request_rank > provider_rank:
        return "classification"
    if constraints.offline_required and not spec.offline:
        return "offline"
    if spec.estimated_cost > constraints.cost_budget:
        return "cost_budget"
    if spec.latency_ms > constraints.latency_budget_ms:
        return "latency_budget"
    if constraints.context_tokens > spec.max_context_tokens:
        return "context"
    if constraints.quality_tier not in spec.quality_tiers:
        return "quality_tier"
    if not _provider_available(policy, spec, constraints):
        return "unavailable"
    return None


def _ordered_candidates(policy: ModelPolicy, capability: CapabilitySpec, quality_tier: str) -> list[str]:
    preferred = list(policy.quality_tier_preferences.get(quality_tier, ()))
    allow = set(capability.providers)
    ordered = [name for name in preferred if name in allow]
    for name in capability.providers:
        if name not in ordered:
            ordered.append(name)
    return ordered


def evaluate_route(policy: ModelPolicy, constraints: RouteConstraints) -> RouteChoice:
    capability = policy.capabilities.get(constraints.capability)
    if capability is None:
        raise RouteNotFoundError(f"unknown capability: {constraints.capability}")
    if not capability.enabled:
        raise CapabilityDisabledError(
            f"capability {constraints.capability} is disabled by policy"
        )
    role = policy.role_contracts.get(constraints.role_contract)
    if role is None:
        raise RoleContractDeniedError(f"unknown role contract: {constraints.role_contract}")
    if constraints.capability not in role.capabilities:
        raise RoleContractDeniedError(
            f"role {constraints.role_contract} may not invoke {constraints.capability}"
        )
    if constraints.role_contract not in capability.allowed_roles:
        raise RoleContractDeniedError(
            f"capability {constraints.capability} does not allow role {constraints.role_contract}"
        )
    if constraints.capability in role.may_not:
        raise RoleContractDeniedError(
            f"role {constraints.role_contract} is forbidden from {constraints.capability}"
        )
    classification_rank(policy, constraints.classification)

    ordered = _ordered_candidates(policy, capability, constraints.quality_tier)
    rejections: dict[str, str] = {}
    for provider_id in ordered:
        spec = policy.providers.get(provider_id)
        if spec is None:
            rejections[provider_id] = "unknown_provider"
            continue
        reason = provider_rejection_reason(policy, spec, constraints)
        if reason is None:
            return _choice(spec, reason=f"preferred:{provider_id}", fallback_from=None)
        rejections[provider_id] = reason

    for provider_id in capability.fallbacks:
        spec = policy.providers.get(provider_id)
        if spec is None:
            rejections[provider_id] = "unknown_provider"
            continue
        reason = provider_rejection_reason(policy, spec, constraints)
        if reason is None:
            preferred = next(iter(rejections), None)
            why = rejections.get(preferred or "", "unavailable")
            return _choice(
                spec,
                reason=f"fallback:{provider_id}; preferred unavailable ({why})",
                fallback_from=preferred,
            )
        rejections[provider_id] = reason

    _raise_from_rejections(rejections, constraints)
    raise RouteNotFoundError("no legal model route")


def _choice(spec: ProviderSpec, *, reason: str, fallback_from: str | None) -> RouteChoice:
    return RouteChoice(
        provider_id=spec.id,
        provider_kind=spec.kind,
        model=spec.model,
        model_version=spec.model_version,
        reason=reason,
        paid=spec.paid or spec.kind == "remote",
        offline=spec.offline,
        estimated_cost=spec.estimated_cost,
        estimated_latency_ms=spec.latency_ms,
        adapter_id=spec.adapter_id,
        fallback_from=fallback_from,
        base_provider=spec.base_provider,
    )


def _raise_from_rejections(rejections: dict[str, str], constraints: RouteConstraints) -> None:
    reasons = set(rejections.values())
    if reasons == {"unavailable"} or reasons <= {"unavailable", "unknown_provider"}:
        raise ProviderUnavailableError(
            f"providers unavailable for {constraints.capability}: {sorted(rejections)}"
        )
    if "classification" in reasons and reasons <= {"classification", "unavailable", "unknown_provider"}:
        raise ClassificationDeniedError(
            f"no provider may handle classification {constraints.classification}"
        )
    if constraints.offline_required and "offline" in reasons:
        if not (reasons - {"offline", "unavailable", "quality_tier", "unknown_provider"}):
            raise OfflineRouteDeniedError(
                "offline/airplane mode denies remote providers and no local route remains"
            )
    if "cost_budget" in reasons or "latency_budget" in reasons:
        if not (reasons - {"cost_budget", "latency_budget", "unavailable", "quality_tier"}):
            raise BudgetExceededError(
                f"no provider fits cost/latency budget for {constraints.capability}"
            )
    raise RouteNotFoundError(
        f"no legal route for {constraints.capability} ({rejections})"
    )
