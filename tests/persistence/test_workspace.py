"""Local-first open/edit/save/reopen/export, outages, and crash-safe acks."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from movie_muse.document.api import apply_operation
from movie_muse.persistence.api import (
    CURRENT_SCHEMA_VERSION,
    LocalSaveState,
    LocalWorkspace,
    SaveNotAcknowledgedError,
    recover_if_corrupt,
)
from movie_muse.schemas.api import (
    ChangeSetOperation,
    OperationType,
    Project,
    ScreenplayDocument,
    new_id,
)
from movie_muse.sync.api import SyncProtocol, SyncUploadBlockedError


def test_airplane_mode_open_edit_save_reopen_export(
    tmp_path: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> None:
    project, document, branch_id = project_bundle
    workspace = LocalWorkspace(tmp_path / "ws")
    workspace.set_airplane_mode(True)
    workspace.set_outage("auth_outage", True)
    workspace.set_outage("subscription_outage", True)
    workspace.set_outage("sync_outage", True)
    workspace.set_outage("ai_outage", True)
    workspace.open_project(project, document, branch_id=branch_id)
    edited = apply_operation(
        document,
        ChangeSetOperation(
            id=new_id("change_set"),
            order=0,
            op_type=OperationType.UPDATE_METADATA,
            target_id=document.id,
            payload={"title": "Pilot — local"},
        ),
    )
    ack = workspace.save(edited, actor_id=project.owner_actor_id, device_id="dev_test")
    assert ack.state is LocalSaveState.QUEUED_FOR_SYNC
    workspace.close()

    reopened = LocalWorkspace(tmp_path / "ws")
    loaded = reopened.reopen()
    assert loaded.title == "Pilot — local"
    export_path = reopened.export_document(tmp_path / "export.json")
    assert export_path.is_file()
    status = reopened.status()
    assert status.connectivity_offline is True
    assert status.auth_outage is True
    assert status.subscription_outage is True
    assert status.sync_outage is True
    assert status.ai_outage is True
    assert status.pending_outbox == 1
    with pytest.raises(SyncUploadBlockedError):
        SyncProtocol(reopened).flush_outbox()
    reopened.close()


def test_acknowledged_save_survives_new_connection(
    tmp_path: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> None:
    project, document, branch_id = project_bundle
    workspace = LocalWorkspace(tmp_path / "ws")
    workspace.open_project(project, document, branch_id=branch_id)
    ack = workspace.save(document, actor_id=project.owner_actor_id, device_id="dev_test")
    workspace.close()
    again = LocalWorkspace(tmp_path / "ws")
    assert again.has_revision(ack.revision_id)
    assert again.reopen().base_revision_id == ack.revision_id
    again.close()


def test_uncommitted_save_is_not_acknowledged(
    tmp_path: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> None:
    project, document, branch_id = project_bundle
    workspace = LocalWorkspace(tmp_path / "ws")
    workspace.open_project(project, document, branch_id=branch_id)
    head = workspace.head_revision_id(document.id)
    with pytest.raises(RuntimeError):
        with workspace.store.transaction():
            workspace.store.execute(
                "UPDATE documents SET head_revision_id=? WHERE id=?",
                ("rev_not_committed", document.id),
            )
            raise RuntimeError("simulated crash")
    assert workspace.head_revision_id(document.id) == head
    workspace.close()


def test_save_without_open_is_not_acknowledged(
    tmp_path: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> None:
    _project, document, _branch = project_bundle
    workspace = LocalWorkspace(tmp_path / "ws")
    with pytest.raises(SaveNotAcknowledgedError):
        workspace.save(document, actor_id="act_missing", device_id="dev_test")
    workspace.close()


def test_backup_restore_and_corruption_recovery(
    tmp_path: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> None:
    project, document, branch_id = project_bundle
    workspace = LocalWorkspace(tmp_path / "ws")
    workspace.open_project(project, document, branch_id=branch_id)
    ack = workspace.save(document, actor_id=project.owner_actor_id, device_id="dev_test")
    backup_dir = workspace.backup(tmp_path / "backup")
    workspace.close()

    db_path = tmp_path / "ws" / "movie_muse.sqlite"
    db_path.write_bytes(b"not a sqlite database")
    recovered = recover_if_corrupt(tmp_path / "ws", backup_dir)
    recovered.close()
    restored = LocalWorkspace(tmp_path / "ws")
    assert restored.has_revision(ack.revision_id)
    restored.close()


def test_forward_migration_from_v1(tmp_path: Path) -> None:
    from movie_muse.persistence.migrations import SCHEMA_V1
    from movie_muse.persistence.store import DB_NAME

    db_path = tmp_path / "old" / DB_NAME
    db_path.parent.mkdir(parents=True)
    import sqlite3

    connection = sqlite3.connect(str(db_path))
    connection.executescript(
        SCHEMA_V1
        + "INSERT INTO schema_migrations(version, name, applied_at) "
        "VALUES (1, 'initial_local_store', '2026-01-01T00:00:00Z');"
    )
    connection.close()
    workspace = LocalWorkspace(tmp_path / "old")
    assert workspace.store.schema_version() == CURRENT_SCHEMA_VERSION
    workspace.store.execute("SELECT last_export_at FROM documents LIMIT 1")
    workspace.close()


def test_interrupted_v2_ddl_before_version_row_is_resumable(tmp_path: Path) -> None:
    """Crash after ADD COLUMN but before schema_migrations insert must reopen."""

    import sqlite3

    from movie_muse.persistence.migrations import SCHEMA_V1, column_exists
    from movie_muse.persistence.store import DB_NAME

    db_path = tmp_path / "crashed" / DB_NAME
    db_path.parent.mkdir(parents=True)
    connection = sqlite3.connect(str(db_path))
    connection.executescript(
        SCHEMA_V1
        + "INSERT INTO schema_migrations(version, name, applied_at) "
        "VALUES (1, 'initial_local_store', '2026-01-01T00:00:00Z');"
        + "ALTER TABLE documents ADD COLUMN last_export_at TEXT;"
    )
    versions = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
    assert versions == {1}
    assert column_exists(connection, "documents", "last_export_at")
    connection.close()

    workspace = LocalWorkspace(tmp_path / "crashed")
    assert workspace.store.schema_version() == CURRENT_SCHEMA_VERSION
    workspace.store.execute("SELECT last_export_at FROM documents LIMIT 1")
    workspace.close()
    again = LocalWorkspace(tmp_path / "crashed")
    assert again.store.schema_version() == CURRENT_SCHEMA_VERSION
    again.close()


def test_status_is_unambiguous_after_save(
    tmp_path: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> None:
    project, document, branch_id = project_bundle
    workspace = LocalWorkspace(tmp_path / "ws")
    workspace.open_project(project, document, branch_id=branch_id)
    workspace.save(document, actor_id=project.owner_actor_id, device_id="dev_test")
    status = workspace.status()
    assert status.save_state is LocalSaveState.QUEUED_FOR_SYNC
    assert status.pending_outbox == 1
    workspace.close()


def test_replace_does_not_drop_export_column(
    tmp_path: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> None:
    project, document, branch_id = project_bundle
    workspace = LocalWorkspace(tmp_path / "ws")
    workspace.open_project(project, document, branch_id=branch_id)
    workspace.export_document(tmp_path / "a.json")
    row = workspace.store.fetchone("SELECT last_export_at FROM documents WHERE id=?", (document.id,))
    assert row is not None and row["last_export_at"]
    workspace.open_project(project, replace(document, title=document.title), branch_id=branch_id)
    row = workspace.store.fetchone("SELECT last_export_at FROM documents WHERE id=?", (document.id,))
    assert row is not None and row["last_export_at"]
    workspace.close()
