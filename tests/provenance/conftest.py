"""Provenance test builders, duplicated to keep test packages independent."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from movie_muse.artifacts.api import ArtifactService
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
from movie_muse.provenance.api import MethodProvenance, ProvenanceService
from movie_muse.revisions.api import RevisionService
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
        title="Provenance Pilot",
        owner_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
    )
    scene_id = new_id("scene")
    heading = Block(
        id=new_id("block"),
        kind=BlockKind.SCENE_HEADING,
        text="INT. LAB - DAY",
        scene_id=scene_id,
        scene_number="1",
    )
    action = Block(
        id=new_id("block"),
        kind=BlockKind.ACTION,
        text="Bo pins the evidence bundle to the wall.",
        scene_id=scene_id,
    )
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="Provenance Pilot",
        sequences=(
            Sequence(id=new_id("sequence"), title="Act One", order=0, scene_ids=(scene_id,)),
        ),
        blocks=(heading, action),
        notes=(
            Note(
                id=new_id("note"),
                block_id=heading.id,
                author_actor_id=actor_id,
                text="Cite licensed sources only.",
                created_at="2026-09-01T00:00:00Z",
            ),
        ),
        production_tags=(
            ProductionTag(
                id=new_id("production_tag"),
                block_id=heading.id,
                department="art",
                tag_type="set",
                value="lab",
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
class ProvenanceStack:
    workspace: LocalWorkspace
    identity: IdentityService
    authorization: AuthorizationService
    audit: AuditLog
    revisions: RevisionService
    artifacts: ArtifactService
    rights: RightsService
    provenance: ProvenanceService
    project: Project
    document: ScreenplayDocument
    owner: Actor

    @property
    def principal(self):
        return self.identity.principal(self.owner.id)

    @property
    def epoch(self) -> int:
        return self.identity.acl_epoch()


def boot_provenance_stack(
    root: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> ProvenanceStack:
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
            name="Provenance Studio",
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
    rights = RightsService(workspace, authorization, audit)
    provenance = ProvenanceService(workspace, authorization, rights, audit, artifacts)
    return ProvenanceStack(
        workspace=workspace,
        identity=identity,
        authorization=authorization,
        audit=audit,
        revisions=revisions,
        artifacts=artifacts,
        rights=rights,
        provenance=provenance,
        project=project,
        document=document,
        owner=owner,
    )


def invite_role(stack: ProvenanceStack, role: Role, *, integration: bool = False):
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


def register_licensed_source(stack: ProvenanceStack, *, title: str = "Licensed research"):
    return stack.rights.register_source(
        project_id=stack.project.id,
        title=title,
        classification=SourceClassification.LICENSED,
        principal=stack.principal,
        acl_epoch=stack.epoch,
        permitted_uses=LICENSED_USES,
        license_summary="licensed for citation",
        license_expiry="2099-01-01T00:00:00Z",
    )


def sample_provenance() -> MethodProvenance:
    return MethodProvenance(
        provider="deterministic-double",
        model="fixture-extractor",
        model_version="1.0.0",
        prompt_version="1.0.0",
        policy_version="1.0.0",
        timestamp="2026-09-01T16:00:00Z",
        prompt_id="prompt.extract",
        method="structured extraction",
    )


@pytest.fixture
def project_bundle() -> tuple[Project, ScreenplayDocument, str]:
    return make_project_and_document()


@pytest.fixture
def provenance_stack(
    tmp_path: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> ProvenanceStack:
    return boot_provenance_stack(tmp_path / "ws", project_bundle)


@pytest.fixture
def licensed_source(provenance_stack: ProvenanceStack):
    return register_licensed_source(provenance_stack)


@pytest.fixture
def member(provenance_stack: ProvenanceStack):
    def _member(role: Role, *, integration: bool = False):
        return invite_role(provenance_stack, role, integration=integration)

    return _member
