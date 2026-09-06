"""Outline and scene cards derived from ScreenplayDocument, not editor pixels."""

from __future__ import annotations

from movie_muse.editor.types import OutlineEntry, SceneCard
from movie_muse.schemas.api import BlockKind, ScreenplayDocument


def outline(document: ScreenplayDocument) -> tuple[OutlineEntry, ...]:
    entries: list[OutlineEntry] = []
    blocks = list(document.blocks)
    for index, block in enumerate(blocks):
        if block.kind is not BlockKind.SCENE_HEADING or not block.scene_id:
            continue
        summary = ""
        for later in blocks[index + 1 :]:
            if later.kind is BlockKind.SCENE_HEADING:
                break
            if later.text.strip():
                summary = later.text.strip()
                break
        entries.append(
            OutlineEntry(
                scene_id=block.scene_id,
                scene_number=block.scene_number or "",
                heading=block.text,
                block_id=block.id,
                summary=summary,
            )
        )
    return tuple(entries)


def cards(document: ScreenplayDocument) -> tuple[SceneCard, ...]:
    result: list[SceneCard] = []
    current_ids: list[str] = []
    heading = ""
    scene_id = ""
    summary = ""
    for block in document.blocks:
        if block.kind is BlockKind.SCENE_HEADING:
            if scene_id:
                result.append(
                    SceneCard(
                        scene_id=scene_id,
                        heading=heading,
                        summary=summary,
                        block_ids=tuple(current_ids),
                    )
                )
            scene_id = block.scene_id or block.id
            heading = block.text
            summary = ""
            current_ids = [block.id]
            continue
        if scene_id:
            current_ids.append(block.id)
            if not summary and block.text.strip() and block.kind is not BlockKind.CHARACTER:
                summary = block.text.strip()
    if scene_id:
        result.append(
            SceneCard(scene_id=scene_id, heading=heading, summary=summary, block_ids=tuple(current_ids))
        )
    return tuple(result)
