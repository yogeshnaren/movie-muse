"""Local workspace: open/edit/save/reopen/export without network."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from movie_muse.document.api import apply_change_set, normalize, semantic_validate
from movie_muse.persistence.backup import create_backup
from movie_muse.persistence.canonical import digest_payload, utc_now
from movie_muse.persistence.errors import PersistenceError, SaveNotAcknowledgedError
from movie_muse.persistence.status import LocalSaveState, SaveAck, WorkspaceStatus
from movie_muse.persistence.store import LocalStore
from movie_muse.schemas.api import ChangeSet, Project, ScreenplayDocument, new_id, new_ulid


class LocalWorkspace:
    """Authoritative local project/document store plus outbox/inbox tables.

    Save is acknowledged only after blob fsync and a committed SQLite
    transaction that writes the revision and outbox envelope together.
    """

    def __init__(self, root: Path) -> None:
        self.store = LocalStore(root)
        self.root = Path(root)

    def close(self) -> None:
        self.store.close()

    def set_outage(self, name: str, enabled: bool) -> None:
        self.store.set_flag(name, enabled)

    def set_airplane_mode(self, enabled: bool) -> None:
        self.store.set_flag("connectivity_offline", enabled)

    def open_project(self, project: Project, document: ScreenplayDocument, *, branch_id: str) -> None:
        if not self.store.local_work_allowed():
            raise PersistenceError("local work must remain available")
        semantic_validate(normalize(document))
        encoded, digest = digest_payload(document.to_dict())
        now = utc_now()
        self.store.put_blob(encoded, expected_digest=digest)
        with self.store.transaction() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO projects(id, payload_json, updated_at) VALUES (?, ?, ?)",
                (project.id, json.dumps(project.to_dict(), sort_keys=True), now),
            )
            conn.execute(
                "INSERT INTO documents("
                "id, project_id, branch_id, head_revision_id, payload_digest, updated_at"
                ") VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET "
                "project_id=excluded.project_id, "
                "branch_id=excluded.branch_id, "
                "head_revision_id=excluded.head_revision_id, "
                "payload_digest=excluded.payload_digest, "
                "updated_at=excluded.updated_at",
                (document.id, project.id, branch_id, document.base_revision_id, digest, now),
            )
            conn.execute(
                "INSERT OR IGNORE INTO revisions("
                "id, project_id, document_id, branch_id, parent_revision_id, blob_digest, created_at, actor_id"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    document.base_revision_id,
                    project.id,
                    document.id,
                    branch_id,
                    None,
                    digest,
                    now,
                    project.owner_actor_id,
                ),
            )
        self.store.set_meta("active_document_id", document.id)
        self.store.set_meta("active_project_id", project.id)
        self.store.set_meta("active_branch_id", branch_id)

    def save(
        self,
        document: ScreenplayDocument,
        *,
        actor_id: str,
        device_id: str,
        change_set: ChangeSet | None = None,
    ) -> SaveAck:
        """Persist a new immutable revision. Returns only after commit."""

        if not self.store.local_work_allowed():
            raise PersistenceError("local work must remain available")
        current = normalize(document)
        if change_set is not None:
            current = apply_change_set(current, change_set)
        semantic_validate(current)
        branch_id = self.store.get_meta("active_branch_id")
        if branch_id is None:
            raise SaveNotAcknowledgedError("workspace has no active branch")
        parent = current.base_revision_id
        revision_id = new_id("revision")
        persisted = replace(current, base_revision_id=revision_id)
        encoded, digest = digest_payload(persisted.to_dict())
        operation_id = new_ulid()
        now = utc_now()
        envelope = {
            "project_id": persisted.project_id,
            "branch_id": branch_id,
            "base_revision_id": parent,
            "resulting_revision_id": revision_id,
            "resulting_hash": digest,
            "actor_id": actor_id,
            "device_id": device_id,
            "operation_id": operation_id,
            "schema_version": "1.0",
            "acl_epoch": int(self.store.get_meta("acl_epoch") or "0"),
            "document": persisted.to_dict(),
        }
        try:
            self.store.put_blob(encoded, expected_digest=digest)
            with self.store.transaction() as conn:
                conn.execute(
                    "INSERT INTO revisions("
                    "id, project_id, document_id, branch_id, parent_revision_id, blob_digest, created_at, actor_id"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        revision_id,
                        persisted.project_id,
                        persisted.id,
                        branch_id,
                        parent,
                        digest,
                        now,
                        actor_id,
                    ),
                )
                conn.execute(
                    "UPDATE documents SET head_revision_id=?, payload_digest=?, updated_at=? WHERE id=?",
                    (revision_id, digest, now, persisted.id),
                )
                conn.execute(
                    "INSERT INTO outbox(operation_id, envelope_json, status, created_at) VALUES (?, ?, ?, ?)",
                    (
                        operation_id,
                        json.dumps(envelope, sort_keys=True, separators=(",", ":")),
                        LocalSaveState.QUEUED_FOR_SYNC.value,
                        now,
                    ),
                )
        except Exception as exc:
            raise SaveNotAcknowledgedError("save did not commit") from exc
        return SaveAck(
            revision_id=revision_id,
            blob_digest=digest,
            operation_id=operation_id,
            state=LocalSaveState.QUEUED_FOR_SYNC,
        )

    def reopen(self, document_id: str | None = None) -> ScreenplayDocument:
        doc_id = document_id or self.store.get_meta("active_document_id")
        if doc_id is None:
            raise PersistenceError("no document to reopen")
        row = self.store.fetchone(
            "SELECT payload_digest, head_revision_id FROM documents WHERE id=?",
            (doc_id,),
        )
        if row is None:
            raise PersistenceError(f"unknown document {doc_id}")
        payload = json.loads(self.store.get_blob(str(row["payload_digest"])).decode("utf-8"))
        document = ScreenplayDocument.from_dict(payload)
        semantic_validate(document)
        return document

    def export_document(self, destination: Path, document_id: str | None = None) -> Path:
        document = self.reopen(document_id)
        encoded, _digest = digest_payload(document.to_dict())
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(encoded)
        self.store.execute(
            "UPDATE documents SET last_export_at=? WHERE id=?",
            (utc_now(), document.id),
        )
        return destination

    def backup(self, destination: Path) -> Path:
        path = create_backup(self.store, destination)
        self.store.set_meta("last_backup_path", str(path))
        return path

    def status(self) -> WorkspaceStatus:
        flags = self.store.flags()
        doc_id = self.store.get_meta("active_document_id")
        head = None
        save_state = LocalSaveState.SAVED_LOCALLY
        if doc_id is not None:
            row = self.store.fetchone(
                "SELECT head_revision_id FROM documents WHERE id=?",
                (doc_id,),
            )
            if row is not None:
                head = str(row["head_revision_id"]) if row["head_revision_id"] else None
        outbox_row = self.store.fetchone(
            "SELECT COUNT(*) AS n FROM outbox WHERE status=?",
            (LocalSaveState.QUEUED_FOR_SYNC.value,),
        )
        pending_outbox = int(outbox_row["n"]) if outbox_row is not None else 0
        inbox_row = self.store.fetchone(
            "SELECT COUNT(*) AS n FROM inbox WHERE status IN (?, ?)",
            ("pending", "buffered"),
        )
        pending_inbox = int(inbox_row["n"]) if inbox_row is not None else 0
        conflicted = self.store.fetchone(
            "SELECT 1 FROM inbox WHERE status=? LIMIT 1",
            (LocalSaveState.CONFLICTED.value,),
        )
        recovery = self.store.fetchone(
            "SELECT 1 FROM outbox WHERE status=? LIMIT 1",
            (LocalSaveState.RECOVERY_ONLY.value,),
        )
        if conflicted is not None:
            save_state = LocalSaveState.CONFLICTED
        elif recovery is not None:
            save_state = LocalSaveState.RECOVERY_ONLY
        elif pending_outbox:
            save_state = LocalSaveState.QUEUED_FOR_SYNC
        elif self.store.get_meta("last_backup_path"):
            save_state = LocalSaveState.BACKED_UP
        elif self.store.get_meta("last_synced_operation_id"):
            save_state = LocalSaveState.SYNCED
        return WorkspaceStatus(
            document_id=doc_id,
            head_revision_id=head,
            save_state=save_state,
            backed_up=self.store.get_meta("last_backup_path") is not None,
            connectivity_offline=flags["connectivity_offline"],
            auth_outage=flags["auth_outage"],
            subscription_outage=flags["subscription_outage"],
            sync_outage=flags["sync_outage"],
            ai_outage=flags["ai_outage"],
            pending_outbox=pending_outbox,
            pending_inbox=pending_inbox,
        )

    def has_revision(self, revision_id: str) -> bool:
        row = self.store.fetchone("SELECT 1 FROM revisions WHERE id=?", (revision_id,))
        return row is not None

    def head_revision_id(self, document_id: str) -> str | None:
        row = self.store.fetchone(
            "SELECT head_revision_id FROM documents WHERE id=?",
            (document_id,),
        )
        if row is None or row["head_revision_id"] is None:
            return None
        return str(row["head_revision_id"])

    def put_outbox_status(self, operation_id: str, status: str) -> None:
        self.store.execute(
            "UPDATE outbox SET status=? WHERE operation_id=?",
            (status, operation_id),
        )

    def pending_outbox(self) -> list[dict[str, Any]]:
        rows = self.store.fetchall(
            "SELECT envelope_json FROM outbox WHERE status=? ORDER BY created_at ASC",
            (LocalSaveState.QUEUED_FOR_SYNC.value,),
        )
        return [json.loads(str(row["envelope_json"])) for row in rows]

    def pending_and_buffered_inbox(self) -> list[dict[str, Any]]:
        rows = self.store.fetchall(
            "SELECT envelope_json FROM inbox WHERE status IN (?, ?) ORDER BY received_at ASC",
            ("pending", "buffered"),
        )
        return [json.loads(str(row["envelope_json"])) for row in rows]
