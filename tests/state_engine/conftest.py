"""Builders for state-engine tests. Duplicated rather than imported from other packages."""

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
from movie_muse.state_engine.api import StateEngine


def make_two_scene_document() -> tuple[Project, ScreenplayDocument, str]:
    actor_id = new_id("actor")
    project = Project(
        id=new_id("project"),
        organization_id="org_local",
        title="State Pilot",
        owner_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
    )
    kitchen = new_id("scene")
    harbor = new_id("scene")
    pair_one = new_id("dialogue_pair")
    pair_two = new_id("dialogue_pair")
    heading_one = Block(
        id=new_id("block"),
        kind=BlockKind.SCENE_HEADING,
        text="INT. KITCHEN - DAY",
        scene_id=kitchen,
        scene_number="1",
    )
    action_one = Block(
        id=new_id("block"),
        kind=BlockKind.ACTION,
        text="Ada studies the lock.",
        scene_id=kitchen,
    )
    character_one = Block(
        id=new_id("block"),
        kind=BlockKind.CHARACTER,
        text="ADA",
        character_cue_id=new_id("character_cue"),
        dialogue_pair_id=pair_one,
    )
    dialogue_one = Block(
        id=new_id("block"),
        kind=BlockKind.DIALOGUE,
        text="It's not locked.",
        dialogue_pair_id=pair_one,
    )
    heading_two = Block(
        id=new_id("block"),
        kind=BlockKind.SCENE_HEADING,
        text="EXT. HARBOR - NIGHT",
        scene_id=harbor,
        scene_number="2",
    )
    action_two = Block(
        id=new_id("block"),
        kind=BlockKind.ACTION,
        text="Ada watches the tide.",
        scene_id=harbor,
    )
    character_two = Block(
        id=new_id("block"),
        kind=BlockKind.CHARACTER,
        text="ADA",
        character_cue_id=new_id("character_cue"),
        dialogue_pair_id=pair_two,
    )
    dialogue_two = Block(
        id=new_id("block"),
        kind=BlockKind.DIALOGUE,
        text="Ben thinks I know.",
        dialogue_pair_id=pair_two,
    )
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="State Pilot",
        sequences=(
            Sequence(
                id=new_id("sequence"),
                title="Act One",
                order=0,
                scene_ids=(kitchen, harbor),
            ),
        ),
        blocks=(
            heading_one,
            action_one,
            character_one,
            dialogue_one,
            heading_two,
            action_two,
            character_two,
            dialogue_two,
        ),
        base_revision_id=new_id("revision"),
    )
    document.validate()
    return project, document, new_id("branch")


@dataclass
class StateStack:
    workspace: LocalWorkspace
    identity: IdentityService
    authorization: AuthorizationService
    film_ir_service: FilmIrService
    engine: StateEngine
    project: Project
    document: ScreenplayDocument
    owner: Actor

    @property
    def principal(self):
        return self.identity.principal(self.owner.id)

    @property
    def epoch(self) -> int:
        return self.identity.acl_epoch()


def boot_state_stack(
    root: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> StateStack:
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
            name="State Studio",
            created_at="2026-09-01T00:00:00Z",
        ),
        project=project,
        owner=owner,
    )
    audit = AuditLog(workspace)
    authorization = AuthorizationService(workspace, identity, audit=audit)
    RevisionService(workspace).bind(actor_id=owner.id)
    compiler = CompilerService()
    film_ir_service = FilmIrService(workspace, compiler, authorization)
    engine = StateEngine(workspace, authorization)
    return StateStack(
        workspace=workspace,
        identity=identity,
        authorization=authorization,
        film_ir_service=film_ir_service,
        engine=engine,
        project=project,
        document=document,
        owner=owner,
    )


@pytest.fixture
def state_stack(tmp_path: Path) -> StateStack:
    return boot_state_stack(tmp_path / "ws", make_two_scene_document())
