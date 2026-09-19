"""Element transitions. Always emit ChangeSet operations, never editor JSON."""

from __future__ import annotations

from movie_muse.editor.errors import EditorCommandError
from movie_muse.editor.types import ENTER_TRANSITIONS, TAB_TRANSITIONS
from movie_muse.schemas.api import (
    Block,
    BlockKind,
    ChangeSet,
    ChangeSetOperation,
    OperationType,
    ScreenplayDocument,
    new_id,
    new_ulid,
)


def next_kind(current: str, key: str) -> str:
    table = ENTER_TRANSITIONS if key == "Enter" else TAB_TRANSITIONS
    nxt = table.get(current)
    if nxt is None:
        raise EditorCommandError(f"no {key} transition from {current}")
    return nxt


_SPEECH_KINDS = frozenset({BlockKind.PARENTHETICAL, BlockKind.DIALOGUE})


def _valid_predecessor(follower: BlockKind, predecessor: BlockKind) -> bool:
    if follower is BlockKind.PARENTHETICAL:
        return predecessor in {BlockKind.CHARACTER, BlockKind.DIALOGUE}
    if follower is BlockKind.DIALOGUE:
        return predecessor in {BlockKind.CHARACTER, BlockKind.PARENTHETICAL}
    return True


def _speech_run_end(blocks: tuple[Block, ...], start: int) -> int:
    index = start
    if blocks[index].kind is BlockKind.CHARACTER:
        index += 1
    while index < len(blocks) and blocks[index].kind in _SPEECH_KINDS:
        index += 1
    return max(start, index - 1)


def insertion_after_id(document: ScreenplayDocument, block_id: str, new_kind: str) -> str | None:
    """Return the block to insert after, or None when the transition already exists."""

    index = next((i for i, block in enumerate(document.blocks) if block.id == block_id), None)
    if index is None:
        raise EditorCommandError(f"unknown block {block_id}")
    kind = BlockKind(new_kind)
    blocks = document.blocks
    if index + 1 < len(blocks):
        follower = blocks[index + 1]
        if follower.kind is kind and kind in _SPEECH_KINDS:
            return None
        if not _valid_predecessor(follower.kind, kind):
            end = _speech_run_end(blocks, index)
            if end + 1 < len(blocks) and not _valid_predecessor(blocks[end + 1].kind, kind):
                return None
            return blocks[end].id
    return blocks[index].id


def transition_change_set(
    document: ScreenplayDocument,
    *,
    block_id: str,
    key: str,
    actor_id: str,
    created_at: str,
) -> ChangeSet | None:
    index = next((i for i, block in enumerate(document.blocks) if block.id == block_id), None)
    if index is None:
        raise EditorCommandError(f"unknown block {block_id}")
    current = document.blocks[index]
    kind = next_kind(current.kind.value, key)
    after_id = insertion_after_id(document, block_id, kind)
    if after_id is None:
        return None
    block = _new_block(kind, current)
    base = document.base_revision_id
    if not base:
        raise EditorCommandError("document has no base revision; cannot author")
    return ChangeSet(
        id=new_id("change_set"),
        base_revision_id=base,
        author_actor_id=actor_id,
        created_at=created_at,
        operations=(
            ChangeSetOperation(
                id=new_ulid(),
                order=0,
                op_type=OperationType.INSERT_BLOCK,
                target_id=block.id,
                payload={"block": block.to_dict(), "after_id": after_id},
            ),
        ),
    )


def _new_block(kind: str, previous: Block) -> Block:
    block_kind = BlockKind(kind)
    extras: dict[str, object] = {}
    scene_id = previous.scene_id
    character_cue_id = None
    dialogue_pair_id = None
    if block_kind is BlockKind.SCENE_HEADING:
        scene_id = new_id("scene")
    if block_kind is BlockKind.CHARACTER:
        character_cue_id = new_id("character_cue")
    if block_kind is BlockKind.DIALOGUE:
        dialogue_pair_id = new_id("dialogue_pair")
        character_cue_id = previous.character_cue_id
        if previous.kind is BlockKind.CHARACTER:
            extras["cue_from"] = previous.id
    if block_kind is BlockKind.PAGE_BREAK:
        text = ""
    else:
        text = ""
    return Block(
        id=new_id("block"),
        kind=block_kind,
        text=text,
        scene_id=scene_id,
        character_cue_id=character_cue_id,
        dialogue_pair_id=dialogue_pair_id,
        unknown_extensions=extras,
    )


def update_text_change_set(
    document: ScreenplayDocument,
    *,
    block_id: str,
    text: str,
    actor_id: str,
    created_at: str,
) -> ChangeSet:
    if not document.base_revision_id:
        raise EditorCommandError("document has no base revision; cannot author")
    if not any(block.id == block_id for block in document.blocks):
        raise EditorCommandError(f"unknown block {block_id}")
    return ChangeSet(
        id=new_id("change_set"),
        base_revision_id=document.base_revision_id,
        author_actor_id=actor_id,
        created_at=created_at,
        operations=(
            ChangeSetOperation(
                id=new_ulid(),
                order=0,
                op_type=OperationType.UPDATE_BLOCK,
                target_id=block_id,
                payload={"text": text},
            ),
        ),
    )


def invert_change_set(
    document: ScreenplayDocument,
    change_set: ChangeSet,
    *,
    created_at: str,
) -> ChangeSet:
    """Build the inverse ChangeSet against the pre-apply document."""

    inverses: list[ChangeSetOperation] = []
    order = 0
    for operation in reversed(change_set.operations):
        if operation.op_type is OperationType.UPDATE_BLOCK:
            prior = next((block for block in document.blocks if block.id == operation.target_id), None)
            if prior is None:
                continue
            payload: dict[str, object] = {"text": prior.text}
            if "unknown_extensions" in (operation.payload or {}):
                payload["unknown_extensions"] = dict(prior.unknown_extensions)
            inverses.append(
                ChangeSetOperation(
                    id=new_ulid(),
                    order=order,
                    op_type=OperationType.UPDATE_BLOCK,
                    target_id=operation.target_id,
                    payload=payload,
                )
            )
            order += 1
        elif operation.op_type is OperationType.INSERT_BLOCK:
            inverses.append(
                ChangeSetOperation(
                    id=new_ulid(),
                    order=order,
                    op_type=OperationType.DELETE_BLOCK,
                    target_id=operation.target_id,
                    payload={},
                )
            )
            order += 1
        elif operation.op_type is OperationType.DELETE_BLOCK:
            prior_index = next(
                (index for index, block in enumerate(document.blocks) if block.id == operation.target_id),
                None,
            )
            if prior_index is None:
                continue
            prior = document.blocks[prior_index]
            insert_payload: dict[str, object] = {"block": prior.to_dict()}
            if prior_index > 0:
                insert_payload["after_id"] = document.blocks[prior_index - 1].id
            inverses.append(
                ChangeSetOperation(
                    id=new_ulid(),
                    order=order,
                    op_type=OperationType.INSERT_BLOCK,
                    target_id=prior.id,
                    payload=insert_payload,
                )
            )
            order += 1
    if not document.base_revision_id:
        raise EditorCommandError("cannot invert without a base revision")
    return ChangeSet(
        id=new_id("change_set"),
        base_revision_id=document.base_revision_id,
        author_actor_id=change_set.author_actor_id,
        created_at=created_at,
        operations=tuple(inverses),
    )
