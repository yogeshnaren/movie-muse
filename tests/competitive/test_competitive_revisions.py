"""Branch/merge workflows represented by Arc Studio."""

from __future__ import annotations

from movie_muse.editor.api import EditorService
from movie_muse.revisions.api import MergeConflictError, RevisionService
from movie_muse.schemas.api import (
    BlockKind,
    ChangeSet,
    ChangeSetOperation,
    OperationType,
    Project,
    ScreenplayDocument,
    new_id,
)


def _update(base_revision_id: str, actor_id: str, block_id: str, text: str) -> ChangeSet:
    return ChangeSet(
        id=new_id("change_set"),
        base_revision_id=base_revision_id,
        author_actor_id=actor_id,
        created_at="2026-09-05T00:00:00Z",
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


def test_arc_history_branch_merge(
    kitchen_session: tuple[EditorService, ScreenplayDocument, Project],
) -> None:
    session, document, project = kitchen_session
    service: RevisionService = session.revisions
    actor_id = project.owner_actor_id
    action = next(block for block in document.blocks if block.kind is BlockKind.ACTION)
    dialogue = next(block for block in document.blocks if block.kind is BlockKind.DIALOGUE)
    base = service.canon_head_id()
    service.create_branch("feature", actor_id=actor_id, from_revision_id=base)
    service.apply_change_set(
        _update(base, actor_id, action.id, "Ada waits at the door."),
        actor_id=actor_id,
        branch_ref="main",
    )
    service.apply_change_set(
        _update(base, actor_id, dialogue.id, "It was never locked."),
        actor_id=actor_id,
        branch_ref="feature",
    )
    merge = service.merge_into(source_branch="feature", target_branch="main", actor_id=actor_id)
    assert merge.conflicts == ()
    merged = service.load_revision(merge.resulting_revision_id or "")
    assert merged.blocks[action_index(merged, action.id)].text == "Ada waits at the door."
    assert merged.blocks[action_index(merged, dialogue.id)].text == "It was never locked."
    assert session.history_text()

    overlap_base = service.canon_head_id()
    service.create_branch("clash", actor_id=actor_id, from_revision_id=overlap_base)
    service.apply_change_set(
        _update(overlap_base, actor_id, action.id, "Ada smiles."),
        actor_id=actor_id,
        branch_ref="main",
    )
    service.apply_change_set(
        _update(overlap_base, actor_id, action.id, "Ada frowns."),
        actor_id=actor_id,
        branch_ref="clash",
    )
    head = service.get_branch("main").head_revision_id
    try:
        service.merge_into(source_branch="clash", target_branch="main", actor_id=actor_id)
        raise AssertionError("overlapping merge must fail closed")
    except MergeConflictError:
        pass
    assert service.get_branch("main").head_revision_id == head


def action_index(document, block_id: str) -> int:
    return next(i for i, block in enumerate(document.blocks) if block.id == block_id)
