"""Rights test builders, duplicated to keep test packages independent."""

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
    make_integration_actor,
)
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.rights.api import PermittedUse, RightsService, SourceClassification
from movie_muse.schemas.api import (
    Block,
    BlockKind,
    Note,
    ProductionTag,
    Project,
    RevisionMark,
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


def make_project_and_document() -> tuple[Project, ScreenplayDocument, str]:
    actor_id = new_id("actor")
    project = Project(
        id=new_id("project"),
        organization_id="org_local",
        title="Rights Pilot",
        owner_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
    )
    scene_id = new_id("scene")
    heading = Block(
        id=new_id("block"),
        kind=BlockKind.SCENE_HEADING,
        text="INT. ARCHIVE - NIGHT",
        scene_id=scene_id,
        scene_number="1",
    )
    action = Block(
        id=new_id("block"),
        kind=BlockKind.ACTION,
        text="Ada opens the rights ledger.",
        scene_id=scene_id,
    )
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="Rights Pilot",
        sequences=(
            Sequence(id=new_id("sequence"), title="Act One", order=0, scene_ids=(scene_id,)),
        ),
        blocks=(heading, action),
        notes=(
            Note(
                id=new_id("note"),
                block_id=heading.id,
                author_actor_id=actor_id,
                text="Record source licenses.",
                created_at="2026-09-01T00:00:00Z",
            ),
        ),
        production_tags=(
            ProductionTag(
                id=new_id("production_tag"),
                block_id=heading.id,
                department="art",
                tag_type="set",
                value="archive",
            ),
        ),
        revision_marks=(
            RevisionMark(
                id=new_id("revision_mark"),
                block_id=action.id,
                revision_color="blue",
                revision_label="Blue",
                created_at="2026-09-01T00:00:00Z",
            ),
        ),
        base_revision_id=new_id("revision"),
    )
    document.validate()
    return project, document, new_id("branch")


@dataclass
class RightsStack:
    workspace: LocalWorkspace
    identity: IdentityService
    authorization: AuthorizationService
    audit: AuditLog
    rights: RightsService
    project: Project
    document: ScreenplayDocument
    owner: Actor

    @property
    def principal(self):
        return self.identity.principal(self.owner.id)

    @property
    def epoch(self) -> int:
        return self.identity.acl_epoch()


def boot_rights_stack(
    root: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> RightsStack:
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
            name="Rights Studio",
            created_at="2026-09-01T00:00:00Z",
        ),
        project=project,
        owner=owner,
    )
    audit = AuditLog(workspace)
    authorization = AuthorizationService(workspace, identity, audit=audit)
    rights = RightsService(workspace, authorization, audit)
    return RightsStack(
        workspace=workspace,
        identity=identity,
        authorization=authorization,
        audit=audit,
        rights=rights,
        project=project,
        document=document,
        owner=owner,
    )


def invite_role(stack: RightsStack, role: Role, *, integration: bool = False):
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


def register_licensed_source(stack: RightsStack, *, title: str = "Licensed corpus"):
    return stack.rights.register_source(
        project_id=stack.project.id,
        title=title,
        classification=SourceClassification.LICENSED,
        principal=stack.principal,
        acl_epoch=stack.epoch,
        permitted_uses=LICENSED_USES,
        license_summary="licensed for citation and generation",
        license_expiry="2099-01-01T00:00:00Z",
    )


@pytest.fixture
def project_bundle() -> tuple[Project, ScreenplayDocument, str]:
    return make_project_and_document()


@pytest.fixture
def rights_stack(
    tmp_path: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> RightsStack:
    return boot_rights_stack(tmp_path / "ws", project_bundle)


@pytest.fixture
def licensed_source(rights_stack: RightsStack):
    return register_licensed_source(rights_stack)


@pytest.fixture
def member(rights_stack: RightsStack):
    def _member(role: Role, *, integration: bool = False):
        return invite_role(rights_stack, role, integration=integration)

    return _member
