"""Authoring/navigation workflows represented by Final Draft and Arc Studio."""

from __future__ import annotations

from movie_muse.editor.api import EditorService
from movie_muse.schemas.api import BlockKind, Project, ScreenplayDocument


def test_fd_author_keyboard(
    kitchen_session: tuple[EditorService, ScreenplayDocument, Project],
) -> None:
    session, document, _project = kitchen_session
    action = next(block for block in document.blocks if block.kind is BlockKind.ACTION)
    existing_character = next(block for block in document.blocks if block.kind is BlockKind.CHARACTER)
    session.transition(action.id, "Tab")
    inserted_character = next(
        block
        for block in session.document().blocks
        if block.kind is BlockKind.CHARACTER and block.id != existing_character.id
    )
    assert inserted_character.character_cue_id
    session.transition(inserted_character.id, "Enter")
    inserted_dialogue = next(
        block
        for block in session.document().blocks
        if block.kind is BlockKind.DIALOGUE and block.character_cue_id == inserted_character.character_cue_id
    )
    assert inserted_dialogue.dialogue_pair_id
    session.transition(existing_character.id, "Enter")
    kinds = [block.kind for block in session.document().blocks]
    existing_index = next(i for i, block in enumerate(session.document().blocks) if block.id == existing_character.id)
    assert kinds[existing_index + 1] in {BlockKind.PARENTHETICAL, BlockKind.DIALOGUE}


def test_arc_outline_cards(
    kitchen_session: tuple[EditorService, ScreenplayDocument, Project],
) -> None:
    session, document, _project = kitchen_session
    headings = [block for block in document.blocks if block.kind is BlockKind.SCENE_HEADING]
    outline = session.outline()
    assert [entry.heading for entry in outline] == [block.text for block in headings]
    cards = session.cards()
    assert {card.scene_id for card in cards} == {block.scene_id for block in headings if block.scene_id}
