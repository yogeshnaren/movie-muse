"""Integrations may propose; only humans commit. Tokens revoke fail-closed."""

from __future__ import annotations

import pytest

from movie_muse.api.api import CommitDeniedError, CredentialError
from movie_muse.authorization.api import AuthorizationError
from movie_muse.identity.api import Role
from movie_muse.schemas.api import ChangeSet, ChangeSetOperation, OperationType, new_id, new_ulid


def test_integration_can_propose_but_cannot_commit(mesh_stack, change_set, member) -> None:
    bot = member(Role.INTEGRATION_SERVICE, integration=True)
    operations = (
        ChangeSetOperation(
            id=f"cop_{new_ulid()}",
            order=0,
            op_type=OperationType.UPDATE_BLOCK,
            target_id=mesh_stack.action_id,
            payload={"text": "Ada waits offstage."},
        ),
    )
    change = ChangeSet(
        id=new_id("change_set"),
        base_revision_id=mesh_stack.revisions.canon_head_id(),
        author_actor_id=bot.actor_id,
        created_at=mesh_stack.clock.stamp(),
        operations=operations,
    )
    envelope = mesh_stack.mesh.propose(
        mesh_stack.project.id,
        change,
        principal=bot,
        acl_epoch=mesh_stack.identity.acl_epoch(),
        intent="bot note",
        rationale_summary="integration proposal",
        provenance="adapter",
    )
    with pytest.raises(CommitDeniedError):
        mesh_stack.mesh.commit(
            envelope.proposal.id,
            principal=bot,
            acl_epoch=mesh_stack.identity.acl_epoch(),
        )
    committed = mesh_stack.mesh.commit(
        envelope.proposal.id,
        principal=mesh_stack.principal,
        acl_epoch=mesh_stack.epoch,
    )
    assert committed["revision_id"]


def test_viewer_cannot_propose(mesh_stack, change_set, member) -> None:
    viewer = member(Role.VIEWER)
    with pytest.raises(AuthorizationError):
        mesh_stack.mesh.propose(
            mesh_stack.project.id,
            change_set(),
            principal=viewer,
            acl_epoch=mesh_stack.identity.acl_epoch(),
            intent="viewer write",
            rationale_summary="should fail",
            provenance="test",
        )


def test_vault_token_round_trip_and_revoke(mesh_stack) -> None:
    issued = mesh_stack.mesh.issue_token(
        mesh_stack.project.id,
        principal=mesh_stack.principal,
        acl_epoch=mesh_stack.epoch,
        scopes=("read", "propose"),
        expires_at="2099-01-01T00:00:00Z",
    )
    assert issued.token.startswith("imt_")
    active = mesh_stack.mesh.authenticate_token(issued.token)
    assert active.actor_id == mesh_stack.owner.id
    mesh_stack.mesh.revoke_token(
        issued.credential.id,
        principal=mesh_stack.principal,
        acl_epoch=mesh_stack.epoch,
    )
    with pytest.raises(CredentialError):
        mesh_stack.mesh.authenticate_token(issued.token)


def test_expired_token_fail_closed(mesh_stack) -> None:
    issued = mesh_stack.mesh.issue_token(
        mesh_stack.project.id,
        principal=mesh_stack.principal,
        acl_epoch=mesh_stack.epoch,
        scopes=("read",),
        expires_at="2020-01-01T00:00:00Z",
    )
    with pytest.raises(CredentialError):
        mesh_stack.mesh.authenticate_token(issued.token)
