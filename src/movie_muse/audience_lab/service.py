"""Evidence-tiered audience resonance. Synthetic personas are never human samples."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from statistics import fmean, pstdev
from typing import Any

from movie_muse.audience_lab.errors import (
    ConsentRequiredError,
    HumanProvenanceError,
    InsufficientCalibrationError,
    PopulationClaimError,
    RunNotFoundError,
)
from movie_muse.audience_lab.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.audience_lab.types import (
    DISCLAIMER,
    FORBIDDEN_POPULATION_PHRASES,
    HUMAN_TIERS,
    NON_INDEPENDENCE_NOTICE,
    AudienceSample,
    CalibrationReport,
    ConsentRecord,
    ConsentState,
    EvidenceTier,
    IntendedEffectComparison,
    LabRun,
    SegmentHypothesis,
)
from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.creative_intent.api import CreativeIntentService, IntentKind
from movie_muse.identity.api import IdentityService, Principal, PrincipalKind
from movie_muse.model_router.api import ModelRequest, ModelRouter, RoleContract
from movie_muse.persistence.api import LocalWorkspace, digest_payload, utc_now
from movie_muse.revisions.api import RevisionService
from movie_muse.rights.api import PermittedUse, RightsService
from movie_muse.schemas.api import new_ulid


def assert_no_population_claim(text: str) -> str:
    lowered = f" {text.lower()} "
    for phrase in FORBIDDEN_POPULATION_PHRASES:
        start = 0
        while True:
            found = lowered.find(phrase, start)
            if found < 0:
                break
            prefix = lowered[max(0, found - 32) : found]
            negated = any(
                marker in prefix for marker in (" not ", " never ", " not a ", " not an ")
            )
            if not negated:
                raise PopulationClaimError(
                    f"synthetic or hypothesis text must not claim a human population: {phrase}"
                )
            start = found + 1
    return text


def _score_for(prompt: str, reading: str, index: int) -> float:
    _, digest = digest_payload(
        {"prompt": prompt, "reading": reading, "index": index, "kind": "audience_score"}
    )
    return round(int(digest[:8], 16) / 0xFFFFFFFF, 6)


def _mean_var(scores: Sequence[float]) -> tuple[float, float]:
    if not scores:
        return 0.0, 0.0
    mean = round(fmean(scores), 6)
    variance = round(pstdev(scores) if len(scores) > 1 else 0.0, 6)
    return mean, variance


class AudienceLabService:
    """Separated evidence tiers. Synthetic output is never a human bootstrap sample."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        identity: IdentityService,
        audit: AuditLog,
        router: ModelRouter,
        rights: RightsService,
        revisions: RevisionService,
        intents: CreativeIntentService,
        *,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.identity = identity
        self.audit = audit
        self.router = router
        self.rights = rights
        self.revisions = revisions
        self.intents = intents
        self.clock = clock

    def consent_view(self, project_id: str) -> ConsentRecord:
        index = load_index(self.workspace)
        raw = dict(index.get("consent", {})).get(project_id)
        if not isinstance(raw, dict):
            return ConsentRecord(project_id=project_id, state=ConsentState.PENDING)
        return ConsentRecord.from_dict({"project_id": project_id, **raw})

    def grant_consent(
        self, project_id: str, *, principal: Principal, acl_epoch: int
    ) -> ConsentRecord:
        if principal.kind is not PrincipalKind.HUMAN:
            raise ConsentRequiredError("only a human principal may grant audience-data consent")
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        record = ConsentRecord(
            project_id=project_id,
            state=ConsentState.GRANTED,
            actor_id=principal.actor_id,
            decided_at=self.clock(),
        )
        self._put_consent(record)
        self._audit(principal, acl_epoch, "audience_lab.consent_grant", project_id, "granted")
        return record

    def withdraw_consent(
        self, project_id: str, *, principal: Principal, acl_epoch: int
    ) -> ConsentRecord:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        record = ConsentRecord(
            project_id=project_id,
            state=ConsentState.WITHDRAWN,
            actor_id=principal.actor_id,
            decided_at=self.clock(),
        )
        self._put_consent(record)
        self._audit(principal, acl_epoch, "audience_lab.consent_withdraw", project_id, "withdrawn")
        return record

    def propose_segment_hypothesis(
        self,
        project_id: str,
        *,
        segment: str,
        statement: str,
        principal: Principal,
        acl_epoch: int,
    ) -> SegmentHypothesis:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        cleaned = assert_no_population_claim(statement.strip())
        if not cleaned:
            raise PopulationClaimError("segment hypothesis statement is required")
        item = SegmentHypothesis(
            id=f"auh_{new_ulid()}",
            project_id=project_id,
            segment=segment.strip(),
            statement=cleaned,
            labeled_hypothesis=True,
            population_estimate=False,
        )
        written = self._put_hypothesis(item)
        self._audit(principal, acl_epoch, "audience_lab.hypothesis", written.id, segment)
        return written

    def run_synthetic(
        self,
        project_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        segment: str,
        prompt: str,
        sample_count: int = 3,
        parent_id: str | None = None,
    ) -> LabRun:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        if sample_count < 1:
            raise PopulationClaimError("synthetic run requires at least one hypothesis sample")
        cleaned = assert_no_population_claim(prompt.strip())
        source_revision_id = self.revisions.canon_head_id()
        _, fingerprint = digest_payload(
            {
                "tier": EvidenceTier.SYNTHETIC_LLM.value,
                "segment": segment,
                "prompt": cleaned,
                "sample_count": sample_count,
                "source_revision_id": source_revision_id,
            }
        )
        reused = self._run_for_fingerprint(project_id, fingerprint)
        if reused is not None:
            self._audit(principal, acl_epoch, "audience_lab.repeat", reused.id, fingerprint)
            return reused
        samples: list[AudienceSample] = []
        uncertainty = "deterministic_fixture"
        for index in range(sample_count):
            result = self._experience(project_id, principal, acl_epoch, cleaned, index)
            reading = assert_no_population_claim(str(result.output.get("reading", "")))
            uncertainty = str(result.output.get("uncertainty") or result.usage.model)
            sample = AudienceSample(
                id=f"aus_{new_ulid()}",
                tier=EvidenceTier.SYNTHETIC_LLM,
                segment=segment,
                reading=reading,
                score=_score_for(cleaned, reading, index),
                uncertainty=str(result.output.get("uncertainty", "high")),
                non_independent=True,
                provenance={
                    **result.provenance.to_dict(),
                    "disclaimer": DISCLAIMER,
                    "non_independence": NON_INDEPENDENCE_NOTICE,
                    "sample_index": index,
                    "tier": EvidenceTier.SYNTHETIC_LLM.value,
                },
            )
            samples.append(sample)
        mean, variance = _mean_var([item.score for item in samples])
        run = LabRun(
            id=f"arl_{new_ulid()}",
            project_id=project_id,
            tier=EvidenceTier.SYNTHETIC_LLM,
            segment=segment,
            prompt=cleaned,
            input_fingerprint=fingerprint,
            samples=tuple(samples),
            mean_score=mean,
            variance=variance,
            uncertainty=uncertainty,
            non_independent=True,
            source_revision_id=source_revision_id,
            parent_id=parent_id,
        )
        written = self._put_run(run)
        self._audit(principal, acl_epoch, "audience_lab.synthetic", written.id, fingerprint)
        return written

    def record_human(
        self,
        project_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        tier: EvidenceTier | str,
        segment: str,
        source_id: str,
        responses: Sequence[Mapping[str, Any]],
    ) -> LabRun:
        parsed = tier if isinstance(tier, EvidenceTier) else EvidenceTier(str(tier))
        if parsed not in HUMAN_TIERS:
            raise HumanProvenanceError("record_human accepts only human evidence tiers")
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        self._require_consent(project_id)
        if not source_id:
            raise HumanProvenanceError("human audience data requires a rights source id")
        decision = self.rights.require_permitted_use(source_id, PermittedUse.CITATION)
        samples: list[AudienceSample] = []
        for index, raw in enumerate(responses):
            payload = dict(raw)
            reading = str(payload.get("reading") or payload.get("notes") or "").strip()
            if not reading:
                raise HumanProvenanceError("each human response needs a reading")
            score = float(payload.get("score", 0.0))
            if not 0.0 <= score <= 1.0:
                raise HumanProvenanceError("human scores must be within [0.0, 1.0]")
            samples.append(
                AudienceSample(
                    id=f"aus_{new_ulid()}",
                    tier=parsed,
                    segment=segment,
                    reading=reading,
                    score=score,
                    uncertainty=str(payload.get("uncertainty", "human_rated")),
                    non_independent=False,
                    provenance={
                        "rights_source_id": source_id,
                        "rights_version_id": decision.version_id,
                        "consent_actor_id": self.consent_view(project_id).actor_id,
                        "captured_at": self.clock(),
                        "respondent_index": index,
                    },
                )
            )
        if not samples:
            raise HumanProvenanceError("human run requires at least one response")
        mean, variance = _mean_var([item.score for item in samples])
        source_revision_id = self.revisions.canon_head_id()
        _, fingerprint = digest_payload(
            {
                "tier": parsed.value,
                "segment": segment,
                "source_id": source_id,
                "readings": [item.reading for item in samples],
                "scores": [item.score for item in samples],
                "source_revision_id": source_revision_id,
            }
        )
        run = LabRun(
            id=f"arl_{new_ulid()}",
            project_id=project_id,
            tier=parsed,
            segment=segment,
            prompt=f"human:{parsed.value}",
            input_fingerprint=fingerprint,
            samples=tuple(samples),
            mean_score=mean,
            variance=variance,
            uncertainty="human_rated",
            non_independent=False,
            source_revision_id=source_revision_id,
            rights_source_id=source_id,
            disclaimer="Human audience data with consent and rights provenance; not a synthetic persona.",
        )
        written = self._put_run(run)
        self._audit(principal, acl_epoch, "audience_lab.human", written.id, parsed.value)
        return written

    def perturb(
        self,
        run_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        prompt_delta: str,
    ) -> LabRun:
        prior = self.get_run(run_id, principal=principal, acl_epoch=acl_epoch)
        if not prior.is_synthetic:
            raise PopulationClaimError("perturbation applies to synthetic hypothesis runs")
        delta = assert_no_population_claim(prompt_delta.strip())
        perturbed_prompt = f"{prior.prompt}\nPERTURBATION: {delta}"
        return self.run_synthetic(
            prior.project_id,
            principal=principal,
            acl_epoch=acl_epoch,
            segment=prior.segment,
            prompt=perturbed_prompt,
            sample_count=len(prior.samples) or 1,
            parent_id=prior.id,
        )

    def calibrate(
        self,
        synthetic_run_id: str,
        human_run_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> CalibrationReport:
        synthetic = self.get_run(synthetic_run_id, principal=principal, acl_epoch=acl_epoch)
        human = self.get_run(human_run_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.PROPOSE, synthetic.project_id, acl_epoch)
        if not synthetic.is_synthetic:
            raise InsufficientCalibrationError("calibration left side must be a synthetic hypothesis run")
        if human.tier not in HUMAN_TIERS:
            raise InsufficientCalibrationError(
                "calibration requires a human evidence tier; synthetic-only residuals "
                "are not a population estimate"
            )
        residual = round(abs(synthetic.mean_score - human.mean_score), 6)
        coverage = round(min(len(synthetic.samples), len(human.samples)) / max(len(human.samples), 1), 6)
        report = CalibrationReport(
            id=f"auc_{new_ulid()}",
            project_id=synthetic.project_id,
            synthetic_run_id=synthetic.id,
            human_run_id=human.id,
            residual=residual,
            coverage=coverage,
            population_estimate=False,
        )
        written = self._put_calibration(report)
        self._audit(principal, acl_epoch, "audience_lab.calibrate", written.id, human.tier.value)
        return written

    def compare_intended_effect(
        self,
        run_id: str,
        intent_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> IntendedEffectComparison:
        stored = self.get_run(run_id, principal=principal, acl_epoch=acl_epoch)
        record = self.intents.get(intent_id)
        if record.envelope.kind is not IntentKind.AUDIENCE_EXPERIENCE:
            raise PopulationClaimError("intended-effect comparison requires audience_experience intent")
        statement = record.intent.statement
        tokens = {part.lower() for part in statement.split() if len(part) > 3}
        readings = " ".join(item.reading for item in stored.samples).lower()
        hits = sum(1 for token in tokens if token in readings)
        overlap = round(hits / max(len(tokens), 1), 6)
        comparison = IntendedEffectComparison(
            run_id=stored.id,
            intent_id=intent_id,
            intent_statement=statement,
            overlap=overlap,
            advisory=True,
        )
        self._audit(principal, acl_epoch, "audience_lab.intended_effect", stored.id, intent_id)
        return comparison

    def export_summary(
        self, run_id: str, *, principal: Principal, acl_epoch: int
    ) -> str:
        stored = self.get_run(run_id, principal=principal, acl_epoch=acl_epoch)
        parts = [
            stored.disclaimer,
            f"TIER {stored.tier.value}",
            f"SEGMENT {stored.segment} (hypothesis, not a population)",
            f"UNCERTAINTY {stored.uncertainty}",
            f"NON_INDEPENDENT {stored.non_independent}",
            f"MEAN {stored.mean_score} VARIANCE {stored.variance}",
        ]
        if stored.is_synthetic:
            parts.insert(1, NON_INDEPENDENCE_NOTICE)
        for sample in stored.samples:
            parts.append(f"SAMPLE {sample.id} score={sample.score} {sample.reading}")
        text = "\n".join(parts)
        if stored.is_synthetic:
            assert_no_population_claim(text)
        return text

    def get_run(
        self, run_id: str, *, principal: Principal, acl_epoch: int
    ) -> LabRun:
        stored = self._load_run(run_id)
        self._require(principal, Action.READ, stored.project_id, acl_epoch)
        return stored

    def list_runs(
        self, project_id: str, *, principal: Principal, acl_epoch: int
    ) -> tuple[LabRun, ...]:
        self._require(principal, Action.READ, project_id, acl_epoch)
        index = load_index(self.workspace)
        ids = list(dict(index.get("by_project", {})).get(project_id, []))
        found: list[LabRun] = []
        for run_id in ids:
            digest = dict(index.get("run_digests", {})).get(str(run_id))
            if digest is None:
                continue
            found.append(LabRun.from_dict(load_payload(self.workspace, str(digest))))
        return tuple(found)

    def _experience(
        self,
        project_id: str,
        principal: Principal,
        acl_epoch: int,
        prompt: str,
        index: int,
    ) -> Any:
        request = ModelRequest(
            capability="experience",
            data_classification="internal",
            latency_budget_ms=5000,
            cost_budget=5.0,
            offline_required=False,
            context_tokens=256,
            structured_output=True,
            quality_tier="fast",
            role_contract=RoleContract.AUDIENCE.value,
            project_id=project_id,
            actor_id=principal.actor_id,
            acl_epoch=acl_epoch,
            permission_snapshot_id=self.identity.permission_snapshot_id(),
            input={"text": prompt, "sample_index": index, "disclaimer": DISCLAIMER},
            consent_granted=True,
        )
        quote = self.router.quote(request)
        return self.router.execute(request, quote_id=quote.id)

    def _require_consent(self, project_id: str) -> None:
        view = self.consent_view(project_id)
        if view.state is ConsentState.GRANTED:
            return
        raise ConsentRequiredError(
            f"human audience data requires granted consent; current state is {view.state.value}"
        )

    def _run_for_fingerprint(self, project_id: str, fingerprint: str) -> LabRun | None:
        index = load_index(self.workspace)
        run_id = dict(index.get("by_fingerprint", {})).get(fingerprint)
        if run_id is None:
            return None
        digest = dict(index.get("run_digests", {})).get(str(run_id))
        if digest is None:
            return None
        stored = LabRun.from_dict(load_payload(self.workspace, str(digest)))
        if stored.project_id != project_id:
            return None
        return stored

    def _load_run(self, run_id: str) -> LabRun:
        index = load_index(self.workspace)
        digest = dict(index.get("run_digests", {})).get(run_id)
        if digest is None:
            raise RunNotFoundError(f"audience lab run {run_id} is not in the index")
        return LabRun.from_dict(load_payload(self.workspace, str(digest)))

    def _put_run(self, stored: LabRun) -> LabRun:
        def persist(index: dict[str, Any]) -> LabRun:
            digest = put_payload(self.workspace, stored.to_dict())
            ids = list(index.get("run_ids", []))
            if stored.id not in ids:
                ids.append(stored.id)
            index["run_ids"] = ids
            digests = dict(index.get("run_digests", {}))
            digests[stored.id] = digest
            index["run_digests"] = digests
            by_project = dict(index.get("by_project", {}))
            project_ids = list(by_project.get(stored.project_id, []))
            if stored.id not in project_ids:
                project_ids.append(stored.id)
            by_project[stored.project_id] = project_ids
            index["by_project"] = by_project
            fingerprints = dict(index.get("by_fingerprint", {}))
            fingerprints[stored.input_fingerprint] = stored.id
            index["by_fingerprint"] = fingerprints
            return stored

        return mutate_index(self.workspace, persist)

    def _put_hypothesis(self, stored: SegmentHypothesis) -> SegmentHypothesis:
        def persist(index: dict[str, Any]) -> SegmentHypothesis:
            digest = put_payload(self.workspace, stored.to_dict())
            ids = list(index.get("hypothesis_ids", []))
            if stored.id not in ids:
                ids.append(stored.id)
            index["hypothesis_ids"] = ids
            digests = dict(index.get("hypothesis_digests", {}))
            digests[stored.id] = digest
            index["hypothesis_digests"] = digests
            return stored

        return mutate_index(self.workspace, persist)

    def _put_calibration(self, stored: CalibrationReport) -> CalibrationReport:
        def persist(index: dict[str, Any]) -> CalibrationReport:
            digest = put_payload(self.workspace, stored.to_dict())
            ids = list(index.get("calibration_ids", []))
            if stored.id not in ids:
                ids.append(stored.id)
            index["calibration_ids"] = ids
            digests = dict(index.get("calibration_digests", {}))
            digests[stored.id] = digest
            index["calibration_digests"] = digests
            return stored

        return mutate_index(self.workspace, persist)

    def _put_consent(self, stored: ConsentRecord) -> ConsentRecord:
        def persist(index: dict[str, Any]) -> ConsentRecord:
            consent = dict(index.get("consent", {}))
            consent[stored.project_id] = {
                "state": stored.state.value,
                "actor_id": stored.actor_id,
                "decided_at": stored.decided_at,
            }
            index["consent"] = consent
            return stored

        return mutate_index(self.workspace, persist)

    def _require(
        self, principal: Principal, action: Action, project_id: str, acl_epoch: int
    ) -> None:
        self.authorization.require(
            principal,
            action,
            self.authorization.resource_for_project(project_id),
            acl_epoch=acl_epoch,
        )

    def _audit(
        self,
        principal: Principal,
        acl_epoch: int,
        operation: str,
        object_id: str,
        reason: str,
    ) -> None:
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation=operation,
            object_kind="audience_lab",
            object_id=object_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=reason,
        )
