"""Fail-closed errors for the identity module."""

from __future__ import annotations


class IdentityError(ValueError):
    """Base error for actor, tenant, invitation, and membership commands."""


class UnknownPrincipalError(IdentityError):
    """The actor or principal is not registered in this workspace."""


class InvitationError(IdentityError):
    """Invitation state does not permit the requested transition."""


class MembershipError(IdentityError):
    """Membership cannot be granted, accepted, or revoked as requested."""
