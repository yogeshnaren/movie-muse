"""Element transitions emit INSERT_BLOCK ChangeSets."""

from __future__ import annotations

import pytest

from movie_muse.editor.api import (
    ENTER_TRANSITIONS,
    TAB_TRANSITIONS,
    EditorCommandError,
    EditorService,
)
from movie_muse.editor.transitions import next_kind, transition_change_set
from movie_muse.schemas.api import BlockKind, OperationType, ScreenplayDocument


def test_enter_and_tab_tables_are_closed() -> None:
    assert ENTER_TRANSITIONS[BlockKind.CHARACTER.value] == BlockKind.DIALOGUE.value
    assert TAB_TRANSITIONS[BlockKind.ACTION.value] == BlockKind.CHARACTER.value


def test_transition_change_set_inserts_after_current(
    editor_session: tuple[EditorService, object, ScreenplayDocument],
) -> None:
    _session, _project, document = editor_session
    action = next(block for block in document.blocks if block.kind is BlockKind.ACTION)
    change = transition_change_set(
        document,
        block_id=action.id,
        key="Tab",
        actor_id="actor_test",
        created_at="2026-09-05T00:00:00Z",
    )
    assert len(change.operations) == 1
    assert change.operations[0].op_type is OperationType.INSERT_BLOCK
    assert change.operations[0].payload["after_id"] == action.id
    assert change.operations[0].payload["block"]["kind"] == BlockKind.CHARACTER.value


def test_unknown_transition_fails() -> None:
    with pytest.raises(EditorCommandError):
        next_kind(BlockKind.PAGE_BREAK.value, "Enter")
