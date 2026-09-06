"""Builders for retrieval tests. Duplicated rather than imported from other packages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from movie_muse.audit.api import AuditLog
from movie_muse.authorization.api import AuthorizationService
from movie_muse.identity.api import (
    Actor,
    IdentityService,
    Organization,
    PrincipalKind,
    Role,
    make_human_actor,
)
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.retrieval.api import RetrievalService
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
    PermittedUse.EXPORT_DISCLOSURE,
)


def make_project_and_document() -> tuple[Project, ScreenplayDocument, str]:
    actor_id = new_id("actor")
    project = Project(
        id=new_id("project"),
        organization_id="org_local",
        title="Context Pilot",
        owner_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
    )
    scene_id = new_id("scene")
    heading = Block(
        id=new_id("block"),
        kind=BlockKind.SCENE_HEADING,
        text="INT. KITCHEN - DAY",
        scene_id=scene_id,
        scene_number="1",
    )
    action = Block(
        id=new_id("block"),
        kind=BlockKind.ACTION,
        text="Ada studies the lock on the pantry.",
        scene_id=scene_id,
    )
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="Context Pilot",
        sequences=(
            Sequence(id=new_id("sequence"), title="Act One", order=0, scene_ids=(scene_id,)),
        ),
        blocks=(heading, action),
        base_revision_id=new_id("revision"),
    )
    document.validate()
    return project, document, new_id("branch")


@dataclass
class RetrievalStack:
    workspace: LocalWorkspace
    identity: IdentityService
    authorization: AuthorizationService
    audit: AuditLog
    rights: RightsService
    revisions: RevisionService
    retrieval: RetrievalService
    project: Project
    document: ScreenplayDocument
    owner: Actor
    branch_id: str

    @property
    def principal(self):
        return self.identity.principal(self.owner.id)

    @property
    def epoch(self) -> int:
        return self.identity.acl_epoch()


def boot_retrieval_stack(
    root: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> RetrievalStack:
    project, document, branch_id = project_bundle
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
            name="Retrieval Studio",
            created_at="2026-09-01T00:00:00Z",
        ),
        project=project,
        owner=owner,
    )
    audit = AuditLog(workspace)
    authorization = AuthorizationService(workspace, identity, audit=audit)
    rights = RightsService(workspace, authorization, audit)
    revisions = RevisionService(workspace)
    revisions.bind(actor_id=owner.id)
    retrieval = RetrievalService(workspace, rights, authorization, audit)
    return RetrievalStack(
        workspace=workspace,
        identity=identity,
        authorization=authorization,
        audit=audit,
        rights=rights,
        revisions=revisions,
        retrieval=retrieval,
        project=project,
        document=document,
        owner=owner,
        branch_id=branch_id,
    )


def invite_role(stack: RetrievalStack, role: Role):
    actor = make_human_actor(organization_id=stack.project.organization_id, display_name=role.value)
    stack.identity.register_actor(actor)
    invitation = stack.identity.invite(
        inviter_actor_id=stack.owner.id,
        invitee_actor_id=actor.id,
        project_id=stack.project.id,
        role=role,
    )
    stack.identity.accept_invitation(invitation.id, actor_id=actor.id)
    return stack.identity.principal(actor.id)


def register_licensed_source(stack: RetrievalStack, *, title: str = "Licensed kitchen notes"):
    return stack.rights.register_source(
        project_id=stack.project.id,
        title=title,
        classification=SourceClassification.LICENSED,
        principal=stack.principal,
        acl_epoch=stack.epoch,
        permitted_uses=LICENSED_USES,
        license_summary="licensed for retrieval and citation",
        license_expiry="2099-01-01T00:00:00Z",
    )


@pytest.fixture
def retrieval_stack(tmp_path: Path) -> RetrievalStack:
    return boot_retrieval_stack(tmp_path / "ws", make_project_and_document())


@pytest.fixture
def licensed_source(retrieval_stack: RetrievalStack):
    return register_licensed_source(retrieval_stack)


@pytest.fixture
def member(retrieval_stack: RetrievalStack):
    def _member(role: Role):
        return invite_role(retrieval_stack, role)

    return _member


@pytest.fixture
def other_stack(tmp_path: Path) -> RetrievalStack:
    return boot_retrieval_stack(tmp_path / "other", make_project_and_document())
