"""Deny-by-default role matrix, craft ownership, and mode action sets."""

from __future__ import annotations

from movie_muse.authorization.types import Action, Mode
from movie_muse.identity.api import Principal, PrincipalKind, Role

# Explicit role matrix. Unlisted (role, action) pairs are denied.
#
# writer: propose + accept authored patches; cannot manage ACL or export.
# viewer: generic read only; cannot export.
# producer: financial visibility; not rights registry.
# administrator: rights + ACL; not sensitive financial.
# owner: all except department craft confirmation (needs matching department or
#        no department on the resource). Integration principals never confirm.
ROLE_ACTIONS: dict[Role, frozenset[Action]] = {
    Role.OWNER: frozenset(
        {
            Action.READ,
            Action.COMMENT,
            Action.PROPOSE,
            Action.ACCEPT,
            Action.MERGE,
            Action.EXPORT,
            Action.MANAGE_PRODUCTION_LOCKS,
            Action.MANAGE_ACL,
            Action.RUN_PAID_PROVIDER,
            Action.VIEW_SENSITIVE_FINANCIAL,
            Action.VIEW_RIGHTS,
        }
    ),
    Role.ADMINISTRATOR: frozenset(
        {
            Action.READ,
            Action.COMMENT,
            Action.PROPOSE,
            Action.ACCEPT,
            Action.MERGE,
            Action.EXPORT,
            Action.MANAGE_PRODUCTION_LOCKS,
            Action.MANAGE_ACL,
            Action.RUN_PAID_PROVIDER,
            Action.VIEW_RIGHTS,
        }
    ),
    Role.WRITER: frozenset(
        {
            Action.READ,
            Action.COMMENT,
            Action.PROPOSE,
            Action.ACCEPT,
        }
    ),
    Role.DIRECTOR: frozenset(
        {
            Action.READ,
            Action.COMMENT,
            Action.PROPOSE,
            Action.ACCEPT,
            Action.MERGE,
            Action.EXPORT,
            Action.MANAGE_PRODUCTION_LOCKS,
        }
    ),
    Role.PRODUCER: frozenset(
        {
            Action.READ,
            Action.COMMENT,
            Action.PROPOSE,
            Action.ACCEPT,
            Action.MERGE,
            Action.EXPORT,
            Action.RUN_PAID_PROVIDER,
            Action.VIEW_SENSITIVE_FINANCIAL,
        }
    ),
    Role.DEPARTMENT_CONTRIBUTOR: frozenset(
        {
            Action.READ,
            Action.COMMENT,
            Action.PROPOSE,
            Action.CONFIRM_CRAFT_DECISION,
        }
    ),
    Role.REVIEWER: frozenset({Action.READ, Action.COMMENT}),
    Role.VIEWER: frozenset({Action.READ}),
    Role.INTEGRATION_SERVICE: frozenset({Action.READ, Action.PROPOSE}),
}

# Mode projections filter the already-granted role actions. Unspecified stay denied.
MODE_ACTIONS: dict[Mode, frozenset[Action]] = {
    Mode.WRITER: frozenset(
        {Action.READ, Action.COMMENT, Action.PROPOSE, Action.ACCEPT}
    ),
    Mode.DIRECTOR: frozenset(
        {
            Action.READ,
            Action.COMMENT,
            Action.PROPOSE,
            Action.ACCEPT,
            Action.MERGE,
            Action.MANAGE_PRODUCTION_LOCKS,
            Action.EXPORT,
        }
    ),
    Mode.PRODUCER: frozenset(
        {
            Action.READ,
            Action.COMMENT,
            Action.PROPOSE,
            Action.ACCEPT,
            Action.MERGE,
            Action.EXPORT,
            Action.RUN_PAID_PROVIDER,
            Action.VIEW_SENSITIVE_FINANCIAL,
        }
    ),
    Mode.AD: frozenset({Action.READ, Action.COMMENT, Action.MANAGE_PRODUCTION_LOCKS}),
    Mode.ROOM: frozenset({Action.READ, Action.COMMENT, Action.PROPOSE}),
    Mode.DEPARTMENT: frozenset(
        {Action.READ, Action.COMMENT, Action.PROPOSE, Action.CONFIRM_CRAFT_DECISION}
    ),
    Mode.INVESTOR: frozenset({Action.READ}),
    Mode.FIELD: frozenset({Action.READ, Action.COMMENT}),
}

MODE_VISIBLE_FIELDS: dict[Mode, tuple[str, ...]] = {
    Mode.WRITER: ("title", "document", "comments", "revisions"),
    Mode.DIRECTOR: ("title", "document", "comments", "revisions", "production_locks", "coverage"),
    Mode.PRODUCER: (
        "title",
        "document",
        "comments",
        "revisions",
        "schedule",
        "budget",
        "paid_operations",
    ),
    Mode.AD: ("title", "document", "production_locks", "schedule", "call_sheet"),
    Mode.ROOM: ("title", "document", "comments", "proposals"),
    Mode.DEPARTMENT: ("title", "document", "department_handoff", "craft_decisions"),
    Mode.INVESTOR: ("title", "approved_artifacts"),
    Mode.FIELD: ("title", "scene_cards", "annotations", "notifications"),
}


def compose_mode_actions(modes: tuple[Mode, ...]) -> frozenset[Action]:
    allowed: set[Action] = set()
    for mode in modes:
        allowed.update(MODE_ACTIONS.get(mode, frozenset()))
    return frozenset(allowed)


def compose_visible_fields(modes: tuple[Mode, ...]) -> tuple[str, ...]:
    fields: list[str] = []
    seen: set[str] = set()
    for mode in modes:
        for name in MODE_VISIBLE_FIELDS.get(mode, ()):
            if name not in seen:
                seen.add(name)
                fields.append(name)
    return tuple(fields)


def role_allows(role: Role, action: Action) -> bool:
    return action in ROLE_ACTIONS.get(role, frozenset())


def craft_decision_allowed(
    *,
    principal: Principal,
    role: Role,
    resource_department: str | None,
    membership_department: str | None,
) -> bool:
    """Department-owned craft confirmation is a human craft-owner act.

    AI/integration principals cannot confirm. A department contributor must
    match the resource department. A human owner may confirm only when the
    resource has no department (project-level), not a foreign department.
    """

    if principal.kind is PrincipalKind.INTEGRATION_SERVICE:
        return False
    if role is Role.INTEGRATION_SERVICE:
        return False
    if role is Role.DEPARTMENT_CONTRIBUTOR:
        if not resource_department or not membership_department:
            return False
        return resource_department == membership_department
    if role is Role.OWNER and not resource_department:
        return True
    return False
