"""Invitation, membership, ACL epoch, and offline revocation quarantine."""

from __future__ import annotations

import json
from pathlib import Path

from movie_muse.identity.api import (
    Actor,
    IdentityService,
    InvitationStatus,
    MembershipError,
    MembershipStatus,
    Organization,
    PrincipalKind,
    Role,
    make_human_actor,
)
from movie_muse.persistence.api import LocalSaveState, LocalWorkspace, PersistenceError
from movie_muse.schemas.api import Project, ScreenplayDocument, new_id
from movie_muse.sync.api import SyncProtocol


def _organization(project: Project, *, name: str = "Studio") -> Organization:
    return Organization(id=project.organization_id, name=name, created_at="2026-09-01T00:00:00Z")


def _owner(project: Project, *, display_name: str = "Owner") -> Actor:
    return Actor(
        id=project.owner_actor_id,
        display_name=display_name,
        principal_kind=PrincipalKind.HUMAN,
        organization_id=project.organization_id,
        created_at="2026-09-01T00:00:00Z",
    )


def test_invite_accept_creates_membership_at_current_epoch(
    bound_identity: tuple[IdentityService, LocalWorkspace, Project, ScreenplayDocument, Actor],
) -> None:
    identity, workspace, project, _document, owner = bound_identity
    writer = make_human_actor(
        organization_id=project.organization_id, display_name="Writer"
    )
    identity.register_actor(writer)
    epoch_before = identity.acl_epoch()
    invitation = identity.invite(
        inviter_actor_id=owner.id,
        invitee_actor_id=writer.id,
        project_id=project.id,
        role=Role.WRITER,
    )
    assert invitation.status is InvitationStatus.PENDING
    membership = identity.accept_invitation(invitation.id, actor_id=writer.id)
    assert membership.status is MembershipStatus.ACCEPTED
    assert membership.acl_epoch_at_grant == epoch_before
    assert membership.role is Role.WRITER
    extra = json.loads(workspace.store.get_meta("authorized_actor_ids") or "[]")
    assert writer.id in extra
    assert writer.id in workspace.authorized_actor_ids(project.id)


def test_revoke_bumps_epoch_and_quarantines_unsynced_outbox(
    bound_identity: tuple[IdentityService, LocalWorkspace, Project, ScreenplayDocument, Actor],
) -> None:
    identity, workspace, project, document, owner = bound_identity
    writer = make_human_actor(
        organization_id=project.organization_id, display_name="Writer"
    )
    identity.register_actor(writer)
    invitation = identity.invite(
        inviter_actor_id=owner.id,
        invitee_actor_id=writer.id,
        project_id=project.id,
        role=Role.WRITER,
    )
    membership = identity.accept_invitation(invitation.id, actor_id=writer.id)
    ack = workspace.save(document, actor_id=writer.id, device_id="dev_writer")
    assert ack.state is LocalSaveState.QUEUED_FOR_SYNC
    assert workspace.pending_outbox()
    snapshot_before = identity.permission_snapshot_id()
    epoch_before = identity.acl_epoch()

    revoked = identity.revoke_membership(membership.id, actor_id=owner.id)
    assert revoked.status is MembershipStatus.REVOKED
    assert identity.acl_epoch() == epoch_before + 1
    assert identity.permission_snapshot_id() != snapshot_before
    assert workspace.store.get_meta("acl_epoch") == str(identity.acl_epoch())
    extra = json.loads(workspace.store.get_meta("authorized_actor_ids") or "[]")
    assert writer.id not in extra
    assert writer.id not in workspace.authorized_actor_ids(project.id)

    pending = workspace.pending_outbox()
    assert pending == []
    recovery = workspace.store.fetchone(
        "SELECT status FROM outbox WHERE operation_id=?",
        (ack.operation_id,),
    )
    assert recovery is not None
    assert str(recovery["status"]) == LocalSaveState.RECOVERY_ONLY.value
    assert workspace.has_revision(ack.revision_id)
    assert workspace.store.get_meta("quarantine_reason") is not None

    flushed = SyncProtocol(workspace).flush_outbox()
    assert ack.operation_id not in flushed
    still = workspace.store.fetchone(
        "SELECT status FROM outbox WHERE operation_id=?",
        (ack.operation_id,),
    )
    assert still is not None
    assert str(still["status"]) == LocalSaveState.RECOVERY_ONLY.value

    owner_ack = workspace.save(
        workspace.reopen(document.id), actor_id=owner.id, device_id="dev_owner"
    )
    assert owner_ack.state is LocalSaveState.QUEUED_FOR_SYNC

    try:
        workspace.save(workspace.reopen(document.id), actor_id=writer.id, device_id="dev_writer")
        raise AssertionError("revoked actor must not save after ACL removal")
    except PersistenceError:
        pass


def test_cannot_revoke_project_owner(
    bound_identity: tuple[IdentityService, LocalWorkspace, Project, ScreenplayDocument, Actor],
) -> None:
    identity, _workspace, project, _document, owner = bound_identity
    memberships = identity.list_memberships(project_id=project.id)
    owner_membership = next(item for item in memberships if item.actor_id == owner.id)
    try:
        identity.revoke_membership(owner_membership.id, actor_id=owner.id)
        raise AssertionError("owner revocation must fail closed")
    except MembershipError:
        pass
    assert identity.acl_epoch() == 0


def test_invitation_is_explicit_and_invitee_only(
    bound_identity: tuple[IdentityService, LocalWorkspace, Project, ScreenplayDocument, Actor],
) -> None:
    identity, _workspace, project, _document, owner = bound_identity
    writer = make_human_actor(
        organization_id=project.organization_id, display_name="Writer"
    )
    identity.register_actor(writer)
    invitation = identity.invite(
        inviter_actor_id=owner.id,
        invitee_actor_id=writer.id,
        project_id=project.id,
        role=Role.VIEWER,
    )
    try:
        identity.accept_invitation(invitation.id, actor_id=owner.id)
        raise AssertionError("only the invitee may accept")
    except Exception:
        pass
    assert identity.get_invitation(invitation.id).status is InvitationStatus.PENDING


def test_second_tenant_can_be_bound_in_the_same_authority(
    tmp_path: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> None:
    project_a, document_a, branch_a = project_bundle
    workspace = LocalWorkspace(tmp_path / "ws")
    workspace.open_project(project_a, document_a, branch_id=branch_a)
    identity = IdentityService(workspace)
    identity.bootstrap(
        organization=_organization(project_a, name="A"),
        project=project_a,
        owner=_owner(project_a, display_name="A Owner"),
    )
    owner_b_id = new_id("actor")
    project_b = Project(
        id=new_id("project"),
        organization_id="org_b",
        title="Other Tenant",
        owner_actor_id=owner_b_id,
        created_at="2026-09-01T00:00:00Z",
    )
    identity.bind_project(
        organization=_organization(project_b, name="B"),
        project=project_b,
        owner=_owner(project_b, display_name="B Owner"),
    )
    assert identity.project_binding(project_a.id)["organization_id"] == project_a.organization_id
    assert identity.project_binding(project_b.id)["organization_id"] == "org_b"
    principal_a = identity.principal(project_a.owner_actor_id)
    assert principal_a.kind is PrincipalKind.HUMAN
    assert principal_a.organization_id == project_a.organization_id
    principal_b = identity.principal(owner_b_id)
    assert principal_b.organization_id == "org_b"
