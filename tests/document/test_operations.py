"""Typed operations mutate a new ScreenplayDocument; the original stays intact."""

from __future__ import annotations

import pytest

from movie_muse.document.api import InvalidOperationError, apply_change_set, apply_operation
from movie_muse.schemas.api import (
    Block,
    BlockKind,
    ChangeSet,
    ChangeSetOperation,
    OperationType,
    ScreenplayDocument,
    new_id,
)


def test_insert_block_does_not_mutate_original(sample_document: ScreenplayDocument) -> None:
    original_len = len(sample_document.blocks)
    block = Block(id=new_id("block"), kind=BlockKind.ACTION, text="She smiles.")
    result = apply_operation(
        sample_document,
        ChangeSetOperation(
            id="op-0",
            order=0,
            op_type=OperationType.INSERT_BLOCK,
            target_id=block.id,
            payload={"block": block.to_dict(), "index": 2},
        ),
    )
    assert len(sample_document.blocks) == original_len
    assert len(result.blocks) == original_len + 1
    assert result.blocks[2].text == "She smiles."


def test_delete_block_drops_annotations(sample_document: ScreenplayDocument) -> None:
    heading_id = sample_document.blocks[0].id
    result = apply_operation(
        sample_document,
        ChangeSetOperation(id="op-0", order=0, op_type=OperationType.DELETE_BLOCK, target_id=heading_id),
    )
    assert heading_id not in {block.id for block in result.blocks}
    assert all(note.block_id != heading_id for note in result.notes)
    assert all(tag.block_id != heading_id for tag in result.production_tags)


def test_update_and_move_round_trip_through_changeset(sample_document: ScreenplayDocument) -> None:
    action = sample_document.blocks[1]
    ops = (
        ChangeSetOperation(
            id="op-0",
            order=0,
            op_type=OperationType.UPDATE_BLOCK,
            target_id=action.id,
            payload={"text": "Ada picks the lock."},
        ),
        ChangeSetOperation(
            id="op-1",
            order=1,
            op_type=OperationType.MOVE_BLOCK,
            target_id=action.id,
            payload={"index": 0},
        ),
    )
    result = apply_change_set(
        sample_document,
        ChangeSet(
            id=new_id("change_set"),
            base_revision_id=sample_document.base_revision_id or sample_document.id,
            author_actor_id=new_id("actor"),
            created_at="2026-09-01T00:00:00Z",
            operations=ops,
        ),
    )
    assert result.blocks[0].id == action.id
    assert result.blocks[0].text == "Ada picks the lock."


def test_unknown_block_delete_fails_closed(sample_document: ScreenplayDocument) -> None:
    with pytest.raises(InvalidOperationError, match="unknown block"):
        apply_operation(
            sample_document,
            ChangeSetOperation(
                id="op-0", order=0, op_type=OperationType.DELETE_BLOCK, target_id=new_id("block")
            ),
        )


def test_insert_scene_appends_to_sequence(sample_document: ScreenplayDocument) -> None:
    scene_id = new_id("scene")
    result = apply_operation(
        sample_document,
        ChangeSetOperation(
            id="op-0",
            order=0,
            op_type=OperationType.INSERT_SCENE,
            target_id=scene_id,
            payload={"scene_id": scene_id, "sequence_id": sample_document.sequences[0].id},
        ),
    )
    assert scene_id in result.sequences[0].scene_ids
