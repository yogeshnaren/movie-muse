"""Builders for privacy tests. Duplicated rather than imported."""

from __future__ import annotations

from pathlib import Path

import pytest

from movie_muse.identity.api import Role, make_human_actor
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
        title="Privacy Pilot",
        owner_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
    )
    scene_id = new_id("scene")
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="Privacy Pilot",
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
def plane(tmp_path: Path) -> ControlPlane:
    project, document, branch_id = make_project_and_document()
    item = ControlPlane.open(tmp_path / "ws", project, document, branch_id=branch_id)
    yield item
    item.close()


@pytest.fixture
def member(plane: ControlPlane):
    def _member(role: Role):
        actor = make_human_actor(organization_id=plane.organization_id, display_name=role.value)
        plane.identity.register_actor(actor)
        invitation = plane.identity.invite(
            inviter_actor_id=plane.principal.actor_id,
            invitee_actor_id=actor.id,
            project_id=plane.project_id,
            role=role,
        )
        plane.identity.accept_invitation(invitation.id, actor_id=actor.id)
        return plane.identity.principal(actor.id)

    return _member
