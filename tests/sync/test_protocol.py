"""Outbox/inbox duplicates, out-of-order envelopes, and quarantine."""

from __future__ import annotations

import json
from pathlib import Path

from movie_muse.persistence.api import LocalSaveState, LocalWorkspace
from movie_muse.schemas.api import Project, ScreenplayDocument, new_id
from movie_muse.sync.api import SyncProtocol


def _envelopes(workspace: LocalWorkspace) -> dict[str, dict[str, object]]:
    rows = workspace.store.fetchall("SELECT operation_id, envelope_json FROM outbox")
    return {
        str(row["operation_id"]): json.loads(str(row["envelope_json"])) for row in rows
    }


def test_duplicate_envelopes_are_ignored(
    tmp_path: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> None:
    project, document, branch_id = project_bundle
    workspace = LocalWorkspace(tmp_path / "ws")
    workspace.open_project(project, document, branch_id=branch_id)
    ack = workspace.save(workspace.reopen(), actor_id=project.owner_actor_id, device_id="dev_a")
    protocol = SyncProtocol(workspace)
    assert ack.operation_id in protocol.flush_outbox()
    envelope = _envelopes(workspace)[ack.operation_id]
    assert protocol.ingest(envelope) == "duplicate"
    assert protocol.ingest(envelope) == "duplicate"
    workspace.close()


def test_out_of_order_envelope_is_buffered_then_applied(
    tmp_path: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> None:
    project, document, branch_id = project_bundle
    source = LocalWorkspace(tmp_path / "source")
    source.open_project(project, document, branch_id=branch_id)
    first = source.save(source.reopen(), actor_id=project.owner_actor_id, device_id="dev_a")
    second = source.save(source.reopen(), actor_id=project.owner_actor_id, device_id="dev_a")
    envelopes = _envelopes(source)
    first_env = envelopes[first.operation_id]
    second_env = envelopes[second.operation_id]

    peer = LocalWorkspace(tmp_path / "peer")
    peer.open_project(project, document, branch_id=branch_id)
    protocol = SyncProtocol(peer)
    assert protocol.ingest(second_env) == "buffered"
    assert not peer.has_revision(second.revision_id)
    assert protocol.ingest(first_env) == "applied"
    assert peer.has_revision(first.revision_id)
    assert peer.has_revision(second.revision_id)
    source.close()
    peer.close()


def test_conflicting_head_is_not_last_writer_wins(
    tmp_path: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> None:
    project, document, branch_id = project_bundle
    workspace = LocalWorkspace(tmp_path / "ws")
    workspace.open_project(project, document, branch_id=branch_id)
    first = workspace.save(workspace.reopen(), actor_id=project.owner_actor_id, device_id="dev_a")
    workspace.save(workspace.reopen(), actor_id=project.owner_actor_id, device_id="dev_a")
    fork = dict(_envelopes(workspace)[first.operation_id])
    fork["operation_id"] = "fork" + first.operation_id[4:]
    fork["resulting_revision_id"] = new_id("revision")
    protocol = SyncProtocol(workspace)
    assert protocol.ingest(fork) == "conflicted"
    assert workspace.status().save_state is LocalSaveState.CONFLICTED
    workspace.close()


def test_quarantine_keeps_unsynced_work(
    tmp_path: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> None:
    project, document, branch_id = project_bundle
    workspace = LocalWorkspace(tmp_path / "ws")
    workspace.open_project(project, document, branch_id=branch_id)
    ack = workspace.save(workspace.reopen(), actor_id=project.owner_actor_id, device_id="dev_a")
    protocol = SyncProtocol(workspace)
    assert protocol.quarantine_unsynced(reason="acl_revoked") == 1
    row = workspace.store.fetchone(
        "SELECT status FROM outbox WHERE operation_id=?",
        (ack.operation_id,),
    )
    assert row is not None
    assert row["status"] == LocalSaveState.RECOVERY_ONLY.value
    assert workspace.reopen().base_revision_id == ack.revision_id
    workspace.close()


def _peer_ingest(
    tmp_path: Path,
    project: Project,
    document: ScreenplayDocument,
    branch_id: str,
    envelope: dict[str, object],
    *,
    label: str,
) -> tuple[str, str | None, ScreenplayDocument]:
    peer = LocalWorkspace(tmp_path / label)
    peer.open_project(project, document, branch_id=branch_id)
    head_before = peer.head_revision_id(document.id)
    outcome = SyncProtocol(peer).ingest(envelope)
    loaded = peer.reopen()
    head_after = peer.head_revision_id(document.id)
    peer.close()
    assert head_before == document.base_revision_id
    return outcome, head_after, loaded


def test_forged_resulting_revision_id_is_conflicted_and_does_not_advance_head(
    tmp_path: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> None:
    """Architecture §4: ancestry/integrity must bind resulting revision to the document."""

    project, document, branch_id = project_bundle
    source = LocalWorkspace(tmp_path / "source")
    source.open_project(project, document, branch_id=branch_id)
    ack = source.save(source.reopen(), actor_id=project.owner_actor_id, device_id="dev_a")
    envelope = dict(_envelopes(source)[ack.operation_id])
    forged = new_id("revision")
    envelope["resulting_revision_id"] = forged
    source.close()

    outcome, head_after, loaded = _peer_ingest(
        tmp_path, project, document, branch_id, envelope, label="peer-forged-rev"
    )
    assert outcome == "conflicted"
    assert head_after == document.base_revision_id
    assert loaded.base_revision_id == document.base_revision_id
    assert loaded.base_revision_id != forged


def test_cross_field_envelope_mismatches_are_conflicted(
    tmp_path: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> None:
    project, document, branch_id = project_bundle
    source = LocalWorkspace(tmp_path / "source")
    source.open_project(project, document, branch_id=branch_id)
    ack = source.save(source.reopen(), actor_id=project.owner_actor_id, device_id="dev_a")
    valid = _envelopes(source)[ack.operation_id]
    source.close()

    cases: dict[str, dict[str, object]] = {
        "project": {**valid, "project_id": new_id("project")},
        "branch": {**valid, "branch_id": new_id("branch")},
        "schema": {**valid, "schema_version": "9.9"},
        "acl_epoch": {**valid, "acl_epoch": 7},
    }
    for label, envelope in cases.items():
        outcome, head_after, loaded = _peer_ingest(
            tmp_path, project, document, branch_id, envelope, label=f"peer-{label}"
        )
        assert outcome == "conflicted", label
        assert head_after == document.base_revision_id, label
        assert loaded.base_revision_id == document.base_revision_id, label


def test_valid_envelope_still_applies_to_peer(
    tmp_path: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> None:
    project, document, branch_id = project_bundle
    source = LocalWorkspace(tmp_path / "source")
    source.open_project(project, document, branch_id=branch_id)
    ack = source.save(source.reopen(), actor_id=project.owner_actor_id, device_id="dev_a")
    envelope = _envelopes(source)[ack.operation_id]
    source.close()

    outcome, head_after, loaded = _peer_ingest(
        tmp_path, project, document, branch_id, envelope, label="peer-valid"
    )
    assert outcome == "applied"
    assert head_after == ack.revision_id
    assert loaded.base_revision_id == ack.revision_id
