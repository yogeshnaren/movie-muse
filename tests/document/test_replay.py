"""Property-style replay and serialization determinism."""

from __future__ import annotations

from movie_muse.document.api import apply_change_set, normalize, replay, structural_diff
from movie_muse.schemas.api import (
    Block,
    BlockKind,
    ChangeSet,
    ChangeSetOperation,
    OperationType,
    ScreenplayDocument,
    new_id,
)


def test_replay_is_idempotent(sample_document: ScreenplayDocument) -> None:
    block = Block(id=new_id("block"), kind=BlockKind.TRANSITION, text="CUT TO:")
    change_set = ChangeSet(
        id=new_id("change_set"),
        base_revision_id=sample_document.base_revision_id or sample_document.id,
        author_actor_id=new_id("actor"),
        created_at="2026-09-01T00:00:00Z",
        operations=(
            ChangeSetOperation(
                id="op-0",
                order=0,
                op_type=OperationType.INSERT_BLOCK,
                target_id=block.id,
                payload={"block": block.to_dict()},
            ),
        ),
    )
    first = replay(sample_document, change_set)
    second = replay(sample_document, change_set)
    assert first == second
    assert first.to_dict() == second.to_dict()


def test_serialization_round_trip_is_deterministic(sample_document: ScreenplayDocument) -> None:
    document = normalize(sample_document)
    restored = ScreenplayDocument.from_dict(document.to_dict())
    assert restored == document
    assert restored.to_dict() == document.to_dict()


def test_diff_apply_reproduces_target(sample_document: ScreenplayDocument) -> None:
    extra = Block(id=new_id("block"), kind=BlockKind.SHOT, text="CLOSE ON the lock.")
    target = apply_change_set(
        sample_document,
        ChangeSet(
            id=new_id("change_set"),
            base_revision_id=sample_document.base_revision_id or sample_document.id,
            author_actor_id=new_id("actor"),
            created_at="2026-09-01T00:00:00Z",
            operations=(
                ChangeSetOperation(
                    id="op-0",
                    order=0,
                    op_type=OperationType.INSERT_BLOCK,
                    target_id=extra.id,
                    payload={"block": extra.to_dict(), "index": 1},
                ),
                ChangeSetOperation(
                    id="op-1",
                    order=1,
                    op_type=OperationType.UPDATE_METADATA,
                    target_id=sample_document.id,
                    payload={"title": "Pilot — revised"},
                ),
            ),
        ),
    )
    diff = structural_diff(
        sample_document,
        target,
        author_actor_id=new_id("actor"),
        created_at="2026-09-01T00:00:00Z",
        base_revision_id=sample_document.base_revision_id,
    )
    replayed = replay(sample_document, diff)
    assert replayed.title == target.title
    assert [block.id for block in replayed.blocks] == [block.id for block in target.blocks]
    assert [block.text for block in replayed.blocks] == [block.text for block in target.blocks]
