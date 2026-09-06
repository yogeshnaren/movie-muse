"""Airplane/outage: branch, checkpoint, diff, and export remain available locally."""

from __future__ import annotations

from pathlib import Path

from movie_muse.persistence.api import LocalWorkspace
from movie_muse.revisions.api import RevisionService
from movie_muse.schemas.api import (
    ChangeSet,
    ChangeSetOperation,
    OperationType,
    Project,
    ScreenplayDocument,
    new_id,
)


def update_block_change_set(
    *,
    base_revision_id: str,
    actor_id: str,
    block_id: str,
    text: str,
) -> ChangeSet:
    return ChangeSet(
        id=new_id("change_set"),
        base_revision_id=base_revision_id,
        author_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
        operations=(
            ChangeSetOperation(
                id="op-0",
                order=0,
                op_type=OperationType.UPDATE_BLOCK,
                target_id=block_id,
                payload={"text": text},
            ),
        ),
    )


def test_airplane_and_outages_do_not_block_branch_checkpoint_diff_export(
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
    service = RevisionService(workspace)
    service.bind(actor_id=project.owner_actor_id)
    before = service.canon_head_id()
    service.create_branch("offline-feature", actor_id=project.owner_actor_id)
    checkpoint = service.create_checkpoint("offline-mark", actor_id=project.owner_actor_id)
    ack = service.apply_change_set(
        update_block_change_set(
            base_revision_id=before,
            actor_id=project.owner_actor_id,
            block_id=document.blocks[1].id,
            text="Ada works without a network.",
        ),
        actor_id=project.owner_actor_id,
    )
    diff = service.diff_projection(before, ack.revision_id, actor_id=project.owner_actor_id)
    assert "update_block" in diff.operations_text
    export_path = service.export_document(tmp_path / "offline-export.json")
    assert export_path.is_file()
    assert checkpoint.revision_id == before
    assert service.get_checkpoint("offline-mark").revision_id == before
    assert service.get_branch("offline-feature").head_revision_id == before
    status = workspace.status()
    assert status.connectivity_offline is True
    assert status.auth_outage is True
    assert status.subscription_outage is True
    assert status.sync_outage is True
    assert status.ai_outage is True
    history = service.render_history_text()
    assert ack.revision_id in history
    workspace.close()
