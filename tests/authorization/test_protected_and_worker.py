"""Protected-branch approval, AuthorizedRevisionService wrapper, worker snapshot re-check."""

from __future__ import annotations

from movie_muse.authorization.api import Action, AuthContext, AuthorizationError, ResourceKind
from movie_muse.identity.api import Role, make_human_actor
from movie_muse.schemas.api import ChangeSet, ChangeSetOperation, OperationType, new_id


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


def _invite_writer(acl_stack):
    writer = make_human_actor(
        organization_id=acl_stack.project.organization_id, display_name="Writer"
    )
    acl_stack.identity.register_actor(writer)
    invitation = acl_stack.identity.invite(
        inviter_actor_id=acl_stack.owner.id,
        invitee_actor_id=writer.id,
        project_id=acl_stack.project.id,
        role=Role.WRITER,
    )
    membership = acl_stack.identity.accept_invitation(invitation.id, actor_id=writer.id)
    return writer, membership


def test_protected_branch_merge_without_approval_is_denied(acl_stack) -> None:
    writer, _membership = _invite_writer(acl_stack)
    protected = acl_stack.revisions.create_branch(
        "locked", actor_id=acl_stack.owner.id, protected=True
    )
    resource = acl_stack.authorization.resource_for_project(
        acl_stack.project.id,
        kind=ResourceKind.BRANCH,
        resource_id=protected.id,
        protected=True,
    )
    principal = acl_stack.identity.principal(writer.id)
    decision = acl_stack.authorization.authorize(
        principal,
        Action.MERGE,
        resource,
        acl_epoch=acl_stack.identity.acl_epoch(),
        context=AuthContext(allow_protected=True),
    )
    assert decision.denied
    assert decision.reason in {"protected_branch_requires_approval", "role_denied"}
    try:
        acl_stack.commands.merge_into(
            source_branch=protected.id,
            target_branch=protected.id,
            actor_id=writer.id,
            allow_protected=True,
        )
        raise AssertionError("writer must not merge a protected branch")
    except AuthorizationError:
        pass
    owner = acl_stack.identity.principal(acl_stack.owner.id)
    approved = acl_stack.authorization.authorize(
        owner,
        Action.MERGE,
        resource,
        acl_epoch=acl_stack.identity.acl_epoch(),
        context=AuthContext(allow_protected=True),
    )
    assert approved.allowed
    denied_without_flag = acl_stack.authorization.authorize(
        owner,
        Action.MERGE,
        resource,
        acl_epoch=acl_stack.identity.acl_epoch(),
        context=AuthContext(allow_protected=False),
    )
    assert denied_without_flag.denied
    assert denied_without_flag.reason == "protected_branch_requires_approval"


def test_wrapper_allows_owner_patch_and_denies_viewer_export(acl_stack) -> None:
    change = update_block_change_set(
        base_revision_id=acl_stack.revisions.canon_head_id(),
        actor_id=acl_stack.owner.id,
        block_id=acl_stack.document.blocks[1].id,
        text="Ada studies the lock twice.",
    )
    ack = acl_stack.commands.apply_change_set(change, actor_id=acl_stack.owner.id)
    assert ack.revision_id == acl_stack.revisions.canon_head_id()
    viewer = make_human_actor(
        organization_id=acl_stack.project.organization_id, display_name="Viewer"
    )
    acl_stack.identity.register_actor(viewer)
    invitation = acl_stack.identity.invite(
        inviter_actor_id=acl_stack.owner.id,
        invitee_actor_id=viewer.id,
        project_id=acl_stack.project.id,
        role=Role.VIEWER,
    )
    acl_stack.identity.accept_invitation(invitation.id, actor_id=viewer.id)
    try:
        acl_stack.commands.export_document(
            acl_stack.workspace.root / "denied.json", actor_id=viewer.id
        )
        raise AssertionError("viewer must not export")
    except AuthorizationError:
        pass


def test_worker_recheck_stale_snapshot_and_epoch_fail(acl_stack) -> None:
    writer, membership = _invite_writer(acl_stack)
    principal = acl_stack.identity.principal(writer.id)
    resource = acl_stack.authorization.resource_for_project(acl_stack.project.id)
    snapshot = acl_stack.authorization.permission_snapshot_id()
    epoch = acl_stack.identity.acl_epoch()
    first = acl_stack.authorization.authorize(
        principal,
        Action.READ,
        resource,
        acl_epoch=epoch,
        context=AuthContext(snapshot_id=snapshot),
    )
    assert first.allowed
    acl_stack.identity.revoke_membership(membership.id, actor_id=acl_stack.owner.id)
    stale_epoch = acl_stack.authorization.authorize(
        principal,
        Action.READ,
        resource,
        acl_epoch=epoch,
        context=AuthContext(snapshot_id=snapshot),
    )
    assert stale_epoch.denied
    assert stale_epoch.reason == "stale_acl_epoch"
    stale_snapshot = acl_stack.authorization.authorize(
        principal,
        Action.READ,
        resource,
        acl_epoch=acl_stack.identity.acl_epoch(),
        context=AuthContext(snapshot_id=snapshot),
    )
    assert stale_snapshot.denied
    assert stale_snapshot.reason == "stale_snapshot"
    owner = acl_stack.identity.principal(acl_stack.owner.id)
    fresh = acl_stack.authorization.authorize(
        owner,
        Action.READ,
        resource,
        acl_epoch=acl_stack.identity.acl_epoch(),
        context=AuthContext(snapshot_id=acl_stack.authorization.permission_snapshot_id()),
    )
    assert fresh.allowed
    assert fresh.snapshot_id != snapshot
