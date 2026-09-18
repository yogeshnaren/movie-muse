"""Builders for project-memory tests. Duplicated rather than imported from other packages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from movie_muse.audit.api import AuditLog
from movie_muse.authorization.api import AuthorizationService
from movie_muse.identity.api import Actor, IdentityService, Organization, PrincipalKind
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.project_memory.api import ProjectMemoryService
from movie_muse.revisions.api import RevisionService
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
        title="Memory Pilot",
        owner_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
    )
    scene_id = new_id("scene")
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="Memory Pilot",
        sequences=(
            Sequence(id=new_id("sequence"), title="Act One", order=0, scene_ids=(scene_id,)),
        ),
        blocks=(
            Block(
                id=new_id("block"),
                kind=BlockKind.SCENE_HEADING,
                text="INT. KITCHEN - DAY",
                scene_id=scene_id,
                scene_number="1",
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.ACTION,
                text="Ada writes a note.",
                scene_id=scene_id,
            ),
        ),
        base_revision_id=new_id("revision"),
    )
    document.validate()
    return project, document, new_id("branch")


@dataclass
class MemoryStack:
    workspace: LocalWorkspace
    identity: IdentityService
    authorization: AuthorizationService
    audit: AuditLog
    memory: ProjectMemoryService
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


def boot_memory_stack(root: Path) -> MemoryStack:
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
            name="Memory Studio",
            created_at="2026-09-01T00:00:00Z",
        ),
        project=project,
        owner=owner,
    )
    audit = AuditLog(workspace)
    authorization = AuthorizationService(workspace, identity, audit=audit)
    RevisionService(workspace).bind(actor_id=owner.id)
    memory = ProjectMemoryService(workspace, authorization, audit)
    return MemoryStack(
        workspace=workspace,
        identity=identity,
        authorization=authorization,
        audit=audit,
        memory=memory,
        project=project,
        document=document,
        owner=owner,
        branch_id=branch_id,
    )


@pytest.fixture
def memory_stack(tmp_path: Path) -> MemoryStack:
    return boot_memory_stack(tmp_path / "ws")
