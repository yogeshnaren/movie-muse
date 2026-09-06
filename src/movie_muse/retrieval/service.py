"""Permissioned, local-first retrieval over registered rights sources."""

from __future__ import annotations

import re
from typing import Any

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.identity.api import Principal
from movie_muse.persistence.api import LocalWorkspace, utc_now
from movie_muse.retrieval.errors import ReferenceNotFoundError, TenantIsolationError
from movie_muse.retrieval.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.retrieval.injection import enforce_untrusted_text
from movie_muse.retrieval.types import Citation, IndexedReference, RetrievedSegment
from movie_muse.rights.api import PermittedUse, RightsService
from movie_muse.schemas.api import new_ulid

_TOKEN = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(match.group(0).lower() for match in _TOKEN.finditer(text))


def _score(query: str, text: str) -> float:
    query_tokens = _tokens(query)
    if not query_tokens:
        return 0.0
    corpus = set(_tokens(text))
    hits = sum(1 for token in query_tokens if token in corpus)
    return hits / len(query_tokens)


class RetrievalService:
    """Index and retrieve only rights-permitted reference text."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        rights: RightsService,
        authorization: AuthorizationService,
        audit: AuditLog | None = None,
    ) -> None:
        self.workspace = workspace
        self.rights = rights
        self.authorization = authorization
        self.audit = audit or AuditLog(workspace)

    def index_reference(
        self,
        *,
        source_id: str,
        text: str,
        principal: Principal,
        acl_epoch: int,
        project_id: str,
        title: str | None = None,
    ) -> IndexedReference:
        source = self.rights.get_source(
            source_id, principal=principal, acl_epoch=acl_epoch
        )
        if source.project_id != project_id:
            raise TenantIsolationError(
                f"source {source_id} belongs to {source.project_id}, not {project_id}"
            )
        self._require(principal, Action.VIEW_RIGHTS, project_id, acl_epoch)
        self.rights.require_permitted_use(source_id, PermittedUse.RETRIEVAL)
        entry = IndexedReference(
            id=f"refidx_{new_ulid()}",
            source_id=source.source_id,
            project_id=source.project_id,
            title=title or source.title,
            text=text,
            indexed_at=utc_now(),
            indexed_by=principal.actor_id,
            classification=source.classification,
            permitted_uses=source.permitted_uses,
            validation_state=source.validation_state,
            rights_record_id=source.rights_record_id,
            source_version_id=source.id,
        )

        def persist(index: dict[str, Any]) -> IndexedReference:
            digest = put_payload(self.workspace, entry.to_dict())
            index["entry_ids"] = [*list(index["entry_ids"]), entry.id]
            digests = dict(index["entry_digests"])
            digests[entry.id] = digest
            index["entry_digests"] = digests
            by_source = dict(index["by_source"])
            by_source[entry.source_id] = [
                *list(by_source.get(entry.source_id, [])),
                entry.id,
            ]
            index["by_source"] = by_source
            by_project = dict(index["by_project"])
            by_project[entry.project_id] = [
                *list(by_project.get(entry.project_id, [])),
                entry.id,
            ]
            index["by_project"] = by_project
            return entry

        stored = mutate_index(self.workspace, persist)
        self._audit(
            principal,
            operation="retrieval_index_reference",
            object_id=stored.id,
            acl_epoch=acl_epoch,
            reason=stored.source_id,
        )
        return stored

    def retrieve(
        self,
        *,
        project_id: str,
        query: str,
        principal: Principal,
        acl_epoch: int,
        limit: int = 8,
        at: str | None = None,
    ) -> tuple[RetrievedSegment, ...]:
        self._require(principal, Action.READ, project_id, acl_epoch)
        if not query.strip() or limit <= 0:
            return ()
        entries = self._project_entries(project_id)
        ranked: list[tuple[float, IndexedReference]] = []
        for entry in entries:
            score = _score(query, f"{entry.title} {entry.text}")
            if score <= 0:
                continue
            ranked.append((score, entry))
        ranked.sort(key=lambda item: (-item[0], item[1].source_id, item[1].id))
        segments: list[RetrievedSegment] = []
        for score, entry in ranked:
            if len(segments) >= limit:
                break
            self.rights.require_permitted_use(
                entry.source_id, PermittedUse.RETRIEVAL, at=at
            )
            citation_decision = self.rights.require_permitted_use(
                entry.source_id, PermittedUse.CITATION, at=at
            )
            inspection = enforce_untrusted_text(entry.text)
            citation = Citation(
                source_id=entry.source_id,
                source_version_id=citation_decision.version_id,
                title=entry.title,
                rights_record_id=citation_decision.rights_record_id,
                license_summary=citation_decision.license_summary,
                classification=entry.classification,
                permitted_uses=entry.permitted_uses,
                validation_state=citation_decision.validation_state,
            )
            segments.append(
                RetrievedSegment(
                    id=f"retseg_{new_ulid()}",
                    project_id=entry.project_id,
                    source_id=entry.source_id,
                    text=inspection.redacted_text,
                    score=score,
                    citation=citation,
                    redacted=inspection.injected,
                )
            )
        self._audit(
            principal,
            operation="retrieval_query",
            object_id=project_id,
            acl_epoch=acl_epoch,
            reason=f"hits={len(segments)}",
        )
        return tuple(segments)

    def list_references(
        self, project_id: str, *, principal: Principal, acl_epoch: int
    ) -> tuple[IndexedReference, ...]:
        self._require(principal, Action.READ, project_id, acl_epoch)
        return self._project_entries(project_id)

    def get_reference(
        self, entry_id: str, *, principal: Principal, acl_epoch: int
    ) -> IndexedReference:
        entry = self._entry(entry_id)
        self._require(principal, Action.READ, entry.project_id, acl_epoch)
        return entry

    def _project_entries(self, project_id: str) -> tuple[IndexedReference, ...]:
        index = load_index(self.workspace)
        entries: list[IndexedReference] = []
        for entry_id in index["by_project"].get(project_id, []):
            entry = self._entry(str(entry_id), index=index)
            if entry.project_id != project_id:
                raise TenantIsolationError(
                    f"indexed reference {entry.id} crossed project boundary"
                )
            entries.append(entry)
        return tuple(entries)

    def _entry(
        self, entry_id: str, *, index: dict[str, Any] | None = None
    ) -> IndexedReference:
        current = index if index is not None else load_index(self.workspace)
        digest = current["entry_digests"].get(entry_id)
        if digest is None:
            raise ReferenceNotFoundError(f"unknown retrieval entry: {entry_id}")
        return IndexedReference.from_dict(load_payload(self.workspace, str(digest)))

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
        *,
        operation: str,
        object_id: str,
        acl_epoch: int,
        reason: str,
    ) -> None:
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation=operation,
            object_kind="retrieval_reference",
            object_id=object_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=reason,
        )
