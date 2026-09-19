"""Local helpers for MM-011 tests. Not a pytest conftest (avoids name clashes)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from movie_muse.audit.api import AuditLog
from movie_muse.authorization.api import AuthorizationService
from movie_muse.dependencies.api import DependencyEngine, NodeKind
from movie_muse.identity.api import Actor, IdentityService, Organization, PrincipalKind
from movie_muse.jobs.api import JobService
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
        self.value = datetime(2026, 9, 1, 16, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> datetime:
        self.value += timedelta(seconds=seconds)
        return self.value


@dataclass
class DependencyStack:
    workspace: LocalWorkspace
    identity: IdentityService
    authorization: AuthorizationService
    audit: AuditLog
    revisions: RevisionService
    jobs: JobService
    engine: DependencyEngine
    project: Project
    document: ScreenplayDocument
    owner: Actor
    clock: MutableClock

    @property
    def principal(self):
        return self.identity.principal(self.owner.id)

    @property
    def epoch(self) -> int:
        return self.identity.acl_epoch()

    def add_source(self, *, kind: NodeKind = NodeKind.SOURCE_REVISION, **kwargs):
        return self.engine.add_node(
            project_id=self.project.id,
            kind=kind,
            principal=self.principal,
            acl_epoch=self.epoch,
            **kwargs,
        )

    def add_derived(self, input_ids: tuple[str, ...] | list[str], **kwargs):
        return self.engine.add_node(
            project_id=self.project.id,
            kind=NodeKind.DERIVED_PROJECTION,
            principal=self.principal,
            acl_epoch=self.epoch,
            input_ids=input_ids,
            **kwargs,
        )


def make_project_and_document() -> tuple[Project, ScreenplayDocument, str]:
    actor_id = new_id("actor")
    project = Project(
        id=new_id("project"),
        organization_id="org_deps",
        title="Dependency Pilot",
        owner_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
    )
    scene_id = new_id("scene")
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="Dependency Pilot",
        sequences=(
            Sequence(
                id=new_id("sequence"),
                title="Act One",
                order=0,
                scene_ids=(scene_id,),
            ),
        ),
        blocks=(
            Block(
                id=new_id("block"),
                kind=BlockKind.SCENE_HEADING,
                text="INT. GRAPH ROOM - DAY",
                scene_id=scene_id,
                scene_number="1",
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.ACTION,
                text="Ada draws the dependency edges.",
                scene_id=scene_id,
            ),
        ),
        base_revision_id=new_id("revision"),
    )
    document.validate()
    return project, document, new_id("branch")


def boot_dependency_stack(root: Path) -> DependencyStack:
    project, document, branch_id = make_project_and_document()
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
            name="Dependency Studio",
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
    return DependencyStack(
        workspace=workspace,
        identity=identity,
        authorization=authorization,
        audit=audit,
        revisions=revisions,
        jobs=jobs,
        engine=engine,
        project=project,
        document=document,
        owner=owner,
        clock=clock,
    )
