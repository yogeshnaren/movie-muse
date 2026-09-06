"""Semantic validation beyond the schema-level ScreenplayDocument.validate()."""

from __future__ import annotations

import re

from movie_muse.document.errors import SemanticValidationError
from movie_muse.schemas.api import Block, BlockKind, ScreenplayDocument

_SCENE_NUMBER = re.compile(r"^[A-Za-z0-9]+([.-][A-Za-z0-9]+)*$")


def semantic_validate(document: ScreenplayDocument) -> None:
    """Raise SemanticValidationError if professional structure is violated."""

    document.validate()
    _validate_scene_numbers(document)
    _validate_dialogue_adjacency(document)
    _validate_dual_dialogue_groups(document)
    _validate_sequence_scenes(document)


def _active_blocks(document: ScreenplayDocument) -> list[Block]:
    return [block for block in document.blocks if not block.is_boneyard]


def _validate_scene_numbers(document: ScreenplayDocument) -> None:
    seen: set[str] = set()
    for block in document.blocks:
        if block.kind is not BlockKind.SCENE_HEADING or not block.scene_number:
            continue
        if not _SCENE_NUMBER.match(block.scene_number):
            raise SemanticValidationError(
                f"scene_number {block.scene_number!r} is not alphanumeric"
            )
        if block.scene_number in seen:
            raise SemanticValidationError(f"duplicate scene_number {block.scene_number!r}")
        seen.add(block.scene_number)


def _validate_dialogue_adjacency(document: ScreenplayDocument) -> None:
    previous: Block | None = None
    for block in _active_blocks(document):
        if block.kind is BlockKind.PARENTHETICAL:
            if previous is None or previous.kind not in {BlockKind.CHARACTER, BlockKind.DIALOGUE}:
                raise SemanticValidationError("parenthetical must follow a character or dialogue block")
        if block.kind is BlockKind.DIALOGUE:
            if previous is None or previous.kind not in {BlockKind.CHARACTER, BlockKind.PARENTHETICAL}:
                raise SemanticValidationError("dialogue must follow a character or parenthetical block")
            if block.is_continued and previous.kind is BlockKind.CHARACTER and not previous.is_continued:
                pass
        previous = block


def _validate_dual_dialogue_groups(document: ScreenplayDocument) -> None:
    groups: dict[str, list[Block]] = {}
    for block in _active_blocks(document):
        if not block.is_dual_dialogue:
            continue
        if not block.dual_dialogue_group_id:
            raise SemanticValidationError("dual dialogue block missing dual_dialogue_group_id")
        groups.setdefault(block.dual_dialogue_group_id, []).append(block)
    for group_id, members in groups.items():
        kinds = [block.kind for block in members]
        if kinds.count(BlockKind.CHARACTER) < 2 or kinds.count(BlockKind.DIALOGUE) < 2:
            raise SemanticValidationError(
                f"dual dialogue group {group_id} must contain at least two character and two dialogue blocks"
            )


def _validate_sequence_scenes(document: ScreenplayDocument) -> None:
    heading_scene_ids = {
        block.scene_id for block in document.blocks if block.kind is BlockKind.SCENE_HEADING and block.scene_id
    }
    for sequence in document.sequences:
        for scene_id in sequence.scene_ids:
            if scene_id not in heading_scene_ids:
                raise SemanticValidationError(
                    f"sequence {sequence.id} references scene {scene_id} with no scene_heading"
                )
