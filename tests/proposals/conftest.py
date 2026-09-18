"""Builders for proposal tests. Duplicated rather than imported from other packages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from movie_muse.audit.api import AuditLog
from movie_muse.authorization.api import AuthorizationService
from movie_muse.dependencies.api import DependencyEngine
from movie_muse.identity.api import (
    Actor,
    IdentityService,
    Organization,
    PrincipalKind,
    Role,
    make_human_actor,
    make_integration_actor,
)
from movie_muse.jobs.api import JobService
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.proposals.api import ProposalService
from movie_muse.revisions.api import RevisionService
from movie_muse.schemas.api import (
    Block,
    BlockKind,
    ChangeSet,
    ChangeSetOperation,
    OperationType,
    Project,
    ScreenplayDocument,
    Sequence,
    new_id,
)


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 1, 16, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> datetime:
        self.value += timedelta(seconds=seconds)
        return self.value


def make_proposal_document() -> tuple[Project, ScreenplayDocument, str]:
    actor_id = new_id("actor")
    project = Project(
        id=new_id("project"),
        organization_id="org_local",
        title="Proposal Pilot",
        owner_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
    )
    scene_id = new_id("scene")
    pair = new_id("dialogue_pair")
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="Proposal Pilot",
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
                text="Ada studies the lock.",
                scene_id=scene_id,
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
        ),
        base_revision_id=new_id("revision"),
    )
    document.validate()
    return project, document, new_id("branch")


def update_text_ops(*pairs: tuple[str, str], base_revision_id: str, actor_id: str) -> ChangeSet:
    operations = tuple(
        ChangeSetOperation(
            id=f"cop_{index}",
            order=index,
            op_type=OperationType.UPDATE_BLOCK,
            target_id=block_id,
            payload={"text": text},
        )
        for index, (block_id, text) in enumerate(pairs)
    )
    return ChangeSet(
        id=new_id("change_set"),
        base_revision_id=base_revision_id,
        author_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
        operations=operations,
    )


@dataclass
class ProposalStack:
    workspace: LocalWorkspace
    identity: IdentityService
    authorization: AuthorizationService
    audit: AuditLog
    revisions: RevisionService
    graph: DependencyEngine
    proposals: ProposalService
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
    def action_id(self) -> str:
        return next(
            block.id for block in self.revisions.replay_head().blocks if block.kind is BlockKind.ACTION
        )

    @property
    def dialogue_id(self) -> str:
        return next(
            block.id
            for block in self.revisions.replay_head().blocks
            if block.kind is BlockKind.DIALOGUE
        )


def boot_proposal_stack(
    root: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> ProposalStack:
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
            name="Proposal Studio",
            created_at="2026-09-01T00:00:00Z",
        ),
        project=project,
        owner=owner,
    )
    audit = AuditLog(workspace)
    authorization = AuthorizationService(workspace, identity, audit=audit)
    revisions = RevisionService(workspace)
    revisions.bind(actor_id=owner.id)
    clock = MutableClock()
    jobs = JobService(
        workspace,
        identity,
        authorization,
        audit,
        lambda job: job.input_fingerprint,
        clock=clock,
    )
    graph = DependencyEngine(workspace, authorization, jobs, audit)
    proposals = ProposalService(revisions, authorization, audit, graph)
    return ProposalStack(
        workspace=workspace,
        identity=identity,
        authorization=authorization,
        audit=audit,
        revisions=revisions,
        graph=graph,
        proposals=proposals,
        project=project,
        document=document,
        owner=owner,
        branch_id=revisions.canon_branch().id,
    )


def invite_integration(stack: ProposalStack):
    actor = make_integration_actor(
        organization_id=stack.project.organization_id, display_name="model-router"
    )
    stack.identity.register_actor(actor)
    invitation = stack.identity.invite(
        inviter_actor_id=stack.owner.id,
        invitee_actor_id=actor.id,
        project_id=stack.project.id,
        role=Role.INTEGRATION_SERVICE,
    )
    stack.identity.accept_invitation(invitation.id, actor_id=actor.id)
    return stack.identity.principal(actor.id)


def invite_human(stack: ProposalStack, role: Role):
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
def proposal_stack(tmp_path: Path) -> ProposalStack:
    return boot_proposal_stack(tmp_path / "ws", make_proposal_document())


@pytest.fixture
def integration_principal(proposal_stack: ProposalStack):
    return invite_integration(proposal_stack)


@pytest.fixture
def viewer_principal(proposal_stack: ProposalStack):
    return invite_human(proposal_stack, Role.VIEWER)
