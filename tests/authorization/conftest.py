"""Builders for authorization tests. Duplicated rather than imported from other test packages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from movie_muse.audit.api import AuditLog
from movie_muse.authorization.api import AuthorizationService, AuthorizedRevisionService
from movie_muse.identity.api import Actor, IdentityService, Organization, PrincipalKind
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.revisions.api import RevisionService
from movie_muse.schemas.api import (
    Block,
    BlockKind,
    ChangeSet,
    ChangeSetOperation,
    Note,
    OperationType,
    ProductionTag,
    Project,
    RevisionMark,
    ScreenplayDocument,
    Sequence,
    new_id,
)


def make_project_and_document(
    *, organization_id: str = "org_local", owner_actor_id: str | None = None
) -> tuple[Project, ScreenplayDocument, str]:
    actor_id = owner_actor_id or new_id("actor")
    project = Project(
        id=new_id("project"),
        organization_id=organization_id,
        title="Pilot",
        owner_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
    )
    scene_id = new_id("scene")
    cue_id = new_id("character_cue")
    pair_id = new_id("dialogue_pair")
    heading = Block(
        id=new_id("block"),
        kind=BlockKind.SCENE_HEADING,
        text="INT. KITCHEN - DAY",
        scene_id=scene_id,
        scene_number="1",
    )
    action = Block(id=new_id("block"), kind=BlockKind.ACTION, text="Ada studies the lock.")
    character = Block(
        id=new_id("block"),
        kind=BlockKind.CHARACTER,
        text="ADA",
        character_cue_id=cue_id,
        dialogue_pair_id=pair_id,
    )
    dialogue = Block(
        id=new_id("block"),
        kind=BlockKind.DIALOGUE,
        text="It's not locked.",
        dialogue_pair_id=pair_id,
    )
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="Pilot",
        sequences=(Sequence(id=new_id("sequence"), title="Act One", order=0, scene_ids=(scene_id,)),),
        blocks=(heading, action, character, dialogue),
        notes=(
            Note(
                id=new_id("note"),
                block_id=heading.id,
                author_actor_id=actor_id,
                text="confirm kitchen",
                created_at="2026-09-01T00:00:00Z",
            ),
        ),
        production_tags=(
            ProductionTag(
                id=new_id("production_tag"),
                block_id=heading.id,
                department="props",
                tag_type="required_prop",
                value="lockpick set",
            ),
        ),
        revision_marks=(
            RevisionMark(
                id=new_id("revision_mark"),
                block_id=action.id,
                revision_color="blue",
                revision_label="2nd Blue",
                created_at="2026-09-01T00:00:00Z",
            ),
        ),
        base_revision_id=new_id("revision"),
    )
    document.validate()
    return project, document, new_id("branch")


def make_owner(project: Project) -> Actor:
    return Actor(
        id=project.owner_actor_id,
        display_name="Owner",
        principal_kind=PrincipalKind.HUMAN,
        organization_id=project.organization_id,
        created_at="2026-09-01T00:00:00Z",
    )


def make_organization(project: Project, *, name: str = "Studio") -> Organization:
    return Organization(id=project.organization_id, name=name, created_at="2026-09-01T00:00:00Z")


def update_block_change_set(
    *,
    base_revision_id: str,
    actor_id: str,
    block_id: str,
    text: str,
) -> ChangeSet:
    return ChangeSet(
        id=new_id("change_set"),
        base_revision_id=base_revision_id,
        author_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
        operations=(
            ChangeSetOperation(
                id="op-0",
                order=0,
                op_type=OperationType.UPDATE_BLOCK,
                target_id=block_id,
                payload={"text": text},
            ),
        ),
    )


@dataclass
class AclStack:
    workspace: LocalWorkspace
    identity: IdentityService
    authorization: AuthorizationService
    audit: AuditLog
    revisions: RevisionService
    commands: AuthorizedRevisionService
    project: Project
    document: ScreenplayDocument
    owner: Actor


def boot_acl_stack(root: Path, project_bundle: tuple[Project, ScreenplayDocument, str]) -> AclStack:
    project, document, branch_id = project_bundle
    workspace = LocalWorkspace(root)
    workspace.open_project(project, document, branch_id=branch_id)
    identity = IdentityService(workspace)
    owner = make_owner(project)
    identity.bootstrap(organization=make_organization(project), project=project, owner=owner)
    audit = AuditLog(workspace)
    authorization = AuthorizationService(workspace, identity, audit=audit)
    revisions = RevisionService(workspace)
    revisions.bind(actor_id=project.owner_actor_id)
    commands = AuthorizedRevisionService(revisions, authorization, identity)
    return AclStack(
        workspace=workspace,
        identity=identity,
        authorization=authorization,
        audit=audit,
        revisions=revisions,
        commands=commands,
        project=project,
        document=document,
        owner=owner,
    )


@pytest.fixture
def project_bundle() -> tuple[Project, ScreenplayDocument, str]:
    return make_project_and_document()


@pytest.fixture
def acl_stack(tmp_path: Path, project_bundle: tuple[Project, ScreenplayDocument, str]) -> AclStack:
    return boot_acl_stack(tmp_path / "ws", project_bundle)
