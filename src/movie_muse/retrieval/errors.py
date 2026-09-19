"""Typed failures for rights-controlled retrieval."""

from __future__ import annotations


class RetrievalError(RuntimeError):
    """Base class for fail-closed retrieval errors."""


class TenantIsolationError(RetrievalError):
    """A retrieve/index crossed project or workspace tenancy."""


class PromptInjectionError(RetrievalError):
    """Retrieved text is an instruction-like payload and cannot be used as data."""


class ReferenceNotFoundError(RetrievalError):
    """An indexed reference id is not present."""
