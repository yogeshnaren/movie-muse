"""Typed failures for the dependency and invalidation engine."""

from __future__ import annotations


class DependencyError(RuntimeError):
    """Base class for fail-closed dependency-graph operations."""


class NodeNotFoundError(DependencyError):
    """A dependency node id is not present in the graph index."""


class EdgeNotFoundError(DependencyError):
    """A dependency edge id is not present in the graph index."""


class CycleError(DependencyError):
    """Adding an edge would create a cycle; the graph stays unchanged."""


class StaleExportDeniedError(DependencyError):
    """A stale node cannot be exported without explicit override and audit."""


class NodeKindError(DependencyError):
    """An unsupported or mismatched dependency node kind was requested."""


class GraphIntegrityError(DependencyError):
    """Persisted graph metadata failed an integrity check."""
