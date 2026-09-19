"""Offline field workflow represented by Scriptation."""

from __future__ import annotations

from movie_muse.editor.api import EditorService
from movie_muse.schemas.api import BlockKind, Project, ScreenplayDocument


def test_sc_offline(
    kitchen_session: tuple[EditorService, ScreenplayDocument, Project],
) -> None:
    session, document, _project = kitchen_session
    action = next(block for block in document.blocks if block.kind is BlockKind.ACTION)
    session.set_airplane(True)
    session.set_outage("auth_outage", True)
    ack = session.update_text(action.id, "Ada writes without a network.")
    assert ack.revision_id
    assert session.document().blocks[next(i for i, block in enumerate(session.document().blocks) if block.id == action.id)].text == (
        "Ada writes without a network."
    )
    assert session.revisions.workspace.status().connectivity_offline is True
    session.record_keystroke({"op": "update_text", "block_id": action.id, "text": "Recovered offline beat."})
    assert session.recover() == 1
    recovered = next(block for block in session.document().blocks if block.id == action.id)
    assert recovered.text == "Recovered offline beat."
    assert session.recover() == 0
