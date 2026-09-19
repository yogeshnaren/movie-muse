"""Builders for correspondence tests. Duplicated rather than imported."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from movie_muse.artifacts.api import ArtifactService
from movie_muse.audit.api import AuditLog
from movie_muse.authorization.api import AuthorizationService
from movie_muse.correspondence.api import CorrespondenceService
from movie_muse.identity.api import Actor, IdentityService, Organization, PrincipalKind
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.revisions.api import RevisionService
from movie_muse.schemas.api import (
    Block,
    BlockKind,
    Project,
    ScreenplayDocument,
    Sequence,
    new_id,
)


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 19, 0, 32, tzinfo=UTC)

    def stamp(self) -> str:
        return self.value.strftime("%Y-%m-%dT%H:%M:%SZ")


def make_document() -> tuple[Project, ScreenplayDocument, str]:
    actor_id = new_id("actor")
    project = Project(
        id=new_id("project"),
        organization_id="org_local",
        title="Correspondence Pilot",
        owner_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
    )
    scene_id = new_id("scene")
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="Correspondence Pilot",
        sequences=(
            Sequence(id=new_id("sequence"), title="Act One", order=0, scene_ids=(scene_id,)),
        ),
        blocks=(
            Block(
                id=new_id("block"),
                kind=BlockKind.SCENE_HEADING,
                text="INT. OFFICE - DAY",
                scene_id=scene_id,
                scene_number="1",
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.ACTION,
                text="Ada files the notice.",
                scene_id=scene_id,
            ),
        ),
        base_revision_id=new_id("revision"),
    )
    document.validate()
    return project, document, new_id("branch")


@dataclass
class CorrespondenceStack:
    workspace: LocalWorkspace
    identity: IdentityService
    authorization: AuthorizationService
    audit: AuditLog
    revisions: RevisionService
    correspondence: CorrespondenceService
    project: Project
    owner: Actor

    @property
    def principal(self):
        return self.identity.principal(self.owner.id)

    @property
    def epoch(self) -> int:
        return self.identity.acl_epoch()


def boot_correspondence_stack(root: Path) -> CorrespondenceStack:
    project, document, branch_id = make_document()
    workspace = LocalWorkspace(root)
    workspace.open_project(project, document, branch_id=branch_id)
    identity = IdentityService(workspace)
    owner = Actor(
        id=project.owner_actor_id,
        display_name="Owner",
        principal_kind=PrincipalKind.HUMAN,
        organization_id=project.organization_id,
        created_at="2026-09-01T00:00:00Z",
    )
    identity.bootstrap(
        organization=Organization(
            id=project.organization_id,
            name="Mail Studio",
            created_at="2026-09-01T00:00:00Z",
        ),
        project=project,
        owner=owner,
    )
    audit = AuditLog(workspace)
    authorization = AuthorizationService(workspace, identity, audit=audit)
    revisions = RevisionService(workspace)
    revisions.bind(actor_id=owner.id)
    artifacts = ArtifactService(workspace, authorization, revisions, audit)
    clock = MutableClock()
    correspondence = CorrespondenceService(
        workspace,
        authorization,
        audit,
        artifacts,
        revisions,
        clock=clock.stamp,
    )
    return CorrespondenceStack(
        workspace=workspace,
        identity=identity,
        authorization=authorization,
        audit=audit,
        revisions=revisions,
        correspondence=correspondence,
        project=project,
        owner=owner,
    )


@pytest.fixture
def correspondence_stack(tmp_path: Path) -> CorrespondenceStack:
    return boot_correspondence_stack(tmp_path / "ws")
