"""Builders for editor session tests. Duplicated rather than imported from other packages."""

from __future__ import annotations

from pathlib import Path

import pytest

from movie_muse.editor.api import EditorService, sample_project_and_document
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.revisions.api import RevisionService
from movie_muse.schemas.api import Project, ScreenplayDocument


@pytest.fixture
def editor_session(
    tmp_path: Path,
) -> tuple[EditorService, Project, ScreenplayDocument]:
    project, document, branch_id = sample_project_and_document()
    workspace = LocalWorkspace(tmp_path / "ws")
    workspace.open_project(project, document, branch_id=branch_id)
    revisions = RevisionService(workspace)
    revisions.bind(actor_id=project.owner_actor_id)
    session = EditorService(revisions, actor_id=project.owner_actor_id)
    return session, project, document
