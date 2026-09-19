"""Competitive suite helpers. Duplicated here rather than imported across packages."""

from __future__ import annotations

from pathlib import Path

import pytest

from movie_muse.editor.api import EditorService
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.revisions.api import RevisionService
from movie_muse.schemas.api import Project, ScreenplayDocument, new_id
from movie_muse.testkit.api import FixtureCatalog


def open_fixture_session(tmp_path: Path, fixture_id: str) -> tuple[EditorService, ScreenplayDocument, Project]:
    fixture = FixtureCatalog().get(fixture_id)
    document = fixture.document
    actor_id = new_id("actor")
    project = Project(
        id=document.project_id,
        organization_id="org_competitive",
        title=document.title,
        owner_actor_id=actor_id,
        created_at="2026-09-05T00:00:00Z",
    )
    workspace = LocalWorkspace(tmp_path / fixture_id)
    workspace.open_project(project, document, branch_id=new_id("branch"))
    revisions = RevisionService(workspace)
    revisions.bind(actor_id=actor_id)
    return EditorService(revisions, actor_id=actor_id), document, project


@pytest.fixture
def kitchen_session(tmp_path: Path) -> tuple[EditorService, ScreenplayDocument, Project]:
    return open_fixture_session(tmp_path, "small_kitchen")
