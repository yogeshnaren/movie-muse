"""Builders for impact tests. Duplicated rather than imported from other packages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from movie_muse.audit.api import AuditLog
from movie_muse.authorization.api import AuthorizationService
from movie_muse.compiler.api import CompilerService
from movie_muse.continuity.api import ContinuityService
from movie_muse.film_ir.api import FilmIrService
from movie_muse.identity.api import Actor, IdentityService, Organization, PrincipalKind
from movie_muse.impact.api import ImpactService
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
        title="Impact Pilot",
        owner_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
    )
    kitchen = new_id("scene")
    harbor = new_id("scene")
    pair_one = new_id("dialogue_pair")
    pair_two = new_id("dialogue_pair")
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="Impact Pilot",
        sequences=(
            Sequence(
                id=new_id("sequence"),
                title="Act One",
                order=0,
                scene_ids=(kitchen, harbor),
            ),
        ),
        blocks=(
            Block(
                id=new_id("block"),
                kind=BlockKind.SCENE_HEADING,
                text="INT. KITCHEN - DAY",
                scene_id=kitchen,
                scene_number="1",
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.ACTION,
                text="Ada studies the lock.",
                scene_id=kitchen,
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.CHARACTER,
                text="ADA",
                character_cue_id=new_id("character_cue"),
                dialogue_pair_id=pair_one,
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.DIALOGUE,
                text="It's not locked.",
                dialogue_pair_id=pair_one,
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.SCENE_HEADING,
                text="EXT. HARBOR - NIGHT",
                scene_id=harbor,
                scene_number="2",
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.ACTION,
                text="Ada watches the tide.",
                scene_id=harbor,
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.CHARACTER,
                text="ADA",
                character_cue_id=new_id("character_cue"),
                dialogue_pair_id=pair_two,
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.DIALOGUE,
                text="Ben thinks I know.",
                dialogue_pair_id=pair_two,
            ),
        ),
        base_revision_id=new_id("revision"),
    )
    document.validate()
    return project, document, new_id("branch")


@dataclass
class ImpactStack:
    workspace: LocalWorkspace
    identity: IdentityService
    authorization: AuthorizationService
    audit: AuditLog
    film_ir_service: FilmIrService
    continuity: ContinuityService
    impact: ImpactService
    project: Project
    document: ScreenplayDocument
    owner: Actor

    @property
    def principal(self):
        return self.identity.principal(self.owner.id)

    @property
    def epoch(self) -> int:
        return self.identity.acl_epoch()


def boot_impact_stack(root: Path) -> ImpactStack:
    project, document, branch_id = make_two_scene_document()
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
            name="Impact Studio",
            created_at="2026-09-01T00:00:00Z",
        ),
        project=project,
        owner=owner,
    )
    audit = AuditLog(workspace)
    authorization = AuthorizationService(workspace, identity, audit=audit)
    RevisionService(workspace).bind(actor_id=owner.id)
    film_ir_service = FilmIrService(workspace, CompilerService(), authorization)
    engine = StateEngine(workspace, authorization)
    continuity = ContinuityService(engine, authorization, audit)
    impact = ImpactService(continuity, authorization, audit)
    return ImpactStack(
        workspace=workspace,
        identity=identity,
        authorization=authorization,
        audit=audit,
        film_ir_service=film_ir_service,
        continuity=continuity,
        impact=impact,
        project=project,
        document=document,
        owner=owner,
    )


@pytest.fixture
def impact_stack(tmp_path: Path) -> ImpactStack:
    return boot_impact_stack(tmp_path / "ws")
