"""Explicitly lossy Fountain and plain-text import pathways."""

from __future__ import annotations

from movie_muse.document.api import normalize, semantic_validate
from movie_muse.fdx.types import LossAccumulator, LossReport
from movie_muse.schemas.api import Block, BlockKind, ScreenplayDocument, Sequence, new_id

_SCENE_PREFIXES = ("INT.", "EXT.", "INT/", "EXT/", "I/E.", "E/I.")
_TRANSITIONS = ("CUT TO:", "FADE OUT.", "FADE IN:", "DISSOLVE TO:", "SMASH CUT TO:")


def import_fountain(text: str) -> tuple[ScreenplayDocument, LossReport]:
    return _import_lossy(text, pathway="fountain")


def import_plain_text(text: str) -> tuple[ScreenplayDocument, LossReport]:
    return _import_lossy(text, pathway="plain_text")


def _import_lossy(text: str, *, pathway: str) -> tuple[ScreenplayDocument, LossReport]:
    losses = LossAccumulator(pathway=pathway)
    losses.add(
        "production_metadata_dropped",
        "Fountain/plain-text cannot preserve notes, tags, revisions, locks, omitted/A-B numbering, or dual dialogue",
    )
    losses.add(
        "ids_minted",
        "Stable Movie Muse identifiers are minted on import; they will not round-trip a prior FDX document",
    )
    blocks: list[Block] = []
    scene_ids: list[str] = []
    pending_character: Block | None = None
    for raw_line in text.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            pending_character = None
            continue
        if line.startswith("Title:"):
            blocks.append(_block(BlockKind.TITLE_PAGE_ELEMENT, line.split(":", 1)[1].strip()))
            continue
        if line.startswith("Credit:") or line.startswith("Author:"):
            blocks.append(_block(BlockKind.TITLE_PAGE_ELEMENT, line.split(":", 1)[1].strip()))
            continue
        if _is_scene(line):
            scene_id = new_id("scene")
            scene_ids.append(scene_id)
            blocks.append(_block(BlockKind.SCENE_HEADING, line.lstrip(".").strip(), scene_id=scene_id, scene_number=str(len(scene_ids))))
            pending_character = None
            continue
        if line.startswith(">") or line.upper().rstrip() in _TRANSITIONS:
            blocks.append(_block(BlockKind.TRANSITION, line.lstrip(">").strip()))
            pending_character = None
            continue
        if line.startswith("(") and line.endswith(")") and pending_character is not None:
            blocks.append(
                _block(
                    BlockKind.PARENTHETICAL,
                    line,
                    character_cue_id=pending_character.character_cue_id,
                )
            )
            continue
        if _looks_like_character(line):
            cue_id = new_id("character_cue")
            pending_character = _block(BlockKind.CHARACTER, line, character_cue_id=cue_id)
            blocks.append(pending_character)
            continue
        if pending_character is not None:
            blocks.append(
                _block(
                    BlockKind.DIALOGUE,
                    line,
                    character_cue_id=pending_character.character_cue_id,
                    dialogue_pair_id=new_id("dialogue_pair"),
                )
            )
            continue
        blocks.append(_block(BlockKind.ACTION, line))
    if not blocks:
        blocks.append(_block(BlockKind.ACTION, text.strip() or "Empty document"))
        losses.add("empty_input", "input contained no screenplay lines; a placeholder action was created")
    title = "Untitled"
    for block in blocks:
        if block.kind is BlockKind.TITLE_PAGE_ELEMENT:
            title = block.text
            break
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=new_id("project"),
        title=title,
        sequences=(
            Sequence(
                id=new_id("sequence"),
                title="Imported",
                order=0,
                scene_ids=tuple(scene_ids),
            ),
        ),
        blocks=tuple(blocks),
    )
    normalized = normalize(document)
    semantic_validate(normalized)
    return normalized, losses.report()


def _block(
    kind: BlockKind,
    text: str,
    *,
    scene_id: str | None = None,
    scene_number: str | None = None,
    character_cue_id: str | None = None,
    dialogue_pair_id: str | None = None,
) -> Block:
    return Block(
        id=new_id("block"),
        kind=kind,
        text=text,
        scene_id=scene_id,
        scene_number=scene_number,
        character_cue_id=character_cue_id,
        dialogue_pair_id=dialogue_pair_id,
    )


def _is_scene(line: str) -> bool:
    stripped = line.lstrip(".").strip().upper()
    return stripped.startswith(_SCENE_PREFIXES)


def _looks_like_character(line: str) -> bool:
    if line.startswith("(") or line.endswith(":"):
        return False
    letters = [char for char in line if char.isalpha()]
    if len(letters) < 2 or len(line) > 40:
        return False
    return line == line.upper() and any(char.isalpha() for char in line)
