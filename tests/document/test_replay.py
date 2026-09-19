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
    assert replayed.sequences == target.sequences


def test_diff_replay_reproduces_sequence_membership(sample_document: ScreenplayDocument) -> None:
    sequence = sample_document.sequences[0]
    extra_scene_id = new_id("scene")
    heading = Block(
        id=new_id("block"),
        kind=BlockKind.SCENE_HEADING,
        text="EXT. ALLEY - NIGHT",
        scene_id=extra_scene_id,
        scene_number="2",
    )
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
                    target_id=heading.id,
                    payload={"block": heading.to_dict()},
                ),
                ChangeSetOperation(
                    id="op-1",
                    order=1,
                    op_type=OperationType.INSERT_SCENE,
                    target_id=extra_scene_id,
                    payload={"scene_id": extra_scene_id, "sequence_id": sequence.id},
                ),
            ),
        ),
    )
    assert extra_scene_id in target.sequences[0].scene_ids
    diff = structural_diff(
        sample_document,
        target,
        author_actor_id=new_id("actor"),
        created_at="2026-09-01T00:00:00Z",
        base_revision_id=sample_document.base_revision_id,
    )
    replayed = replay(sample_document, diff)
    assert replayed.sequences == target.sequences
    assert [block.scene_id for block in replayed.blocks if block.kind is BlockKind.SCENE_HEADING] == [
        block.scene_id for block in target.blocks if block.kind is BlockKind.SCENE_HEADING
    ]
    assert normalize(replayed) == normalize(target)


def test_diff_replay_reproduces_sequence_reorder_and_removal(
    sample_document: ScreenplayDocument,
) -> None:
    sequence = sample_document.sequences[0]
    first_scene = sequence.scene_ids[0]
    extra_scene_id = new_id("scene")
    heading = Block(
        id=new_id("block"),
        kind=BlockKind.SCENE_HEADING,
        text="EXT. ALLEY - NIGHT",
        scene_id=extra_scene_id,
        scene_number="2",
    )
    two_scenes = apply_change_set(
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
                    target_id=heading.id,
                    payload={"block": heading.to_dict()},
                ),
                ChangeSetOperation(
                    id="op-1",
                    order=1,
                    op_type=OperationType.INSERT_SCENE,
                    target_id=extra_scene_id,
                    payload={
                        "sequence_id": sequence.id,
                        "scene_ids": (extra_scene_id, first_scene),
                    },
                ),
            ),
        ),
    )
    assert two_scenes.sequences[0].scene_ids == (extra_scene_id, first_scene)
    removed = apply_change_set(
        two_scenes,
        ChangeSet(
            id=new_id("change_set"),
            base_revision_id=two_scenes.base_revision_id or two_scenes.id,
            author_actor_id=new_id("actor"),
            created_at="2026-09-01T00:00:00Z",
            operations=(
                ChangeSetOperation(
                    id="op-0",
                    order=0,
                    op_type=OperationType.INSERT_SCENE,
                    target_id=extra_scene_id,
                    payload={"sequence_id": sequence.id, "scene_ids": (first_scene,)},
                ),
            ),
        ),
    )
    assert removed.sequences[0].scene_ids == (first_scene,)
    reordered_diff = structural_diff(
        sample_document,
        two_scenes,
        author_actor_id=new_id("actor"),
        created_at="2026-09-01T00:00:00Z",
        base_revision_id=sample_document.base_revision_id,
    )
    assert replay(sample_document, reordered_diff).sequences == two_scenes.sequences
    removed_diff = structural_diff(
        two_scenes,
        removed,
        author_actor_id=new_id("actor"),
        created_at="2026-09-01T00:00:00Z",
        base_revision_id=two_scenes.base_revision_id,
    )
    replayed = replay(two_scenes, removed_diff)
    assert replayed.sequences == removed.sequences
    assert extra_scene_id not in replayed.sequences[0].scene_ids
