"""Airplane and outage paths keep local authoring durable."""

from __future__ import annotations

import json

import pytest

from movie_muse.editor.api import EditorService, RecoveryError
from movie_muse.editor.service import JOURNAL_KEY
from movie_muse.schemas.api import BlockKind, ScreenplayDocument


def test_airplane_and_outages_still_save(
    editor_session: tuple[EditorService, object, ScreenplayDocument],
) -> None:
    session, _project, original = editor_session
    action = next(block for block in original.blocks if block.kind is BlockKind.ACTION)
    session.set_airplane(True)
    session.set_outage("auth_outage", True)
    session.set_outage("subscription_outage", True)
    session.set_outage("ai_outage", True)
    ack = session.update_text(action.id, "Ada writes offline.")
    assert ack.revision_id
    assert session.document().blocks[1].text == "Ada writes offline."
    status = session.revisions.workspace.status()
    assert status.connectivity_offline is True


def test_recovery_replays_unacked_keystrokes(
    editor_session: tuple[EditorService, object, ScreenplayDocument],
) -> None:
    session, _project, original = editor_session
    action = next(block for block in original.blocks if block.kind is BlockKind.ACTION)
    session.record_keystroke({"op": "update_text", "block_id": action.id, "text": "Ada recovered the beat."})
    assert session.pending_keystrokes()
    replayed = session.recover()
    assert replayed == 1
    assert session.document().blocks[1].text == "Ada recovered the beat."
    assert session.recover() == 0


def test_recovery_does_not_double_apply_acked_updates(
    editor_session: tuple[EditorService, object, ScreenplayDocument],
) -> None:
    session, _project, original = editor_session
    action = next(block for block in original.blocks if block.kind is BlockKind.ACTION)
    session.update_text(action.id, "Ada already saved.")
    assert session.recover() == 0
    assert session.document().blocks[1].text == "Ada already saved."


def test_new_session_loads_journal_and_recovers(
    editor_session: tuple[EditorService, object, ScreenplayDocument],
) -> None:
    session, _project, original = editor_session
    action = next(block for block in original.blocks if block.kind is BlockKind.ACTION)
    session.record_keystroke({"op": "update_text", "block_id": action.id, "text": "journal survived."})
    resumed = EditorService(session.revisions, actor_id=session.actor_id)
    assert resumed.pending_keystrokes()
    assert resumed.recover() == 1
    assert resumed.document().blocks[1].text == "journal survived."


def test_corrupt_journal_fails_closed(
    editor_session: tuple[EditorService, object, ScreenplayDocument],
) -> None:
    session, _project, _original = editor_session
    session.revisions.workspace.store.set_meta(JOURNAL_KEY, "{not-json")
    with pytest.raises(RecoveryError):
        EditorService(session.revisions, actor_id=session.actor_id)


def test_journal_is_stored_as_workspace_meta(
    editor_session: tuple[EditorService, object, ScreenplayDocument],
) -> None:
    session, _project, original = editor_session
    action = next(block for block in original.blocks if block.kind is BlockKind.ACTION)
    session.update_text(action.id, "persisted")
    raw = session.revisions.workspace.store.get_meta(JOURNAL_KEY)
    assert raw
    journal = json.loads(raw)
    assert isinstance(journal, list)
    assert journal[-1]["acked"] is True
