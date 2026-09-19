"""Builders for video previs tests. Duplicated rather than imported."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from movie_muse.artifacts.api import ArtifactService
from movie_muse.audit.api import AuditLog
from movie_muse.authorization.api import AuthorizationService
from movie_muse.dependencies.api import DependencyEngine
from movie_muse.director.api import DirectorVisionService, SubjectPosition
from movie_muse.identity.api import (
    Actor,
    IdentityService,
    Organization,
    PrincipalKind,
    Role,
    make_human_actor,
    make_integration_actor,
)
from movie_muse.jobs.api import JobService
from movie_muse.model_router.api import ModelRouter
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.revisions.api import RevisionService
from movie_muse.schemas.api import (
    Block,
    BlockKind,
    CameraSpec,
    Project,
    ScreenplayDocument,
    Sequence,
    new_id,
)
from movie_muse.shot_ir.api import ShotIRService
from movie_muse.storyboard.api import StoryboardService
from movie_muse.video_previs.api import VideoPrevisService


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 19, 4, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value

    def stamp(self) -> str:
        return self.value.strftime("%Y-%m-%dT%H:%M:%SZ")

    def advance(self, seconds: int) -> str:
        self.value += timedelta(seconds=seconds)
        return self.stamp()


def make_document() -> tuple[Project, ScreenplayDocument, str, tuple[str, str]]:
    actor_id = new_id("actor")
    project = Project(
        id=new_id("project"),
        organization_id="org_local",
        title="Video Previs Pilot",
        owner_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
    )
    scene_ids = (new_id("scene"), new_id("scene"))
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="Video Previs Pilot",
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
        ),
        base_revision_id=new_id("revision"),
    )
    document.validate()
    return project, document, new_id("branch"), scene_ids


@dataclass
class VideoPrevisStack:
    workspace: LocalWorkspace
    identity: IdentityService
    authorization: AuthorizationService
    audit: AuditLog
    revisions: RevisionService
    jobs: JobService
    director: DirectorVisionService
    shots: ShotIRService
    artifacts: ArtifactService
    router: ModelRouter
    storyboard: StoryboardService
    previs: VideoPrevisService
    project: Project
    document: ScreenplayDocument
    owner: Actor
    branch_id: str
    scene_ids: tuple[str, str]
    clock: MutableClock

    @property
    def principal(self):
        return self.identity.principal(self.owner.id)

    @property
    def epoch(self) -> int:
        return self.identity.acl_epoch()


def boot_video_previs_stack(root: Path) -> VideoPrevisStack:
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
            name="Previs Studio",
            created_at="2026-09-01T00:00:00Z",
        ),
        project=project,
        owner=owner,
    )
    audit = AuditLog(workspace)
    authorization = AuthorizationService(workspace, identity, audit=audit)
    revisions = RevisionService(workspace)
    revisions.bind(actor_id=owner.id)
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
    director = DirectorVisionService(
        workspace, authorization, audit, dependencies=engine, clock=clock.stamp
    )
    shots = ShotIRService(
        workspace, authorization, audit, director, dependencies=engine, clock=clock.stamp
    )
    artifacts = ArtifactService(workspace, authorization, revisions, audit)
    router = ModelRouter(workspace, authorization, identity, audit)
    storyboard = StoryboardService(
        workspace,
        authorization,
        identity,
        audit,
        shots,
        director,
        artifacts,
        router,
        revisions,
        clock=clock.stamp,
    )
    previs = VideoPrevisService(
        workspace,
        authorization,
        identity,
        audit,
        shots,
        storyboard,
        artifacts,
        router,
        revisions,
        jobs,
        clock=clock.stamp,
    )
    return VideoPrevisStack(
        workspace=workspace,
        identity=identity,
        authorization=authorization,
        audit=audit,
        revisions=revisions,
        jobs=jobs,
        director=director,
        shots=shots,
        artifacts=artifacts,
        router=router,
        storyboard=storyboard,
        previs=previs,
        project=project,
        document=document,
        owner=owner,
        branch_id=branch_id,
        scene_ids=scene_ids,
        clock=clock,
    )


def default_camera() -> CameraSpec:
    return CameraSpec(
        position_x=0.0,
        position_y=4.0,
        height_m=1.6,
        orientation_degrees=180.0,
        sensor="super35",
        lens_mm=35.0,
        movement="static",
    )


def open_space(stack: VideoPrevisStack, scene_id: str | None = None):
    return stack.director.create_scene_space(
        project_id=stack.project.id,
        scene_id=scene_id or stack.scene_ids[0],
        geometry_description="Kitchen 8m x 5m, island center.",
        principal=stack.principal,
        acl_epoch=stack.epoch,
        subject_positions=(
            SubjectPosition(subject_id="ada", x=1.5, y=2.0, orientation_degrees=90.0),
        ),
    )


def create_shot(stack: VideoPrevisStack):
    space = open_space(stack)
    return stack.shots.create_shot(
        scene_space_id=space.space.id,
        camera=default_camera(),
        composition_notes="Ada mid-frame at the island.",
        light_direction="window-left",
        performance_intent="restrained, listening",
        principal=stack.principal,
        acl_epoch=stack.epoch,
        eyeline_subject_ids=("ada",),
        color_intent="tungsten-warm",
        continuity_notes="Match day kitchen eyeline.",
        coverage_purpose="master",
    )


def invite_role(stack: VideoPrevisStack, role: Role, *, integration: bool = False):
    factory = make_integration_actor if integration else make_human_actor
    actor = factory(organization_id=stack.project.organization_id, display_name=role.value)
    stack.identity.register_actor(actor)
    invitation = stack.identity.invite(
        inviter_actor_id=stack.owner.id,
        invitee_actor_id=actor.id,
        project_id=stack.project.id,
        role=role,
    )
    stack.identity.accept_invitation(invitation.id, actor_id=actor.id)
    return stack.identity.principal(actor.id)


@pytest.fixture
def previs_stack(tmp_path: Path) -> VideoPrevisStack:
    return boot_video_previs_stack(tmp_path / "ws")


@pytest.fixture
def stored_shot(previs_stack: VideoPrevisStack):
    return create_shot(previs_stack)


@pytest.fixture
def member(previs_stack: VideoPrevisStack):
    def _member(role: Role, *, integration: bool = False):
        return invite_role(previs_stack, role, integration=integration)

    return _member
