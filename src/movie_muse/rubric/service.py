"""Evidence-linked rubric analysis. Scores are advisory and never canon writes."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from statistics import fmean
from typing import Any

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.creative_intent.api import CreativeIntentService
from movie_muse.film_ir.api import FilmIR, FilmIrService
from movie_muse.identity.api import IdentityService, Principal, PrincipalKind
from movie_muse.model_router.api import ModelRequest, ModelRouter, RoleContract
from movie_muse.persistence.api import LocalWorkspace, digest_payload, utc_now
from movie_muse.revisions.api import RevisionService
from movie_muse.rubric.errors import (
    AdvisoryLabelError,
    AnalysisNotFoundError,
    CalibrationError,
    EvidenceLinkError,
    OverrideDeniedError,
    RatingNotFoundError,
    RubricNotFoundError,
    UnexplainedScoreError,
)
from movie_muse.rubric.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.rubric.types import (
    DISCLAIMER,
    REQUIRED_CRITERIA,
    CalibrationReport,
    CounterEvidence,
    CreatorOverride,
    CriterionKind,
    CriterionSpec,
    DisagreementReport,
    RaterKind,
    Rating,
    RubricAnalysis,
    RubricDefinition,
    ScoreTrace,
    default_criteria,
)
from movie_muse.schemas.api import new_ulid


def _score_for(payload: Mapping[str, Any]) -> float:
    _, digest = digest_payload({"kind": "rubric_score", **dict(payload)})
    return round(int(digest[:8], 16) / 0xFFFFFFFF, 6)


def _confidence(evidence_count: int, rationale: str) -> float:
    length_factor = min(len(rationale.strip()) / 80.0, 1.0)
    evidence_factor = min(evidence_count / 3.0, 1.0)
    return round(0.4 + 0.3 * length_factor + 0.3 * evidence_factor, 6)


def _parse_criterion(value: CriterionKind | str) -> CriterionKind:
    return value if isinstance(value, CriterionKind) else CriterionKind(str(value))


class RubricService:
    """Configurable rubrics. Analysis is labeled advisory and never writes FilmIR."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        identity: IdentityService,
        audit: AuditLog,
        router: ModelRouter,
        revisions: RevisionService,
        film_ir: FilmIrService,
        intents: CreativeIntentService,
        *,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.identity = identity
        self.audit = audit
        self.router = router
        self.revisions = revisions
        self.film_ir = film_ir
        self.intents = intents
        self.clock = clock

    def define_rubric(
        self,
        project_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        name: str,
        version: str,
        criteria: Sequence[CriterionSpec] | None = None,
    ) -> RubricDefinition:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        specs = tuple(criteria) if criteria is not None else default_criteria()
        if not specs:
            raise UnexplainedScoreError("a rubric needs at least one criterion")
        kinds = {item.kind.value for item in specs}
        missing = [item for item in REQUIRED_CRITERIA if item not in kinds]
        if missing:
            raise UnexplainedScoreError(
                f"rubric is missing required criteria: {', '.join(missing)}"
            )
        stored = RubricDefinition(
            id=f"rbd_{new_ulid()}",
            project_id=project_id,
            name=name.strip(),
            version=version.strip(),
            criteria=specs,
        )
        written = self._put_rubric(stored)
        self._audit(principal, acl_epoch, "rubric.define", written.id, written.version)
        return written

    def get_rubric(self, rubric_id: str) -> RubricDefinition:
        return self._load_rubric(rubric_id)

    def analyze(
        self,
        project_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        rubric_id: str,
        film_ir_id: str,
        intent_ids: Sequence[str] = (),
        parent_id: str | None = None,
        probe_delta: str | None = None,
    ) -> RubricAnalysis:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        rubric = self._load_rubric(rubric_id)
        if rubric.project_id != project_id:
            raise RubricNotFoundError(f"rubric {rubric_id} is not in project {project_id}")
        projection = self.film_ir.get(film_ir_id)
        if projection.project_id != project_id:
            raise EvidenceLinkError("FilmIR project does not match the analysis project")
        resolved_intents: list[str] = []
        for intent_id in intent_ids:
            record = self.intents.get(str(intent_id))
            resolved_intents.append(record.intent.id)
        source_revision_id = projection.source_revision_id
        _, fingerprint = digest_payload(
            {
                "rubric_id": rubric.id,
                "rubric_version": rubric.version,
                "film_ir_id": projection.id,
                "source_revision_id": source_revision_id,
                "intent_ids": resolved_intents,
                "probe_delta": probe_delta or "",
            }
        )
        reused = self._analysis_for_fingerprint(project_id, fingerprint)
        if reused is not None:
            self._audit(principal, acl_epoch, "rubric.repeat", reused.id, fingerprint)
            return reused
        analysis = RubricAnalysis(
            id=f"rba_{new_ulid()}",
            project_id=project_id,
            rubric_id=rubric.id,
            rubric_version=rubric.version,
            film_ir_id=projection.id,
            source_revision_id=source_revision_id,
            intent_ids=tuple(resolved_intents),
            input_fingerprint=fingerprint,
            parent_id=parent_id,
            probe_delta=probe_delta,
        )
        written = self._put_analysis(analysis)
        self._audit(principal, acl_epoch, "rubric.analyze", written.id, fingerprint)
        return written

    def rate_human(
        self,
        analysis_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        criterion: CriterionKind | str,
        score: float,
        evidence_refs: Sequence[str],
        rationale: str,
    ) -> Rating:
        analysis = self.get_analysis(analysis_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.PROPOSE, analysis.project_id, acl_epoch)
        if principal.kind is not PrincipalKind.HUMAN:
            raise OverrideDeniedError("model and integration raters must use rate_model")
        return self._store_rating(
            analysis,
            principal=principal,
            acl_epoch=acl_epoch,
            criterion=_parse_criterion(criterion),
            score=score,
            evidence_refs=evidence_refs,
            rationale=rationale,
            rater_kind=RaterKind.HUMAN,
            model_id=None,
        )

    def rate_model(
        self,
        analysis_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        criterion: CriterionKind | str,
        parent_rating_id: str | None = None,
    ) -> Rating:
        analysis = self.get_analysis(analysis_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.PROPOSE, analysis.project_id, acl_epoch)
        parsed = _parse_criterion(criterion)
        film_ir = self.film_ir.get(analysis.film_ir_id)
        refs = self._default_evidence(film_ir, analysis)
        result = self._generate(
            analysis.project_id,
            principal,
            acl_epoch,
            parsed,
            analysis,
            film_ir,
        )
        rationale = str(result.output.get("text") or "").strip()
        if analysis.probe_delta:
            rationale = f"{rationale} PROBE {analysis.probe_delta}"
        if not rationale:
            raise UnexplainedScoreError("model rating produced an empty rationale")
        score = _score_for(
            {
                "criterion": parsed.value,
                "rationale": rationale,
                "rubric_version": analysis.rubric_version,
                "film_ir_id": analysis.film_ir_id,
                "probe_delta": analysis.probe_delta or "",
                "model": result.provenance.model_version,
            }
        )
        return self._store_rating(
            analysis,
            principal=principal,
            acl_epoch=acl_epoch,
            criterion=parsed,
            score=score,
            evidence_refs=refs,
            rationale=rationale,
            rater_kind=RaterKind.MODEL,
            model_id=result.provenance.model_version,
            parent_rating_id=parent_rating_id,
        )

    def add_counter_evidence(
        self,
        analysis_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        statement: str,
        evidence_refs: Sequence[str],
        rating_id: str | None = None,
        criterion: CriterionKind | str | None = None,
    ) -> CounterEvidence:
        analysis = self.get_analysis(analysis_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.PROPOSE, analysis.project_id, acl_epoch)
        cleaned = statement.strip()
        if not cleaned:
            raise UnexplainedScoreError("counter-evidence requires a statement")
        allowed = self._allowed_refs(analysis)
        refs = tuple(str(item).strip() for item in evidence_refs if str(item).strip())
        self._require_explained(refs, cleaned)
        self._require_known_refs(refs, allowed)
        item = CounterEvidence(
            id=f"rce_{new_ulid()}",
            analysis_id=analysis.id,
            statement=cleaned,
            evidence_refs=refs,
            actor_id=principal.actor_id,
            rating_id=rating_id,
            criterion=_parse_criterion(criterion) if criterion is not None else None,
            created_at=self.clock(),
        )
        written = self._put_counter(item)
        self._attach(analysis.id, counter_id=written.id)
        self._audit(principal, acl_epoch, "rubric.counter_evidence", written.id, analysis.id)
        return written

    def override(
        self,
        analysis_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        criterion: CriterionKind | str,
        score: float,
        evidence_refs: Sequence[str],
        rationale: str,
    ) -> CreatorOverride:
        if principal.kind is not PrincipalKind.HUMAN:
            raise OverrideDeniedError("only a human principal may ACCEPT a creator override")
        analysis = self.get_analysis(analysis_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.ACCEPT, analysis.project_id, acl_epoch)
        parsed = _parse_criterion(criterion)
        self._require_score_range(score)
        refs = tuple(str(item).strip() for item in evidence_refs if str(item).strip())
        cleaned = rationale.strip()
        self._require_explained(refs, cleaned)
        self._require_known_refs(refs, self._allowed_refs(analysis))
        priors = tuple(
            item.id
            for item in self._ratings_for(analysis)
            if item.criterion is parsed
        )
        stored = CreatorOverride(
            id=f"rov_{new_ulid()}",
            analysis_id=analysis.id,
            criterion=parsed,
            score=score,
            evidence_refs=refs,
            rationale=cleaned,
            actor_id=principal.actor_id,
            prior_rating_ids=priors,
            created_at=self.clock(),
            deletes_prior=False,
        )
        written = self._put_override(stored)
        self._attach(analysis.id, override_id=written.id)
        self._audit(principal, acl_epoch, "rubric.override", written.id, parsed.value)
        return written

    def disagreement(
        self,
        analysis_id: str,
        criterion: CriterionKind | str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> DisagreementReport:
        analysis = self.get_analysis(analysis_id, principal=principal, acl_epoch=acl_epoch)
        parsed = _parse_criterion(criterion)
        scores = tuple(
            item.score for item in self._ratings_for(analysis) if item.criterion is parsed
        )
        if len(scores) < 2:
            raise CalibrationError("disagreement requires at least two ratings for a criterion")
        spread = round(max(scores) - min(scores), 6)
        confidence = round(max(0.0, 1.0 - spread), 6)
        return DisagreementReport(
            analysis_id=analysis.id,
            criterion=parsed,
            scores=scores,
            spread=spread,
            confidence=confidence,
            rater_count=len(scores),
        )

    def calibrate(
        self,
        left_analysis_id: str,
        right_analysis_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> CalibrationReport:
        left = self.get_analysis(left_analysis_id, principal=principal, acl_epoch=acl_epoch)
        right = self.get_analysis(right_analysis_id, principal=principal, acl_epoch=acl_epoch)
        left_mean = self._mean_score(left)
        right_mean = self._mean_score(right)
        if left_mean is None or right_mean is None:
            raise CalibrationError("calibration requires ratings on both analyses")
        left_count = len(left.rating_ids)
        right_count = len(right.rating_ids)
        coverage = round(min(left_count, right_count) / max(max(left_count, right_count), 1), 6)
        return CalibrationReport(
            left_analysis_id=left.id,
            right_analysis_id=right.id,
            residual=round(abs(left_mean - right_mean), 6),
            coverage=coverage,
        )

    def adversarial_probe(
        self,
        analysis_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        prompt_delta: str,
    ) -> RubricAnalysis:
        prior = self.get_analysis(analysis_id, principal=principal, acl_epoch=acl_epoch)
        delta = prompt_delta.strip()
        if not delta:
            raise UnexplainedScoreError("adversarial probe requires a prompt delta")
        probed = self.analyze(
            prior.project_id,
            principal=principal,
            acl_epoch=acl_epoch,
            rubric_id=prior.rubric_id,
            film_ir_id=prior.film_ir_id,
            intent_ids=prior.intent_ids,
            parent_id=prior.id,
            probe_delta=delta,
        )
        parent_by_criterion = {
            item.criterion: item.id for item in self._ratings_for(prior)
        }
        for spec in self._load_rubric(prior.rubric_id).criteria:
            parent_id = parent_by_criterion.get(spec.kind)
            self.rate_model(
                probed.id,
                principal=principal,
                acl_epoch=acl_epoch,
                criterion=spec.kind,
                parent_rating_id=parent_id,
            )
        return self.get_analysis(probed.id, principal=principal, acl_epoch=acl_epoch)

    def score_trace(
        self, rating_id: str, *, principal: Principal, acl_epoch: int
    ) -> ScoreTrace:
        rating = self._load_rating(rating_id)
        analysis = self.get_analysis(
            rating.analysis_id, principal=principal, acl_epoch=acl_epoch
        )
        return ScoreTrace(
            rating_id=rating.id,
            analysis_id=analysis.id,
            criterion=rating.criterion,
            score=rating.score,
            film_ir_id=analysis.film_ir_id,
            source_revision_id=analysis.source_revision_id,
            evidence_refs=rating.evidence_refs,
            model_id=rating.model_id,
            rubric_id=rating.rubric_id,
            rubric_version=rating.rubric_version,
            input_fingerprint=rating.input_fingerprint,
            rater_kind=rating.rater_kind,
        )

    def export_summary(
        self, analysis_id: str, *, principal: Principal, acl_epoch: int
    ) -> str:
        analysis = self.get_analysis(analysis_id, principal=principal, acl_epoch=acl_epoch)
        if not analysis.advisory:
            raise AdvisoryLabelError("analysis missing advisory label")
        parts = [
            analysis.disclaimer,
            DISCLAIMER,
            f"ANALYSIS {analysis.id} ADVISORY {analysis.advisory}",
            f"RUBRIC {analysis.rubric_id} VERSION {analysis.rubric_version}",
            f"FILM_IR {analysis.film_ir_id} REVISION {analysis.source_revision_id}",
            f"FINGERPRINT {analysis.input_fingerprint}",
        ]
        for rating in self._ratings_for(analysis):
            parts.append(
                f"RATING {rating.id} {rating.criterion.value}={rating.score} "
                f"rater={rating.rater_kind.value} model={rating.model_id or 'human'} "
                f"version={rating.rubric_version} evidence={','.join(rating.evidence_refs)}"
            )
        for stored in self._overrides_for(analysis):
            parts.append(
                f"OVERRIDE {stored.id} {stored.criterion.value}={stored.score} "
                f"prior={','.join(stored.prior_rating_ids)} deletes_prior={stored.deletes_prior}"
            )
        return "\n".join(parts)

    def get_analysis(
        self, analysis_id: str, *, principal: Principal, acl_epoch: int
    ) -> RubricAnalysis:
        stored = self._load_analysis(analysis_id)
        self._require(principal, Action.READ, stored.project_id, acl_epoch)
        return stored

    def list_analyses(
        self, project_id: str, *, principal: Principal, acl_epoch: int
    ) -> tuple[RubricAnalysis, ...]:
        self._require(principal, Action.READ, project_id, acl_epoch)
        index = load_index(self.workspace)
        ids = list(dict(dict(index.get("by_project", {})).get(project_id, {})).get("analyses", []))
        found: list[RubricAnalysis] = []
        for analysis_id in ids:
            digest = dict(index.get("analysis_digests", {})).get(str(analysis_id))
            if digest is None:
                continue
            found.append(RubricAnalysis.from_dict(load_payload(self.workspace, str(digest))))
        return tuple(found)

    def _store_rating(
        self,
        analysis: RubricAnalysis,
        *,
        principal: Principal,
        acl_epoch: int,
        criterion: CriterionKind,
        score: float,
        evidence_refs: Sequence[str],
        rationale: str,
        rater_kind: RaterKind,
        model_id: str | None,
        parent_rating_id: str | None = None,
    ) -> Rating:
        self._require_score_range(score)
        refs = tuple(str(item).strip() for item in evidence_refs if str(item).strip())
        cleaned = rationale.strip()
        self._require_explained(refs, cleaned)
        self._require_known_refs(refs, self._allowed_refs(analysis))
        _, fingerprint = digest_payload(
            {
                "analysis_id": analysis.id,
                "criterion": criterion.value,
                "score": score,
                "evidence_refs": list(refs),
                "rationale": cleaned,
                "rater_kind": rater_kind.value,
                "model_id": model_id or "",
                "rubric_version": analysis.rubric_version,
                "film_ir_id": analysis.film_ir_id,
                "probe_delta": analysis.probe_delta or "",
            }
        )
        rating = Rating(
            id=f"rrt_{new_ulid()}",
            analysis_id=analysis.id,
            criterion=criterion,
            score=score,
            evidence_refs=refs,
            rationale=cleaned,
            rater_kind=rater_kind,
            rater_id=principal.actor_id,
            rubric_id=analysis.rubric_id,
            rubric_version=analysis.rubric_version,
            confidence=_confidence(len(refs), cleaned),
            input_fingerprint=fingerprint,
            model_id=model_id,
            parent_rating_id=parent_rating_id,
            created_at=self.clock(),
        )
        written = self._put_rating(rating)
        self._attach(analysis.id, rating_id=written.id)
        self._audit(principal, acl_epoch, "rubric.rate", written.id, criterion.value)
        return written

    def _generate(
        self,
        project_id: str,
        principal: Principal,
        acl_epoch: int,
        criterion: CriterionKind,
        analysis: RubricAnalysis,
        film_ir: FilmIR,
    ) -> Any:
        names = ", ".join(entity.canonical_name for entity in film_ir.entities[:8])
        prompt = (
            f"Advisory {criterion.value} reading of FilmIR {film_ir.id} "
            f"revision {film_ir.source_revision_id} entities {names}. "
            f"Rubric {analysis.rubric_id} version {analysis.rubric_version}."
        )
        if analysis.probe_delta:
            prompt = f"{prompt} ADVERSARIAL_DELTA: {analysis.probe_delta}"
        request = ModelRequest(
            capability="generate_text",
            data_classification="internal",
            latency_budget_ms=5000,
            cost_budget=5.0,
            offline_required=False,
            context_tokens=256,
            structured_output=True,
            quality_tier="fast",
            role_contract=RoleContract.EXPERT.value,
            project_id=project_id,
            actor_id=principal.actor_id,
            acl_epoch=acl_epoch,
            permission_snapshot_id=self.identity.permission_snapshot_id(),
            input={"text": prompt, "criterion": criterion.value, "disclaimer": DISCLAIMER},
            consent_granted=True,
        )
        quote = self.router.quote(request)
        return self.router.execute(request, quote_id=quote.id)

    def _allowed_refs(self, analysis: RubricAnalysis) -> set[str]:
        film_ir = self.film_ir.get(analysis.film_ir_id)
        allowed = {
            film_ir.id,
            film_ir.source_revision_id,
            analysis.rubric_id,
            analysis.id,
            *analysis.intent_ids,
        }
        for entity in film_ir.entities:
            allowed.add(entity.id)
            allowed.update(entity.scene_ids)
            allowed.update(entity.mention_block_ids)
        allowed.update(film_ir.scene_order)
        return {item for item in allowed if item}

    def _default_evidence(self, film_ir: FilmIR, analysis: RubricAnalysis) -> tuple[str, ...]:
        refs = [film_ir.id]
        if film_ir.entities:
            refs.append(film_ir.entities[0].id)
        if film_ir.scene_order:
            refs.append(film_ir.scene_order[0])
        refs.extend(analysis.intent_ids[:1])
        return tuple(dict.fromkeys(refs))

    def _require_explained(self, evidence_refs: Sequence[str], rationale: str) -> None:
        if not evidence_refs:
            raise UnexplainedScoreError("score is unexplained without evidence_refs")
        if not rationale.strip():
            raise UnexplainedScoreError("score is unexplained without a rationale")

    def _require_known_refs(self, evidence_refs: Sequence[str], allowed: set[str]) -> None:
        unknown = [item for item in evidence_refs if item not in allowed]
        if unknown:
            raise EvidenceLinkError(f"unknown evidence refs: {', '.join(unknown)}")

    def _require_score_range(self, score: float) -> None:
        if not 0.0 <= score <= 1.0:
            raise UnexplainedScoreError("scores must be within [0.0, 1.0]")

    def _mean_score(self, analysis: RubricAnalysis) -> float | None:
        scores = [item.score for item in self._ratings_for(analysis)]
        if not scores:
            return None
        return round(fmean(scores), 6)

    def _ratings_for(self, analysis: RubricAnalysis) -> tuple[Rating, ...]:
        fresh = self._load_analysis(analysis.id)
        return tuple(self._load_rating(rating_id) for rating_id in fresh.rating_ids)

    def _overrides_for(self, analysis: RubricAnalysis) -> tuple[CreatorOverride, ...]:
        fresh = self._load_analysis(analysis.id)
        index = load_index(self.workspace)
        found: list[CreatorOverride] = []
        for override_id in fresh.override_ids:
            digest = dict(index.get("override_digests", {})).get(override_id)
            if digest is None:
                continue
            found.append(CreatorOverride.from_dict(load_payload(self.workspace, str(digest))))
        return tuple(found)

    def _analysis_for_fingerprint(self, project_id: str, fingerprint: str) -> RubricAnalysis | None:
        index = load_index(self.workspace)
        analysis_id = dict(index.get("by_fingerprint", {})).get(fingerprint)
        if analysis_id is None:
            return None
        digest = dict(index.get("analysis_digests", {})).get(str(analysis_id))
        if digest is None:
            return None
        stored = RubricAnalysis.from_dict(load_payload(self.workspace, str(digest)))
        if stored.project_id != project_id:
            return None
        return stored

    def _load_rubric(self, rubric_id: str) -> RubricDefinition:
        index = load_index(self.workspace)
        digest = dict(index.get("rubric_digests", {})).get(rubric_id)
        if digest is None:
            raise RubricNotFoundError(f"rubric {rubric_id} is not in the index")
        return RubricDefinition.from_dict(load_payload(self.workspace, str(digest)))

    def _load_analysis(self, analysis_id: str) -> RubricAnalysis:
        index = load_index(self.workspace)
        digest = dict(index.get("analysis_digests", {})).get(analysis_id)
        if digest is None:
            raise AnalysisNotFoundError(f"analysis {analysis_id} is not in the index")
        return RubricAnalysis.from_dict(load_payload(self.workspace, str(digest)))

    def _load_rating(self, rating_id: str) -> Rating:
        index = load_index(self.workspace)
        digest = dict(index.get("rating_digests", {})).get(rating_id)
        if digest is None:
            raise RatingNotFoundError(f"rating {rating_id} is not in the index")
        return Rating.from_dict(load_payload(self.workspace, str(digest)))

    def _put_rubric(self, stored: RubricDefinition) -> RubricDefinition:
        def persist(index: dict[str, Any]) -> RubricDefinition:
            digest = put_payload(self.workspace, stored.to_dict())
            ids = list(index.get("rubric_ids", []))
            if stored.id not in ids:
                ids.append(stored.id)
            index["rubric_ids"] = ids
            digests = dict(index.get("rubric_digests", {}))
            digests[stored.id] = digest
            index["rubric_digests"] = digests
            self._project_bucket(index, stored.project_id, "rubrics", stored.id)
            return stored

        return mutate_index(self.workspace, persist)

    def _put_analysis(self, stored: RubricAnalysis) -> RubricAnalysis:
        def persist(index: dict[str, Any]) -> RubricAnalysis:
            digest = put_payload(self.workspace, stored.to_dict())
            ids = list(index.get("analysis_ids", []))
            if stored.id not in ids:
                ids.append(stored.id)
            index["analysis_ids"] = ids
            digests = dict(index.get("analysis_digests", {}))
            digests[stored.id] = digest
            index["analysis_digests"] = digests
            fingerprints = dict(index.get("by_fingerprint", {}))
            fingerprints[stored.input_fingerprint] = stored.id
            index["by_fingerprint"] = fingerprints
            self._project_bucket(index, stored.project_id, "analyses", stored.id)
            return stored

        return mutate_index(self.workspace, persist)

    def _put_rating(self, stored: Rating) -> Rating:
        def persist(index: dict[str, Any]) -> Rating:
            digest = put_payload(self.workspace, stored.to_dict())
            ids = list(index.get("rating_ids", []))
            if stored.id not in ids:
                ids.append(stored.id)
            index["rating_ids"] = ids
            digests = dict(index.get("rating_digests", {}))
            digests[stored.id] = digest
            index["rating_digests"] = digests
            return stored

        return mutate_index(self.workspace, persist)

    def _put_override(self, stored: CreatorOverride) -> CreatorOverride:
        def persist(index: dict[str, Any]) -> CreatorOverride:
            digest = put_payload(self.workspace, stored.to_dict())
            ids = list(index.get("override_ids", []))
            if stored.id not in ids:
                ids.append(stored.id)
            index["override_ids"] = ids
            digests = dict(index.get("override_digests", {}))
            digests[stored.id] = digest
            index["override_digests"] = digests
            return stored

        return mutate_index(self.workspace, persist)

    def _put_counter(self, stored: CounterEvidence) -> CounterEvidence:
        def persist(index: dict[str, Any]) -> CounterEvidence:
            digest = put_payload(self.workspace, stored.to_dict())
            ids = list(index.get("counter_ids", []))
            if stored.id not in ids:
                ids.append(stored.id)
            index["counter_ids"] = ids
            digests = dict(index.get("counter_digests", {}))
            digests[stored.id] = digest
            index["counter_digests"] = digests
            return stored

        return mutate_index(self.workspace, persist)

    def _attach(
        self,
        analysis_id: str,
        *,
        rating_id: str | None = None,
        override_id: str | None = None,
        counter_id: str | None = None,
    ) -> RubricAnalysis:
        def persist(index: dict[str, Any]) -> RubricAnalysis:
            digest = dict(index.get("analysis_digests", {})).get(analysis_id)
            if digest is None:
                raise AnalysisNotFoundError(f"analysis {analysis_id} is not in the index")
            current = RubricAnalysis.from_dict(load_payload(self.workspace, str(digest)))
            ratings = list(current.rating_ids)
            overrides = list(current.override_ids)
            counters = list(current.counter_evidence_ids)
            if rating_id and rating_id not in ratings:
                ratings.append(rating_id)
            if override_id and override_id not in overrides:
                overrides.append(override_id)
            if counter_id and counter_id not in counters:
                counters.append(counter_id)
            updated = RubricAnalysis(
                id=current.id,
                project_id=current.project_id,
                rubric_id=current.rubric_id,
                rubric_version=current.rubric_version,
                film_ir_id=current.film_ir_id,
                source_revision_id=current.source_revision_id,
                intent_ids=current.intent_ids,
                input_fingerprint=current.input_fingerprint,
                rating_ids=tuple(ratings),
                override_ids=tuple(overrides),
                counter_evidence_ids=tuple(counters),
                parent_id=current.parent_id,
                probe_delta=current.probe_delta,
                advisory=current.advisory,
                disclaimer=current.disclaimer,
            )
            new_digest = put_payload(self.workspace, updated.to_dict())
            digests = dict(index.get("analysis_digests", {}))
            digests[updated.id] = new_digest
            index["analysis_digests"] = digests
            return updated

        return mutate_index(self.workspace, persist)

    def _project_bucket(
        self, index: dict[str, Any], project_id: str, key: str, item_id: str
    ) -> None:
        by_project = dict(index.get("by_project", {}))
        bucket = dict(by_project.get(project_id, {}))
        items = list(bucket.get(key, []))
        if item_id not in items:
            items.append(item_id)
        bucket[key] = items
        by_project[project_id] = bucket
        index["by_project"] = by_project

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
            object_kind="rubric",
            object_id=object_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=reason,
        )
