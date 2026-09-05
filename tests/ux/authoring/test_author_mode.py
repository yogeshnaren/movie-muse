"""Distraction-safe author mode is a projection, not a forked project."""

from __future__ import annotations

from pathlib import Path

from movie_muse.editor.api import AuthorMode, EditorService, sample_project_and_document
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.revisions.api import RevisionService
from movie_muse.schemas.api import BlockKind


def test_author_and_review_share_one_document(tmp_path: Path) -> None:
    project, document, branch_id = sample_project_and_document()
    workspace = LocalWorkspace(tmp_path / "author")
    workspace.open_project(project, document, branch_id=branch_id)
    revisions = RevisionService(workspace)
    revisions.bind(actor_id=project.owner_actor_id)
    session = EditorService(revisions, actor_id=project.owner_actor_id)
    action = next(block for block in document.blocks if block.kind is BlockKind.ACTION)
    session.set_mode(AuthorMode.AUTHOR)
    session.update_text(action.id, "Quiet draft.")
    session.set_mode(AuthorMode.REVIEW)
    assert session.document().blocks[1].text == "Quiet draft."
    assert session.document().id == document.id
    assert session.mode is AuthorMode.REVIEW
