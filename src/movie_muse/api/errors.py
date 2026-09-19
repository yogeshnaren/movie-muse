"""Typed failures for the Integration Mesh."""

from __future__ import annotations


class MeshError(RuntimeError):
    """Base class for Integration Mesh failures."""


class CompatibilityError(MeshError):
    """Unsupported API version or breaking contract change."""


class IdempotencyConflictError(MeshError):
    """The same idempotency key was reused with a different payload."""


class RateLimitError(MeshError):
    """Principal exceeded the mesh rate limit."""


class InjectionRejectedError(MeshError):
    """Untrusted tool/API text looked like an instruction takeover."""


class CommitDeniedError(MeshError):
    """Integrations cannot commit canon or bypass creator approval."""


class SourceOfTruthError(MeshError):
    """A field is owned by another system and cannot be written here."""


class CredentialError(MeshError):
    """OAuth/vault token is missing, expired, or revoked."""


class ReviewConnectorUnavailableError(MeshError):
    """Live specialist review connector is unset; fail closed, not skipped."""


class MeshNotFoundError(MeshError):
    """A named mesh object is not in the index."""
