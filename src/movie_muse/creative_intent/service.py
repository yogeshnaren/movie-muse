"""Permissioned, versioned CreativeIntentIR service.

Direct manipulation and chat write the same ``IntentCommand``. Inferred
suggestions are never locked and never silently promoted to stated intent.
"""

from __future__ import annotations

from typing import Any

from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.creative_intent.errors import (
    IntentLockError,
    IntentMergeConflictError,
    IntentScopeError,
    StaleIntentError,
    UnknownIntentError,
)
from movie_muse.creative_intent.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.creative_intent.types import (
    IntentAction,
    IntentCommand,
    IntentConflict,
    IntentEnvelope,
    IntentKind,
    IntentMergeResult,
    IntentOrigin,
    IntentRecord,
    intent_key,
)
from movie_muse.identity.api import Principal
from movie_muse.persistence.api import LocalWorkspace, utc_now
from movie_muse.revisions.api import RevisionService
from movie_muse.schemas.api import (
    CreativeIntentIR,
    FilmIR,
    IntentScope,
    IntentSourceRole,
    new_id,
)


class CreativeIntentService:
    """Creator-owned intent. No model calls."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        revisions: RevisionService,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.revisions = revisions

    def command(
        self,
        *,
        action: IntentAction | str,
        kind: IntentKind | str,
        scope: IntentScope | str,
        scope_target_id: str,
        statement: str,
        source_role: IntentSourceRole | str,
        origin: IntentOrigin | str,
        expected_revision_id: str,
        branch_id: str,
        project_id: str,
        confidence: float = 1.0,
        is_locked: bool = False,
        exceptions: tuple[str, ...] = (),
        anti_rules: tuple[str, ...] = (),
    ) -> IntentCommand:
        return IntentCommand(
            action=IntentAction(action),
            kind=IntentKind(kind),
            scope=IntentScope(scope),
            scope_target_id=scope_target_id,
            statement=statement,
            source_role=IntentSourceRole(source_role),
            origin=IntentOrigin(origin),
            expected_revision_id=expected_revision_id,
            branch_id=branch_id,
            project_id=project_id,
            confidence=confidence,
            is_locked=is_locked,
            exceptions=exceptions,
            anti_rules=anti_rules,
        )

    def apply_direct(
        self,
        command: IntentCommand,
        *,
        principal: Principal,
        acl_epoch: int,
        film_ir: FilmIR | None = None,
    ) -> IntentEnvelope:
        return self.apply(
            command.with_origin(IntentOrigin.DIRECT),
            principal=principal,
            acl_epoch=acl_epoch,
            film_ir=film_ir,
        )

    def apply_chat(
        self,
        command: IntentCommand,
        *,
        principal: Principal,
        acl_epoch: int,
        film_ir: FilmIR | None = None,
    ) -> IntentEnvelope:
        return self.apply(
            command.with_origin(IntentOrigin.CHAT),
            principal=principal,
            acl_epoch=acl_epoch,
            film_ir=film_ir,
        )

    def apply(
        self,
        command: IntentCommand,
        *,
        principal: Principal,
        acl_epoch: int,
        film_ir: FilmIR | None = None,
    ) -> IntentEnvelope:
        self._validate_command(command, film_ir=film_ir)
        action = Action.PROPOSE if command.source_role is IntentSourceRole.INFERRED else Action.ACCEPT
        if command.action in {IntentAction.LOCK, IntentAction.UNLOCK}:
            action = Action.ACCEPT
        self._require(principal, action, command.project_id, acl_epoch)
        head = self.revisions.get_branch(command.branch_id).head_revision_id
        if command.expected_revision_id != head:
            raise StaleIntentError(
                f"intent expected {command.expected_revision_id} but branch head is {head}"
            )
        if command.source_role is IntentSourceRole.INFERRED and (
            command.is_locked or command.action is IntentAction.LOCK
        ):
            raise IntentLockError("inferred creative intent cannot be locked")

        def persist(index: dict[str, Any]) -> IntentEnvelope:
            key = intent_key(
                branch_id=command.branch_id,
                scope=command.scope,
                scope_target_id=command.scope_target_id,
                kind=command.kind,
            )
            current_id = index["active_keys"].get(key)
            current = self._load_id(index, str(current_id)) if current_id else None
            if command.action is IntentAction.UNLOCK:
                if current is None:
                    raise UnknownIntentError(f"no active intent for {key}")
                return self._write_envelope(
                    index,
                    self._evolve(
                        current,
                        command,
                        principal=principal,
                        revision_id=head,
                        locked=False,
                    ),
                    previous=current,
                )
            if current is not None and current.intent.is_locked:
                if command.action is IntentAction.LOCK and command.statement == current.intent.statement:
                    return current
                if command.action is not IntentAction.LOCK:
                    raise IntentLockError(f"locked intent {current.intent.id} cannot be overwritten")
            locked = command.action is IntentAction.LOCK or command.is_locked
            if current is None:
                envelope = self._new_envelope(command, principal=principal, revision_id=head, locked=locked)
                return self._write_envelope(index, envelope, previous=None)
            return self._write_envelope(
                index,
                self._evolve(
                    current,
                    command,
                    principal=principal,
                    revision_id=head,
                    locked=locked or current.intent.is_locked,
                ),
                previous=current,
            )

        return mutate_index(self.workspace, persist)

    def suggest(
        self,
        command: IntentCommand,
        *,
        principal: Principal,
        acl_epoch: int,
        film_ir: FilmIR | None = None,
    ) -> IntentEnvelope:
        inferred = IntentCommand(
            action=command.action,
            kind=command.kind,
            scope=command.scope,
            scope_target_id=command.scope_target_id,
            statement=command.statement,
            source_role=IntentSourceRole.INFERRED,
            origin=command.origin,
            expected_revision_id=command.expected_revision_id,
            branch_id=command.branch_id,
            project_id=command.project_id,
            confidence=command.confidence,
            is_locked=False,
            exceptions=command.exceptions,
            anti_rules=command.anti_rules,
        )
        return self.apply(inferred, principal=principal, acl_epoch=acl_epoch, film_ir=film_ir)

    def accept_suggestion(
        self,
        intent_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        source_role: IntentSourceRole = IntentSourceRole.WRITER,
    ) -> IntentEnvelope:
        record = self.get(intent_id)
        if not record.envelope.is_inferred:
            raise IntentLockError("only inferred suggestions can be accepted into stated intent")
        self._require(principal, Action.ACCEPT, record.intent.project_id, acl_epoch)
        head = self.revisions.get_branch(record.envelope.branch_id).head_revision_id
        if record.stale:
            raise StaleIntentError(f"suggestion {intent_id} is stale against {head}")
        command = IntentCommand(
            action=IntentAction.SET,
            kind=record.envelope.kind,
            scope=record.intent.scope,
            scope_target_id=record.intent.scope_target_id,
            statement=record.intent.statement,
            source_role=source_role,
            origin=record.envelope.origin,
            expected_revision_id=head,
            branch_id=record.envelope.branch_id,
            project_id=record.intent.project_id,
            confidence=1.0,
            is_locked=False,
            exceptions=record.intent.exceptions,
            anti_rules=record.intent.anti_rules,
        )
        return self.apply(command, principal=principal, acl_epoch=acl_epoch)

    def rebind(
        self,
        intent_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        expected_revision_id: str,
    ) -> IntentEnvelope:
        record = self.get(intent_id)
        self._require(principal, Action.ACCEPT, record.intent.project_id, acl_epoch)
        head = self.revisions.get_branch(record.envelope.branch_id).head_revision_id
        if expected_revision_id != head:
            raise StaleIntentError(
                f"rebind expected {expected_revision_id} but branch head is {head}"
            )

        def persist(index: dict[str, Any]) -> IntentEnvelope:
            current = self._load_id(index, intent_id)
            if current is None:
                raise UnknownIntentError(f"unknown intent: {intent_id}")
            rebound = IntentEnvelope(
                intent=CreativeIntentIR(
                    id=new_id("creative_intent"),
                    project_id=current.intent.project_id,
                    scope=current.intent.scope,
                    scope_target_id=current.intent.scope_target_id,
                    statement=current.intent.statement,
                    source_role=current.intent.source_role,
                    is_locked=current.intent.is_locked,
                    revision_id=head,
                    created_at=utc_now(),
                    exceptions=current.intent.exceptions,
                    anti_rules=current.intent.anti_rules,
                ),
                kind=current.kind,
                action=current.action,
                origin=current.origin,
                confidence=current.confidence,
                owner_actor_id=current.owner_actor_id,
                branch_id=current.branch_id,
                evolves_from_id=current.intent.id,
            )
            return self._write_envelope(index, rebound, previous=current)

        return mutate_index(self.workspace, persist)

    def get(self, intent_id: str, *, head_revision_id: str | None = None) -> IntentRecord:
        index = load_index(self.workspace)
        envelope = self._load_id(index, intent_id)
        if envelope is None:
            raise UnknownIntentError(f"unknown intent: {intent_id}")
        head = head_revision_id or self.revisions.get_branch(envelope.branch_id).head_revision_id
        active_id = index["active_keys"].get(envelope.key)
        return IntentRecord(
            envelope=envelope,
            stale=envelope.intent.revision_id != head,
            active=active_id == envelope.intent.id,
        )

    def list(
        self,
        branch_id: str,
        *,
        include_superseded: bool = False,
        stated_only: bool = False,
        inferred_only: bool = False,
    ) -> tuple[IntentRecord, ...]:
        index = load_index(self.workspace)
        head = self.revisions.get_branch(branch_id).head_revision_id
        ids = [str(item) for item in index["by_branch"].get(branch_id, [])]
        records: list[IntentRecord] = []
        for item_id in ids:
            envelope = self._load_id(index, item_id)
            if envelope is None:
                continue
            active = index["active_keys"].get(envelope.key) == envelope.intent.id
            if not include_superseded and not active:
                continue
            if stated_only and envelope.is_inferred:
                continue
            if inferred_only and not envelope.is_inferred:
                continue
            records.append(
                IntentRecord(
                    envelope=envelope,
                    stale=envelope.intent.revision_id != head,
                    active=active,
                )
            )
        return tuple(records)

    def stated_and_inferred(
        self, branch_id: str
    ) -> tuple[tuple[IntentRecord, ...], tuple[IntentRecord, ...]]:
        stated = self.list(branch_id, stated_only=True)
        inferred = self.list(branch_id, inferred_only=True)
        return stated, inferred

    def fork_to_branch(
        self,
        *,
        source_branch_id: str,
        target_branch_id: str,
        principal: Principal,
        acl_epoch: int,
        project_id: str,
    ) -> tuple[IntentEnvelope, ...]:
        self._require(principal, Action.ACCEPT, project_id, acl_epoch)
        source = self.list(source_branch_id)
        copied: list[IntentEnvelope] = []

        def persist(index: dict[str, Any]) -> list[IntentEnvelope]:
            written: list[IntentEnvelope] = []
            for record in source:
                if not record.active:
                    continue
                clone = IntentEnvelope(
                    intent=CreativeIntentIR(
                        id=new_id("creative_intent"),
                        project_id=record.intent.project_id,
                        scope=record.intent.scope,
                        scope_target_id=record.intent.scope_target_id,
                        statement=record.intent.statement,
                        source_role=record.intent.source_role,
                        is_locked=record.intent.is_locked,
                        revision_id=record.intent.revision_id,
                        created_at=utc_now(),
                        exceptions=record.intent.exceptions,
                        anti_rules=record.intent.anti_rules,
                    ),
                    kind=record.envelope.kind,
                    action=record.envelope.action,
                    origin=record.envelope.origin,
                    confidence=record.envelope.confidence,
                    owner_actor_id=principal.actor_id,
                    branch_id=target_branch_id,
                    evolves_from_id=record.intent.id,
                )
                written.append(self._write_envelope(index, clone, previous=None))
            return written

        copied.extend(mutate_index(self.workspace, persist))
        return tuple(copied)

    def merge_from(
        self,
        *,
        source_branch_id: str,
        target_branch_id: str,
        principal: Principal,
        acl_epoch: int,
        project_id: str,
    ) -> IntentMergeResult:
        self._require(principal, Action.MERGE, project_id, acl_epoch)
        source = {record.envelope.key: record for record in self.list(source_branch_id)}
        target = {record.envelope.key: record for record in self.list(target_branch_id)}
        conflicts: list[IntentConflict] = []
        to_copy: list[IntentRecord] = []
        for key, record in source.items():
            other = target.get(_retarget_key(key, target_branch_id))
            if other is None:
                to_copy.append(record)
                continue
            if other.intent.statement == record.intent.statement and other.envelope.kind is record.envelope.kind:
                continue
            conflicts.append(
                IntentConflict(
                    key=key,
                    source_id=record.intent.id,
                    target_id=other.intent.id,
                    source_statement=record.intent.statement,
                    target_statement=other.intent.statement,
                )
            )
        if conflicts:
            raise IntentMergeConflictError(
                "intent merge conflicts: " + ", ".join(item.key for item in conflicts)
            )

        def persist(index: dict[str, Any]) -> list[str]:
            copied: list[str] = []
            for record in to_copy:
                clone = IntentEnvelope(
                    intent=CreativeIntentIR(
                        id=new_id("creative_intent"),
                        project_id=record.intent.project_id,
                        scope=record.intent.scope,
                        scope_target_id=record.intent.scope_target_id,
                        statement=record.intent.statement,
                        source_role=record.intent.source_role,
                        is_locked=record.intent.is_locked,
                        revision_id=record.intent.revision_id,
                        created_at=utc_now(),
                        exceptions=record.intent.exceptions,
                        anti_rules=record.intent.anti_rules,
                    ),
                    kind=record.envelope.kind,
                    action=record.envelope.action,
                    origin=record.envelope.origin,
                    confidence=record.envelope.confidence,
                    owner_actor_id=principal.actor_id,
                    branch_id=target_branch_id,
                    evolves_from_id=record.intent.id,
                )
                written = self._write_envelope(index, clone, previous=None)
                copied.append(written.intent.id)
            return copied

        copied_ids = tuple(mutate_index(self.workspace, persist))
        return IntentMergeResult(copied_ids=copied_ids, conflicts=tuple(conflicts))

    def _validate_command(self, command: IntentCommand, *, film_ir: FilmIR | None) -> None:
        if not command.statement.strip():
            raise IntentScopeError("intent statement is required")
        if not 0.0 <= command.confidence <= 1.0:
            raise IntentScopeError("confidence must be within [0.0, 1.0]")
        if film_ir is not None and command.scope is IntentScope.SCENE:
            if command.scope_target_id not in film_ir.scene_order:
                raise IntentScopeError(f"unknown scene: {command.scope_target_id}")

    def _new_envelope(
        self,
        command: IntentCommand,
        *,
        principal: Principal,
        revision_id: str,
        locked: bool,
    ) -> IntentEnvelope:
        return IntentEnvelope(
            intent=CreativeIntentIR(
                id=new_id("creative_intent"),
                project_id=command.project_id,
                scope=command.scope,
                scope_target_id=command.scope_target_id,
                statement=command.statement,
                source_role=command.source_role,
                is_locked=locked,
                revision_id=revision_id,
                created_at=utc_now(),
                exceptions=command.exceptions,
                anti_rules=command.anti_rules,
            ),
            kind=command.kind,
            action=command.action,
            origin=command.origin,
            confidence=command.confidence,
            owner_actor_id=principal.actor_id,
            branch_id=command.branch_id,
        )

    def _evolve(
        self,
        current: IntentEnvelope,
        command: IntentCommand,
        *,
        principal: Principal,
        revision_id: str,
        locked: bool,
    ) -> IntentEnvelope:
        return IntentEnvelope(
            intent=CreativeIntentIR(
                id=new_id("creative_intent"),
                project_id=command.project_id,
                scope=command.scope,
                scope_target_id=command.scope_target_id,
                statement=command.statement,
                source_role=command.source_role,
                is_locked=locked,
                revision_id=revision_id,
                created_at=utc_now(),
                exceptions=command.exceptions or current.intent.exceptions,
                anti_rules=command.anti_rules or current.intent.anti_rules,
            ),
            kind=command.kind,
            action=command.action,
            origin=command.origin,
            confidence=command.confidence,
            owner_actor_id=principal.actor_id,
            branch_id=command.branch_id,
            evolves_from_id=current.intent.id,
        )

    def _write_envelope(
        self,
        index: dict[str, Any],
        envelope: IntentEnvelope,
        *,
        previous: IntentEnvelope | None,
    ) -> IntentEnvelope:
        digest = put_payload(self.workspace, envelope.to_dict())
        index["digests"][envelope.intent.id] = digest
        if envelope.intent.id not in list(index["ids"]):
            index["ids"] = [*list(index["ids"]), envelope.intent.id]
        branch_ids = list(index["by_branch"].get(envelope.branch_id, []))
        if envelope.intent.id not in branch_ids:
            branch_ids.append(envelope.intent.id)
        by_branch = dict(index["by_branch"])
        by_branch[envelope.branch_id] = branch_ids
        index["by_branch"] = by_branch
        active = dict(index["active_keys"])
        if previous is not None:
            closed = IntentEnvelope(
                intent=previous.intent,
                kind=previous.kind,
                action=previous.action,
                origin=previous.origin,
                confidence=previous.confidence,
                owner_actor_id=previous.owner_actor_id,
                branch_id=previous.branch_id,
                superseded_id=envelope.intent.id,
                evolves_from_id=previous.evolves_from_id,
            )
            closed_digest = put_payload(self.workspace, closed.to_dict())
            index["digests"][closed.intent.id] = closed_digest
        active[envelope.key] = envelope.intent.id
        index["active_keys"] = active
        return envelope

    def _load_id(self, index: dict[str, Any], intent_id: str) -> IntentEnvelope | None:
        digest = index["digests"].get(intent_id)
        if digest is None:
            return None
        return IntentEnvelope.from_dict(load_payload(self.workspace, str(digest)))

    def _require(
        self, principal: Principal, action: Action, project_id: str, acl_epoch: int
    ) -> None:
        self.authorization.require(
            principal,
            action,
            self.authorization.resource_for_project(project_id),
            acl_epoch=acl_epoch,
        )


def _retarget_key(key: str, target_branch_id: str) -> str:
    parts = key.split("|", 1)
    if len(parts) != 2:
        return key
    return f"{target_branch_id}|{parts[1]}"
