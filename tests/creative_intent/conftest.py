"""Builders for creative-intent tests. Duplicated rather than imported from other packages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from movie_muse.audit.api import AuditLog
from movie_muse.authorization.api import AuthorizationService
from movie_muse.creative_intent.api import CreativeIntentService
from movie_muse.identity.api import (
    Actor,
    IdentityService,
    Organization,
    PrincipalKind,
    Role,
    make_human_actor,
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


def make_intent_document() -> tuple[Project, ScreenplayDocument, str]:
    actor_id = new_id("actor")
    project = Project(
        id=new_id("project"),
        organization_id="org_local",
        title="Intent Pilot",
        owner_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
    )
    kitchen = new_id("scene")
    harbor = new_id("scene")
    pair = new_id("dialogue_pair")
    sequence = Sequence(
        id=new_id("sequence"),
        title="Act One",
        order=0,
        scene_ids=(kitchen, harbor),
    )
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="Intent Pilot",
        sequences=(sequence,),
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
                dialogue_pair_id=pair,
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.DIALOGUE,
                text="It's not locked.",
                dialogue_pair_id=pair,
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
        ),
        base_revision_id=new_id("revision"),
    )
    document.validate()
    return project, document, new_id("branch")


@dataclass
class IntentStack:
    workspace: LocalWorkspace
    identity: IdentityService
    authorization: AuthorizationService
    revisions: RevisionService
    intents: CreativeIntentService
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
    def head(self) -> str:
        return self.revisions.get_branch(self.branch_id).head_revision_id

    @property
    def kitchen_id(self) -> str:
        return self.document.sequences[0].scene_ids[0]

    @property
    def sequence_id(self) -> str:
        return self.document.sequences[0].id


def boot_intent_stack(
    root: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> IntentStack:
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
            name="Intent Studio",
            created_at="2026-09-01T00:00:00Z",
        ),
        project=project,
        owner=owner,
    )
    audit = AuditLog(workspace)
    authorization = AuthorizationService(workspace, identity, audit=audit)
    revisions = RevisionService(workspace)
    revisions.bind(actor_id=owner.id)
    intents = CreativeIntentService(workspace, authorization, revisions)
    return IntentStack(
        workspace=workspace,
        identity=identity,
        authorization=authorization,
        revisions=revisions,
        intents=intents,
        project=project,
        document=document,
        owner=owner,
        branch_id=revisions.canon_branch().id,
    )


def invite_role(stack: IntentStack, role: Role):
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


@pytest.fixture
def intent_stack(tmp_path: Path) -> IntentStack:
    return boot_intent_stack(tmp_path / "ws", make_intent_document())
