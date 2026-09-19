"""EditorService: keyboard authoring session over RevisionService.

Editor JSON is never persisted as canon. Every mutation is a ChangeSet or
an explicit RevisionService command. Local save stays available in airplane
mode and through auth/subscription/provider outages.
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from movie_muse.document.api import EditorProjection, from_editor, to_editor
from movie_muse.editor.accessibility import accessibility_contract
from movie_muse.editor.autocomplete import suggestions
from movie_muse.editor.errors import EditorCanonError, EditorCommandError, RecoveryError
from movie_muse.editor.outline import cards, outline
from movie_muse.editor.search import replace_change_set, search
from movie_muse.editor.transitions import (
    invert_change_set,
    transition_change_set,
    update_text_change_set,
)
from movie_muse.editor.types import (
    AccessibilityContract,
    AuthorMode,
    AutocompleteSuggestion,
    ContextualAction,
    OutlineEntry,
    SceneCard,
    SearchHit,
)
from movie_muse.persistence.api import LocalSaveState, SaveAck, digest_payload, utc_now
from movie_muse.revisions.api import RevisionService
from movie_muse.schemas.api import ChangeSet, Note, ScreenplayDocument, new_id

JOURNAL_KEY = "editor_recovery_journal"


class EditorService:
    """Session facade. Hosts import this through ``movie_muse.editor.api``."""

    def __init__(self, revisions: RevisionService, *, actor_id: str) -> None:
        self.revisions = revisions
        self.actor_id = actor_id
        self.mode = AuthorMode.AUTHOR
        self._undo: list[ChangeSet] = []
        self._redo: list[ChangeSet] = []
        self._keystrokes = self._load_journal()

    def document(self) -> ScreenplayDocument:
        return self.revisions.replay_head()

    def projection(self) -> EditorProjection:
        return to_editor(self.document())

    def set_mode(self, mode: AuthorMode | str) -> AuthorMode:
        self.mode = AuthorMode(mode)
        return self.mode

    def set_airplane(self, enabled: bool) -> None:
        self.revisions.workspace.set_airplane_mode(enabled)

    def set_outage(self, name: str, enabled: bool) -> None:
        self.revisions.workspace.set_outage(name, enabled)

    def record_keystroke(self, payload: dict[str, Any]) -> None:
        entry = {"acked": False, "payload": dict(payload), "at": utc_now()}
        self._keystrokes.append(entry)
        self._persist_journal()

    def pending_keystrokes(self) -> tuple[dict[str, Any], ...]:
        return tuple(item for item in self._keystrokes if not item.get("acked"))

    def update_text(self, block_id: str, text: str) -> SaveAck:
        self.record_keystroke({"op": "update_text", "block_id": block_id, "text": text})
        return self._apply_update(block_id, text)

    def transition(self, block_id: str, key: str) -> SaveAck:
        if key not in {"Enter", "Tab"}:
            raise EditorCommandError(f"unsupported transition key: {key}")
        self.record_keystroke({"op": "transition", "block_id": block_id, "key": key})
        return self._apply_transition(block_id, key)

    def search(self, query: str) -> tuple[SearchHit, ...]:
        return search(self.document(), query)

    def replace(self, query: str, replacement: str, *, block_id: str | None = None) -> SaveAck:
        self.record_keystroke({"op": "replace", "query": query, "replacement": replacement})
        document = self.document()
        change = replace_change_set(
            document,
            query=query,
            replacement=replacement,
            actor_id=self.actor_id,
            created_at=utc_now(),
            block_id=block_id,
        )
        return self._commit(document, change)

    def autocomplete(self, *, prefix: str, kind: str) -> tuple[AutocompleteSuggestion, ...]:
        return suggestions(self.document(), prefix=prefix, kind=kind)

    def outline(self) -> tuple[OutlineEntry, ...]:
        return outline(self.document())

    def cards(self) -> tuple[SceneCard, ...]:
        return cards(self.document())

    def add_note(self, *, block_id: str, text: str) -> SaveAck:
        document = self.document()
        if not any(block.id == block_id for block in document.blocks):
            raise EditorCommandError(f"unknown block {block_id}")
        note = Note(
            id=new_id("note"),
            block_id=block_id,
            author_actor_id=self.actor_id,
            text=text,
            created_at=utc_now(),
        )
        updated = replace(document, notes=(*document.notes, note))
        ack = self.revisions.save_document(updated, actor_id=self.actor_id)
        self._ack_last()
        return ack

    def contextual(self, action: ContextualAction | str, *, block_id: str) -> str:
        kind = ContextualAction(action)
        document = self.document()
        block = next((item for item in document.blocks if item.id == block_id), None)
        if block is None:
            raise EditorCommandError(f"unknown block {block_id}")
        if kind is ContextualAction.EXPLORE:
            branch = self.revisions.create_branch(
                f"explore-{block_id[-6:]}", actor_id=self.actor_id
            )
            return branch.id
        if kind is ContextualAction.LOCK:
            extras = dict(block.unknown_extensions)
            extras["locked_scene"] = True
            change = update_text_change_set(
                document,
                block_id=block_id,
                text=block.text,
                actor_id=self.actor_id,
                created_at=utc_now(),
            )
            # Lock is a typed extra, not a silent pagination unlock.
            locked = ChangeSet(
                id=new_id("change_set"),
                base_revision_id=document.base_revision_id or "",
                author_actor_id=self.actor_id,
                created_at=utc_now(),
                operations=(
                    replace(
                        change.operations[0],
                        payload={"text": block.text, "unknown_extensions": extras},
                    ),
                ),
            )
            self._commit(document, locked)
            return "locked"
        if kind is ContextualAction.PRESERVE:
            self.add_note(block_id=block_id, text="PRESERVE: keep this beat")
            return "preserved"
        self.add_note(block_id=block_id, text="INTENT: creator-owned invariant")
        return "intent"

    def undo(self) -> SaveAck:
        if not self._undo:
            raise EditorCommandError("nothing to undo")
        inverse = self._undo.pop()
        before = self.document()
        retargeted = replace(inverse, base_revision_id=before.base_revision_id or inverse.base_revision_id)
        ack = self.revisions.apply_change_set(retargeted, actor_id=self.actor_id)
        self._redo.append(self._retarget(invert_change_set(before, retargeted, created_at=utc_now()), ack.revision_id))
        return ack

    def redo(self) -> SaveAck:
        if not self._redo:
            raise EditorCommandError("nothing to redo")
        change = self._redo.pop()
        before = self.document()
        retargeted = replace(change, base_revision_id=before.base_revision_id or change.base_revision_id)
        ack = self.revisions.apply_change_set(retargeted, actor_id=self.actor_id)
        self._undo.append(self._retarget(invert_change_set(before, retargeted, created_at=utc_now()), ack.revision_id))
        return ack

    def checkpoint(self, name: str) -> Any:
        return self.revisions.create_checkpoint(name, actor_id=self.actor_id)

    def branch(self, name: str) -> Any:
        return self.revisions.create_branch(name, actor_id=self.actor_id)

    def diff(self, left: str, right: str) -> Any:
        return self.revisions.diff_projection(left, right, actor_id=self.actor_id)

    def history_text(self) -> str:
        return self.revisions.render_history_text()

    def accessibility(self) -> AccessibilityContract:
        return accessibility_contract(self.document())

    def reject_editor_json(self, payload: dict[str, Any]) -> None:
        if payload.get("format") == "movie-muse.editor.projection.v1" or "nodes" in payload:
            raise EditorCanonError("editor projection cannot be saved as ScreenplayDocument canon")
        raise EditorCanonError("unknown payload is not a typed document command")

    def adopt_projection(self, projection: Any) -> ScreenplayDocument:
        """Reconstruct typed canon from a projection. Does not persist."""

        document = from_editor(projection)
        if document.id != self.document().id:
            raise EditorCanonError("projection document id does not match the open session")
        return document

    def recover(self) -> int:
        """Replay unacked journal entries without recording them again."""

        replayed = 0
        for item in self._keystrokes:
            if item.get("acked"):
                continue
            payload = item.get("payload") or {}
            if not isinstance(payload, dict):
                raise RecoveryError("recovery journal entry is missing a payload")
            if self._already_applied(payload):
                item["acked"] = True
                continue
            self._replay_payload(payload)
            item["acked"] = True
            replayed += 1
        self._persist_journal()
        return replayed

    def _already_applied(self, payload: dict[str, Any]) -> bool:
        document = self.document()
        op = payload.get("op")
        if op == "update_text":
            block = next((item for item in document.blocks if item.id == payload.get("block_id")), None)
            return block is not None and block.text == str(payload.get("text", ""))
        if op == "replace":
            query = str(payload.get("query") or "")
            return bool(query) and query not in "".join(block.text for block in document.blocks)
        return False

    def _replay_payload(self, payload: dict[str, Any]) -> SaveAck:
        op = payload.get("op")
        if op == "update_text":
            return self._apply_update(str(payload["block_id"]), str(payload["text"]), ack_journal=False)
        if op == "transition":
            return self._apply_transition(str(payload["block_id"]), str(payload["key"]), ack_journal=False)
        if op == "replace":
            document = self.document()
            change = replace_change_set(
                document,
                query=str(payload["query"]),
                replacement=str(payload["replacement"]),
                actor_id=self.actor_id,
                created_at=utc_now(),
            )
            return self._commit(document, change, ack_journal=False)
        raise RecoveryError(f"unsupported recovery op: {op}")

    def _apply_update(self, block_id: str, text: str, *, ack_journal: bool = True) -> SaveAck:
        document = self.document()
        change = update_text_change_set(
            document, block_id=block_id, text=text, actor_id=self.actor_id, created_at=utc_now()
        )
        return self._commit(document, change, ack_journal=ack_journal)

    def _apply_transition(self, block_id: str, key: str, *, ack_journal: bool = True) -> SaveAck:
        document = self.document()
        change = transition_change_set(
            document, block_id=block_id, key=key, actor_id=self.actor_id, created_at=utc_now()
        )
        if change is None:
            if ack_journal:
                self._ack_last()
            return self._unchanged_ack(document)
        return self._commit(document, change, ack_journal=ack_journal)

    def _unchanged_ack(self, document: ScreenplayDocument) -> SaveAck:
        _, digest = digest_payload(document.to_dict())
        return SaveAck(
            revision_id=document.base_revision_id or "",
            blob_digest=digest,
            operation_id="editor_transition_noop",
            state=LocalSaveState.SAVED_LOCALLY,
        )

    def _commit(self, before: ScreenplayDocument, change: ChangeSet, *, ack_journal: bool = True) -> SaveAck:
        inverse = invert_change_set(before, change, created_at=utc_now())
        ack = self.revisions.apply_change_set(change, actor_id=self.actor_id)
        self._undo.append(self._retarget(inverse, ack.revision_id))
        self._redo.clear()
        if ack_journal:
            self._ack_last()
        return ack

    def _load_journal(self) -> list[dict[str, Any]]:
        raw = self.revisions.workspace.store.get_meta(JOURNAL_KEY)
        if not raw:
            return []
        try:
            journal = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RecoveryError("recovery journal is not valid JSON") from exc
        if not isinstance(journal, list):
            raise RecoveryError("recovery journal must be a list")
        loaded: list[dict[str, Any]] = []
        for item in journal:
            if not isinstance(item, dict):
                raise RecoveryError("recovery journal entries must be objects")
            loaded.append(dict(item))
        return loaded

    def _retarget(self, change: ChangeSet, revision_id: str) -> ChangeSet:
        return replace(change, base_revision_id=revision_id)

    def _ack_last(self) -> None:
        if self._keystrokes:
            self._keystrokes[-1]["acked"] = True
        self._persist_journal()

    def _persist_journal(self) -> None:
        self.revisions.workspace.store.set_meta(JOURNAL_KEY, json.dumps(self._keystrokes, sort_keys=True))
