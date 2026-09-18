"""Typed failures for writer-unblock / Creative Divergence."""

from __future__ import annotations


class WriterUnblockError(RuntimeError):
    """Base class for divergence workflow failures."""


class ExecutorRequiredError(WriterUnblockError):
    """Prose generation requires an explicit Executor role contract."""


class HiddenAuthorityError(WriterUnblockError):
    """Generated language claimed hidden authority over the writer."""


class UnknownRouteError(WriterUnblockError):
    """Named route is not in the workspace session."""


class ConsentRequiredError(WriterUnblockError):
    """Metrics that touch suggestion retention require explicit consent."""


class InvariantConflictError(WriterUnblockError):
    """A route would silently violate a declared creator invariant."""


class CombineError(WriterUnblockError):
    """Combining routes requires at least two selected candidates."""
