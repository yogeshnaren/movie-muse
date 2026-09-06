"""Assemble tenant-isolated, citation-bearing context without calling a model."""

from __future__ import annotations

from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.context.budget import bundle_counts, fit_segments
from movie_muse.context.errors import (
    BranchIsolationError,
    StaleCanonError,
    TenantIsolationError,
)
from movie_muse.context.types import (
    BoundState,
    ContextBundle,
    ContextRequest,
    ContextSegment,
    Freshness,
    SegmentKind,
    SegmentRights,
)
from movie_muse.identity.api import Principal
from movie_muse.persistence.api import utc_now
from movie_muse.retrieval.api import RetrievalService
from movie_muse.revisions.api import RevisionService
from movie_muse.rights.api import PermittedUse, SourceClassification, SourceValidationState
from movie_muse.schemas.api import (
    AuthoredFact,
    CreativeIntentIR,
    InferredClaim,
    OperationalAssumption,
    ProjectMemory,
    ScenarioOutput,
    ScreenplayDocument,
    StructuralFact,
    new_ulid,
)

_PROJECT_CANON_RIGHTS = SegmentRights(
    classification=SourceClassification.USER_OWNED,
    permitted_uses=(PermittedUse.RETRIEVAL, PermittedUse.CITATION),
    rights_record_id=None,
    validation_state=SourceValidationState.VALIDATED,
    license_summary="project-owned canon",
)

_KIND_BY_TYPE = {
    AuthoredFact: SegmentKind.AUTHORED_FACT,
    StructuralFact: SegmentKind.STRUCTURAL_FACT,
    InferredClaim: SegmentKind.INFERRED_CLAIM,
    OperationalAssumption: SegmentKind.OPERATIONAL_ASSUMPTION,
    ScenarioOutput: SegmentKind.SCENARIO_OUTPUT,
}


class ContextService:
    """Token/model-independent context builder over current revisions."""

    def __init__(
        self,
        revisions: RevisionService,
        retrieval: RetrievalService,
        authorization: AuthorizationService,
    ) -> None:
        self.revisions = revisions
        self.retrieval = retrieval
        self.authorization = authorization

    def assemble(self, request: ContextRequest) -> ContextBundle:
        self._require(
            request.principal,
            Action.READ,
            request.project_id,
            request.acl_epoch,
        )
        branch = self.revisions.get_branch(request.branch_id)
        if branch.project_id != request.project_id:
            raise TenantIsolationError(
                f"branch {branch.id} belongs to {branch.project_id}, not {request.project_id}"
            )
        if branch.id != request.branch_id and branch.name != request.branch_id:
            raise BranchIsolationError(f"branch ref {request.branch_id} resolved incorrectly")
        head_id = branch.head_revision_id
        if (
            request.expected_revision_id is not None
            and request.expected_revision_id != head_id
        ):
            raise StaleCanonError(
                f"expected revision {request.expected_revision_id} but branch head is {head_id}"
            )
        document = self.revisions.load_revision(head_id)
        if document.project_id != request.project_id:
            raise TenantIsolationError("revision document belongs to another project")
        if document.base_revision_id != head_id:
            raise StaleCanonError("stored revision blob is not the live branch head")
        as_of = utc_now()
        freshness = Freshness(
            revision_id=head_id,
            expected_revision_id=request.expected_revision_id,
            as_of=as_of,
        )
        candidates: list[ContextSegment] = []
        candidates.extend(
            self._revision_segments(document, request.project_id, branch.id, freshness)
        )
        for memory in request.memories:
            candidates.append(
                self._memory_segment(memory, request.project_id, branch.id, freshness)
            )
        for intent in request.intents:
            candidates.append(
                self._intent_segment(
                    intent, request.project_id, branch.id, freshness, head_id
                )
            )
        for bound in request.states:
            if bound.branch_id not in {request.branch_id, branch.id}:
                raise BranchIsolationError(
                    f"typed state belongs to branch {bound.branch_id}, not {branch.id}"
                )
            candidates.append(
                self._state_segment(
                    bound, request.project_id, branch.id, freshness, head_id
                )
            )
        if request.retrieval_query:
            for hit in self.retrieval.retrieve(
                project_id=request.project_id,
                query=request.retrieval_query,
                principal=request.principal,
                acl_epoch=request.acl_epoch,
            ):
                if hit.project_id != request.project_id:
                    raise TenantIsolationError("retrieved segment crossed project boundary")
                candidates.append(
                    ContextSegment(
                        id=f"ctxseg_{new_ulid()}",
                        kind=SegmentKind.REFERENCE,
                        text=hit.text,
                        project_id=request.project_id,
                        branch_id=branch.id,
                        revision_id=head_id,
                        source_id=hit.source_id,
                        source_ids=hit.source_ids,
                        rights=SegmentRights(
                            classification=hit.citation.classification,
                            permitted_uses=hit.citation.permitted_uses,
                            rights_record_id=hit.citation.rights_record_id,
                            validation_state=hit.citation.validation_state,
                            license_summary=hit.citation.license_summary,
                        ),
                        citation=hit.citation,
                        freshness=freshness,
                        redacted=hit.redacted,
                        untrusted=True,
                    )
                )
        fitted = fit_segments(candidates, request.budget)
        for segment in fitted:
            self._assert_segment_bound(segment, request.project_id, branch.id, head_id)
        chars, nbytes = bundle_counts(fitted)
        return ContextBundle(
            id=f"ctx_{new_ulid()}",
            project_id=request.project_id,
            branch_id=branch.id,
            revision_id=head_id,
            assembled_at=as_of,
            segments=fitted,
            char_count=chars,
            byte_count=nbytes,
        )

    def _revision_segments(
        self,
        document: ScreenplayDocument,
        project_id: str,
        branch_id: str,
        freshness: Freshness,
    ) -> list[ContextSegment]:
        segments: list[ContextSegment] = []
        for block in document.blocks:
            if not block.text:
                continue
            source_ids = (document.id, block.id, freshness.revision_id)
            segments.append(
                ContextSegment(
                    id=f"ctxseg_{new_ulid()}",
                    kind=SegmentKind.REVISION,
                    text=block.text,
                    project_id=project_id,
                    branch_id=branch_id,
                    revision_id=freshness.revision_id,
                    source_id=block.id,
                    source_ids=source_ids,
                    rights=_PROJECT_CANON_RIGHTS,
                    citation=None,
                    freshness=freshness,
                    redacted=False,
                    untrusted=False,
                    epistemic_level="authored",
                )
            )
        return segments

    def _memory_segment(
        self,
        memory: ProjectMemory,
        project_id: str,
        branch_id: str,
        freshness: Freshness,
    ) -> ContextSegment:
        if memory.project_id != project_id:
            raise TenantIsolationError(
                f"project memory {memory.id} belongs to {memory.project_id}"
            )
        return ContextSegment(
            id=f"ctxseg_{new_ulid()}",
            kind=SegmentKind.MEMORY,
            text=memory.summary,
            project_id=project_id,
            branch_id=branch_id,
            revision_id=freshness.revision_id,
            source_id=memory.id,
            source_ids=(memory.id, project_id),
            rights=_PROJECT_CANON_RIGHTS,
            citation=None,
            freshness=freshness,
            redacted=False,
            untrusted=False,
        )

    def _intent_segment(
        self,
        intent: CreativeIntentIR,
        project_id: str,
        branch_id: str,
        freshness: Freshness,
        head_id: str,
    ) -> ContextSegment:
        if intent.project_id != project_id:
            raise TenantIsolationError(
                f"creative intent {intent.id} belongs to {intent.project_id}"
            )
        if intent.revision_id != head_id:
            raise StaleCanonError(
                f"creative intent {intent.id} is bound to stale revision {intent.revision_id}"
            )
        parts = [intent.statement, *intent.exceptions, *intent.anti_rules]
        return ContextSegment(
            id=f"ctxseg_{new_ulid()}",
            kind=SegmentKind.INTENT,
            text="\n".join(part for part in parts if part),
            project_id=project_id,
            branch_id=branch_id,
            revision_id=head_id,
            source_id=intent.id,
            source_ids=(intent.id, intent.revision_id),
            rights=_PROJECT_CANON_RIGHTS,
            citation=None,
            freshness=freshness,
            redacted=False,
            untrusted=False,
        )

    def _state_segment(
        self,
        bound: BoundState,
        project_id: str,
        branch_id: str,
        freshness: Freshness,
        head_id: str,
    ) -> ContextSegment:
        if bound.project_id != project_id:
            raise TenantIsolationError(
                f"typed state belongs to {bound.project_id}, not {project_id}"
            )
        payload = bound.payload
        kind = _KIND_BY_TYPE[type(payload)]
        if isinstance(payload, AuthoredFact) and payload.source_revision_id != head_id:
            raise StaleCanonError(
                f"authored fact {payload.id} is bound to stale revision"
            )
        if isinstance(payload, StructuralFact) and payload.derived_from_revision_id != head_id:
            raise StaleCanonError(
                f"structural fact {payload.id} is bound to stale revision"
            )
        if (
            isinstance(payload, OperationalAssumption)
            and payload.valid_until_revision_id is not None
            and payload.valid_until_revision_id != head_id
        ):
            raise StaleCanonError(
                f"operational assumption {payload.id} expired at {payload.valid_until_revision_id}"
            )
        text = f"{payload.attribute}={payload.value}"
        return ContextSegment(
            id=f"ctxseg_{new_ulid()}",
            kind=kind,
            text=text,
            project_id=project_id,
            branch_id=branch_id,
            revision_id=head_id,
            source_id=payload.id,
            source_ids=(payload.id, bound.project_id, branch_id),
            rights=_PROJECT_CANON_RIGHTS,
            citation=None,
            freshness=freshness,
            redacted=False,
            untrusted=kind
            in {SegmentKind.INFERRED_CLAIM, SegmentKind.SCENARIO_OUTPUT},
            epistemic_level=payload.kind.value,
        )

    def _assert_segment_bound(
        self,
        segment: ContextSegment,
        project_id: str,
        branch_id: str,
        revision_id: str,
    ) -> None:
        if segment.project_id != project_id:
            raise TenantIsolationError("assembled segment crossed project boundary")
        if segment.branch_id != branch_id:
            raise BranchIsolationError("assembled segment crossed branch boundary")
        if segment.revision_id != revision_id:
            raise StaleCanonError("assembled segment is not bound to the live head")
        if not segment.source_ids:
            raise StaleCanonError("assembled segment dropped its source ids")

    def _require(
        self, principal: Principal, action: Action, project_id: str, acl_epoch: int
    ) -> None:
        self.authorization.require(
            principal,
            action,
            self.authorization.resource_for_project(project_id),
            acl_epoch=acl_epoch,
        )
