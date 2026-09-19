"""Builders for rubric tests. Duplicated rather than imported from other packages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from movie_muse.audit.api import AuditLog
from movie_muse.authorization.api import AuthorizationService
from movie_muse.compiler.api import CompilerService
from movie_muse.creative_intent.api import CreativeIntentService
from movie_muse.film_ir.api import FilmIrService
from movie_muse.identity.api import (
    Actor,
    IdentityService,
    Organization,
    PrincipalKind,
    Role,
    make_human_actor,
    make_integration_actor,
)
from movie_muse.model_router.api import ModelRouter
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.revisions.api import RevisionService
from movie_muse.rubric.api import RubricService
from movie_muse.schemas.api import (
    Block,
    BlockKind,
    Project,
    ScreenplayDocument,
    Sequence,
    new_id,
)


def make_document() -> tuple[Project, ScreenplayDocument, str]:
    actor_id = new_id("actor")
    project = Project(
        id=new_id("project"),
        organization_id="org_local",
        title="Rubric Pilot",
        owner_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
    )
    scene_id = new_id("scene")
    pair = new_id("dialogue_pair")
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
        text="Ada studies the lock.",
        scene_id=scene_id,
    )
    character = Block(
        id=new_id("block"),
        kind=BlockKind.CHARACTER,
        text="ADA",
        character_cue_id=new_id("character_cue"),
        dialogue_pair_id=pair,
    )
    dialogue = Block(
        id=new_id("block"),
        kind=BlockKind.DIALOGUE,
        text="It's not locked.",
        dialogue_pair_id=pair,
    )
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="Rubric Pilot",
        sequences=(
            Sequence(id=new_id("sequence"), title="Act One", order=0, scene_ids=(scene_id,)),
        ),
        blocks=(heading, action, character, dialogue),
        base_revision_id=new_id("revision"),
    )
    document.validate()
    return project, document, new_id("branch")


@dataclass
class RubricStack:
    workspace: LocalWorkspace
    identity: IdentityService
    authorization: AuthorizationService
    audit: AuditLog
    revisions: RevisionService
    router: ModelRouter
    compiler: CompilerService
    film_ir: FilmIrService
    intents: CreativeIntentService
    rubric: RubricService
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

    @property
    def snapshot(self) -> str:
        return self.identity.permission_snapshot_id()

    @property
    def head(self) -> str:
        return self.revisions.canon_branch().head_revision_id


def boot_rubric_stack(root: Path) -> RubricStack:
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
            name="Rubric Studio",
            created_at="2026-09-01T00:00:00Z",
        ),
        project=project,
        owner=owner,
    )
    audit = AuditLog(workspace)
    authorization = AuthorizationService(workspace, identity, audit=audit)
    revisions = RevisionService(workspace)
    revisions.bind(actor_id=owner.id)
    router = ModelRouter(workspace, authorization, identity, audit)
    compiler = CompilerService()
    film_ir = FilmIrService(workspace, compiler, authorization, router)
    intents = CreativeIntentService(workspace, authorization, revisions)
    rubric = RubricService(
        workspace, authorization, identity, audit, router, revisions, film_ir, intents
    )
    return RubricStack(
        workspace=workspace,
        identity=identity,
        authorization=authorization,
        audit=audit,
        revisions=revisions,
        router=router,
        compiler=compiler,
        film_ir=film_ir,
        intents=intents,
        rubric=rubric,
        project=project,
        document=document,
        owner=owner,
        branch_id=revisions.canon_branch().id,
    )


def invite_role(stack: RubricStack, role: Role, *, integration: bool = False):
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
def rubric_stack(tmp_path: Path) -> RubricStack:
    return boot_rubric_stack(tmp_path / "ws")


@pytest.fixture
def member(rubric_stack: RubricStack):
    def _member(role: Role, *, integration: bool = False):
        return invite_role(rubric_stack, role, integration=integration)

    return _member
