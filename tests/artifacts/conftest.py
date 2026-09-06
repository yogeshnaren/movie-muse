"""Artifact test builders, duplicated to keep test packages independent."""

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
)
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.revisions.api import RevisionService
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


def make_project_and_document() -> tuple[Project, ScreenplayDocument, str]:
    actor_id = new_id("actor")
    project = Project(
        id=new_id("project"),
        organization_id="org_local",
        title="Artifact Pilot",
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
        text="Ada opens the evidence case.",
        scene_id=scene_id,
    )
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="Artifact Pilot",
        sequences=(
            Sequence(
                id=new_id("sequence"),
                title="Act One",
                order=0,
                scene_ids=(scene_id,),
            ),
        ),
        blocks=(heading, action),
        notes=(
            Note(
                id=new_id("note"),
                block_id=heading.id,
                author_actor_id=actor_id,
                text="Preserve the archive location.",
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
class ArtifactStack:
    workspace: LocalWorkspace
    identity: IdentityService
    authorization: AuthorizationService
    audit: AuditLog
    revisions: RevisionService
    artifacts: ArtifactService
    project: Project
    document: ScreenplayDocument
    owner: Actor

    @property
    def principal(self):
        return self.identity.principal(self.owner.id)

    @property
    def epoch(self) -> int:
        return self.identity.acl_epoch()


def boot_artifact_stack(
    root: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> ArtifactStack:
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
    organization = Organization(
        id=project.organization_id,
        name="Artifact Studio",
        created_at="2026-09-01T00:00:00Z",
    )
    identity.bootstrap(organization=organization, project=project, owner=owner)
    audit = AuditLog(workspace)
    authorization = AuthorizationService(workspace, identity, audit=audit)
    revisions = RevisionService(workspace)
    revisions.bind(actor_id=owner.id)
    artifacts = ArtifactService(workspace, authorization, revisions, audit)
    return ArtifactStack(
        workspace=workspace,
        identity=identity,
        authorization=authorization,
        audit=audit,
        revisions=revisions,
        artifacts=artifacts,
        project=project,
        document=document,
        owner=owner,
    )


@pytest.fixture
def project_bundle() -> tuple[Project, ScreenplayDocument, str]:
    return make_project_and_document()


@pytest.fixture
def artifact_stack(
    tmp_path: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> ArtifactStack:
    return boot_artifact_stack(tmp_path / "ws", project_bundle)
