"""Thin editor host. Mutations go through EditorService only."""

from __future__ import annotations

from pathlib import Path

from movie_muse.editor.api import EditorService
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.revisions.api import RevisionService
from movie_muse.schemas.api import Project, ScreenplayDocument


def open_editor_session(
    root: Path,
    *,
    project: Project,
    document: ScreenplayDocument,
    branch_id: str,
    actor_id: str,
) -> EditorService:
    """Open a local workspace and bind a keyboard authoring session."""

    workspace = LocalWorkspace(root)
    workspace.open_project(project, document, branch_id=branch_id)
    revisions = RevisionService(workspace)
    revisions.bind(actor_id=actor_id)
    return EditorService(revisions, actor_id=actor_id)


def bind_existing_workspace(root: Path, *, actor_id: str) -> EditorService:
    """Resume an already-opened local workspace without network."""

    workspace = LocalWorkspace(root)
    revisions = RevisionService(workspace)
    revisions.bind(actor_id=actor_id)
    return EditorService(revisions, actor_id=actor_id)
