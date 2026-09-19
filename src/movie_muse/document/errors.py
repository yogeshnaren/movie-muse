"""Document-kernel errors. Fail closed; never silently drop authored structure."""

from __future__ import annotations


class DocumentKernelError(ValueError):
    """Base error for typed screenplay operations."""


class InvalidOperationError(DocumentKernelError):
    """A ChangeSet operation cannot be applied to the current document."""


class SemanticValidationError(DocumentKernelError):
    """The document violates professional screenplay semantics."""


class SelectionError(DocumentKernelError):
    """A selection anchor does not resolve against the current document."""
