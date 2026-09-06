"""Identity authority: actors, tenants, invitations, membership, ACL epochs."""

from __future__ import annotations

import json
from typing import Any

from movie_muse.identity.errors import (
    AclDeniedError,
    ActorImmutableError,
    IdentityError,
    InvitationError,
    MembershipError,
    UnknownPrincipalError,
)
from movie_muse.identity.index import clone_index, commit_index, empty_index, load_index
from movie_muse.identity.types import (
    Actor,
    EpochBinding,
    Invitation,
    InvitationStatus,
    Membership,
    MembershipStatus,
    Organization,
    Principal,
    PrincipalKind,
    Role,
)
from movie_muse.persistence.api import LocalSaveState, LocalWorkspace, digest_payload, utc_now
from movie_muse.schemas.api import Project, new_id, new_ulid
from movie_muse.sync.api import SyncEnvelope

# Must match authorization.policy.ROLE_ACTIONS for Action.MANAGE_ACL.
# Identity cannot import authorization.policy: that would cycle through
# identity.api and violate the public-sibling import boundary.
_MANAGE_ACL_ROLES = frozenset({Role.OWNER, Role.ADMINISTRATOR})


class IdentityService:
    """Local-authority identity store. No network is required."""

    def __init__(self, workspace: LocalWorkspace) -> None:
        self.workspace = workspace

    def bootstrap(
        self,
        *,
        organization: Organization,
        project: Project,
        owner: Actor,
    ) -> Membership:
        """Register the open project's tenant, owner actor, and epoch-0 membership."""

        if owner.organization_id != organization.id:
            raise IdentityError("owner actor organization_id must match the organization")
        if project.organization_id != organization.id:
            raise IdentityError("project organization_id must match the organization")
        if project.owner_actor_id != owner.id:
            raise IdentityError("project owner_actor_id must match the owner actor")
        return self.bind_project(organization=organization, project=project, owner=owner)

    def bind_project(
        self,
        *,
        organization: Organization,
        project: Project,
        owner: Actor,
    ) -> Membership:
        """Register a project tenant binding and owner membership if missing."""

        index = self._ensure_index()
        existing_project = index["projects"].get(project.id)
        if existing_project is not None:
            return self._membership_for_actor(index, owner.id, project.id)
        index = clone_index(index)
        now = utc_now()
        index["organizations"][organization.id] = organization.to_dict()
        self._put_actor(index, owner)
        index["projects"][project.id] = {
            "id": project.id,
            "organization_id": organization.id,
            "owner_actor_id": owner.id,
            "title": project.title,
        }
        if not index["epoch_log"]:
            index["acl_epoch"] = 0
            index["epoch_log"].append(
                EpochBinding(epoch=0, reason="bootstrap", created_at=now, actor_id=owner.id).to_dict()
            )
        membership = Membership(
            id=self._new_membership_id(),
            organization_id=organization.id,
            project_id=project.id,
            actor_id=owner.id,
            role=Role.OWNER,
            status=MembershipStatus.ACCEPTED,
            accepted_at=now,
            acl_epoch_at_grant=int(index["acl_epoch"]),
            department=None,
            invitation_id=None,
        )
        index["memberships"][membership.id] = membership.to_dict()
        self._commit(index)
        return membership

    def register_organization(self, organization: Organization) -> Organization:
        index = clone_index(self._ensure_index())
        index["organizations"][organization.id] = organization.to_dict()
        self._commit(index)
        return organization

    def register_actor(self, actor: Actor) -> Actor:
        index = clone_index(self._ensure_index())
        if actor.organization_id not in index["organizations"]:
            raise IdentityError(f"unknown organization: {actor.organization_id}")
        stored = self._put_actor(index, actor)
        self._commit(index)
        return stored

    def register_project(self, project: Project) -> None:
        index = clone_index(self._ensure_index())
        if project.organization_id not in index["organizations"]:
            raise IdentityError(f"unknown organization: {project.organization_id}")
        if project.owner_actor_id not in index["actors"]:
            raise UnknownPrincipalError(f"unknown owner actor: {project.owner_actor_id}")
        index["projects"][project.id] = {
            "id": project.id,
            "organization_id": project.organization_id,
            "owner_actor_id": project.owner_actor_id,
            "title": project.title,
        }
        self._commit(index)

    def get_organization(self, organization_id: str) -> Organization:
        index = self._ensure_index()
        raw = index["organizations"].get(organization_id)
        if raw is None:
            raise IdentityError(f"unknown organization: {organization_id}")
        return Organization.from_dict(raw)

    def get_actor(self, actor_id: str) -> Actor:
        index = self._ensure_index()
        raw = index["actors"].get(actor_id)
        if raw is None:
            raise UnknownPrincipalError(f"unknown actor: {actor_id}")
        return Actor.from_dict(raw)

    def principal(self, actor_id: str) -> Principal:
        actor = self.get_actor(actor_id)
        return Principal(
            actor_id=actor.id,
            kind=actor.principal_kind,
            organization_id=actor.organization_id,
            display_name=actor.display_name,
        )

    def project_binding(self, project_id: str) -> dict[str, str]:
        index = self._ensure_index()
        raw = index["projects"].get(project_id)
        if raw is None:
            raise IdentityError(f"unknown project: {project_id}")
        return {
            "id": str(raw["id"]),
            "organization_id": str(raw["organization_id"]),
            "owner_actor_id": str(raw["owner_actor_id"]),
            "title": str(raw.get("title", "")),
        }

    def acl_epoch(self) -> int:
        index = self._ensure_index()
        return int(index["acl_epoch"])

    def epoch_log(self) -> tuple[EpochBinding, ...]:
        index = self._ensure_index()
        return tuple(EpochBinding.from_dict(raw) for raw in index["epoch_log"])

    def permission_snapshot_id(self) -> str:
        """Versioned grant id. Changes whenever identity, membership, or ACL epoch changes."""

        index = self._ensure_index()
        memberships = [
            {
                "id": mid,
                "actor_id": raw["actor_id"],
                "role": raw["role"],
                "status": raw["status"],
                "department": raw.get("department"),
                "acl_epoch_at_grant": raw["acl_epoch_at_grant"],
            }
            for mid, raw in sorted(index["memberships"].items())
        ]
        actors = [
            {
                "id": actor_id,
                "principal_kind": raw["principal_kind"],
                "organization_id": raw["organization_id"],
            }
            for actor_id, raw in sorted(index["actors"].items())
        ]
        payload = {
            "acl_epoch": int(index["acl_epoch"]),
            "memberships": memberships,
            "actors": actors,
        }
        _encoded, digest = digest_payload(payload)
        return digest

    def invite(
        self,
        *,
        inviter_actor_id: str,
        invitee_actor_id: str,
        project_id: str,
        role: Role,
        department: str | None = None,
    ) -> Invitation:
        index = clone_index(self._ensure_index())
        if inviter_actor_id not in index["actors"]:
            raise UnknownPrincipalError(f"unknown inviter: {inviter_actor_id}")
        if invitee_actor_id not in index["actors"]:
            raise UnknownPrincipalError(f"unknown invitee: {invitee_actor_id}")
        project = index["projects"].get(project_id)
        if project is None:
            raise IdentityError(f"unknown project: {project_id}")
        invitee = Actor.from_dict(index["actors"][invitee_actor_id])
        if invitee.organization_id != str(project["organization_id"]):
            raise InvitationError("invitee organization does not match the project tenant")
        self._require_manage_acl(index, inviter_actor_id, project_id)
        if role is Role.DEPARTMENT_CONTRIBUTOR and not department:
            raise InvitationError("department contributor invitations require a department")
        invitation = Invitation(
            id=self._new_invitation_id(),
            organization_id=str(project["organization_id"]),
            project_id=project_id,
            invitee_actor_id=invitee_actor_id,
            inviter_actor_id=inviter_actor_id,
            role=role,
            status=InvitationStatus.PENDING,
            created_at=utc_now(),
            acl_epoch_at_invite=int(index["acl_epoch"]),
            department=department,
        )
        index["invitations"][invitation.id] = invitation.to_dict()
        self._commit(index)
        return invitation

    def accept_invitation(self, invitation_id: str, *, actor_id: str) -> Membership:
        index = clone_index(self._ensure_index())
        raw = index["invitations"].get(invitation_id)
        if raw is None:
            raise InvitationError(f"unknown invitation: {invitation_id}")
        invitation = Invitation.from_dict(raw)
        if invitation.status is not InvitationStatus.PENDING:
            raise InvitationError("only pending invitations can be accepted")
        if actor_id != invitation.invitee_actor_id:
            raise InvitationError("invitation can be accepted only by the invitee")
        now = utc_now()
        epoch = int(index["acl_epoch"])
        membership = Membership(
            id=self._new_membership_id(),
            organization_id=invitation.organization_id,
            project_id=invitation.project_id,
            actor_id=invitation.invitee_actor_id,
            role=invitation.role,
            status=MembershipStatus.ACCEPTED,
            accepted_at=now,
            acl_epoch_at_grant=epoch,
            department=invitation.department,
            invitation_id=invitation.id,
        )
        accepted = invitation.to_dict()
        accepted["status"] = InvitationStatus.ACCEPTED.value
        accepted["accepted_at"] = now
        accepted["membership_id"] = membership.id
        index["invitations"][invitation.id] = accepted
        index["memberships"][membership.id] = membership.to_dict()
        self._commit(index)
        return membership

    def revoke_invitation(self, invitation_id: str, *, actor_id: str) -> Invitation:
        index = clone_index(self._ensure_index())
        raw = index["invitations"].get(invitation_id)
        if raw is None:
            raise InvitationError(f"unknown invitation: {invitation_id}")
        invitation = Invitation.from_dict(raw)
        if invitation.status is not InvitationStatus.PENDING:
            raise InvitationError("only pending invitations can be revoked")
        self._require_manage_acl(index, actor_id, invitation.project_id)
        now = utc_now()
        updated = invitation.to_dict()
        updated["status"] = InvitationStatus.REVOKED.value
        updated["revoked_at"] = now
        index["invitations"][invitation.id] = updated
        self._commit(index)
        return Invitation.from_dict(updated)

    def revoke_membership(self, membership_id: str, *, actor_id: str) -> Membership:
        """Revoke membership, bump ACL epoch, and quarantine unsynced outbox.

        Architecture §4: revoked unsynced work is preserved locally as
        recovery-only. It is never uploaded and never destroyed.
        """

        index = clone_index(self._ensure_index())
        raw = index["memberships"].get(membership_id)
        if raw is None:
            raise MembershipError(f"unknown membership: {membership_id}")
        membership = Membership.from_dict(raw)
        if membership.status is not MembershipStatus.ACCEPTED:
            raise MembershipError("only accepted memberships can be revoked")
        self._require_manage_acl(index, actor_id, membership.project_id)
        project = index["projects"].get(membership.project_id)
        if project is not None and str(project["owner_actor_id"]) == membership.actor_id:
            raise MembershipError("cannot revoke the project owner")
        now = utc_now()
        new_epoch = int(index["acl_epoch"]) + 1
        index["acl_epoch"] = new_epoch
        index["epoch_log"].append(
            EpochBinding(
                epoch=new_epoch,
                reason=f"revoke:{membership.actor_id}",
                created_at=now,
                actor_id=actor_id,
            ).to_dict()
        )
        revoked = membership.to_dict()
        revoked["status"] = MembershipStatus.REVOKED.value
        revoked["revoked_at"] = now
        index["memberships"][membership.id] = revoked
        self._commit(index)
        self._quarantine_revoked_unsynced(
            actor_id=membership.actor_id,
            project_id=membership.project_id,
            reason=f"acl_revocation:{membership.actor_id}:epoch:{new_epoch}",
        )
        return Membership.from_dict(revoked)

    def get_invitation(self, invitation_id: str) -> Invitation:
        index = self._ensure_index()
        raw = index["invitations"].get(invitation_id)
        if raw is None:
            raise InvitationError(f"unknown invitation: {invitation_id}")
        return Invitation.from_dict(raw)

    def list_invitations(self) -> tuple[Invitation, ...]:
        index = self._ensure_index()
        invitations = [Invitation.from_dict(raw) for raw in index["invitations"].values()]
        return tuple(sorted(invitations, key=lambda item: item.id))

    def get_membership(self, membership_id: str) -> Membership:
        index = self._ensure_index()
        raw = index["memberships"].get(membership_id)
        if raw is None:
            raise MembershipError(f"unknown membership: {membership_id}")
        return Membership.from_dict(raw)

    def list_memberships(
        self, *, project_id: str | None = None, include_revoked: bool = False
    ) -> tuple[Membership, ...]:
        index = self._ensure_index()
        memberships = [Membership.from_dict(raw) for raw in index["memberships"].values()]
        if project_id is not None:
            memberships = [item for item in memberships if item.project_id == project_id]
        if not include_revoked:
            memberships = [item for item in memberships if item.status is MembershipStatus.ACCEPTED]
        return tuple(sorted(memberships, key=lambda item: item.id))

    def accepted_membership_for(
        self, actor_id: str, *, project_id: str, organization_id: str | None = None
    ) -> Membership | None:
        for membership in self.list_memberships(project_id=project_id):
            if membership.actor_id != actor_id:
                continue
            if organization_id is not None and membership.organization_id != organization_id:
                continue
            return membership
        return None

    def _put_actor(self, index: dict[str, Any], actor: Actor) -> Actor:
        existing = index["actors"].get(actor.id)
        if existing is None:
            index["actors"][actor.id] = actor.to_dict()
            return actor
        current = Actor.from_dict(existing)
        if (
            current.principal_kind != actor.principal_kind
            or current.organization_id != actor.organization_id
        ):
            raise ActorImmutableError(
                f"actor {actor.id} principal kind and tenant binding are immutable"
            )
        return current

    def _require_manage_acl(self, index: dict[str, Any], actor_id: str, project_id: str) -> None:
        membership = self._membership_for_actor(index, actor_id, project_id)
        if membership.role not in _MANAGE_ACL_ROLES:
            raise AclDeniedError(f"actor {actor_id} is denied manage_acl on {project_id}")

    def _quarantine_revoked_unsynced(self, *, actor_id: str, project_id: str, reason: str) -> int:
        """Preserve only the revoked principal's unsynced work as recovery-only.

        Architecture §4: revoked unsynced work is never uploaded and never
        destroyed. Authorized collaborators remain queued for sync.
        """

        quarantined = 0
        for payload in self.workspace.pending_outbox():
            envelope = SyncEnvelope.from_dict(payload)
            if envelope.actor_id != actor_id or envelope.project_id != project_id:
                continue
            self.workspace.put_outbox_status(
                envelope.operation_id, LocalSaveState.RECOVERY_ONLY.value
            )
            quarantined += 1
        self.workspace.store.set_meta("quarantine_reason", reason)
        return quarantined

    def _membership_for_actor(self, index: dict[str, Any], actor_id: str, project_id: str) -> Membership:
        for raw in index["memberships"].values():
            membership = Membership.from_dict(raw)
            if (
                membership.actor_id == actor_id
                and membership.project_id == project_id
                and membership.status is MembershipStatus.ACCEPTED
            ):
                return membership
        raise MembershipError(f"no accepted membership for {actor_id} on {project_id}")

    def _ensure_index(self) -> dict[str, Any]:
        loaded = load_index(self.workspace)
        if loaded is not None:
            return loaded
        return empty_index()

    def _commit(self, index: dict[str, Any]) -> None:
        commit_index(self.workspace, index)
        self._sync_workspace_acl(index)

    def _sync_workspace_acl(self, index: dict[str, Any]) -> None:
        actor_ids: list[str] = []
        seen: set[str] = set()
        for raw in index["memberships"].values():
            membership = Membership.from_dict(raw)
            if membership.status is not MembershipStatus.ACCEPTED:
                continue
            if membership.actor_id in seen:
                continue
            seen.add(membership.actor_id)
            actor_ids.append(membership.actor_id)
        for project in index["projects"].values():
            owner = str(project["owner_actor_id"])
            if owner not in seen:
                seen.add(owner)
                actor_ids.append(owner)
        actor_ids.sort()
        self.workspace.store.set_meta("authorized_actor_ids", json.dumps(actor_ids))
        self.workspace.store.set_meta("acl_epoch", str(int(index["acl_epoch"])))

    @staticmethod
    def _new_invitation_id() -> str:
        return f"inv_{new_ulid()}"

    @staticmethod
    def _new_membership_id() -> str:
        return f"mem_{new_ulid()}"


def make_human_actor(*, organization_id: str, display_name: str, actor_id: str | None = None) -> Actor:
    return Actor(
        id=actor_id or new_id("actor"),
        display_name=display_name,
        principal_kind=PrincipalKind.HUMAN,
        organization_id=organization_id,
        created_at=utc_now(),
    )


def make_integration_actor(
    *, organization_id: str, display_name: str, actor_id: str | None = None
) -> Actor:
    return Actor(
        id=actor_id or new_id("actor"),
        display_name=display_name,
        principal_kind=PrincipalKind.INTEGRATION_SERVICE,
        organization_id=organization_id,
        created_at=utc_now(),
    )
