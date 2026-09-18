"""Rights-controlled Reference Lens. Never claims model training memory."""

from __future__ import annotations

import re
from typing import Any

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.identity.api import Principal
from movie_muse.reference_lens.errors import (
    CitationUnresolvedError,
    LensDisabledError,
    TrainingMemoryClaimError,
)
from movie_muse.reference_lens.index import load_index, mutate_index
from movie_muse.reference_lens.types import (
    CounterReference,
    LensHit,
    LensSettings,
    RightsContext,
)
from movie_muse.retrieval.api import Citation, IndexedReference, RetrievalService, RetrievedSegment
from movie_muse.rights.api import RightsService, SourceVersion
from movie_muse.schemas.api import new_ulid

_TOKEN = re.compile(r"[a-z0-9]+", re.IGNORECASE)

TRAINING_MEMORY_PHRASES = (
    "model training memory",
    "training-data memory",
    "training data memory",
    "remembered from training",
    "the model was trained on",
    "from the model's training",
)


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(match.group(0).lower() for match in _TOKEN.finditer(text))


def _assert_not_training_memory(text: str) -> None:
    lowered = text.lower()
    for phrase in TRAINING_MEMORY_PHRASES:
        if phrase in lowered:
            raise TrainingMemoryClaimError(
                "Reference Lens cannot retrieve unverifiable model training memory"
            )


class ReferenceLensService:
    """Surface permitted references with rights, citations, and contrast."""

    def __init__(
        self,
        retrieval: RetrievalService,
        rights: RightsService,
        authorization: AuthorizationService,
        audit: AuditLog,
    ) -> None:
        self.retrieval = retrieval
        self.rights = rights
        self.authorization = authorization
        self.audit = audit
        self.workspace = retrieval.workspace

    def query(
        self,
        *,
        project_id: str,
        query: str,
        principal: Principal,
        acl_epoch: int,
        limit: int = 8,
    ) -> tuple[LensHit, ...]:
        _assert_not_training_memory(query)
        self._require(principal, Action.READ, project_id, acl_epoch)
        settings = self.settings(project_id)
        if not settings.enabled:
            raise LensDisabledError("Reference Lens is disabled for this project")
        blocked = set(settings.tombstoned_entry_ids)
        segments = self.retrieval.retrieve(
            project_id=project_id,
            query=query,
            principal=principal,
            acl_epoch=acl_epoch,
            limit=max(limit * 2, 8),
        )
        indexed = {
            item.source_id: item
            for item in self.retrieval.list_references(
                project_id, principal=principal, acl_epoch=acl_epoch
            )
            if item.id not in blocked
        }
        visible: list[RetrievedSegment] = []
        for segment in segments:
            entry = indexed.get(segment.source_id)
            if entry is None or entry.id in blocked:
                continue
            visible.append(segment)
            if len(visible) >= limit:
                break
        hits: list[LensHit] = []
        for segment in visible:
            counter = self._counter_reference(segment, visible, indexed)
            hits.append(self._hit(query, segment, indexed[segment.source_id], counter))
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation="reference_lens.query",
            object_kind="reference_lens",
            object_id=project_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=f"hits={len(hits)}",
        )
        return tuple(hits)

    def resolve_citation(
        self, citation: Citation, *, principal: Principal, acl_epoch: int
    ) -> SourceVersion:
        try:
            return self.rights.get_source_version(
                citation.source_version_id, principal=principal, acl_epoch=acl_epoch
            )
        except Exception as exc:
            raise CitationUnresolvedError(
                f"citation {citation.source_version_id} did not resolve"
            ) from exc

    def disable(
        self, project_id: str, *, principal: Principal, acl_epoch: int
    ) -> LensSettings:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        current = self.settings(project_id)
        updated = LensSettings(
            project_id=project_id,
            enabled=False,
            tombstoned_entry_ids=current.tombstoned_entry_ids,
        )
        self._put_settings(updated)
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation="reference_lens.disable",
            object_kind="reference_lens",
            object_id=project_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason="writer disabled local reference lens",
        )
        return updated

    def enable(
        self, project_id: str, *, principal: Principal, acl_epoch: int
    ) -> LensSettings:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        current = self.settings(project_id)
        updated = LensSettings(
            project_id=project_id,
            enabled=True,
            tombstoned_entry_ids=current.tombstoned_entry_ids,
        )
        self._put_settings(updated)
        return updated

    def delete_local_indexes(
        self, project_id: str, *, principal: Principal, acl_epoch: int
    ) -> LensSettings:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        entries = self.retrieval.list_references(
            project_id, principal=principal, acl_epoch=acl_epoch
        )
        current = self.settings(project_id)
        tombstoned = tuple(
            sorted({*current.tombstoned_entry_ids, *(item.id for item in entries)})
        )
        updated = LensSettings(
            project_id=project_id,
            enabled=current.enabled,
            tombstoned_entry_ids=tombstoned,
        )
        self._put_settings(updated)
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation="reference_lens.delete_indexes",
            object_kind="reference_lens",
            object_id=project_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=f"tombstoned={len(tombstoned)}",
        )
        return updated

    def settings(self, project_id: str) -> LensSettings:
        index = load_index(self.workspace)
        payload = index["projects"].get(project_id)
        if not payload:
            return LensSettings(project_id=project_id, enabled=True)
        return LensSettings.from_dict(dict(payload))

    def _hit(
        self,
        query: str,
        segment: RetrievedSegment,
        entry: IndexedReference,
        counter: CounterReference | None,
    ) -> LensHit:
        query_tokens = set(_tokens(query))
        passage_tokens = set(_tokens(segment.text))
        shared = tuple(sorted(query_tokens & passage_tokens))
        missing = tuple(sorted(query_tokens - passage_tokens))
        why = (
            f"Surfaced from a {entry.classification.value.replace('_', '-')} source "
            "registered in the rights registry because it permits retrieval and "
            "citation and overlaps the query. This is a registry lookup, not a "
            "claim about model weights."
        )
        _assert_not_training_memory(why)
        rights = RightsContext(
            classification=entry.classification,
            permitted_uses=entry.permitted_uses,
            validation_state=entry.validation_state,
            license_summary=segment.citation.license_summary,
            rights_record_id=segment.citation.rights_record_id,
            why_permitted=(
                f"{entry.classification.value} source with "
                f"{', '.join(item.value for item in entry.permitted_uses) or 'no'} uses"
            ),
        )
        return LensHit(
            id=f"rln_{new_ulid()}",
            source_id=segment.source_id,
            title=entry.title,
            similarity=(
                f"token overlap {segment.score:.2f}"
                + (f" on {', '.join(shared)}" if shared else "")
            ),
            relevant_passage=segment.text,
            structure_note=self._structure_note(segment.text),
            difference=(
                "query introduces " + ", ".join(missing)
                if missing
                else "query tokens are covered by the passage"
            ),
            why_surfaced=why,
            rights=rights,
            citation=segment.citation,
            redacted=segment.redacted,
            score=segment.score,
            counter_reference=counter,
        )

    def _structure_note(self, text: str) -> str:
        stripped = text.strip()
        if stripped.upper().startswith(("INT.", "EXT.")):
            return "scene-heading / location structure"
        if "\n" in stripped:
            return "multi-beat passage structure"
        return "single-passage structure"

    def _counter_reference(
        self,
        segment: RetrievedSegment,
        visible: list[RetrievedSegment],
        indexed: dict[str, IndexedReference],
    ) -> CounterReference | None:
        for other in visible:
            if other.source_id == segment.source_id:
                continue
            entry = indexed[other.source_id]
            return CounterReference(
                source_id=other.source_id,
                title=entry.title,
                contrast=(
                    f"{entry.title} is a different permitted source "
                    f"({entry.classification.value}) that also matches the query"
                ),
                citation=other.citation,
            )
        extras = [item for item in indexed.values() if item.source_id != segment.source_id]
        if not extras:
            return None
        other_entry = extras[0]
        return CounterReference(
            source_id=other_entry.source_id,
            title=other_entry.title,
            contrast=(
                f"{other_entry.title} is indexed as a counter-reference "
                "and was not the top overlap for this query"
            ),
            citation=Citation(
                source_id=other_entry.source_id,
                source_version_id=other_entry.source_version_id,
                title=other_entry.title,
                rights_record_id=other_entry.rights_record_id,
                license_summary=None,
                classification=other_entry.classification,
                permitted_uses=other_entry.permitted_uses,
                validation_state=other_entry.validation_state,
            ),
        )

    def _put_settings(self, settings: LensSettings) -> None:
        def persist(index: dict[str, Any]) -> None:
            projects = dict(index["projects"])
            projects[settings.project_id] = settings.to_dict()
            index["projects"] = projects

        mutate_index(self.workspace, persist)

    def _require(
        self, principal: Principal, action: Action, project_id: str, acl_epoch: int
    ) -> None:
        self.authorization.require(
            principal,
            action,
            self.authorization.resource_for_project(project_id),
            acl_epoch=acl_epoch,
        )
