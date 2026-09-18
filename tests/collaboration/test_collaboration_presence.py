"""Presence is ephemeral; comments and decisions are durable."""

from __future__ import annotations

import pytest

from movie_muse.authorization.api import AuthorizationError
from movie_muse.collaboration.api import PRESENCE_TTL, PromotionState
from movie_muse.identity.api import Role, make_human_actor


def test_presence_expires_and_leave_removes_it(collab_stack) -> None:
    record = collab_stack.collab.heartbeat(
        project_id=collab_stack.project.id,
        branch_id=collab_stack.revisions.canon_branch().id,
        principal=collab_stack.principal,
        acl_epoch=collab_stack.epoch,
        device_id="dev_a",
        cursor_block_id=collab_stack.document.blocks[0].id,
    )
    assert record.cursor_block_id == collab_stack.document.blocks[0].id
    listed = collab_stack.collab.list_presence(
        project_id=collab_stack.project.id,
        branch_id=collab_stack.revisions.canon_branch().id,
        principal=collab_stack.principal,
        acl_epoch=collab_stack.epoch,
    )
    assert len(listed) == 1
    collab_stack.clock.advance(int(PRESENCE_TTL.total_seconds()) + 1)
    expired = collab_stack.collab.list_presence(
        project_id=collab_stack.project.id,
        branch_id=collab_stack.revisions.canon_branch().id,
        principal=collab_stack.principal,
        acl_epoch=collab_stack.epoch,
    )
    assert expired == ()
    collab_stack.collab.heartbeat(
        project_id=collab_stack.project.id,
        branch_id=collab_stack.revisions.canon_branch().id,
        principal=collab_stack.principal,
        acl_epoch=collab_stack.epoch,
        device_id="dev_a",
    )
    collab_stack.collab.leave(
        project_id=collab_stack.project.id,
        principal=collab_stack.principal,
        acl_epoch=collab_stack.epoch,
        device_id="dev_a",
    )
    assert (
        collab_stack.collab.list_presence(
            project_id=collab_stack.project.id,
            branch_id=collab_stack.revisions.canon_branch().id,
            principal=collab_stack.principal,
            acl_epoch=collab_stack.epoch,
        )
        == ()
    )


def test_comments_are_durable_and_audited(collab_stack) -> None:
    block_id = collab_stack.document.blocks[1].id
    note = collab_stack.collab.comment(
        project_id=collab_stack.project.id,
        branch_id=collab_stack.revisions.canon_branch().id,
        block_id=block_id,
        text="Keep the brass key beat.",
        principal=collab_stack.principal,
        acl_epoch=collab_stack.epoch,
    )
    assert note.id.startswith("note_")
    listed = collab_stack.collab.list_comments(
        project_id=collab_stack.project.id,
        principal=collab_stack.principal,
        acl_epoch=collab_stack.epoch,
    )
    assert listed[0].text == "Keep the brass key beat."
    operations = [record.operation for record in collab_stack.audit.list_records()]
    assert "collaboration.comment" in operations


def test_decisions_are_durable_and_not_auto_promoted(collab_stack) -> None:
    event = collab_stack.collab.capture_decision(
        project_id=collab_stack.project.id,
        summary="Lock the harbor night exterior",
        principal=collab_stack.principal,
        acl_epoch=collab_stack.epoch,
    )
    assert event.promotion_state is PromotionState.CAPTURED
    assert event.promoted_project_memory_id is None
    recovered = collab_stack.collab.list_decisions(collab_stack.project.id)
    assert recovered[0].id == event.id


def test_viewer_cannot_comment(collab_stack) -> None:
    actor = make_human_actor(
        organization_id=collab_stack.project.organization_id, display_name="Viewer"
    )
    collab_stack.identity.register_actor(actor)
    invitation = collab_stack.identity.invite(
        inviter_actor_id=collab_stack.owner.id,
        invitee_actor_id=actor.id,
        project_id=collab_stack.project.id,
        role=Role.VIEWER,
    )
    collab_stack.identity.accept_invitation(invitation.id, actor_id=actor.id)
    viewer = collab_stack.identity.principal(actor.id)
    with pytest.raises(AuthorizationError):
        collab_stack.collab.comment(
            project_id=collab_stack.project.id,
            branch_id=collab_stack.revisions.canon_branch().id,
            block_id=collab_stack.document.blocks[0].id,
            text="nope",
            principal=viewer,
            acl_epoch=collab_stack.identity.acl_epoch(),
        )


def test_reconnect_returns_ops_since_lamport(collab_stack) -> None:
    missed = collab_stack.collab.reconnect(
        project_id=collab_stack.project.id,
        branch_id=collab_stack.revisions.canon_branch().id,
        principal=collab_stack.principal,
        acl_epoch=collab_stack.epoch,
        device_id="dev_b",
        since_lamport=0,
    )
    assert missed
    assert all(item.lamport > 0 for item in missed)
