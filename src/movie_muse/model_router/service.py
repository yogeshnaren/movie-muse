"""Capability-based ModelRouter. Policy-tested, auditable, fail-closed."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import (
    Action,
    AuthContext,
    AuthorizationError,
    AuthorizationService,
    ResourceKind,
)
from movie_muse.identity.api import IdentityService
from movie_muse.model_router.adapters.double import DeterministicDoubleAdapter
from movie_muse.model_router.adapters.fine_tuned import FineTunedAdapter
from movie_muse.model_router.adapters.fixtures import DEFAULT_OUTPUT_SCHEMAS
from movie_muse.model_router.adapters.local import LocalModelAdapter, local_runtime_configured
from movie_muse.model_router.adapters.remote import (
    HttpClient,
    RemoteProviderAdapter,
    remote_base_url,
)
from movie_muse.model_router.errors import (
    AiOffError,
    ConsentRequiredError,
    PromptImmutableError,
    PromptNotFoundError,
    ProviderUnavailableError,
    QuoteNotFoundError,
    StaleAuthorizationError,
    StructuredOutputError,
)
from movie_muse.model_router.policy import (
    consent_required,
    evaluate_route,
    load_model_policy,
    provider_rejection_reason,
)
from movie_muse.model_router.storage import (
    INDEX_META_KEY,
    load_index,
    load_json_blob,
    mutate_index,
    put_json_blob,
)
from movie_muse.model_router.types import (
    AdapterResult,
    CostQuote,
    ExecutionResult,
    ModelPolicy,
    ModelProvenance,
    ModelRequest,
    PromptVersion,
    RouteConstraints,
    RoutingDecision,
    UsageRecord,
    contains_chain_of_thought,
)
from movie_muse.persistence.api import LocalWorkspace, digest_payload, utc_now
from movie_muse.schemas.api import Project, new_ulid

BUILTIN_PROMPT_TEMPLATE = (
    "Capability={{capability}}\n"
    "Return structured JSON with method, assumptions, and uncertainty. "
    "Do not include chain-of-thought."
)


class ModelRouter:
    """Routes, quotes, and executes model operations through policy and adapters."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        identity: IdentityService,
        audit: AuditLog | None = None,
        *,
        policy_dir: Path | None = None,
        http_client: HttpClient | None = None,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.identity = identity
        self.audit = audit or AuditLog(workspace)
        self.policy: ModelPolicy = load_model_policy(policy_dir)
        self.remote = RemoteProviderAdapter(
            base_url_env=self.policy.remote_base_url_env,
            api_key_env=self.policy.remote_api_key_env,
            http_client=http_client,
        )
        self.local = LocalModelAdapter(runtime_env=self.policy.local_runtime_env)
        self.double = DeterministicDoubleAdapter()
        self.fine_tuned = FineTunedAdapter()
        self._ensure_builtin_prompt()

    def route(self, request: ModelRequest) -> RoutingDecision:
        return self._persist_decision_and_quote(request)[0]

    def quote(self, request: ModelRequest) -> CostQuote:
        return self._persist_decision_and_quote(request)[1]

    def execute(self, request: ModelRequest, *, quote_id: str) -> ExecutionResult:
        quote = self._quote(quote_id)
        request_digest = self._request_digest(request)
        if quote.request_digest != request_digest:
            raise QuoteNotFoundError("quote does not match the execute request")
        if quote.capability != request.capability:
            raise QuoteNotFoundError("quote capability does not match the request")
        self._assert_fresh_auth(request)
        decision = self._decision(quote.decision_id)
        if decision.paid:
            self._require_paid(request)
        prompt = self._resolve_prompt(request)
        cache_key = self._cache_key(request, decision, prompt)
        cached = self._load_cache(cache_key) if self.policy.cache_enabled else None
        if cached is not None:
            usage = self._record_usage(
                quote,
                decision,
                actual_cost=0.0,
                input_tokens=0,
                output_tokens=0,
                cache_hit=True,
            )
            provenance = self._provenance(decision, prompt, cached["provenance"])
            result = ExecutionResult(
                output=dict(cached["output"]),
                usage=usage,
                provenance=provenance,
                cache_hit=True,
                quote_id=quote.id,
                decision=decision,
            )
            self._audit(
                request,
                PolicyDecision.ALLOW,
                "model_router.execute_cache",
                decision.id,
                "cache_hit",
            )
            return result

        adapter_result, decision = self._invoke_with_fallback(
            request, decision, prompt.template
        )
        self._validate_output(request, adapter_result.output)
        usage = self._record_usage(
            quote,
            decision,
            actual_cost=adapter_result.actual_cost,
            input_tokens=adapter_result.input_tokens,
            output_tokens=adapter_result.output_tokens,
            cache_hit=False,
        )
        provenance = ModelProvenance(
            provider=decision.provider,
            model=decision.model,
            model_version=adapter_result.model_version,
            prompt_id=prompt.prompt_id,
            prompt_version=prompt.version,
            policy_version=decision.policy_version,
            timestamp=utc_now(),
            method=adapter_result.method,
            assumptions=adapter_result.assumptions,
            uncertainty=adapter_result.uncertainty,
            adapter_id=decision.adapter_id,
        )
        if self.policy.cache_enabled:
            self._store_cache(
                cache_key,
                {
                    "output": adapter_result.output,
                    "provenance": provenance.to_dict(),
                    "decision": decision.to_dict(),
                },
            )
        self._audit(
            request,
            PolicyDecision.ALLOW,
            "model_router.execute",
            decision.id,
            f"provider={decision.provider}",
        )
        return ExecutionResult(
            output=adapter_result.output,
            usage=usage,
            provenance=provenance,
            cache_hit=False,
            quote_id=quote.id,
            decision=decision,
        )

    def register_prompt(self, prompt_id: str, version: str, template: str) -> PromptVersion:
        digest = digest_payload({"prompt_id": prompt_id, "version": version, "template": template})[1]
        created = utc_now()

        def mutate(index: dict[str, Any]) -> PromptVersion:
            key = f"{prompt_id}@{version}"
            existing_digest = index["prompt_digests"].get(key)
            if existing_digest:
                existing = PromptVersion.from_dict(load_json_blob(self.workspace, str(existing_digest)))
                if existing.template != template:
                    raise PromptImmutableError(
                        f"prompt {prompt_id} version {version} is immutable"
                    )
                return existing
            record = PromptVersion(
                prompt_id=prompt_id,
                version=version,
                template=template,
                created_at=created,
                digest=digest,
            )
            blob = put_json_blob(self.workspace, record.to_dict())
            index["prompt_keys"] = [*index["prompt_keys"], key]
            index["prompt_digests"][key] = blob
            return record

        return mutate_index(self.workspace, mutate)

    def register_fine_tuned_adapter(
        self,
        adapter_id: str,
        *,
        base_provider: str,
        model: str,
        model_version: str,
    ) -> dict[str, str]:
        payload = {
            "adapter_id": adapter_id,
            "base_provider": base_provider,
            "model": model,
            "model_version": model_version,
            "kind": "fine_tuned",
        }

        def mutate(index: dict[str, Any]) -> dict[str, str]:
            existing = index["fine_tuned_adapters"].get(adapter_id)
            if existing is not None and existing != payload:
                raise PromptImmutableError(f"fine-tuned adapter {adapter_id} is immutable")
            index["fine_tuned_adapters"][adapter_id] = payload
            return payload

        return mutate_index(self.workspace, mutate)

    def get_quote(self, quote_id: str) -> CostQuote:
        return self._quote(quote_id)

    def get_decision(self, decision_id: str) -> RoutingDecision:
        return self._decision(decision_id)

    def list_usage(self) -> tuple[UsageRecord, ...]:
        index = load_index(self.workspace)
        records = []
        for usage_id in index["usage_ids"]:
            digest = index["usage_digests"][str(usage_id)]
            records.append(UsageRecord.from_dict(load_json_blob(self.workspace, str(digest))))
        return tuple(records)

    def _persist_decision_and_quote(
        self, request: ModelRequest
    ) -> tuple[RoutingDecision, CostQuote]:
        self._assert_project_and_consent(request)
        constraints = self._constraints(request)
        try:
            choice = evaluate_route(self.policy, constraints)
        except Exception as exc:
            self._audit(
                request,
                PolicyDecision.DENY,
                "model_router.route",
                request.capability,
                str(exc),
            )
            raise
        prompt = self._resolve_prompt(request)
        now = utc_now()
        decision_id = f"rtd_{new_ulid()}"
        quote_id = f"qte_{new_ulid()}"
        decision = RoutingDecision(
            id=decision_id,
            provider=choice.provider_id,
            model=choice.model,
            reason=choice.reason,
            policy_version=self.policy.version,
            capability=request.capability,
            classification=request.data_classification,
            offline=request.offline_required or self._airplane(),
            cost_quote_id=quote_id,
            prompt_id=prompt.prompt_id,
            prompt_version=prompt.version,
            provider_kind=choice.provider_kind,
            model_version=choice.model_version,
            timestamp=now,
            paid=choice.paid,
            estimated_cost=choice.estimated_cost,
            role_contract=request.role_contract,
            adapter_id=choice.adapter_id,
            fallback_from=choice.fallback_from,
        )
        quote = CostQuote(
            id=quote_id,
            estimated_cost=choice.estimated_cost,
            estimated_credits=choice.estimated_cost,
            currency=self.policy.currency,
            provider=choice.provider_id,
            model=choice.model,
            paid=choice.paid,
            capability=request.capability,
            policy_version=self.policy.version,
            request_digest=self._request_digest(request),
            decision_id=decision_id,
            created_at=now,
        )

        def mutate(index: dict[str, Any]) -> tuple[RoutingDecision, CostQuote]:
            decision_digest = put_json_blob(self.workspace, decision.to_dict())
            quote_digest = put_json_blob(self.workspace, quote.to_dict())
            index["decision_ids"] = [*index["decision_ids"], decision.id]
            index["decision_digests"][decision.id] = decision_digest
            index["quote_ids"] = [*index["quote_ids"], quote.id]
            index["quote_digests"][quote.id] = quote_digest
            return decision, quote

        stored = mutate_index(self.workspace, mutate)
        self._audit(
            request,
            PolicyDecision.ALLOW,
            "model_router.route",
            decision.id,
            decision.reason,
        )
        return stored

    def _invoke_with_fallback(
        self,
        request: ModelRequest,
        decision: RoutingDecision,
        prompt_template: str,
    ) -> tuple[AdapterResult, RoutingDecision]:
        try:
            result = self._adapter(decision.provider_kind).invoke(
                request, decision, prompt_template
            )
            return result, decision
        except ProviderUnavailableError as exc:
            capability = self.policy.capabilities.get(request.capability)
            if capability is None:
                raise
            constraints = self._constraints(request)
            for fallback_id in capability.fallbacks:
                if fallback_id == decision.provider:
                    continue
                spec = self.policy.providers.get(fallback_id)
                if spec is None:
                    continue
                if provider_rejection_reason(self.policy, spec, constraints) is not None:
                    continue
                fallback_decision = RoutingDecision(
                    id=decision.id,
                    provider=spec.id,
                    model=spec.model,
                    reason=f"execute_fallback:{spec.id}; {exc}",
                    policy_version=decision.policy_version,
                    capability=decision.capability,
                    classification=decision.classification,
                    offline=spec.offline,
                    cost_quote_id=decision.cost_quote_id,
                    prompt_id=decision.prompt_id,
                    prompt_version=decision.prompt_version,
                    provider_kind=spec.kind,
                    model_version=spec.model_version,
                    timestamp=utc_now(),
                    paid=spec.paid or spec.kind == "remote",
                    estimated_cost=spec.estimated_cost,
                    role_contract=decision.role_contract,
                    adapter_id=spec.adapter_id,
                    fallback_from=decision.provider,
                )
                if fallback_decision.paid:
                    self._require_paid(request)
                result = self._adapter(spec.kind).invoke(
                    request, fallback_decision, prompt_template
                )
                return result, fallback_decision
            raise

    def _adapter(self, kind: str) -> DeterministicDoubleAdapter | LocalModelAdapter | RemoteProviderAdapter | FineTunedAdapter:
        if kind == "double":
            return self.double
        if kind == "local":
            return self.local
        if kind == "remote":
            return self.remote
        if kind == "fine_tuned":
            return self.fine_tuned
        raise ProviderUnavailableError(f"unknown adapter kind: {kind}")

    def _assert_project_and_consent(self, request: ModelRequest) -> None:
        project = self._load_project(request.project_id)
        if project.ai_off:
            raise AiOffError(f"project {request.project_id} has ai_off enabled")
        if consent_required(self.policy, request.data_classification) and not request.consent_granted:
            raise ConsentRequiredError(
                f"classification {request.data_classification} requires consent"
            )

    def _assert_fresh_auth(self, request: ModelRequest) -> None:
        if request.acl_epoch != self.identity.acl_epoch():
            raise StaleAuthorizationError("acl_epoch is stale")
        if request.permission_snapshot_id != self.identity.permission_snapshot_id():
            raise StaleAuthorizationError("permission_snapshot_id is stale")

    def _require_paid(self, request: ModelRequest) -> None:
        principal = self.identity.principal(request.actor_id)
        try:
            self.authorization.require(
                principal,
                Action.RUN_PAID_PROVIDER,
                self.authorization.resource_for_project(
                    request.project_id,
                    kind=ResourceKind.PROJECT,
                ),
                acl_epoch=request.acl_epoch,
                context=AuthContext(snapshot_id=request.permission_snapshot_id),
            )
        except AuthorizationError:
            self._audit(
                request,
                PolicyDecision.DENY,
                "model_router.paid",
                request.capability,
                "run_paid_provider_denied",
            )
            raise

    def _constraints(self, request: ModelRequest) -> RouteConstraints:
        airplane = self._airplane()
        ai_outage = bool(self.workspace.store.flags().get("ai_outage"))
        remote_ok = (
            remote_base_url(self.policy.remote_base_url_env) is not None
            and not airplane
            and not ai_outage
        )
        local_ok = local_runtime_configured(self.policy.local_runtime_env)
        return RouteConstraints(
            capability=request.capability,
            classification=request.data_classification,
            offline_required=request.offline_required or airplane,
            cost_budget=request.cost_budget,
            latency_budget_ms=request.latency_budget_ms,
            quality_tier=request.quality_tier,
            context_tokens=request.context_tokens,
            role_contract=request.role_contract,
            remote_available=remote_ok,
            local_available=local_ok,
        )

    def _airplane(self) -> bool:
        return bool(self.workspace.store.flags().get("connectivity_offline"))

    def _load_project(self, project_id: str) -> Project:
        row = self.workspace.store.fetchone(
            "SELECT payload_json FROM projects WHERE id=?",
            (project_id,),
        )
        if row is None:
            raise AiOffError(f"unknown project: {project_id}")
        return Project.from_dict(json.loads(str(row["payload_json"])))

    def _resolve_prompt(self, request: ModelRequest) -> PromptVersion:
        prompt_id = request.prompt_id or self.policy.default_prompt_id
        version = request.prompt_version or self.policy.default_prompt_version
        key = f"{prompt_id}@{version}"
        index = load_index(self.workspace)
        digest = index["prompt_digests"].get(key)
        if digest is None:
            raise PromptNotFoundError(f"unknown prompt {prompt_id} version {version}")
        return PromptVersion.from_dict(load_json_blob(self.workspace, str(digest)))

    def _ensure_builtin_prompt(self) -> None:
        self.register_prompt(
            self.policy.default_prompt_id,
            self.policy.default_prompt_version,
            BUILTIN_PROMPT_TEMPLATE,
        )

    def _request_digest(self, request: ModelRequest) -> str:
        payload = {
            "capability": request.capability,
            "data_classification": request.data_classification,
            "offline_required": request.offline_required,
            "quality_tier": request.quality_tier,
            "role_contract": request.role_contract,
            "input": request.input_mapping(),
            "prompt_id": request.prompt_id or self.policy.default_prompt_id,
            "prompt_version": request.prompt_version or self.policy.default_prompt_version,
            "structured_output": request.to_dict()["structured_output"],
            "context_tokens": request.context_tokens,
            "cost_budget": request.cost_budget,
            "latency_budget_ms": request.latency_budget_ms,
            "project_id": request.project_id,
        }
        return digest_payload(payload)[1]

    def _cache_key(
        self, request: ModelRequest, decision: RoutingDecision, prompt: PromptVersion
    ) -> str:
        payload = {
            "capability": request.capability,
            "input": request.input_mapping(),
            "policy_version": decision.policy_version,
            "prompt_version": prompt.version,
            "model": decision.model,
        }
        return digest_payload(payload)[1]

    def _load_cache(self, cache_key: str) -> dict[str, Any] | None:
        index = load_index(self.workspace)
        digest = index["cache"].get(cache_key)
        if digest is None:
            return None
        return load_json_blob(self.workspace, str(digest))

    def _store_cache(self, cache_key: str, payload: dict[str, Any]) -> None:
        def mutate(index: dict[str, Any]) -> None:
            index["cache"][cache_key] = put_json_blob(self.workspace, payload)

        mutate_index(self.workspace, mutate)

    def _record_usage(
        self,
        quote: CostQuote,
        decision: RoutingDecision,
        *,
        actual_cost: float,
        input_tokens: int,
        output_tokens: int,
        cache_hit: bool,
    ) -> UsageRecord:
        record = UsageRecord(
            id=f"usg_{new_ulid()}",
            quote_id=quote.id,
            estimated_cost=quote.estimated_cost,
            actual_cost=actual_cost,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_hit=cache_hit,
            provider=decision.provider,
            model=decision.model,
            created_at=utc_now(),
        )

        def mutate(index: dict[str, Any]) -> UsageRecord:
            digest = put_json_blob(self.workspace, record.to_dict())
            index["usage_ids"] = [*index["usage_ids"], record.id]
            index["usage_digests"][record.id] = digest
            return record

        return mutate_index(self.workspace, mutate)

    def _quote(self, quote_id: str) -> CostQuote:
        index = load_index(self.workspace)
        digest = index["quote_digests"].get(quote_id)
        if digest is None:
            raise QuoteNotFoundError(f"unknown quote: {quote_id}")
        return CostQuote.from_dict(load_json_blob(self.workspace, str(digest)))

    def _decision(self, decision_id: str) -> RoutingDecision:
        index = load_index(self.workspace)
        digest = index["decision_digests"].get(decision_id)
        if digest is None:
            raise QuoteNotFoundError(f"unknown routing decision: {decision_id}")
        return RoutingDecision.from_dict(load_json_blob(self.workspace, str(digest)))

    def _validate_output(self, request: ModelRequest, output: Mapping[str, Any]) -> None:
        if contains_chain_of_thought(output):
            raise StructuredOutputError("adapter output exposed chain-of-thought")
        schema: Mapping[str, Any] | None
        if isinstance(request.structured_output, Mapping):
            schema = request.structured_output
        elif request.structured_output:
            schema = DEFAULT_OUTPUT_SCHEMAS.get(request.capability)
        else:
            schema = None
        if schema is None:
            return
        validator = Draft202012Validator(dict(schema))
        errors = sorted(validator.iter_errors(dict(output)), key=lambda item: list(item.path))
        if errors:
            raise StructuredOutputError(str(errors[0].message))

    def _provenance(
        self,
        decision: RoutingDecision,
        prompt: PromptVersion,
        stored: Mapping[str, Any],
    ) -> ModelProvenance:
        return ModelProvenance(
            provider=str(stored.get("provider") or decision.provider),
            model=str(stored.get("model") or decision.model),
            model_version=str(stored.get("model_version") or decision.model_version),
            prompt_id=str(stored.get("prompt_id") or prompt.prompt_id),
            prompt_version=str(stored.get("prompt_version") or prompt.version),
            policy_version=str(stored.get("policy_version") or decision.policy_version),
            timestamp=str(stored.get("timestamp") or utc_now()),
            method=str(stored.get("method") or "cache"),
            assumptions=tuple(str(item) for item in stored.get("assumptions") or ("cached",)),
            uncertainty=str(stored.get("uncertainty") or "cached"),
            adapter_id=str(stored["adapter_id"]) if stored.get("adapter_id") else decision.adapter_id,
        )

    def _audit(
        self,
        request: ModelRequest,
        decision: PolicyDecision,
        operation: str,
        object_id: str,
        reason: str,
    ) -> None:
        self.audit.append(
            actor_id=request.actor_id,
            effective_principal_id=request.actor_id,
            operation=operation,
            object_kind="model_route",
            object_id=object_id,
            policy_decision=decision,
            acl_epoch=request.acl_epoch,
            reason=reason[:200],
        )


def index_meta_key() -> str:
    return INDEX_META_KEY


def env_remote_configured() -> bool:
    return remote_base_url() is not None


def env_local_configured() -> bool:
    return local_runtime_configured()
