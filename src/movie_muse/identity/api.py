"""Public surface of ``movie_muse.identity``.

Hosts and other modules must import this module, never sibling internals.
"""

from __future__ import annotations

from movie_muse.identity.errors import (
    IdentityError,
    InvitationError,
    MembershipError,
    UnknownPrincipalError,
)
from movie_muse.identity.service import IdentityService, make_human_actor, make_integration_actor
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

__all__ = [
    "Actor",
    "EpochBinding",
    "IdentityError",
    "IdentityService",
    "Invitation",
    "InvitationError",
    "InvitationStatus",
    "Membership",
    "MembershipError",
    "MembershipStatus",
    "Organization",
    "Principal",
    "PrincipalKind",
    "Role",
    "UnknownPrincipalError",
    "make_human_actor",
    "make_integration_actor",
]
