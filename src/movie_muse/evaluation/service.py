"""Bench registry, local/fine-tuned baselines, correction burden, Creator Leverage."""

from __future__ import annotations

from typing import Any

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService, Resource, ResourceKind
from movie_muse.evaluation.errors import (
    BaselineError,
    EvaluationError,
    LeverageError,
    PopulationClaimError,
)
from movie_muse.evaluation.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.evaluation.types import (
    FORBIDDEN_POPULATION_PHRASES,
    QUALITY_BASELINE,
    SAFETY_BASELINE,
    CorrectionBurden,
    CreatorLeverage,
    EvalRun,
)
from movie_muse.identity.api import IdentityService, Principal
from movie_muse.model_router.api import ModelRequest, ModelRouter
from movie_muse.persistence.api import LocalWorkspace, utc_now
from movie_muse.retrieval.api import inspect_untrusted_text
from movie_muse.schemas.api import new_ulid
from movie_muse.testkit.api import SYNTHETIC_AUDIENCE_DISCLAIMER, BenchRegistry, BenchTask


def assert_no_population_claim(text: str) -> None:
    lowered = text.lower()
    for phrase in FORBIDDEN_POPULATION_PHRASES:
        start = 0
        while True:
            index = lowered.find(phrase, start)
            if index < 0:
                break
            prefix = lowered[max(0, index - 32) : index]
            if " not " in prefix or " never " in prefix or " not a " in prefix or " not an " in prefix:
                start = index + len(phrase)
                continue
            raise PopulationClaimError(f"forbidden population claim: {phrase}")


class EvaluationService:
    """MovieMuse Bench runs. Synthetic output is never a human population sample."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        identity: IdentityService,
        audit: AuditLog,
        *,
        organization_id: str,
        project_id: str,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.identity = identity
        self.audit = audit
        self.organization_id = organization_id
        self.project_id = project_id
        self.router = ModelRouter(workspace, authorization, identity, audit)
        self.bench = BenchRegistry()

    def _resource(self) -> Resource:
        return Resource(
            kind=ResourceKind.PROJECT,
            id=self.project_id,
            organization_id=self.organization_id,
            project_id=self.project_id,
        )

    def tasks(self) -> tuple[BenchTask, ...]:
        return self.bench.tasks()

    def evaluate_route(
        self,
        *,
        kind: str,
        task_id: str,
        principal: Principal,
        acl_epoch: int,
    ) -> EvalRun:
        self.authorization.require(principal, Action.READ, self._resource(), acl_epoch=acl_epoch)
        task = self.bench.task(task_id)
        if kind == "local":
            quality_tier = "standard"
        elif kind == "fine_tuned":
            quality_tier = "premium"
        else:
            raise EvaluationError(f"unsupported route kind: {kind}")
        request = ModelRequest(
            capability="generate_text",
            data_classification="public",
            latency_budget_ms=5000,
            cost_budget=5.0,
            offline_required=True,
            context_tokens=128,
            structured_output=True,
            quality_tier=quality_tier,
            role_contract="executor",
            project_id=self.project_id,
            actor_id=principal.actor_id,
            acl_epoch=acl_epoch,
            permission_snapshot_id=self.identity.permission_snapshot_id(),
            input={"text": f"Evaluate {task.id} as a labeled hypothesis, not a human sample."},
            consent_granted=True,
        )
        quote = self.router.quote(request)
        result = self.router.execute(request, quote_id=quote.id)
        if kind == "local" and result.decision.provider_kind != "local":
            raise BaselineError(f"expected local route, got {result.decision.provider_kind}")
        if kind == "fine_tuned" and result.decision.provider_kind != "fine_tuned":
            raise BaselineError(f"expected fine-tuned route, got {result.decision.provider_kind}")
        inspection = inspect_untrusted_text(str(result.output))
        leaked_cot = "chain_of_thought" in str(result.output).lower() or "chain-of-thought" in str(
            result.output
        ).lower()
        safety = 0.0 if inspection.rejected or leaked_cot else 1.0
        quality = 1.0 if result.output and not inspection.rejected else 0.0
        if quality < QUALITY_BASELINE or safety < SAFETY_BASELINE:
            raise BaselineError(
                f"{kind} missed baseline quality={quality} safety={safety} "
                f"(need {QUALITY_BASELINE}/{SAFETY_BASELINE})"
            )
        run = EvalRun(
            id=f"evl_{new_ulid()}",
            task_id=task.id,
            route_kind=kind,
            provider=result.decision.provider,
            quality=quality,
            safety=safety,
            recorded_at=utc_now(),
        )
        digest = put_payload(self.workspace, run.to_dict())

        def persist(index: dict[str, Any]) -> None:
            ids = list(index.get("run_ids", []))
            ids.append(run.id)
            index["run_ids"] = ids
            digests = dict(index.get("run_digests", {}))
            digests[run.id] = digest
            index["run_digests"] = digests

        mutate_index(self.workspace, persist)
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation="evaluation.run",
            object_kind="evaluation",
            object_id=run.id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=kind,
        )
        return run

    def list_runs(self) -> tuple[EvalRun, ...]:
        index = load_index(self.workspace)
        items: list[EvalRun] = []
        for run_id in index.get("run_ids", []):
            digest = dict(index.get("run_digests", {})).get(str(run_id))
            if digest:
                items.append(EvalRun.from_dict(load_payload(self.workspace, str(digest))))
        return tuple(items)

    def correction_burden(
        self,
        *,
        regenerations: int,
        accepted: int,
        correction_minutes: float,
    ) -> CorrectionBurden:
        if accepted <= 0:
            raise EvaluationError("accepted count must be positive")
        return CorrectionBurden(
            regenerations=regenerations,
            accepted=accepted,
            correction_minutes=correction_minutes,
            ratio=regenerations / accepted,
        )

    def creator_leverage(
        self,
        *,
        useful_minutes_removed: float,
        correction_minutes: float,
        verification_minutes: float,
    ) -> CreatorLeverage:
        cost = correction_minutes + verification_minutes
        if cost <= 0:
            raise LeverageError("verification/correction cost must be positive")
        ratio = useful_minutes_removed / cost
        record = CreatorLeverage(
            useful_minutes_removed=useful_minutes_removed,
            correction_minutes=correction_minutes,
            verification_minutes=verification_minutes,
            ratio=ratio,
        )
        if ratio <= 1.0:
            raise LeverageError(
                f"Creator Leverage Ratio {ratio:.3f} is not positive "
                "(useful work removed must exceed verification/correction cost)"
            )
        return record

    def assert_advisory_label(self, text: str) -> None:
        assert_no_population_claim(text)
        if SYNTHETIC_AUDIENCE_DISCLAIMER.lower() not in text.lower() and "not a human sample" not in text.lower():
            raise PopulationClaimError("evaluation output must remain labeled as non-population")
