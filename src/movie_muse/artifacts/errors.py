"""Errors raised by the generic artifact subsystem."""

from __future__ import annotations


class ArtifactError(Exception):
    """Base error for artifact lifecycle operations."""


class ArtifactNotFoundError(ArtifactError):
    """An artifact id is not present in the artifact index."""


class ArtifactVersionNotFoundError(ArtifactError):
    """An artifact-version id is not present in the artifact index."""


class ArtifactTemplateNotFoundError(ArtifactError):
    """A requested template id/version is not registered."""


class ArtifactTypeError(ArtifactError):
    """An unsupported generic artifact type was requested."""


class ArtifactImmutableError(ArtifactError):
    """An operation attempted to rewrite or delete immutable history."""


class ArtifactReviewError(ArtifactError):
    """A review-state transition is invalid."""


class ArtifactDeliveryError(ArtifactError):
    """A delivery lacks explicit confirmation or a matching preview."""


class ArtifactIntegrityError(ArtifactError):
    """Persisted artifact metadata or content failed an integrity check."""
