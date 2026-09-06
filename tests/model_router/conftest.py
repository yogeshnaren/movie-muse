"""MM-009 model-router fixtures; duplicated rather than imported from other tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from movie_muse.audit.api import AuditLog
from movie_muse.authorization.api import AuthorizationService
from movie_muse.identity.api import (
    Actor,
    IdentityService,
    Organization,
    PrincipalKind,
    Role,
    make_human_actor,
)
from movie_muse.model_router.api import ModelRequest, ModelRouter
from movie_muse.persistence.api import LocalWorkspace
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


class FakeHttpClient:
    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.payload = payload or {
            "output": {
                "text": "INT. SOUNDSTAGE - DAY\nRemote draft.",
                "method": "remote_http",
                "assumptions": ["configured_provider"],
                "uncertainty": "provider_reported",
            },
            "usage": {"input_tokens": 12, "output_tokens": 8, "cost": 1.25},
            "model_version": "remote-1.0.0",
        }

    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout_s: float,
    ) -> dict[str, Any]:
        self.calls.append(
            {"url": url, "payload": dict(payload), "headers": dict(headers), "timeout_s": timeout_s}
        )
        return dict(self.payload)


@dataclass
class RouterStack:
    workspace: LocalWorkspace
    identity: IdentityService
    authorization: AuthorizationService
    audit: AuditLog
    revisions: RevisionService
    router: ModelRouter
    project: Project
    document: ScreenplayDocument
    owner: Actor
    http: FakeHttpClient

    @property
    def principal(self):
        return self.identity.principal(self.owner.id)

    @property
    def epoch(self) -> int:
        return self.identity.acl_epoch()

    @property
    def snapshot(self) -> str:
        return self.identity.permission_snapshot_id()


def make_project_and_document(*, ai_off: bool = False) -> tuple[Project, ScreenplayDocument, str]:
    actor_id = new_id("actor")
    project = Project(
        id=new_id("project"),
        organization_id="org_model_router",
        title="Router Pilot",
        owner_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
        ai_off=ai_off,
    )
    scene_id = new_id("scene")
    heading = Block(
        id=new_id("block"),
        kind=BlockKind.SCENE_HEADING,
        text="INT. ROUTER LAB - DAY",
        scene_id=scene_id,
        scene_number="1",
    )
    action = Block(
        id=new_id("block"),
        kind=BlockKind.ACTION,
        text="The author keeps writing without a model.",
        scene_id=scene_id,
    )
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="Router Pilot",
        sequences=(
            Sequence(
                id=new_id("sequence"),
                title="Act One",
                order=0,
                scene_ids=(scene_id,),
            ),
        ),
        blocks=(heading, action),
        base_revision_id=new_id("revision"),
    )
    document.validate()
    return project, document, new_id("branch")


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


def boot_router_stack(
    root: Path,
    *,
    ai_off: bool = False,
    http: FakeHttpClient | None = None,
) -> RouterStack:
    project, document, branch_id = make_project_and_document(ai_off=ai_off)
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
            name="Router Studio",
            created_at="2026-09-01T00:00:00Z",
        ),
        project=project,
        owner=owner,
    )
    audit = AuditLog(workspace)
    authorization = AuthorizationService(workspace, identity, audit=audit)
    revisions = RevisionService(workspace)
    revisions.bind(actor_id=owner.id)
    client = http or FakeHttpClient()
    router = ModelRouter(workspace, authorization, identity, audit, http_client=client)
    return RouterStack(
        workspace=workspace,
        identity=identity,
        authorization=authorization,
        audit=audit,
        revisions=revisions,
        router=router,
        project=project,
        document=document,
        owner=owner,
        http=client,
    )


def add_member(stack: RouterStack, role: Role, *, display_name: str | None = None):
    actor = make_human_actor(
        organization_id=stack.project.organization_id,
        display_name=display_name or role.value,
    )
    stack.identity.register_actor(actor)
    invitation = stack.identity.invite(
        inviter_actor_id=stack.owner.id,
        invitee_actor_id=actor.id,
        project_id=stack.project.id,
        role=role,
    )
    stack.identity.accept_invitation(invitation.id, actor_id=actor.id)
    return stack.identity.principal(actor.id)


def make_request(stack: RouterStack, **overrides: Any) -> ModelRequest:
    values: dict[str, Any] = {
        "capability": "generate_text",
        "data_classification": "public",
        "latency_budget_ms": 5000,
        "cost_budget": 5.0,
        "offline_required": False,
        "context_tokens": 128,
        "structured_output": True,
        "quality_tier": "fast",
        "role_contract": "executor",
        "project_id": stack.project.id,
        "actor_id": stack.owner.id,
        "acl_epoch": stack.epoch,
        "permission_snapshot_id": stack.snapshot,
        "input": {"text": "Write a scene heading."},
        "consent_granted": True,
    }
    values.update(overrides)
    return ModelRequest(**values)


@pytest.fixture
def router_stack(tmp_path: Path) -> RouterStack:
    stack = boot_router_stack(tmp_path / "workspace")
    yield stack
    stack.workspace.close()


@pytest.fixture
def ai_off_stack(tmp_path: Path) -> RouterStack:
    stack = boot_router_stack(tmp_path / "ai-off", ai_off=True)
    yield stack
    stack.workspace.close()


@pytest.fixture
def request_factory(router_stack: RouterStack):
    def _factory(**overrides: Any) -> ModelRequest:
        return make_request(router_stack, **overrides)

    return _factory


@pytest.fixture
def member_factory(router_stack: RouterStack):
    def _factory(role: Role, *, display_name: str | None = None):
        return add_member(router_stack, role, display_name=display_name)

    return _factory
