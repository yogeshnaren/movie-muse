"""Identity-module domain objects. Roles are assigned at membership grant time."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class PrincipalKind(str, Enum):
    HUMAN = "human"
    INTEGRATION_SERVICE = "integration_service"


class Role(str, Enum):
    """Architecture §3.4 minimum roles."""

    OWNER = "owner"
    ADMINISTRATOR = "administrator"
    WRITER = "writer"
    DIRECTOR = "director"
    PRODUCER = "producer"
    DEPARTMENT_CONTRIBUTOR = "department_contributor"
    REVIEWER = "reviewer"
    VIEWER = "viewer"
    INTEGRATION_SERVICE = "integration_service"


class InvitationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"


class MembershipStatus(str, Enum):
    ACCEPTED = "accepted"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class Organization:
    id: str
    name: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "created_at": self.created_at}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Organization:
        return cls(id=str(data["id"]), name=str(data["name"]), created_at=str(data["created_at"]))


@dataclass(frozen=True, slots=True)
class Actor:
    id: str
    display_name: str
    principal_kind: PrincipalKind
    organization_id: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "principal_kind": self.principal_kind.value,
            "organization_id": self.organization_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Actor:
        return cls(
            id=str(data["id"]),
            display_name=str(data["display_name"]),
            principal_kind=PrincipalKind(str(data["principal_kind"])),
            organization_id=str(data["organization_id"]),
            created_at=str(data["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class Principal:
    """Effective security subject. Distinct from the durable Actor record."""

    actor_id: str
    kind: PrincipalKind
    organization_id: str
    display_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "kind": self.kind.value,
            "organization_id": self.organization_id,
            "display_name": self.display_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Principal:
        return cls(
            actor_id=str(data["actor_id"]),
            kind=PrincipalKind(str(data["kind"])),
            organization_id=str(data["organization_id"]),
            display_name=str(data.get("display_name", "")),
        )


@dataclass(frozen=True, slots=True)
class Invitation:
    id: str
    organization_id: str
    project_id: str
    invitee_actor_id: str
    inviter_actor_id: str
    role: Role
    status: InvitationStatus
    created_at: str
    acl_epoch_at_invite: int
    department: str | None = None
    accepted_at: str | None = None
    revoked_at: str | None = None
    membership_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "project_id": self.project_id,
            "invitee_actor_id": self.invitee_actor_id,
            "inviter_actor_id": self.inviter_actor_id,
            "role": self.role.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "acl_epoch_at_invite": self.acl_epoch_at_invite,
            "department": self.department,
            "accepted_at": self.accepted_at,
            "revoked_at": self.revoked_at,
            "membership_id": self.membership_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Invitation:
        department = data.get("department")
        return cls(
            id=str(data["id"]),
            organization_id=str(data["organization_id"]),
            project_id=str(data["project_id"]),
            invitee_actor_id=str(data["invitee_actor_id"]),
            inviter_actor_id=str(data["inviter_actor_id"]),
            role=Role(str(data["role"])),
            status=InvitationStatus(str(data["status"])),
            created_at=str(data["created_at"]),
            acl_epoch_at_invite=int(data["acl_epoch_at_invite"]),
            department=str(department) if department is not None else None,
            accepted_at=str(data["accepted_at"]) if data.get("accepted_at") else None,
            revoked_at=str(data["revoked_at"]) if data.get("revoked_at") else None,
            membership_id=str(data["membership_id"]) if data.get("membership_id") else None,
        )


@dataclass(frozen=True, slots=True)
class Membership:
    id: str
    organization_id: str
    project_id: str
    actor_id: str
    role: Role
    status: MembershipStatus
    accepted_at: str
    acl_epoch_at_grant: int
    department: str | None = None
    invitation_id: str | None = None
    revoked_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "project_id": self.project_id,
            "actor_id": self.actor_id,
            "role": self.role.value,
            "status": self.status.value,
            "accepted_at": self.accepted_at,
            "acl_epoch_at_grant": self.acl_epoch_at_grant,
            "department": self.department,
            "invitation_id": self.invitation_id,
            "revoked_at": self.revoked_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Membership:
        department = data.get("department")
        return cls(
            id=str(data["id"]),
            organization_id=str(data["organization_id"]),
            project_id=str(data["project_id"]),
            actor_id=str(data["actor_id"]),
            role=Role(str(data["role"])),
            status=MembershipStatus(str(data["status"])),
            accepted_at=str(data["accepted_at"]),
            acl_epoch_at_grant=int(data["acl_epoch_at_grant"]),
            department=str(department) if department is not None else None,
            invitation_id=str(data["invitation_id"]) if data.get("invitation_id") else None,
            revoked_at=str(data["revoked_at"]) if data.get("revoked_at") else None,
        )


@dataclass(frozen=True, slots=True)
class EpochBinding:
    """Append-only record that an ACL epoch was established."""

    epoch: int
    reason: str
    created_at: str
    actor_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "epoch": self.epoch,
            "reason": self.reason,
            "created_at": self.created_at,
            "actor_id": self.actor_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EpochBinding:
        actor_id = data.get("actor_id")
        return cls(
            epoch=int(data["epoch"]),
            reason=str(data["reason"]),
            created_at=str(data["created_at"]),
            actor_id=str(actor_id) if actor_id is not None else None,
        )
