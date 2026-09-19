"""Public surface of ``movie_muse.writer_unblock``.

Hosts and other modules must import this module, never sibling internals.
Divergence routes are non-canonical proposals. Prose requires Executor mode.
"""

from __future__ import annotations

from movie_muse.writer_unblock.errors import (
    CombineError,
    ConsentRequiredError,
    ExecutorRequiredError,
    HiddenAuthorityError,
    InvariantConflictError,
    UnknownRouteError,
    WriterUnblockError,
)
from movie_muse.writer_unblock.service import WriterUnblockService, assert_no_hidden_authority
from movie_muse.writer_unblock.types import (
    DivergenceRoute,
    DivergenceSession,
    MetricKind,
    MetricRecord,
    RouteKind,
)

__all__ = [
    "CombineError",
    "ConsentRequiredError",
    "DivergenceRoute",
    "DivergenceSession",
    "ExecutorRequiredError",
    "HiddenAuthorityError",
    "InvariantConflictError",
    "MetricKind",
    "MetricRecord",
    "RouteKind",
    "UnknownRouteError",
    "WriterUnblockError",
    "WriterUnblockService",
    "assert_no_hidden_authority",
]
