"""Builders for FilmIR tests. Duplicated rather than imported from other packages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from movie_muse.audit.api import AuditLog
from movie_muse.authorization.api import AuthorizationService
from movie_muse.compiler.api import CompilerService
from movie_muse.film_ir.api import FilmIrService
from movie_muse.identity.api import (
    Actor,
    IdentityService,
    Organization,
    PrincipalKind,
)
from movie_muse.model_router.api import ModelRouter
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


def make_project_and_document() -> tuple[Project, ScreenplayDocument, str]:
    actor_id = new_id("actor")
    project = Project(
        id=new_id("project"),
        organization_id="org_local",
        title="FilmIR Pilot",
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
        text="Ada studies the lock.",
        scene_id=scene_id,
    )
    character = Block(
        id=new_id("block"),
        kind=BlockKind.CHARACTER,
        text="ADA",
        character_cue_id=new_id("character_cue"),
        dialogue_pair_id=new_id("dialogue_pair"),
    )
    dialogue = Block(
        id=new_id("block"),
        kind=BlockKind.DIALOGUE,
        text="It's not locked.",
        dialogue_pair_id=character.dialogue_pair_id,
    )
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="FilmIR Pilot",
        sequences=(
            Sequence(id=new_id("sequence"), title="Act One", order=0, scene_ids=(scene_id,)),
        ),
        blocks=(heading, action, character, dialogue),
        base_revision_id=new_id("revision"),
    )
    document.validate()
    return project, document, new_id("branch")


@dataclass
class FilmIrStack:
    workspace: LocalWorkspace
    identity: IdentityService
    authorization: AuthorizationService
    revisions: RevisionService
    router: ModelRouter
    compiler: CompilerService
    film_ir: FilmIrService
    project: Project
    document: ScreenplayDocument
    owner: Actor

    @property
    def principal(self):
        return self.identity.principal(self.owner.id)

    @property
    def epoch(self) -> int:
        return self.identity.acl_epoch()

    @property
    def snapshot(self) -> str:
        return self.identity.permission_snapshot_id()


def boot_film_ir_stack(
    root: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> FilmIrStack:
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
            name="FilmIR Studio",
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
    return FilmIrStack(
        workspace=workspace,
        identity=identity,
        authorization=authorization,
        revisions=revisions,
        router=router,
        compiler=compiler,
        film_ir=film_ir,
        project=project,
        document=document,
        owner=owner,
    )


@pytest.fixture
def film_ir_stack(tmp_path: Path) -> FilmIrStack:
    return boot_film_ir_stack(tmp_path / "ws", make_project_and_document())
