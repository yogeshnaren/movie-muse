"""Builders for evaluation tests. Duplicated rather than imported."""

from __future__ import annotations

from pathlib import Path

import pytest

from movie_muse.model_router.api import LOCAL_RUNTIME_ENV
from movie_muse.schemas.api import (
    Block,
    BlockKind,
    Project,
    ScreenplayDocument,
    Sequence,
    new_id,
)
from movie_muse.security.api import ControlPlane


def make_project_and_document() -> tuple[Project, ScreenplayDocument, str]:
    actor_id = new_id("actor")
    project = Project(
        id=new_id("project"),
        organization_id="org_local",
        title="Evaluation Pilot",
        owner_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
    )
    scene_id = new_id("scene")
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="Evaluation Pilot",
        sequences=(Sequence(id=new_id("sequence"), title="Act One", order=0, scene_ids=(scene_id,)),),
        blocks=(
            Block(
                id=new_id("block"),
                kind=BlockKind.SCENE_HEADING,
                text="INT. KITCHEN - DAY",
                scene_id=scene_id,
                scene_number="1",
            ),
            Block(id=new_id("block"), kind=BlockKind.ACTION, text="Ada studies the lock."),
        ),
        base_revision_id=new_id("revision"),
    )
    document.validate()
    return project, document, new_id("branch")


@pytest.fixture
def plane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ControlPlane:
    monkeypatch.setenv(LOCAL_RUNTIME_ENV, "stub")
    project, document, branch_id = make_project_and_document()
    item = ControlPlane.open(tmp_path / "ws", project, document, branch_id=branch_id)
    yield item
    item.close()
