"""Builders for beat-framework tests. Duplicated rather than imported from other packages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from movie_muse.audit.api import AuditLog
from movie_muse.authorization.api import AuthorizationService
from movie_muse.beats.api import BeatService
from movie_muse.dependencies.api import DependencyEngine
from movie_muse.identity.api import Actor, IdentityService, Organization, PrincipalKind
from movie_muse.jobs.api import JobService
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.revisions.api import RevisionService
from movie_muse.rights.api import PermittedUse, RightsService, SourceClassification
from movie_muse.schemas.api import (
    Block,
    BlockKind,
    Project,
    ScreenplayDocument,
    Sequence,
    new_id,
)

LICENSED_USES = (
    PermittedUse.RETRIEVAL,
    PermittedUse.CITATION,
    PermittedUse.GENERATION,
    PermittedUse.FORECAST,
    PermittedUse.EXPORT_DISCLOSURE,
)


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 18, 23, 21, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value

    def stamp(self) -> str:
        return self.value.strftime("%Y-%m-%dT%H:%M:%SZ")

    def advance(self, seconds: int) -> str:
        self.value += timedelta(seconds=seconds)
        return self.stamp()


def make_document() -> tuple[Project, ScreenplayDocument, str, tuple[str, str, str]]:
    actor_id = new_id("actor")
    project = Project(
        id=new_id("project"),
        organization_id="org_local",
        title="Beat Pilot",
        owner_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
    )
    scene_ids = (new_id("scene"), new_id("scene"), new_id("scene"))
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="Beat Pilot",
        sequences=(
            Sequence(
                id=new_id("sequence"),
                title="Act One",
                order=0,
                scene_ids=scene_ids,
            ),
        ),
        blocks=(
            Block(
                id=new_id("block"),
                kind=BlockKind.SCENE_HEADING,
                text="INT. KITCHEN - DAY",
                scene_id=scene_ids[0],
                scene_number="1",
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.ACTION,
                text="Ada writes a note.",
                scene_id=scene_ids[0],
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.SCENE_HEADING,
                text="EXT. HARBOR - NIGHT",
                scene_id=scene_ids[1],
                scene_number="2",
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.ACTION,
                text="A ferry horn sounds.",
                scene_id=scene_ids[1],
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.SCENE_HEADING,
                text="INT. STUDIO - DAY",
                scene_id=scene_ids[2],
                scene_number="3",
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.ACTION,
                text="Ada locks the brass key.",
                scene_id=scene_ids[2],
            ),
        ),
        base_revision_id=new_id("revision"),
    )
    document.validate()
    return project, document, new_id("branch"), scene_ids


@dataclass
class BeatStack:
    workspace: LocalWorkspace
    identity: IdentityService
    authorization: AuthorizationService
    audit: AuditLog
    rights: RightsService
    jobs: JobService
    engine: DependencyEngine
    beats: BeatService
    revisions: RevisionService
    project: Project
    document: ScreenplayDocument
    owner: Actor
    branch_id: str
    scene_ids: tuple[str, str, str]
    clock: MutableClock

    @property
    def principal(self):
        return self.identity.principal(self.owner.id)

    @property
    def epoch(self) -> int:
        return self.identity.acl_epoch()


def boot_beat_stack(root: Path) -> BeatStack:
    project, document, branch_id, scene_ids = make_document()
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
            name="Beat Studio",
            created_at="2026-09-01T00:00:00Z",
        ),
        project=project,
        owner=owner,
    )
    audit = AuditLog(workspace)
    authorization = AuthorizationService(workspace, identity, audit=audit)
    revisions = RevisionService(workspace)
    revisions.bind(actor_id=owner.id)
    rights = RightsService(workspace, authorization, audit)
    clock = MutableClock()
    jobs = JobService(
        workspace,
        identity,
        authorization,
        audit,
        lambda job: job.input_fingerprint,
        clock=clock,
    )
    engine = DependencyEngine(workspace, authorization, jobs, audit)
    beats = BeatService(
        workspace,
        authorization,
        audit,
        rights=rights,
        dependencies=engine,
        clock=clock.stamp,
    )
    return BeatStack(
        workspace=workspace,
        identity=identity,
        authorization=authorization,
        audit=audit,
        rights=rights,
        jobs=jobs,
        engine=engine,
        beats=beats,
        revisions=revisions,
        project=project,
        document=document,
        owner=owner,
        branch_id=branch_id,
        scene_ids=scene_ids,
        clock=clock,
    )


@pytest.fixture
def beat_stack(tmp_path: Path) -> BeatStack:
    return boot_beat_stack(tmp_path / "ws")


@pytest.fixture
def licensed_source(beat_stack: BeatStack):
    return register_licensed_template(beat_stack)


def register_licensed_template(stack: BeatStack, title: str = "Licensed beat template"):
    return stack.rights.register_source(
        project_id=stack.project.id,
        title=title,
        classification=SourceClassification.LICENSED,
        principal=stack.principal,
        acl_epoch=stack.epoch,
        permitted_uses=LICENSED_USES,
        license_summary="named template license",
    )
