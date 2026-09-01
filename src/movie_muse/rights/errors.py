"""Typed failures for the rights registry."""

from __future__ import annotations


class RightsError(RuntimeError):
    """Base class for fail-closed rights registry errors."""


class SourceNotFoundError(RightsError):
    """A source id or version is not present in the registry."""


class UnlicensedSourceError(RightsError):
    """The source is unlicensed or disallowed and cannot be used."""


class PermittedUseDeniedError(RightsError):
    """A requested use is outside the source's permitted-use policy."""


class SourceImmutableError(RightsError):
    """An operation attempted to rewrite an immutable source version."""


class HumanValidationError(RightsError):
    """Human-validation was requested by a non-human or unauthorized principal."""
