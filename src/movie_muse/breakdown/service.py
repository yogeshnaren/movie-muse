"""Locked-revision production breakdown with evidence, verification, and ChangeSets."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.breakdown.errors import (
    BreakdownNotFoundError,
    ElementNotFoundError,
    ProposalRequiredError,
    StaleBreakdownError,
    UnlockedSourceError,
    UnverifiedEditError,
)
from movie_muse.breakdown.extractors import scan_cues
from movie_muse.breakdown.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.breakdown.thresholds import DECLARED_THRESHOLDS
from movie_muse.breakdown.types import (
    BreakdownElement,
    CompletenessReport,
    ElementKind,
    PendingEdit,
    ScreenplayEvidence,
    StoredBreakdown,
    VerificationState,
)
from movie_muse.compiler.api import CompiledScreenplay, CompilerService
from movie_muse.dependencies.api import DependencyEngine, NodeKind, NodeState
from movie_muse.identity.api import Principal, PrincipalKind
from movie_muse.persistence.api import LocalWorkspace, utc_now
from movie_muse.proposals.api import (
    ImpactSummary,
    ProposalEnvelope,
    ProposalOrigin,
    ProposalService,
)
from movie_muse.revisions.api import RevisionService
from movie_muse.schemas.api import (
    ChangeSet,
    ChangeSetOperation,
    FilmIR,
    FilmIrEntityKind,
    OperationType,
    ProductionProjection,
    ProjectionKind,
    ScreenplayDocument,
    new_id,
    new_ulid,
)


class BreakdownService:
    """Derive production elements from a locked source revision. Edits use ChangeSets."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        audit: AuditLog,
        revisions: RevisionService,
        *,
        compiler: CompilerService | None = None,
        proposals: ProposalService | None = None,
        dependencies: DependencyEngine | None = None,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.audit = audit
        self.revisions = revisions
        self.compiler = compiler or CompilerService()
        self.proposals = proposals
        self.dependencies = dependencies
        self.clock = clock

    def lock_source_revision(
        self,
        *,
        project_id: str,
        revision_id: str,
        principal: Principal,
        acl_epoch: int,
    ) -> str:
        self._require(principal, Action.MANAGE_PRODUCTION_LOCKS, project_id, acl_epoch)
        document = self.revisions.load_revision(revision_id)
        if document.project_id != project_id:
            raise UnlockedSourceError(
                f"revision {revision_id} does not belong to project {project_id}"
            )

        def persist(index: dict[str, Any]) -> str:
            locked = dict(index.get("locked_revisions", {}))
            locked[project_id] = revision_id
            index["locked_revisions"] = locked
            return revision_id

        stored = mutate_index(self.workspace, persist)
        self._audit(principal, acl_epoch, "breakdown.lock_source", stored, project_id)
        return stored

    def derive(
        self,
        *,
        project_id: str,
        revision_id: str,
        principal: Principal,
        acl_epoch: int,
        film_ir: FilmIR | None = None,
    ) -> StoredBreakdown:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        locked = dict(load_index(self.workspace).get("locked_revisions", {})).get(project_id)
        if locked != revision_id:
            raise UnlockedSourceError(
                "derivation requires a locked source revision; call lock_source_revision first"
            )
        document = self.revisions.load_revision(revision_id)
        if document.project_id != project_id:
            raise UnlockedSourceError(
                f"revision {revision_id} does not belong to project {project_id}"
            )
        compiled = self.compiler.compile(document)
        elements = self._elements_from_sources(document, compiled, film_ir, revision_id)
        projection = ProductionProjection(
            id=new_id("production_projection"),
            project_id=project_id,
            kind=ProjectionKind.BREAKDOWN,
            source_revision_id=revision_id,
            computed_at=self.clock(),
            data={
                "element_ids": [item.id for item in elements],
                "locked_revision_id": revision_id,
            },
            is_stale=False,
        )
        stored = StoredBreakdown(
            projection=projection,
            elements=elements,
            locked_revision_id=revision_id,
        )
        stored = self._put_breakdown(stored)
        stored = self._attach_dependency_nodes(stored, principal, acl_epoch)
        self._audit(principal, acl_epoch, "breakdown.derive", stored.projection.id, revision_id)
        return stored

    def get_breakdown(
        self,
        breakdown_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> StoredBreakdown:
        stored = self._load(breakdown_id)
        self._require(principal, Action.READ, stored.projection.project_id, acl_epoch)
        return self._with_freshness(stored, principal, acl_epoch)

    def list_breakdowns(
        self,
        project_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> tuple[StoredBreakdown, ...]:
        self._require(principal, Action.READ, project_id, acl_epoch)
        index = load_index(self.workspace)
        found: list[StoredBreakdown] = []
        for breakdown_id in dict(index.get("by_project", {})).get(project_id, ()):
            digest = dict(index.get("breakdown_digests", {})).get(str(breakdown_id))
            if digest is None:
                continue
            stored = StoredBreakdown.from_dict(load_payload(self.workspace, str(digest)))
            found.append(self._with_freshness(stored, principal, acl_epoch))
        return tuple(found)

    def verify_element(
        self,
        breakdown_id: str,
        element_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        state: VerificationState = VerificationState.VERIFIED,
        notes: str = "",
    ) -> StoredBreakdown:
        if principal.kind is not PrincipalKind.HUMAN:
            raise UnverifiedEditError("only a human principal may verify breakdown elements")
        stored = self.get_breakdown(breakdown_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.ACCEPT, stored.projection.project_id, acl_epoch)
        if stored.labeled_stale:
            raise StaleBreakdownError("stale breakdown is not current; re-derive after rebind")
        element = self._element(stored, element_id)
        if state is VerificationState.DERIVED:
            raise UnverifiedEditError("verification cannot return an element to derived")
        updated = BreakdownElement(
            id=element.id,
            kind=element.kind,
            name=element.name,
            verification=state,
            evidence=element.evidence,
            quantity=element.quantity,
            notes=notes if notes else element.notes,
            verified_by_actor_id=principal.actor_id,
            change_set_id=element.change_set_id,
        )
        written = self._replace_element(stored, updated)
        self._audit(principal, acl_epoch, "breakdown.verify", element_id, state.value)
        return written

    def propose_edit(
        self,
        breakdown_id: str,
        element_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        name: str | None = None,
        quantity: int | None = None,
        notes: str | None = None,
    ) -> ProposalEnvelope:
        if self.proposals is None:
            raise ProposalRequiredError("breakdown edits require ProposalService")
        stored = self.get_breakdown(breakdown_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.PROPOSE, stored.projection.project_id, acl_epoch)
        if stored.labeled_stale:
            raise StaleBreakdownError("stale breakdown is not current; re-derive after rebind")
        element = self._element(stored, element_id)
        head = self.revisions.canon_branch().head_revision_id
        document = self.revisions.load_revision(head)
        patch = PendingEdit(
            proposal_id="",
            breakdown_id=stored.projection.id,
            element_id=element.id,
            name=name,
            quantity=quantity,
            notes=notes,
        )
        change_set = ChangeSet(
            id=new_id("change_set"),
            base_revision_id=head,
            author_actor_id=principal.actor_id,
            created_at=self.clock(),
            operations=(
                ChangeSetOperation(
                    id=f"cop_{new_ulid()}",
                    order=0,
                    op_type=OperationType.UPDATE_METADATA,
                    target_id=document.id,
                    payload={"title": document.title},
                ),
            ),
        )
        envelope = self.proposals.submit(
            change_set,
            principal=principal,
            acl_epoch=acl_epoch,
            project_id=stored.projection.project_id,
            intent="breakdown.edit",
            rationale_summary=(
                f"breakdown element {element.id} kind={element.kind.value} "
                f"name={name if name is not None else element.name} "
                f"quantity={quantity if quantity is not None else element.quantity}"
            ),
            provenance=f"breakdown:{stored.projection.id}:element:{element.id}",
            origin=ProposalOrigin.HUMAN,
            impact=ImpactSummary(production=(stored.projection.id, element.id)),
            evidence_ids=tuple(item.block_id for item in element.evidence),
        )
        pending = PendingEdit(
            proposal_id=envelope.proposal.id,
            breakdown_id=patch.breakdown_id,
            element_id=patch.element_id,
            name=patch.name,
            quantity=patch.quantity,
            notes=patch.notes,
        )

        def persist(index: dict[str, Any]) -> None:
            edits = dict(index.get("pending_edits", {}))
            edits[pending.proposal_id] = pending.to_dict()
            index["pending_edits"] = edits

        mutate_index(self.workspace, persist)
        self._audit(
            principal, acl_epoch, "breakdown.propose_edit", envelope.proposal.id, element_id
        )
        return envelope

    def accept_edit(
        self,
        proposal_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        branch_ref: str | None = None,
    ) -> StoredBreakdown:
        if self.proposals is None:
            raise ProposalRequiredError("breakdown edits require ProposalService")
        if principal.kind is not PrincipalKind.HUMAN:
            raise UnverifiedEditError("only a human principal may accept breakdown edits")
        index = load_index(self.workspace)
        raw = dict(index.get("pending_edits", {})).get(proposal_id)
        if raw is None:
            raise ProposalRequiredError(f"no pending breakdown edit for proposal {proposal_id}")
        pending = PendingEdit.from_dict(raw)
        stored = self.get_breakdown(
            pending.breakdown_id, principal=principal, acl_epoch=acl_epoch
        )
        self._require(principal, Action.ACCEPT, stored.projection.project_id, acl_epoch)
        if stored.labeled_stale:
            raise StaleBreakdownError("stale breakdown is not current; re-derive after rebind")
        result = self.proposals.accept(
            proposal_id, principal=principal, acl_epoch=acl_epoch, branch_ref=branch_ref
        )
        element = self._element(stored, pending.element_id)
        updated = BreakdownElement(
            id=element.id,
            kind=element.kind,
            name=pending.name if pending.name is not None else element.name,
            verification=element.verification,
            evidence=element.evidence,
            quantity=pending.quantity if pending.quantity is not None else element.quantity,
            notes=pending.notes if pending.notes is not None else element.notes,
            verified_by_actor_id=element.verified_by_actor_id,
            change_set_id=result.proposal.change_set.id,
        )
        written = self._replace_element(stored, updated)

        def clear(index_payload: dict[str, Any]) -> None:
            edits = dict(index_payload.get("pending_edits", {}))
            edits.pop(proposal_id, None)
            index_payload["pending_edits"] = edits

        mutate_index(self.workspace, clear)
        self._audit(principal, acl_epoch, "breakdown.accept_edit", proposal_id, updated.id)
        return written

    def completeness_report(
        self,
        breakdown_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> CompletenessReport:
        stored = self.get_breakdown(breakdown_id, principal=principal, acl_epoch=acl_epoch)
        document = self.revisions.load_revision(stored.locked_revision_id)
        valid_ids = {block.id for block in document.blocks}
        derived_count = 0
        verified_count = 0
        not_applicable_count = 0
        reviewed = 0
        accurate = 0
        linked = 0
        total = len(stored.elements)
        for element in stored.elements:
            if element.verification is VerificationState.DERIVED:
                derived_count += 1
            elif element.verification is VerificationState.VERIFIED:
                verified_count += 1
                reviewed += 1
            elif element.verification is VerificationState.NOT_APPLICABLE:
                not_applicable_count += 1
                reviewed += 1
            else:
                reviewed += 1
            if element.evidence and all(item.block_id in valid_ids for item in element.evidence):
                accurate += 1
                linked += 1
        completeness = 1.0 if total == 0 else reviewed / total
        accuracy = 1.0 if total == 0 else accurate / total
        evidence_link_rate = 1.0 if total == 0 else linked / total
        meets = (
            completeness >= DECLARED_THRESHOLDS["completeness"]
            and accuracy >= DECLARED_THRESHOLDS["accuracy"]
            and evidence_link_rate >= DECLARED_THRESHOLDS["evidence_link_rate"]
        )
        return CompletenessReport(
            completeness=completeness,
            accuracy=accuracy,
            evidence_link_rate=evidence_link_rate,
            derived_count=derived_count,
            verified_count=verified_count,
            not_applicable_count=not_applicable_count,
            meets_thresholds=meets,
            current=not stored.labeled_stale,
            labeled_stale=stored.labeled_stale,
        )

    def require_complete(
        self,
        breakdown_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> CompletenessReport:
        report = self.completeness_report(
            breakdown_id, principal=principal, acl_epoch=acl_epoch
        )
        if report.labeled_stale or not report.current:
            raise StaleBreakdownError("stale breakdown is not current")
        if not report.meets_thresholds:
            raise UnverifiedEditError(
                "human verification is required before the breakdown is complete"
            )
        return report

    def notify_source_changed(
        self,
        project_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        breakdown_id: str | None = None,
    ) -> tuple[str, ...]:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        targets = (
            (self.get_breakdown(breakdown_id, principal=principal, acl_epoch=acl_epoch),)
            if breakdown_id
            else self.list_breakdowns(project_id, principal=principal, acl_epoch=acl_epoch)
        )
        stale_ids: list[str] = []
        for stored in targets:
            if self.dependencies is not None and stored.config_node_id:
                self.dependencies.invalidate_inputs(
                    [stored.config_node_id],
                    principal=principal,
                    acl_epoch=acl_epoch,
                )
            marked = self._put_breakdown(
                self._with_projection_stale(
                    StoredBreakdown(
                        projection=stored.projection,
                        elements=stored.elements,
                        locked_revision_id=stored.locked_revision_id,
                        config_node_id=stored.config_node_id,
                        analysis_node_id=stored.analysis_node_id,
                        labeled_stale=True,
                    ),
                    stale=True,
                )
            )
            stale_ids.append(marked.projection.id)
        self._audit(
            principal, acl_epoch, "breakdown.notify_source_changed", project_id, ",".join(stale_ids)
        )
        return tuple(stale_ids)

    def _elements_from_sources(
        self,
        document: ScreenplayDocument,
        compiled: CompiledScreenplay,
        film_ir: FilmIR | None,
        locked_revision_id: str,
    ) -> tuple[BreakdownElement, ...]:
        by_key: dict[tuple[ElementKind, str], BreakdownElement] = {}
        for entity in compiled.entities:
            kind = {
                "character": ElementKind.CAST,
                "location": ElementKind.LOCATION,
                "prop": ElementKind.PROP,
            }.get(entity.kind)
            if kind is None:
                continue
            evidence = self._evidence(document, entity.mention_block_ids)
            self._upsert_element(by_key, kind, entity.canonical_name, evidence)
        for scene in compiled.scenes:
            if not scene.time_of_day:
                continue
            evidence = self._evidence(document, (scene.heading_block_id,))
            self._upsert_element(by_key, ElementKind.TIMING, scene.time_of_day, evidence)
        if film_ir is not None and film_ir.source_revision_id in {
            compiled.source_revision_id,
            locked_revision_id,
        }:
            for film_entity in film_ir.entities:
                if film_entity.kind is not FilmIrEntityKind.PROP:
                    continue
                evidence = self._evidence(document, film_entity.mention_block_ids)
                self._upsert_element(
                    by_key, ElementKind.PROP, film_entity.canonical_name, evidence
                )
        for kind, hits in scan_cues(document).items():
            grouped: dict[str, list[ScreenplayEvidence]] = {}
            for cue, block in hits:
                grouped.setdefault(cue, []).append(
                    ScreenplayEvidence(
                        block_id=block.id,
                        scene_id=block.scene_id,
                        excerpt=block.text[:240],
                    )
                )
            for cue, evidence_items in grouped.items():
                self._upsert_element(by_key, kind, cue, tuple(evidence_items))
        return tuple(
            sorted(by_key.values(), key=lambda item: (item.kind.value, item.name, item.id))
        )

    def _upsert_element(
        self,
        by_key: dict[tuple[ElementKind, str], BreakdownElement],
        kind: ElementKind,
        name: str,
        evidence: tuple[ScreenplayEvidence, ...],
    ) -> None:
        cleaned = name.strip()
        if not cleaned:
            return
        key = (kind, cleaned.casefold())
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = BreakdownElement(
                id=f"bke_{new_ulid()}",
                kind=kind,
                name=cleaned,
                verification=VerificationState.DERIVED,
                evidence=evidence,
            )
            return
        seen = {item.block_id for item in existing.evidence}
        merged = list(existing.evidence)
        for item in evidence:
            if item.block_id not in seen:
                merged.append(item)
                seen.add(item.block_id)
        by_key[key] = BreakdownElement(
            id=existing.id,
            kind=existing.kind,
            name=existing.name,
            verification=existing.verification,
            evidence=tuple(merged),
            quantity=existing.quantity,
            notes=existing.notes,
            verified_by_actor_id=existing.verified_by_actor_id,
            change_set_id=existing.change_set_id,
        )

    def _evidence(
        self, document: ScreenplayDocument, block_ids: tuple[str, ...]
    ) -> tuple[ScreenplayEvidence, ...]:
        by_id = {block.id: block for block in document.blocks}
        items: list[ScreenplayEvidence] = []
        seen: set[str] = set()
        for block_id in block_ids:
            if block_id in seen:
                continue
            block = by_id.get(block_id)
            if block is None:
                continue
            seen.add(block_id)
            items.append(
                ScreenplayEvidence(
                    block_id=block.id,
                    scene_id=block.scene_id,
                    excerpt=block.text[:240],
                )
            )
        return tuple(items)

    def _element(self, stored: StoredBreakdown, element_id: str) -> BreakdownElement:
        for element in stored.elements:
            if element.id == element_id:
                return element
        raise ElementNotFoundError(
            f"element {element_id} is not on breakdown {stored.projection.id}"
        )

    def _replace_element(
        self, stored: StoredBreakdown, updated: BreakdownElement
    ) -> StoredBreakdown:
        elements = tuple(
            updated if item.id == updated.id else item for item in stored.elements
        )
        projection_data = dict(stored.projection.data)
        projection_data["element_ids"] = [item.id for item in elements]
        payload = stored.projection.to_dict()
        payload["data"] = projection_data
        rewritten = StoredBreakdown(
            projection=ProductionProjection.from_dict(payload),
            elements=elements,
            locked_revision_id=stored.locked_revision_id,
            config_node_id=stored.config_node_id,
            analysis_node_id=stored.analysis_node_id,
            labeled_stale=stored.labeled_stale,
        )
        return self._put_breakdown(rewritten)

    def _attach_dependency_nodes(
        self,
        stored: StoredBreakdown,
        principal: Principal,
        acl_epoch: int,
    ) -> StoredBreakdown:
        if self.dependencies is None:
            return stored
        config = self.dependencies.add_node(
            project_id=stored.projection.project_id,
            kind=NodeKind.CONFIGURATION,
            principal=principal,
            acl_epoch=acl_epoch,
            subject_id=stored.projection.id,
        )
        analysis = self.dependencies.add_node(
            project_id=stored.projection.project_id,
            kind=NodeKind.DERIVED_PROJECTION,
            principal=principal,
            acl_epoch=acl_epoch,
            input_ids=(config.id,),
            subject_id=stored.projection.id,
        )
        rewritten = StoredBreakdown(
            projection=stored.projection,
            elements=stored.elements,
            locked_revision_id=stored.locked_revision_id,
            config_node_id=config.id,
            analysis_node_id=analysis.id,
            labeled_stale=False,
        )
        return self._put_breakdown(rewritten)

    def _with_freshness(
        self, stored: StoredBreakdown, principal: Principal, acl_epoch: int
    ) -> StoredBreakdown:
        labeled = stored.labeled_stale
        if self.dependencies is not None and stored.analysis_node_id:
            view = self.dependencies.view_node(
                stored.analysis_node_id, principal=principal, acl_epoch=acl_epoch
            )
            labeled = labeled or view.state is NodeState.STALE
        if labeled == stored.labeled_stale and stored.projection.is_stale == labeled:
            return stored
        rewritten = self._with_projection_stale(
            StoredBreakdown(
                projection=stored.projection,
                elements=stored.elements,
                locked_revision_id=stored.locked_revision_id,
                config_node_id=stored.config_node_id,
                analysis_node_id=stored.analysis_node_id,
                labeled_stale=labeled,
            ),
            stale=labeled,
        )
        return self._put_breakdown(rewritten)

    def _with_projection_stale(self, stored: StoredBreakdown, *, stale: bool) -> StoredBreakdown:
        payload = stored.projection.to_dict()
        payload["is_stale"] = stale
        return StoredBreakdown(
            projection=ProductionProjection.from_dict(payload),
            elements=stored.elements,
            locked_revision_id=stored.locked_revision_id,
            config_node_id=stored.config_node_id,
            analysis_node_id=stored.analysis_node_id,
            labeled_stale=stale,
        )

    def _load(self, breakdown_id: str) -> StoredBreakdown:
        index = load_index(self.workspace)
        digest = dict(index.get("breakdown_digests", {})).get(breakdown_id)
        if digest is None:
            raise BreakdownNotFoundError(f"breakdown {breakdown_id} is not in the index")
        return StoredBreakdown.from_dict(load_payload(self.workspace, str(digest)))

    def _put_breakdown(self, stored: StoredBreakdown) -> StoredBreakdown:
        def persist(index: dict[str, Any]) -> StoredBreakdown:
            digest = put_payload(self.workspace, stored.to_dict())
            ids = list(index.get("breakdown_ids", []))
            if stored.projection.id not in ids:
                ids.append(stored.projection.id)
            index["breakdown_ids"] = ids
            digests = dict(index.get("breakdown_digests", {}))
            digests[stored.projection.id] = digest
            index["breakdown_digests"] = digests
            by_project = dict(index.get("by_project", {}))
            project_ids = list(by_project.get(stored.projection.project_id, []))
            if stored.projection.id not in project_ids:
                project_ids.append(stored.projection.id)
            by_project[stored.projection.project_id] = project_ids
            index["by_project"] = by_project
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
            object_kind="production_projection",
            object_id=object_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=reason,
        )
