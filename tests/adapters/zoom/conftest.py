"""Builders for Zoom adapter tests. Duplicated rather than imported."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from movie_muse.adapters.zoom.api import ZoomAdapter
from movie_muse.artifacts.api import ArtifactService
from movie_muse.audit.api import AuditLog
from movie_muse.authorization.api import AuthorizationService
from movie_muse.identity.api import Actor, IdentityService, Organization, PrincipalKind
from movie_muse.meeting_capture.api import MeetingCaptureService
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.project_memory.api import ProjectMemoryService
from movie_muse.revisions.api import RevisionService
from movie_muse.schemas.api import (
    Block,
    BlockKind,
    Project,
    ScreenplayDocument,
    Sequence,
    new_id,
)

SIGNING_KEY = "zoom-contract-hmac"


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 19, 2, 0, tzinfo=UTC)

    def __call__(self) -> str:
        return self.value.strftime("%Y-%m-%dT%H:%M:%SZ")

    def unix(self) -> str:
        return str(int(self.value.timestamp()))

    def advance(self, seconds: int) -> str:
        self.value += timedelta(seconds=seconds)
        return self()


def make_document() -> tuple[Project, ScreenplayDocument, str]:
    actor_id = new_id("actor")
    project = Project(
        id=new_id("project"),
        organization_id="org_local",
        title="Zoom Adapter Pilot",
        owner_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
    )
    scene_id = new_id("scene")
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="Zoom Adapter Pilot",
        sequences=(
            Sequence(id=new_id("sequence"), title="Act One", order=0, scene_ids=(scene_id,)),
        ),
        blocks=(
            Block(
                id=new_id("block"),
                kind=BlockKind.SCENE_HEADING,
                text="INT. KITCHEN - DAY",
                scene_id=scene_id,
                scene_number="1",
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.ACTION,
                text="Ada joins the Zoom room.",
                scene_id=scene_id,
            ),
        ),
        base_revision_id=new_id("revision"),
    )
    document.validate()
    return project, document, new_id("branch")


@dataclass
class ZoomStack:
    workspace: LocalWorkspace
    identity: IdentityService
    authorization: AuthorizationService
    audit: AuditLog
    meetings: MeetingCaptureService
    zoom: ZoomAdapter
    revisions: RevisionService
    project: Project
    owner: Actor
    branch_id: str
    clock: MutableClock

    @property
    def principal(self):
        return self.identity.principal(self.owner.id)

    @property
    def epoch(self) -> int:
        return self.identity.acl_epoch()


def boot_zoom_stack(root: Path) -> ZoomStack:
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
            name="Zoom Studio",
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
    memory = ProjectMemoryService(workspace, authorization, audit)
    clock = MutableClock()
    meetings = MeetingCaptureService(artifacts, memory, authorization, audit, clock=clock)
    zoom = ZoomAdapter(
        workspace,
        meetings,
        authorization,
        audit,
        webhook_secret=SIGNING_KEY,
        clock=clock,
    )
    return ZoomStack(
        workspace=workspace,
        identity=identity,
        authorization=authorization,
        audit=audit,
        meetings=meetings,
        zoom=zoom,
        revisions=revisions,
        project=project,
        owner=owner,
        branch_id=branch_id,
        clock=clock,
    )


@pytest.fixture
def zoom_stack(tmp_path: Path) -> ZoomStack:
    return boot_zoom_stack(tmp_path / "ws")
