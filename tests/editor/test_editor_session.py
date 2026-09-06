"""Editor session commands go through document/revision commands."""

from __future__ import annotations

import pytest

from movie_muse.document.api import EDITOR_FORMAT
from movie_muse.editor.api import (
    AuthorMode,
    ContextualAction,
    EditorCanonError,
    EditorCommandError,
    EditorService,
)
from movie_muse.schemas.api import BlockKind, ScreenplayDocument


def test_update_text_is_durable_revision(
    editor_session: tuple[EditorService, object, ScreenplayDocument],
) -> None:
    session, _project, original = editor_session
    action = next(block for block in original.blocks if block.kind is BlockKind.ACTION)
    ack = session.update_text(action.id, "Ada studies the lock twice.")
    assert ack.revision_id
    updated = session.document()
    rewritten = next(block for block in updated.blocks if block.id == action.id)
    assert rewritten.text == "Ada studies the lock twice."
    assert updated.base_revision_id == ack.revision_id


def test_enter_and_tab_insert_typed_blocks(
    editor_session: tuple[EditorService, object, ScreenplayDocument],
) -> None:
    session, _project, original = editor_session
    action = next(block for block in original.blocks if block.kind is BlockKind.ACTION)
    before = len(session.document().blocks)
    session.transition(action.id, "Tab")
    after_tab = session.document().blocks
    assert len(after_tab) == before + 1
    inserted = after_tab[list(block.id for block in after_tab).index(action.id) + 1]
    assert inserted.kind is BlockKind.CHARACTER
    session.transition(inserted.id, "Enter")
    after_enter = session.document().blocks
    dialogue = after_enter[list(block.id for block in after_enter).index(inserted.id) + 1]
    assert dialogue.kind is BlockKind.DIALOGUE
    assert dialogue.dialogue_pair_id


def test_undo_and_redo_restore_authored_text(
    editor_session: tuple[EditorService, object, ScreenplayDocument],
) -> None:
    session, _project, original = editor_session
    action = next(block for block in original.blocks if block.kind is BlockKind.ACTION)
    session.update_text(action.id, "Ada waits.")
    session.undo()
    assert next(block for block in session.document().blocks if block.id == action.id).text == action.text
    session.redo()
    assert next(block for block in session.document().blocks if block.id == action.id).text == "Ada waits."


def test_search_replace_and_autocomplete(
    editor_session: tuple[EditorService, object, ScreenplayDocument],
) -> None:
    session, _project, original = editor_session
    hits = session.search("Ada")
    assert hits
    session.replace("Ada", "IRENE")
    assert "IRENE" in session.document().blocks[1].text
    names = session.autocomplete(prefix="AD", kind="character")
    assert any(item.text == "ADA" for item in names)
    headings = session.autocomplete(prefix="INT", kind="scene_heading")
    assert headings
    assert headings[0].text.startswith("INT.")


def test_outline_cards_notes_and_history(
    editor_session: tuple[EditorService, object, ScreenplayDocument],
) -> None:
    session, _project, original = editor_session
    entries = session.outline()
    assert len(entries) == 1
    assert entries[0].heading == "INT. KITCHEN - DAY"
    cards = session.cards()
    assert cards[0].heading == "INT. KITCHEN - DAY"
    heading = original.blocks[0]
    session.add_note(block_id=heading.id, text="keep the kitchen")
    assert any(note.text == "keep the kitchen" for note in session.document().notes)
    text = session.history_text()
    assert text


def test_checkpoint_branch_and_diff(
    editor_session: tuple[EditorService, object, ScreenplayDocument],
) -> None:
    session, _project, original = editor_session
    action = next(block for block in original.blocks if block.kind is BlockKind.ACTION)
    before = session.document().base_revision_id
    assert before
    session.checkpoint("draft-one")
    session.update_text(action.id, "Ada studies the lock again.")
    after = session.document().base_revision_id
    assert after and after != before
    branch = session.branch("alt-ending")
    assert branch.name == "alt-ending"
    diff = session.diff(before, after)
    assert diff.from_revision_id == before
    assert diff.to_revision_id == after


def test_contextual_explore_lock_preserve_intent(
    editor_session: tuple[EditorService, object, ScreenplayDocument],
) -> None:
    session, _project, original = editor_session
    heading = original.blocks[0]
    explore_id = session.contextual(ContextualAction.EXPLORE, block_id=heading.id)
    assert explore_id.startswith("brn_") or explore_id
    assert session.contextual(ContextualAction.LOCK, block_id=heading.id) == "locked"
    locked = next(block for block in session.document().blocks if block.id == heading.id)
    assert locked.unknown_extensions["locked_scene"] is True
    assert session.contextual(ContextualAction.PRESERVE, block_id=heading.id) == "preserved"
    assert session.contextual(ContextualAction.INTENT, block_id=heading.id) == "intent"
    notes = [note.text for note in session.document().notes]
    assert any(text.startswith("PRESERVE:") for text in notes)
    assert any(text.startswith("INTENT:") for text in notes)


def test_author_mode_does_not_fork_document(
    editor_session: tuple[EditorService, object, ScreenplayDocument],
) -> None:
    session, _project, original = editor_session
    assert session.set_mode(AuthorMode.REVIEW) is AuthorMode.REVIEW
    assert session.document().id == original.id
    session.set_mode("author")
    assert session.mode is AuthorMode.AUTHOR


def test_editor_json_cannot_become_canon(
    editor_session: tuple[EditorService, object, ScreenplayDocument],
) -> None:
    session, _project, _original = editor_session
    projection = session.projection()
    assert projection.format == EDITOR_FORMAT
    with pytest.raises(EditorCanonError):
        session.reject_editor_json(
            {"format": EDITOR_FORMAT, "nodes": [{"id": "n1", "type": "action", "text": "no"}]}
        )
    adopted = session.adopt_projection(projection)
    assert adopted.id == session.document().id
    assert adopted.title == session.document().title


def test_enter_on_existing_character_does_not_split_dialogue(
    editor_session: tuple[EditorService, object, ScreenplayDocument],
) -> None:
    session, _project, original = editor_session
    character = next(block for block in original.blocks if block.kind is BlockKind.CHARACTER)
    before = [block.kind for block in session.document().blocks]
    session.transition(character.id, "Enter")
    after = [block.kind for block in session.document().blocks]
    assert after == before
    dialogue = next(block for block in session.document().blocks if block.kind is BlockKind.DIALOGUE)
    assert dialogue.text == "It's not locked."


def test_tab_on_existing_character_inserts_action_after_dialogue(
    editor_session: tuple[EditorService, object, ScreenplayDocument],
) -> None:
    session, _project, original = editor_session
    character = next(block for block in original.blocks if block.kind is BlockKind.CHARACTER)
    session.transition(character.id, "Tab")
    kinds = [block.kind for block in session.document().blocks]
    assert kinds[-1] is BlockKind.ACTION
    assert kinds == [
        BlockKind.SCENE_HEADING,
        BlockKind.ACTION,
        BlockKind.CHARACTER,
        BlockKind.DIALOGUE,
        BlockKind.ACTION,
    ]


def test_sample_element_transition_matrix(
    editor_session: tuple[EditorService, object, ScreenplayDocument],
) -> None:
    session, _project, original = editor_session
    by_kind = {block.kind: block.id for block in original.blocks}
    session.transition(by_kind[BlockKind.SCENE_HEADING], "Enter")
    session.transition(by_kind[BlockKind.ACTION], "Enter")
    session.transition(by_kind[BlockKind.CHARACTER], "Enter")
    session.transition(by_kind[BlockKind.DIALOGUE], "Enter")
    session.transition(by_kind[BlockKind.ACTION], "Tab")
    session.transition(by_kind[BlockKind.CHARACTER], "Tab")
    session.transition(by_kind[BlockKind.DIALOGUE], "Tab")
    session.transition(by_kind[BlockKind.SCENE_HEADING], "Tab")
    kinds = [block.kind for block in session.document().blocks]
    assert BlockKind.DIALOGUE in kinds
    assert kinds.count(BlockKind.CHARACTER) >= 1
    assert all(
        block.kind is not BlockKind.DIALOGUE
        or (index > 0 and session.document().blocks[index - 1].kind in {BlockKind.CHARACTER, BlockKind.PARENTHETICAL})
        for index, block in enumerate(session.document().blocks)
    )


def test_unsupported_transition_fails_closed(
    editor_session: tuple[EditorService, object, ScreenplayDocument],
) -> None:
    session, _project, original = editor_session
    with pytest.raises(EditorCommandError):
        session.transition(original.blocks[0].id, "Escape")
