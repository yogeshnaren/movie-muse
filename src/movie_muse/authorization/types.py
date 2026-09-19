"""Authorization domain types: actions, resources, decisions, modes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from movie_muse.identity.api import Principal, PrincipalKind


class Action(str, Enum):
    """Architecture §3.4 permission verbs, plus department craft confirmation."""

    READ = "read"
    COMMENT = "comment"
    PROPOSE = "propose"
    ACCEPT = "accept"
    MERGE = "merge"
    EXPORT = "export"
    MANAGE_PRODUCTION_LOCKS = "manage_production_locks"
    MANAGE_ACL = "manage_acl"
    RUN_PAID_PROVIDER = "run_paid_provider"
    VIEW_SENSITIVE_FINANCIAL = "view_sensitive_financial"
    VIEW_RIGHTS = "view_rights"
    CONFIRM_CRAFT_DECISION = "confirm_craft_decision"


class ResourceKind(str, Enum):
    ORGANIZATION = "organization"
    PROJECT = "project"
    DOCUMENT = "document"
    BRANCH = "branch"
    ARTIFACT = "artifact"
    OPERATION = "operation"


class DecisionEffect(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


class Mode(str, Enum):
    """Permissioned projections over one canonical project. They never fork state."""

    WRITER = "writer"
    DIRECTOR = "director"
    PRODUCER = "producer"
    AD = "ad"
    ROOM = "room"
    DEPARTMENT = "department"
    INVESTOR = "investor"
    FIELD = "field"


@dataclass(frozen=True, slots=True)
class Resource:
    kind: ResourceKind
    id: str
    organization_id: str
    project_id: str | None = None
    department: str | None = None
    protected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "id": self.id,
            "organization_id": self.organization_id,
            "project_id": self.project_id,
            "department": self.department,
            "protected": self.protected,
        }


@dataclass(frozen=True, slots=True)
class AuthContext:
    """Optional authorize() inputs. Missing/unknown values stay deny-by-default."""

    snapshot_id: str | None = None
    department: str | None = None
    allow_protected: bool = False
    correlation_id: str | None = None
    before_revision_id: str | None = None
    after_revision_id: str | None = None
    audit: bool = True
    modes: tuple[Mode, ...] = ()
    claimed_organization_id: str | None = None


@dataclass(frozen=True, slots=True)
class Decision:
    effect: DecisionEffect
    action: str
    resource_kind: str
    resource_id: str
    principal_id: str
    reason: str
    acl_epoch: int
    snapshot_id: str
    role: str | None = None

    @property
    def allowed(self) -> bool:
        return self.effect is DecisionEffect.ALLOW

    @property
    def denied(self) -> bool:
        return self.effect is DecisionEffect.DENY

    def to_dict(self) -> dict[str, Any]:
        return {
            "effect": self.effect.value,
            "action": self.action,
            "resource_kind": self.resource_kind,
            "resource_id": self.resource_id,
            "principal_id": self.principal_id,
            "reason": self.reason,
            "acl_epoch": self.acl_epoch,
            "snapshot_id": self.snapshot_id,
            "role": self.role,
        }


@dataclass(frozen=True, slots=True)
class ProjectView:
    """Projection of one canonical project. Holds ids, not a forked document copy."""

    mode: tuple[Mode, ...]
    project_id: str
    organization_id: str
    head_revision_id: str
    visible_fields: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    principal_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": [item.value for item in self.mode],
            "project_id": self.project_id,
            "organization_id": self.organization_id,
            "head_revision_id": self.head_revision_id,
            "visible_fields": list(self.visible_fields),
            "allowed_actions": list(self.allowed_actions),
            "principal_id": self.principal_id,
        }


@dataclass(frozen=True, slots=True)
class ComposedMode:
    modes: tuple[Mode, ...]
    allowed_actions: frozenset[Action] = field(default_factory=frozenset)

    def permits(self, action: Action) -> bool:
        return action in self.allowed_actions


def parse_action(action: Action | str) -> Action | None:
    if isinstance(action, Action):
        return action
    try:
        return Action(str(action))
    except ValueError:
        return None


def parse_resource_kind(kind: ResourceKind | str) -> ResourceKind | None:
    if isinstance(kind, ResourceKind):
        return kind
    try:
        return ResourceKind(str(kind))
    except ValueError:
        return None


def is_integration_principal(principal: Principal) -> bool:
    return principal.kind is PrincipalKind.INTEGRATION_SERVICE
