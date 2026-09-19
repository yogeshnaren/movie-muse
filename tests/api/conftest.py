"""Builders for Integration Mesh API tests. Duplicated rather than imported."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from movie_muse.api.api import IntegrationMeshService
from movie_muse.artifacts.api import ArtifactClassification, ArtifactService, ArtifactType
from movie_muse.audit.api import AuditLog
from movie_muse.authorization.api import AuthorizationService
from movie_muse.dependencies.api import DependencyEngine
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
from movie_muse.mcp.api import MeshMcpService
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.proposals.api import ProposalService
from movie_muse.revisions.api import RevisionService
from movie_muse.schemas.api import (
    ArtifactStatus,
    Block,
    BlockKind,
    ChangeSet,
    ChangeSetOperation,
    OperationType,
    Project,
    ScreenplayDocument,
    Sequence,
    new_id,
    new_ulid,
)
from movie_muse.webhooks.api import WebhookService

SIGNING_KEY = "mesh-hmac"


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 19, 8, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value

    def stamp(self) -> str:
        return self.value.strftime("%Y-%m-%dT%H:%M:%SZ")

    def advance(self, seconds: int) -> datetime:
        self.value += timedelta(seconds=seconds)
        return self.value


def make_document() -> tuple[Project, ScreenplayDocument, str]:
    actor_id = new_id("actor")
    project = Project(
        id=new_id("project"),
        organization_id="org_local",
        title="Mesh Pilot",
        owner_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
    )
    scene_id = new_id("scene")
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="Mesh Pilot",
        sequences=(
            Sequence(id=new_id("sequence"), title="Act One", order=0, scene_ids=(scene_id,)),
        ),
        blocks=(
            Block(
                id=new_id("block"),
                kind=BlockKind.SCENE_HEADING,
                text="INT. STAGE - DAY",
                scene_id=scene_id,
                scene_number="1",
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.ACTION,
                text="Ada checks the call sheet.",
                scene_id=scene_id,
            ),
        ),
        base_revision_id=new_id("revision"),
    )
    document.validate()
    return project, document, new_id("branch")


@dataclass
class MeshStack:
    workspace: LocalWorkspace
    identity: IdentityService
    authorization: AuthorizationService
    audit: AuditLog
    revisions: RevisionService
    artifacts: ArtifactService
    proposals: ProposalService
    mesh: IntegrationMeshService
    mcp: MeshMcpService
    webhooks: WebhookService
    project: Project
    owner: Actor
    clock: MutableClock

    @property
    def principal(self):
        return self.identity.principal(self.owner.id)

    @property
    def epoch(self) -> int:
        return self.identity.acl_epoch()

    @property
    def action_id(self) -> str:
        return next(
            block.id
            for block in self.revisions.replay_head().blocks
            if block.kind is BlockKind.ACTION
        )


def boot_mesh_stack(root: Path, *, rate_limit: int = 64) -> MeshStack:
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
            name="Mesh Studio",
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
    graph = DependencyEngine(workspace, authorization, jobs, audit)
    proposals = ProposalService(revisions, authorization, audit, graph)
    artifacts = ArtifactService(workspace, authorization, revisions, audit)
    mesh = IntegrationMeshService(
        workspace,
        authorization,
        identity,
        audit,
        revisions,
        proposals,
        artifacts,
        clock=clock,
        rate_limit=rate_limit,
    )
    return MeshStack(
        workspace=workspace,
        identity=identity,
        authorization=authorization,
        audit=audit,
        revisions=revisions,
        artifacts=artifacts,
        proposals=proposals,
        mesh=mesh,
        mcp=MeshMcpService(mesh),
        webhooks=WebhookService(
            workspace, authorization, audit, signing_key=SIGNING_KEY, clock=clock
        ),
        project=project,
        owner=owner,
        clock=clock,
    )


def make_change_set(stack: MeshStack, text: str) -> ChangeSet:
    return ChangeSet(
        id=new_id("change_set"),
        base_revision_id=stack.revisions.canon_head_id(),
        author_actor_id=stack.principal.actor_id,
        created_at=stack.clock.stamp(),
        operations=(
            ChangeSetOperation(
                id=f"cop_{new_ulid()}",
                order=0,
                op_type=OperationType.UPDATE_BLOCK,
                target_id=stack.action_id,
                payload={"text": text},
            ),
        ),
    )


def invite_role(stack: MeshStack, role: Role, *, integration: bool = False):
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


def approve_source_version(stack: MeshStack) -> str:
    stack.artifacts.register_template(
        project_id=stack.project.id,
        version="1",
        renderer_version="json/1",
        body="mesh source {title}",
        principal=stack.principal,
        acl_epoch=stack.epoch,
        template_id="tmpl_mesh_source",
    )
    artifact = stack.artifacts.create_artifact(
        project_id=stack.project.id,
        artifact_type=ArtifactType.DOCUMENT,
        title="Reviewed packet",
        principal=stack.principal,
        acl_epoch=stack.epoch,
    )
    view = stack.artifacts.create_version(
        artifact.id,
        inputs={"title": "Reviewed packet"},
        source_revision_id=stack.revisions.canon_head_id(),
        template_id="tmpl_mesh_source",
        template_version="1",
        renderer_version="json/1",
        classification=ArtifactClassification.INTERNAL,
        principal=stack.principal,
        acl_epoch=stack.epoch,
    )
    stack.artifacts.transition_review(
        view.version.id,
        ArtifactStatus.IN_REVIEW,
        principal=stack.principal,
        acl_epoch=stack.epoch,
    )
    approved = stack.artifacts.transition_review(
        view.version.id,
        ArtifactStatus.APPROVED,
        principal=stack.principal,
        acl_epoch=stack.epoch,
    )
    return approved.version.id


@pytest.fixture
def mesh_stack(tmp_path: Path) -> MeshStack:
    return boot_mesh_stack(tmp_path / "ws")


@pytest.fixture
def tight_stack(tmp_path: Path) -> MeshStack:
    return boot_mesh_stack(tmp_path / "tight", rate_limit=2)


@pytest.fixture
def change_set(mesh_stack: MeshStack):
    def _make(text: str = "Ada revises the call sheet.") -> ChangeSet:
        return make_change_set(mesh_stack, text)

    return _make


@pytest.fixture
def member(mesh_stack: MeshStack):
    def _member(role: Role, *, integration: bool = False):
        return invite_role(mesh_stack, role, integration=integration)

    return _member


@pytest.fixture
def approved_version(mesh_stack: MeshStack) -> str:
    return approve_source_version(mesh_stack)
