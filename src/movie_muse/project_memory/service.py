"""Permissioned project-memory capture, search, and reviewed promotion."""

from __future__ import annotations

import re
from typing import Any

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.identity.api import Principal, PrincipalKind
from movie_muse.persistence.api import LocalWorkspace, utc_now
from movie_muse.project_memory.errors import (
    AutoPromoteError,
    CandidateClosedError,
    CandidateNotFoundError,
    DuplicateCandidateError,
    HumanRequiredError,
    UnpromotableKindError,
)
from movie_muse.project_memory.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.project_memory.types import (
    PROMOTABLE_KINDS,
    MemoryCandidate,
    MemoryCandidateKind,
    MemoryStatus,
    ProvenanceEntry,
)
from movie_muse.schemas.api import ProjectMemory, new_id, new_ulid

_TOKEN = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _tokens(text: str) -> frozenset[str]:
    return frozenset(match.group(0).lower() for match in _TOKEN.finditer(text))


def _normalize(summary: str) -> str:
    return " ".join(summary.casefold().split())


class ProjectMemoryService:
    """Candidates stay candidates until a human promotes them into ProjectMemory."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        audit: AuditLog,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.audit = audit

    def capture(
        self,
        *,
        project_id: str,
        kind: MemoryCandidateKind,
        summary: str,
        principal: Principal,
        acl_epoch: int,
        branch_id: str,
        revision_id: str,
        source_collaboration_event_id: str | None = None,
        link_url: str | None = None,
        artifact_id: str | None = None,
        rights_record_id: str | None = None,
        supersede_id: str | None = None,
        auto_promote: bool = False,
    ) -> MemoryCandidate:
        if auto_promote:
            raise AutoPromoteError("candidate memory never becomes canon automatically")
        if kind is MemoryCandidateKind.REJECTED_IDEA:
            status = MemoryStatus.REJECTED
        else:
            status = MemoryStatus.CAPTURED
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        now = utc_now()
        candidate = MemoryCandidate(
            id=f"pmc_{new_ulid()}",
            project_id=project_id,
            kind=kind,
            summary=summary,
            status=status,
            branch_id=branch_id,
            revision_id=revision_id,
            captured_by_actor_id=principal.actor_id,
            captured_at=now,
            provenance=(
                ProvenanceEntry(
                    actor_id=principal.actor_id,
                    operation="capture",
                    created_at=now,
                    note=kind.value,
                ),
            ),
            source_collaboration_event_id=source_collaboration_event_id,
            link_url=link_url,
            artifact_id=artifact_id,
            rights_record_id=rights_record_id,
            conflict_of_id=supersede_id,
        )
        stored = self._persist_new(candidate, principal=principal, supersede_id=supersede_id)
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation="project_memory.capture",
            object_kind="memory_candidate",
            object_id=stored.id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=f"{kind.value}:{status.value}",
        )
        return stored

    def edit(
        self,
        candidate_id: str,
        *,
        summary: str,
        principal: Principal,
        acl_epoch: int,
        revision_id: str | None = None,
    ) -> MemoryCandidate:
        current = self.get_candidate(candidate_id)
        self._require(principal, Action.PROPOSE, current.project_id, acl_epoch)
        if current.status is not MemoryStatus.CAPTURED:
            raise CandidateClosedError(f"candidate {candidate_id} is {current.status.value}")
        now = utc_now()
        updated = MemoryCandidate(
            id=current.id,
            project_id=current.project_id,
            kind=current.kind,
            summary=summary,
            status=MemoryStatus.CAPTURED,
            branch_id=current.branch_id,
            revision_id=revision_id or current.revision_id,
            captured_by_actor_id=current.captured_by_actor_id,
            captured_at=current.captured_at,
            provenance=(
                *current.provenance,
                ProvenanceEntry(
                    actor_id=principal.actor_id,
                    operation="edit",
                    created_at=now,
                    note=f"from {current.summary}",
                ),
            ),
            previous_id=current.previous_id,
            source_collaboration_event_id=current.source_collaboration_event_id,
            link_url=current.link_url,
            artifact_id=current.artifact_id,
            rights_record_id=current.rights_record_id,
            conflict_of_id=current.conflict_of_id,
        )

        def persist(index: dict[str, Any]) -> MemoryCandidate:
            self._put_candidate(index, updated)
            return updated

        stored = mutate_index(self.workspace, persist)
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation="project_memory.edit",
            object_kind="memory_candidate",
            object_id=stored.id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=f"previous={current.id}",
        )
        return stored

    def promote(
        self,
        candidate_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> ProjectMemory:
        if principal.kind is not PrincipalKind.HUMAN:
            raise HumanRequiredError("only a human principal may promote project memory")
        candidate = self.get_candidate(candidate_id)
        self._require(principal, Action.ACCEPT, candidate.project_id, acl_epoch)
        if candidate.status is not MemoryStatus.CAPTURED:
            raise CandidateClosedError(f"candidate {candidate_id} is {candidate.status.value}")
        mapped = PROMOTABLE_KINDS.get(candidate.kind)
        if mapped is None:
            raise UnpromotableKindError(
                f"{candidate.kind.value} cannot become a schema ProjectMemory record"
            )
        now = utc_now()
        memory = ProjectMemory(
            id=new_id("project_memory"),
            project_id=candidate.project_id,
            kind=mapped,
            summary=candidate.summary,
            reviewed_by_actor_id=principal.actor_id,
            reviewed_at=now,
            source_collaboration_event_id=candidate.source_collaboration_event_id,
        )
        closed = MemoryCandidate(
            id=candidate.id,
            project_id=candidate.project_id,
            kind=candidate.kind,
            summary=candidate.summary,
            status=MemoryStatus.PROMOTED,
            branch_id=candidate.branch_id,
            revision_id=candidate.revision_id,
            captured_by_actor_id=candidate.captured_by_actor_id,
            captured_at=candidate.captured_at,
            provenance=(
                *candidate.provenance,
                ProvenanceEntry(
                    actor_id=principal.actor_id,
                    operation="promote",
                    created_at=now,
                    note=memory.id,
                ),
            ),
            previous_id=candidate.previous_id,
            source_collaboration_event_id=candidate.source_collaboration_event_id,
            link_url=candidate.link_url,
            artifact_id=candidate.artifact_id,
            rights_record_id=candidate.rights_record_id,
            promoted_memory_id=memory.id,
            conflict_of_id=candidate.conflict_of_id,
        )

        def persist(index: dict[str, Any]) -> ProjectMemory:
            self._put_candidate(index, closed)
            digest = put_payload(self.workspace, memory.to_dict())
            memories = dict(index["memory_digests"])
            memories[memory.id] = digest
            index["memory_digests"] = memories
            by_project = dict(index["memory_ids_by_project"])
            ids = list(by_project.get(memory.project_id, []))
            ids.append(memory.id)
            by_project[memory.project_id] = ids
            index["memory_ids_by_project"] = by_project
            return memory

        stored = mutate_index(self.workspace, persist)
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation="project_memory.promote",
            object_kind="project_memory",
            object_id=stored.id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=f"from {candidate.id}",
        )
        return stored

    def reject(
        self,
        candidate_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        note: str = "",
    ) -> MemoryCandidate:
        if principal.kind is not PrincipalKind.HUMAN:
            raise HumanRequiredError("only a human principal may reject project memory")
        candidate = self.get_candidate(candidate_id)
        self._require(principal, Action.ACCEPT, candidate.project_id, acl_epoch)
        if candidate.status is not MemoryStatus.CAPTURED:
            raise CandidateClosedError(f"candidate {candidate_id} is {candidate.status.value}")
        now = utc_now()
        closed = MemoryCandidate(
            id=candidate.id,
            project_id=candidate.project_id,
            kind=candidate.kind,
            summary=candidate.summary,
            status=MemoryStatus.REJECTED,
            branch_id=candidate.branch_id,
            revision_id=candidate.revision_id,
            captured_by_actor_id=candidate.captured_by_actor_id,
            captured_at=candidate.captured_at,
            provenance=(
                *candidate.provenance,
                ProvenanceEntry(
                    actor_id=principal.actor_id,
                    operation="reject",
                    created_at=now,
                    note=note,
                ),
            ),
            previous_id=candidate.previous_id,
            source_collaboration_event_id=candidate.source_collaboration_event_id,
            link_url=candidate.link_url,
            artifact_id=candidate.artifact_id,
            rights_record_id=candidate.rights_record_id,
            conflict_of_id=candidate.conflict_of_id,
        )

        def persist(index: dict[str, Any]) -> MemoryCandidate:
            self._put_candidate(index, closed)
            return closed

        stored = mutate_index(self.workspace, persist)
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation="project_memory.reject",
            object_kind="memory_candidate",
            object_id=stored.id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=note or "rejected",
        )
        return stored

    def search(
        self,
        *,
        project_id: str,
        query: str,
        principal: Principal,
        acl_epoch: int,
        branch_id: str | None = None,
        include_rejected: bool = False,
    ) -> tuple[MemoryCandidate, ...]:
        self._require(principal, Action.READ, project_id, acl_epoch)
        needles = _tokens(query)
        hits: list[MemoryCandidate] = []
        for candidate in self._candidates(project_id):
            if branch_id is not None and candidate.branch_id != branch_id:
                continue
            if candidate.status is MemoryStatus.REJECTED and not include_rejected:
                continue
            if candidate.status is MemoryStatus.PROMOTED:
                continue
            if needles and not (needles & _tokens(candidate.summary)):
                continue
            hits.append(candidate)
        return tuple(hits)

    def list_memories(
        self,
        project_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> tuple[ProjectMemory, ...]:
        """Active reviewed memory. Rejected candidates are never included."""

        self._require(principal, Action.READ, project_id, acl_epoch)
        index = load_index(self.workspace)
        memories: list[ProjectMemory] = []
        for memory_id in index.get("memory_ids_by_project", {}).get(project_id, ()):
            digest = index["memory_digests"][memory_id]
            memories.append(ProjectMemory.from_dict(load_payload(self.workspace, str(digest))))
        return tuple(memories)

    def get_candidate(self, candidate_id: str) -> MemoryCandidate:
        index = load_index(self.workspace)
        digest = index["candidate_digests"].get(candidate_id)
        if digest is None:
            raise CandidateNotFoundError(f"unknown candidate: {candidate_id}")
        return MemoryCandidate.from_dict(load_payload(self.workspace, str(digest)))

    def _persist_new(
        self,
        candidate: MemoryCandidate,
        *,
        principal: Principal,
        supersede_id: str | None,
    ) -> MemoryCandidate:
        def persist(index: dict[str, Any]) -> MemoryCandidate:
            if candidate.status is MemoryStatus.CAPTURED:
                duplicate = self._duplicate(index, candidate)
                if duplicate is not None:
                    if supersede_id is None or duplicate.id != supersede_id:
                        raise DuplicateCandidateError(
                            f"open {candidate.kind.value} already exists as {duplicate.id}"
                        )
                    superseded = self._with_status(duplicate, MemoryStatus.REJECTED, principal.actor_id)
                    self._put_candidate(index, superseded)
            self._put_candidate(index, candidate)
            ids = list(index["candidate_ids_by_project"].get(candidate.project_id, []))
            ids.append(candidate.id)
            by_project = dict(index["candidate_ids_by_project"])
            by_project[candidate.project_id] = ids
            index["candidate_ids_by_project"] = by_project
            return candidate

        return mutate_index(self.workspace, persist)

    def _duplicate(self, index: dict[str, Any], candidate: MemoryCandidate) -> MemoryCandidate | None:
        target = _normalize(candidate.summary)
        for item_id in index["candidate_ids_by_project"].get(candidate.project_id, ()):
            digest = index["candidate_digests"].get(item_id)
            if digest is None:
                continue
            existing = MemoryCandidate.from_dict(load_payload(self.workspace, str(digest)))
            if existing.status is not MemoryStatus.CAPTURED:
                continue
            if existing.kind is not candidate.kind:
                continue
            if existing.branch_id != candidate.branch_id:
                continue
            if _normalize(existing.summary) == target:
                return existing
        return None

    def _candidates(self, project_id: str) -> tuple[MemoryCandidate, ...]:
        index = load_index(self.workspace)
        items: list[MemoryCandidate] = []
        for item_id in index["candidate_ids_by_project"].get(project_id, ()):
            digest = index["candidate_digests"].get(item_id)
            if digest is None:
                continue
            items.append(MemoryCandidate.from_dict(load_payload(self.workspace, str(digest))))
        return tuple(items)

    def _put_candidate(self, index: dict[str, Any], candidate: MemoryCandidate) -> None:
        digest = put_payload(self.workspace, candidate.to_dict())
        digests = dict(index["candidate_digests"])
        digests[candidate.id] = digest
        index["candidate_digests"] = digests

    @staticmethod
    def _with_status(
        candidate: MemoryCandidate, status: MemoryStatus, actor_id: str
    ) -> MemoryCandidate:
        return MemoryCandidate(
            id=candidate.id,
            project_id=candidate.project_id,
            kind=candidate.kind,
            summary=candidate.summary,
            status=status,
            branch_id=candidate.branch_id,
            revision_id=candidate.revision_id,
            captured_by_actor_id=candidate.captured_by_actor_id,
            captured_at=candidate.captured_at,
            provenance=(
                *candidate.provenance,
                ProvenanceEntry(
                    actor_id=actor_id,
                    operation="supersede",
                    created_at=utc_now(),
                    note=status.value,
                ),
            ),
            previous_id=candidate.previous_id,
            source_collaboration_event_id=candidate.source_collaboration_event_id,
            link_url=candidate.link_url,
            artifact_id=candidate.artifact_id,
            rights_record_id=candidate.rights_record_id,
            promoted_memory_id=candidate.promoted_memory_id,
            conflict_of_id=candidate.conflict_of_id,
        )

    def _require(
        self, principal: Principal, action: Action, project_id: str, acl_epoch: int
    ) -> None:
        self.authorization.require(
            principal,
            action,
            self.authorization.resource_for_project(project_id),
            acl_epoch=acl_epoch,
        )
