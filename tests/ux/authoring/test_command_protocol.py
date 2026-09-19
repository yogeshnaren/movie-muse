"""Authoring UX may only emit typed commands, never editor JSON as canon."""

from __future__ import annotations

from pathlib import Path

from movie_muse.document.api import EDITOR_FORMAT
from movie_muse.editor.api import EditorCanonError, EditorService, sample_project_and_document
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.revisions.api import RevisionService
from movie_muse.schemas.api import BlockKind


def _session(tmp_path: Path) -> tuple[EditorService, object]:
    project, document, branch_id = sample_project_and_document()
    workspace = LocalWorkspace(tmp_path / "ux")
    workspace.open_project(project, document, branch_id=branch_id)
    revisions = RevisionService(workspace)
    revisions.bind(actor_id=project.owner_actor_id)
    return EditorService(revisions, actor_id=project.owner_actor_id), document


def test_keystroke_commands_are_change_sets(tmp_path: Path) -> None:
    session, document = _session(tmp_path)
    action = next(block for block in document.blocks if block.kind is BlockKind.ACTION)
    session.update_text(action.id, "Ada types a command.")
    head = session.document()
    assert all(isinstance(block.kind, BlockKind) for block in head.blocks)
    assert head.base_revision_id != document.base_revision_id


def test_projection_round_trip_is_not_a_save(tmp_path: Path) -> None:
    session, document = _session(tmp_path)
    projection = session.projection()
    assert projection.format == EDITOR_FORMAT
    reconstructed = session.adopt_projection(projection)
    assert reconstructed.id == document.id
    try:
        session.reject_editor_json({"format": EDITOR_FORMAT, "nodes": []})
    except EditorCanonError as exc:
        assert "cannot be saved" in str(exc)
    else:
        raise AssertionError("editor JSON must be rejected as canon")
