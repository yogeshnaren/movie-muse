"""Typed model-router requests, decisions, quotes, results, and provenance."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RoleContract(str, Enum):
    ACTOR = "actor"
    AUDIENCE = "audience"
    EXPERT = "expert"
    RESEARCHER = "researcher"
    DIVERGENCE = "divergence"
    EXECUTOR = "executor"
    PRODUCTION_ANALYST = "production_analyst"


class DataClassification(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class QualityTier(str, Enum):
    FAST = "fast"
    STANDARD = "standard"
    PREMIUM = "premium"


class ProviderKind(str, Enum):
    DOUBLE = "double"
    LOCAL = "local"
    REMOTE = "remote"
    FINE_TUNED = "fine_tuned"


CHAIN_OF_THOUGHT_KEYS = frozenset(
    {
        "chain_of_thought",
        "chain-of-thought",
        "chainOfThought",
        "private_cot",
        "thinking",
        "<thinking>",
    }
)


def contains_chain_of_thought(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, inner in value.items():
            if str(key) in CHAIN_OF_THOUGHT_KEYS:
                return True
            if contains_chain_of_thought(inner):
                return True
        return False
    if isinstance(value, list | tuple):
        return any(contains_chain_of_thought(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return "chain-of-thought" in lowered or "chain_of_thought" in lowered
    return False


@dataclass(frozen=True, slots=True)
class ModelRequest:
    capability: str
    data_classification: str
    latency_budget_ms: int
    cost_budget: float
    offline_required: bool
    context_tokens: int
    structured_output: bool | Mapping[str, Any]
    quality_tier: str
    role_contract: str
    project_id: str
    actor_id: str
    acl_epoch: int
    permission_snapshot_id: str
    input: Mapping[str, Any] | str = ""
    prompt_id: str | None = None
    prompt_version: str | None = None
    consent_granted: bool = False

    def input_mapping(self) -> dict[str, Any]:
        if isinstance(self.input, Mapping):
            return dict(self.input)
        return {"text": str(self.input)}

    def to_dict(self) -> dict[str, Any]:
        structured: bool | dict[str, Any]
        if isinstance(self.structured_output, Mapping):
            structured = dict(self.structured_output)
        else:
            structured = bool(self.structured_output)
        return {
            "capability": self.capability,
            "data_classification": self.data_classification,
            "latency_budget_ms": self.latency_budget_ms,
            "cost_budget": self.cost_budget,
            "offline_required": self.offline_required,
            "context_tokens": self.context_tokens,
            "structured_output": structured,
            "quality_tier": self.quality_tier,
            "role_contract": self.role_contract,
            "project_id": self.project_id,
            "actor_id": self.actor_id,
            "acl_epoch": self.acl_epoch,
            "permission_snapshot_id": self.permission_snapshot_id,
            "input": self.input_mapping(),
            "prompt_id": self.prompt_id,
            "prompt_version": self.prompt_version,
            "consent_granted": self.consent_granted,
        }


@dataclass(frozen=True, slots=True)
class ModelProvenance:
    provider: str
    model: str
    model_version: str
    prompt_id: str
    prompt_version: str
    policy_version: str
    timestamp: str
    method: str
    assumptions: tuple[str, ...] = ()
    uncertainty: str = "unspecified"
    adapter_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "provider": self.provider,
            "model": self.model,
            "model_version": self.model_version,
            "prompt_id": self.prompt_id,
            "prompt_version": self.prompt_version,
            "policy_version": self.policy_version,
            "timestamp": self.timestamp,
            "method": self.method,
            "assumptions": list(self.assumptions),
            "uncertainty": self.uncertainty,
            "adapter_id": self.adapter_id,
        }
        assert "chain_of_thought" not in payload
        return payload


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    id: str
    provider: str
    model: str
    reason: str
    policy_version: str
    capability: str
    classification: str
    offline: bool
    cost_quote_id: str
    prompt_id: str
    prompt_version: str
    provider_kind: str
    model_version: str
    timestamp: str
    paid: bool
    estimated_cost: float
    role_contract: str
    adapter_id: str | None = None
    fallback_from: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "provider": self.provider,
            "model": self.model,
            "reason": self.reason,
            "policy_version": self.policy_version,
            "capability": self.capability,
            "classification": self.classification,
            "offline": self.offline,
            "cost_quote_id": self.cost_quote_id,
            "prompt_id": self.prompt_id,
            "prompt_version": self.prompt_version,
            "provider_kind": self.provider_kind,
            "model_version": self.model_version,
            "timestamp": self.timestamp,
            "paid": self.paid,
            "estimated_cost": self.estimated_cost,
            "role_contract": self.role_contract,
            "adapter_id": self.adapter_id,
            "fallback_from": self.fallback_from,
        }
        assert "chain_of_thought" not in payload
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RoutingDecision:
        return cls(
            id=str(data["id"]),
            provider=str(data["provider"]),
            model=str(data["model"]),
            reason=str(data["reason"]),
            policy_version=str(data["policy_version"]),
            capability=str(data["capability"]),
            classification=str(data["classification"]),
            offline=bool(data["offline"]),
            cost_quote_id=str(data["cost_quote_id"]),
            prompt_id=str(data["prompt_id"]),
            prompt_version=str(data["prompt_version"]),
            provider_kind=str(data["provider_kind"]),
            model_version=str(data["model_version"]),
            timestamp=str(data["timestamp"]),
            paid=bool(data["paid"]),
            estimated_cost=float(data["estimated_cost"]),
            role_contract=str(data["role_contract"]),
            adapter_id=str(data["adapter_id"]) if data.get("adapter_id") else None,
            fallback_from=str(data["fallback_from"]) if data.get("fallback_from") else None,
        )


@dataclass(frozen=True, slots=True)
class CostQuote:
    id: str
    estimated_cost: float
    estimated_credits: float
    currency: str
    provider: str
    model: str
    paid: bool
    capability: str
    policy_version: str
    request_digest: str
    decision_id: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "estimated_cost": self.estimated_cost,
            "estimated_credits": self.estimated_credits,
            "currency": self.currency,
            "provider": self.provider,
            "model": self.model,
            "paid": self.paid,
            "capability": self.capability,
            "policy_version": self.policy_version,
            "request_digest": self.request_digest,
            "decision_id": self.decision_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CostQuote:
        return cls(
            id=str(data["id"]),
            estimated_cost=float(data["estimated_cost"]),
            estimated_credits=float(data["estimated_credits"]),
            currency=str(data["currency"]),
            provider=str(data["provider"]),
            model=str(data["model"]),
            paid=bool(data["paid"]),
            capability=str(data["capability"]),
            policy_version=str(data["policy_version"]),
            request_digest=str(data["request_digest"]),
            decision_id=str(data["decision_id"]),
            created_at=str(data["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class UsageRecord:
    id: str
    quote_id: str
    estimated_cost: float
    actual_cost: float
    input_tokens: int
    output_tokens: int
    cache_hit: bool
    provider: str
    model: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "quote_id": self.quote_id,
            "estimated_cost": self.estimated_cost,
            "actual_cost": self.actual_cost,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_hit": self.cache_hit,
            "provider": self.provider,
            "model": self.model,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> UsageRecord:
        return cls(
            id=str(data["id"]),
            quote_id=str(data["quote_id"]),
            estimated_cost=float(data["estimated_cost"]),
            actual_cost=float(data["actual_cost"]),
            input_tokens=int(data["input_tokens"]),
            output_tokens=int(data["output_tokens"]),
            cache_hit=bool(data["cache_hit"]),
            provider=str(data["provider"]),
            model=str(data["model"]),
            created_at=str(data["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class PromptVersion:
    prompt_id: str
    version: str
    template: str
    created_at: str
    digest: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_id": self.prompt_id,
            "version": self.version,
            "template": self.template,
            "created_at": self.created_at,
            "digest": self.digest,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PromptVersion:
        return cls(
            prompt_id=str(data["prompt_id"]),
            version=str(data["version"]),
            template=str(data["template"]),
            created_at=str(data["created_at"]),
            digest=str(data["digest"]),
        )


@dataclass(frozen=True, slots=True)
class AdapterResult:
    output: dict[str, Any]
    model_version: str
    input_tokens: int = 0
    output_tokens: int = 0
    actual_cost: float = 0.0
    method: str = "adapter"
    assumptions: tuple[str, ...] = ()
    uncertainty: str = "deterministic"


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    output: dict[str, Any]
    usage: UsageRecord
    provenance: ModelProvenance
    cache_hit: bool
    quote_id: str
    decision: RoutingDecision

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "output": self.output,
            "usage": self.usage.to_dict(),
            "provenance": self.provenance.to_dict(),
            "cache_hit": self.cache_hit,
            "quote_id": self.quote_id,
            "decision": self.decision.to_dict(),
        }
        assert "chain_of_thought" not in payload
        return payload


@dataclass(frozen=True, slots=True)
class RouteConstraints:
    capability: str
    classification: str
    offline_required: bool
    cost_budget: float
    latency_budget_ms: int
    quality_tier: str
    context_tokens: int
    role_contract: str
    remote_available: bool
    local_available: bool


@dataclass(frozen=True, slots=True)
class RouteChoice:
    provider_id: str
    provider_kind: str
    model: str
    model_version: str
    reason: str
    paid: bool
    offline: bool
    estimated_cost: float
    estimated_latency_ms: int
    adapter_id: str | None = None
    fallback_from: str | None = None
    base_provider: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    id: str
    kind: str
    model: str
    model_version: str
    paid: bool
    offline: bool
    max_classification: str
    estimated_cost: float
    latency_ms: int
    quality_tiers: tuple[str, ...]
    max_context_tokens: int
    adapter_id: str | None = None
    base_provider: str | None = None


@dataclass(frozen=True, slots=True)
class CapabilitySpec:
    id: str
    enabled: bool
    allowed_roles: tuple[str, ...]
    providers: tuple[str, ...]
    fallbacks: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RoleContractSpec:
    id: str
    may: tuple[str, ...]
    may_not: tuple[str, ...]
    capabilities: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ModelPolicy:
    version: str
    capabilities: dict[str, CapabilitySpec]
    providers: dict[str, ProviderSpec]
    role_contracts: dict[str, RoleContractSpec]
    classification_ranks: dict[str, int]
    consent_required_for: dict[str, bool]
    quality_tier_preferences: dict[str, tuple[str, ...]]
    cache_enabled: bool
    currency: str
    default_prompt_id: str
    default_prompt_version: str
    remote_base_url_env: str
    remote_api_key_env: str
    local_runtime_env: str
    extra: dict[str, Any] = field(default_factory=dict)
