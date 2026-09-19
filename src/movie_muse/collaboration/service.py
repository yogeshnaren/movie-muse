"""Permissioned live collaboration: presence, comments, CRDT ops, reconnect."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.collaboration.crdt import conflicts_in, merge_ops
from movie_muse.collaboration.errors import (
    BranchMismatchError,
    ForbiddenDomainError,
    StaleOperationError,
)
from movie_muse.collaboration.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.collaboration.types import (
    FORBIDDEN_DOMAINS,
    ApplyResult,
    CollabComment,
    CollabOp,
    CollabOpKind,
    ConflictView,
    PresenceRecord,
)
from movie_muse.identity.api import Principal
from movie_muse.persistence.api import utc_now
from movie_muse.revisions.api import RevisionService, StaleBaseError
from movie_muse.schemas.api import (
    ChangeSet,
    ChangeSetOperation,
    CollaborationEvent,
    CollaborationRecordKind,
    OperationType,
    PromotionState,
    new_id,
    new_ulid,
)

PRESENCE_TTL = timedelta(seconds=30)


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class CollaborationService:
    """Typed collab ops. Presence is ephemeral; comments and decisions are durable.

    A CRDT coordinates authored document patches, comments, cursors, and
    presence. It never writes FilmIR, intent, production, or financial state.
    """

    def __init__(
        self,
        revisions: RevisionService,
        authorization: AuthorizationService,
        audit: AuditLog,
        *,
        clock: Callable[[], str] = utc_now,
        presence_ttl: timedelta = PRESENCE_TTL,
    ) -> None:
        self.revisions = revisions
        self.authorization = authorization
        self.audit = audit
        self.workspace = revisions.workspace
        self.clock = clock
        self.presence_ttl = presence_ttl

    def heartbeat(
        self,
        *,
        project_id: str,
        branch_id: str,
        principal: Principal,
        acl_epoch: int,
        device_id: str,
        cursor_block_id: str | None = None,
    ) -> PresenceRecord:
        self._require(principal, Action.READ, project_id, acl_epoch)
        record = PresenceRecord(
            actor_id=principal.actor_id,
            device_id=device_id,
            project_id=project_id,
            branch_id=branch_id,
            seen_at=self.clock(),
            cursor_block_id=cursor_block_id,
        )

        def persist(index: dict[str, Any]) -> PresenceRecord:
            presence = dict(index["presence"])
            presence[f"{record.actor_id}:{record.device_id}"] = record.to_dict()
            index["presence"] = presence
            return record

        stored = mutate_index(self.workspace, persist)
        op = self._op(
            kind=CollabOpKind.PRESENCE,
            project_id=project_id,
            branch_id=branch_id,
            principal=principal,
            acl_epoch=acl_epoch,
            device_id=device_id,
            base_revision_id=self._head(),
            target_id=principal.actor_id,
            payload={"cursor_block_id": cursor_block_id},
        )
        self._append_op(op)
        return stored

    def leave(
        self,
        *,
        project_id: str,
        principal: Principal,
        acl_epoch: int,
        device_id: str,
    ) -> None:
        self._require(principal, Action.READ, project_id, acl_epoch)
        key = f"{principal.actor_id}:{device_id}"

        def persist(index: dict[str, Any]) -> None:
            presence = dict(index["presence"])
            presence.pop(key, None)
            index["presence"] = presence

        mutate_index(self.workspace, persist)

    def list_presence(
        self,
        *,
        project_id: str,
        branch_id: str,
        principal: Principal,
        acl_epoch: int,
        now: str | None = None,
    ) -> tuple[PresenceRecord, ...]:
        self._require(principal, Action.READ, project_id, acl_epoch)
        moment = _parse_iso(now or self.clock())
        index = load_index(self.workspace)
        visible: list[PresenceRecord] = []
        for payload in dict(index.get("presence", {})).values():
            record = PresenceRecord.from_dict(payload)
            if record.project_id != project_id or record.branch_id != branch_id:
                continue
            if moment - _parse_iso(record.seen_at) > self.presence_ttl:
                continue
            visible.append(record)
        return tuple(sorted(visible, key=lambda item: (item.actor_id, item.device_id)))

    def comment(
        self,
        *,
        project_id: str,
        branch_id: str,
        block_id: str,
        text: str,
        principal: Principal,
        acl_epoch: int,
        device_id: str = "dev_local",
    ) -> CollabComment:
        self._require(principal, Action.COMMENT, project_id, acl_epoch)
        revision_id = self._head()
        note = CollabComment(
            id=new_id("note"),
            project_id=project_id,
            branch_id=branch_id,
            revision_id=revision_id,
            block_id=block_id,
            author_actor_id=principal.actor_id,
            text=text,
            created_at=self.clock(),
        )

        def persist(index: dict[str, Any]) -> CollabComment:
            digest = put_payload(self.workspace, note.to_dict())
            ids = list(index["comment_ids"])
            ids.append(note.id)
            index["comment_ids"] = ids
            digests = dict(index["comment_digests"])
            digests[note.id] = digest
            index["comment_digests"] = digests
            return note

        stored = mutate_index(self.workspace, persist)
        op = self._op(
            kind=CollabOpKind.COMMENT,
            project_id=project_id,
            branch_id=branch_id,
            principal=principal,
            acl_epoch=acl_epoch,
            device_id=device_id,
            base_revision_id=revision_id,
            target_id=block_id,
            payload={"comment_id": stored.id, "text": text},
        )
        self._append_op(op)
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation="collaboration.comment",
            object_kind="note",
            object_id=stored.id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=block_id,
        )
        return stored

    def list_comments(
        self,
        *,
        project_id: str,
        principal: Principal,
        acl_epoch: int,
        branch_id: str | None = None,
    ) -> tuple[CollabComment, ...]:
        self._require(principal, Action.READ, project_id, acl_epoch)
        index = load_index(self.workspace)
        comments: list[CollabComment] = []
        for comment_id in index.get("comment_ids", ()):
            digest = index["comment_digests"][comment_id]
            item = CollabComment.from_dict(load_payload(self.workspace, str(digest)))
            if item.project_id != project_id:
                continue
            if branch_id is not None and item.branch_id != branch_id:
                continue
            comments.append(item)
        return tuple(comments)

    def capture_decision(
        self,
        *,
        project_id: str,
        summary: str,
        principal: Principal,
        acl_epoch: int,
        record_kind: CollaborationRecordKind = CollaborationRecordKind.DECISION,
    ) -> CollaborationEvent:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        event = CollaborationEvent(
            id=new_id("collaboration_event"),
            project_id=project_id,
            source="live_collaboration",
            record_kind=record_kind,
            summary=summary,
            captured_at=self.clock(),
            speaker_actor_id=principal.actor_id,
            promotion_state=PromotionState.CAPTURED,
        )

        def persist(index: dict[str, Any]) -> CollaborationEvent:
            decisions = dict(index["decisions"])
            decisions[event.id] = event.to_dict()
            index["decisions"] = decisions
            return event

        stored = mutate_index(self.workspace, persist)
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation="collaboration.decision",
            object_kind="collaboration_event",
            object_id=stored.id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=stored.promotion_state.value,
        )
        return stored

    def list_decisions(self, project_id: str) -> tuple[CollaborationEvent, ...]:
        index = load_index(self.workspace)
        return tuple(
            CollaborationEvent.from_dict(payload)
            for payload in dict(index.get("decisions", {})).values()
            if str(payload.get("project_id")) == project_id
        )

    def patch_block(
        self,
        *,
        project_id: str,
        branch_id: str,
        block_id: str,
        text: str,
        principal: Principal,
        acl_epoch: int,
        device_id: str,
        domain: str = "document",
    ) -> ApplyResult:
        self._assert_domain(domain)
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        head = self._head()
        op = self._op(
            kind=CollabOpKind.DOCUMENT_PATCH,
            project_id=project_id,
            branch_id=branch_id,
            principal=principal,
            acl_epoch=acl_epoch,
            device_id=device_id,
            base_revision_id=head,
            target_id=block_id,
            payload={"text": text, "domain": domain},
        )
        return self._commit_op(op, persist_document=True)

    def ingest_ops(
        self,
        ops: tuple[CollabOp, ...],
        *,
        principal: Principal,
        acl_epoch: int,
        persist_document: bool = True,
    ) -> tuple[ApplyResult, ...]:
        results: list[ApplyResult] = []
        for op in ops:
            self._require(principal, Action.READ, op.project_id, acl_epoch)
            results.append(self._commit_op(op, persist_document=persist_document))
        return tuple(results)

    def ops_since(self, lamport: int) -> tuple[CollabOp, ...]:
        return tuple(item for item in self.list_ops() if item.lamport > lamport)

    def list_ops(self) -> tuple[CollabOp, ...]:
        index = load_index(self.workspace)
        ops: list[CollabOp] = []
        for op_id in index.get("op_ids", ()):
            digest = index["op_digests"][op_id]
            ops.append(CollabOp.from_dict(load_payload(self.workspace, str(digest))))
        return tuple(ops)

    def conflicts(self) -> tuple[ConflictView, ...]:
        index = load_index(self.workspace)
        found: list[ConflictView] = []
        for raw in index.get("conflicts", ()):
            found.append(
                ConflictView(
                    left_op_id=str(raw["left_op_id"]),
                    right_op_id=str(raw["right_op_id"]),
                    target_id=str(raw["target_id"]),
                    reason=str(raw["reason"]),
                    left_payload=dict(raw["left_payload"]),
                    right_payload=dict(raw["right_payload"]),
                )
            )
        return tuple(found)

    def reconnect(
        self,
        *,
        project_id: str,
        branch_id: str,
        principal: Principal,
        acl_epoch: int,
        device_id: str,
        since_lamport: int = 0,
    ) -> tuple[CollabOp, ...]:
        self.heartbeat(
            project_id=project_id,
            branch_id=branch_id,
            principal=principal,
            acl_epoch=acl_epoch,
            device_id=device_id,
        )
        return self.ops_since(since_lamport)

    def share_branch(
        self,
        *,
        project_id: str,
        branch_id: str,
        peer_actor_id: str,
        principal: Principal,
        acl_epoch: int,
    ) -> None:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)

        def persist(index: dict[str, Any]) -> None:
            shares = dict(index["shares"])
            key = f"{project_id}:{branch_id}"
            peers = list(shares.get(key, []))
            if peer_actor_id not in peers:
                peers.append(peer_actor_id)
            shares[key] = peers
            index["shares"] = shares

        mutate_index(self.workspace, persist)

    def _commit_op(self, op: CollabOp, *, persist_document: bool) -> ApplyResult:
        self._assert_domain(str(op.payload.get("domain", "document")))
        if op.branch_id != self.revisions.canon_branch().id and not self._shared(op):
            raise BranchMismatchError(f"branch {op.branch_id} is not shared with this replica")
        existing = {item.id: item for item in self.list_ops()}
        if op.id in existing:
            return ApplyResult(op=existing[op.id], applied=False)
        merged = merge_ops(tuple(existing.values()), (op,))
        found = conflicts_in(merged)
        if found and op.kind is CollabOpKind.DOCUMENT_PATCH:
            self._store_ops((op,), found)
            return ApplyResult(op=op, conflicts=found, applied=False)
        if op.kind is CollabOpKind.DOCUMENT_PATCH and persist_document:
            self._apply_patch(op)
        self._store_ops((op,), found)
        return ApplyResult(op=op, conflicts=found, applied=True)

    def _apply_patch(self, op: CollabOp) -> None:
        head = self._head()
        if op.base_revision_id != head:
            overlapping = [
                item
                for item in self.list_ops()
                if item.kind is CollabOpKind.DOCUMENT_PATCH and item.target_id == op.target_id
            ]
            if overlapping:
                raise StaleOperationError(
                    "stale overlapping document_patch; fail closed"
                )
        change_set = ChangeSet(
            id=new_id("change_set"),
            base_revision_id=self._head(),
            author_actor_id=op.actor_id,
            created_at=op.created_at,
            operations=(
                ChangeSetOperation(
                    id=f"cso_{new_ulid()}",
                    order=0,
                    op_type=OperationType.UPDATE_BLOCK,
                    target_id=op.target_id,
                    payload={"text": str(op.payload["text"])},
                ),
            ),
        )
        try:
            self.revisions.apply_change_set(
                change_set, actor_id=op.actor_id, device_id=op.device_id
            )
        except StaleBaseError as exc:
            raise StaleOperationError(str(exc)) from exc

    def _store_ops(self, ops: tuple[CollabOp, ...], found: tuple[ConflictView, ...]) -> None:
        def persist(index: dict[str, Any]) -> None:
            ids = list(index["op_ids"])
            digests = dict(index["op_digests"])
            clock = int(index["clock"])
            for op in ops:
                if op.id in digests:
                    continue
                digests[op.id] = put_payload(self.workspace, op.to_dict())
                ids.append(op.id)
                clock = max(clock, op.lamport)
            index["op_ids"] = ids
            index["op_digests"] = digests
            index["clock"] = clock
            if found:
                conflicts = list(index["conflicts"])
                for item in found:
                    payload = item.to_dict()
                    if payload not in conflicts:
                        conflicts.append(payload)
                index["conflicts"] = conflicts

        mutate_index(self.workspace, persist)

    def _append_op(self, op: CollabOp) -> None:
        self._store_ops((op,), ())

    def _op(
        self,
        *,
        kind: CollabOpKind,
        project_id: str,
        branch_id: str,
        principal: Principal,
        acl_epoch: int,
        device_id: str,
        base_revision_id: str,
        target_id: str,
        payload: dict[str, Any],
    ) -> CollabOp:
        index = load_index(self.workspace)
        lamport = int(index.get("clock", 0)) + 1
        return CollabOp(
            id=f"cop_{new_ulid()}",
            kind=kind,
            project_id=project_id,
            branch_id=branch_id,
            actor_id=principal.actor_id,
            device_id=device_id,
            lamport=lamport,
            acl_epoch=acl_epoch,
            base_revision_id=base_revision_id,
            target_id=target_id,
            payload=payload,
            created_at=self.clock(),
        )

    def _shared(self, op: CollabOp) -> bool:
        index = load_index(self.workspace)
        key = f"{op.project_id}:{op.branch_id}"
        peers = list(index.get("shares", {}).get(key, ()))
        return op.actor_id in peers

    def _head(self) -> str:
        return self.revisions.canon_branch().head_revision_id

    @staticmethod
    def _assert_domain(domain: str) -> None:
        if domain in FORBIDDEN_DOMAINS:
            raise ForbiddenDomainError(
                f"collaboration cannot mutate {domain} outside validated domain commands"
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
