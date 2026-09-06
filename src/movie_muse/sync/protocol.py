"""Outbox/inbox protocol: duplicates and out-of-order envelopes are safe."""

from __future__ import annotations

import json
from typing import Any

from movie_muse.persistence.api import (
    LocalSaveState,
    LocalWorkspace,
    digest_payload,
    utc_now,
)
from movie_muse.schemas.api import ScreenplayDocument
from movie_muse.sync.envelopes import (
    SyncEnvelope,
    authorization_errors,
    cross_field_integrity_errors,
)
from movie_muse.sync.errors import SyncUploadBlockedError


class SyncProtocol:
    """Applies idempotent envelopes. Never last-writer-wins."""

    def __init__(self, workspace: LocalWorkspace) -> None:
        self.workspace = workspace

    def flush_outbox(self) -> list[str]:
        """Mark queued envelopes synced when upload is allowed.

        This slice records the protocol outcome locally. A later package owns
        the network transport. Outages refuse flush without locking local save.
        """

        if not self.workspace.store.sync_upload_allowed():
            raise SyncUploadBlockedError(
                "upload blocked by connectivity, auth, subscription, or sync outage"
            )
        flushed: list[str] = []
        for payload in self.workspace.pending_outbox():
            envelope = SyncEnvelope.from_dict(payload)
            self.workspace.put_outbox_status(envelope.operation_id, LocalSaveState.SYNCED.value)
            flushed.append(envelope.operation_id)
        if flushed:
            self.workspace.store.set_meta("last_synced_operation_id", flushed[-1])
        return flushed

    def ingest(self, payload: dict[str, Any]) -> str:
        """Accept a remote or replayed envelope.

        Duplicate operation IDs are ignored. Unknown bases are buffered.
        Ancestry that does not match the current head becomes an explicit
        conflict. Cross-field integrity failures (resulting revision, project,
        branch, schema version, ACL epoch) are conflicted and must not advance
        head. Unauthorized actors are conflicted even when integrity holds.
        """

        envelope = SyncEnvelope.from_dict(payload)
        existing = self.workspace.store.fetchone(
            "SELECT status FROM inbox WHERE operation_id=?",
            (envelope.operation_id,),
        )
        if existing is not None:
            return "duplicate"
        outbox = self.workspace.store.fetchone(
            "SELECT 1 FROM outbox WHERE operation_id=?",
            (envelope.operation_id,),
        )
        if outbox is not None:
            return "duplicate"
        now = utc_now()
        self.workspace.store.execute(
            "INSERT INTO inbox(operation_id, envelope_json, status, received_at) VALUES (?, ?, ?, ?)",
            (
                envelope.operation_id,
                json.dumps(envelope.to_dict(), sort_keys=True, separators=(",", ":")),
                "pending",
                now,
            ),
        )
        return self._apply_ready()

    def drain_inbox(self) -> str:
        return self._apply_ready()

    def _apply_ready(self) -> str:
        last = "buffered"
        progressed = True
        while progressed:
            progressed = False
            for payload in self.workspace.pending_and_buffered_inbox():
                outcome = self._apply_one(payload)
                if outcome in {"applied", "duplicate"}:
                    progressed = True
                last = outcome
        return last

    def _mark_inbox(self, operation_id: str, status: str) -> None:
        self.workspace.store.execute(
            "UPDATE inbox SET status=? WHERE operation_id=?",
            (status, operation_id),
        )

    def _integrity_conflict(self, envelope: SyncEnvelope) -> bool:
        document = ScreenplayDocument.from_dict(envelope.document)
        row = self.workspace.store.fetchone(
            "SELECT project_id, branch_id FROM documents WHERE id=?",
            (document.id,),
        )
        if row is None:
            return True
        expected_acl_epoch = int(self.workspace.store.get_meta("acl_epoch") or "0")
        return bool(
            cross_field_integrity_errors(
                envelope,
                expected_project_id=str(row["project_id"]),
                expected_branch_id=str(row["branch_id"]),
                expected_acl_epoch=expected_acl_epoch,
            )
        )

    def _authorization_conflict(self, envelope: SyncEnvelope) -> bool:
        return bool(
            authorization_errors(
                envelope,
                authorized_actor_ids=self.workspace.authorized_actor_ids(envelope.project_id),
            )
        )

    def _apply_one(self, payload: dict[str, Any]) -> str:
        envelope = SyncEnvelope.from_dict(payload)
        if self._integrity_conflict(envelope) or self._authorization_conflict(envelope):
            self._mark_inbox(envelope.operation_id, LocalSaveState.CONFLICTED.value)
            return "conflicted"
        if self.workspace.has_revision(envelope.resulting_revision_id):
            self._mark_inbox(envelope.operation_id, "applied")
            return "duplicate"
        if not self.workspace.has_revision(envelope.base_revision_id):
            self._mark_inbox(envelope.operation_id, "buffered")
            return "buffered"
        document = ScreenplayDocument.from_dict(envelope.document)
        head = self.workspace.head_revision_id(document.id)
        if head is not None and head != envelope.base_revision_id:
            self._mark_inbox(envelope.operation_id, LocalSaveState.CONFLICTED.value)
            return "conflicted"
        encoded, digest = digest_payload(document.to_dict())
        if digest != envelope.resulting_hash:
            self._mark_inbox(envelope.operation_id, LocalSaveState.CONFLICTED.value)
            return "conflicted"
        self.workspace.store.put_blob(encoded, expected_digest=digest)
        now = utc_now()
        with self.workspace.store.transaction() as conn:
            conn.execute(
                "INSERT INTO revisions("
                "id, project_id, document_id, branch_id, parent_revision_id, "
                "blob_digest, created_at, actor_id"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    envelope.resulting_revision_id,
                    envelope.project_id,
                    document.id,
                    envelope.branch_id,
                    envelope.base_revision_id,
                    digest,
                    now,
                    envelope.actor_id,
                ),
            )
            conn.execute(
                "UPDATE documents SET head_revision_id=?, payload_digest=?, updated_at=? WHERE id=?",
                (envelope.resulting_revision_id, digest, now, document.id),
            )
            conn.execute(
                "UPDATE inbox SET status=? WHERE operation_id=?",
                ("applied", envelope.operation_id),
            )
        return "applied"

    def quarantine_unsynced(self, *, reason: str) -> int:
        """Keep unsynced work locally as recovery-only; never upload or destroy it."""

        rows = self.workspace.pending_outbox()
        for payload in rows:
            envelope = SyncEnvelope.from_dict(payload)
            self.workspace.put_outbox_status(
                envelope.operation_id, LocalSaveState.RECOVERY_ONLY.value
            )
        self.workspace.store.set_meta("quarantine_reason", reason)
        return len(rows)
