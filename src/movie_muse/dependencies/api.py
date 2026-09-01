"""Public surface of ``movie_muse.dependencies``.

Hosts and other modules must import this module, never sibling internals.
"""

from __future__ import annotations

from movie_muse.dependencies.errors import (
    CycleError,
    DependencyError,
    EdgeNotFoundError,
    GraphIntegrityError,
    NodeKindError,
    NodeNotFoundError,
    StaleExportDeniedError,
)
from movie_muse.dependencies.graph import (
    compose_derived_hashes,
    dependent_closure,
    frontier_of,
    output_identity,
    stale_closure_from_scratch,
    topological_order,
    would_create_cycle,
)
from movie_muse.dependencies.index import INDEX_META_KEY
from movie_muse.dependencies.projection import render_graph_html, render_node_html, render_node_text
from movie_muse.dependencies.service import DependencyEngine, GraphService
from movie_muse.dependencies.types import (
    CODE_VERSION,
    DERIVED_KINDS,
    RECOMPUTE_JOB_TYPE,
    SCHEMA_VERSION,
    SOURCE_KINDS,
    DependencyEdge,
    ExportRecord,
    InputHashes,
    InvalidationResult,
    NodeKind,
    NodeState,
    NodeView,
    RecomputeResult,
    StoredNode,
    parse_node_kind,
    parse_node_state,
)

__all__ = [
    "CODE_VERSION",
    "DERIVED_KINDS",
    "INDEX_META_KEY",
    "RECOMPUTE_JOB_TYPE",
    "SCHEMA_VERSION",
    "SOURCE_KINDS",
    "CycleError",
    "DependencyEdge",
    "DependencyEngine",
    "DependencyError",
    "EdgeNotFoundError",
    "ExportRecord",
    "GraphIntegrityError",
    "GraphService",
    "InputHashes",
    "InvalidationResult",
    "NodeKind",
    "NodeKindError",
    "NodeNotFoundError",
    "NodeState",
    "NodeView",
    "RecomputeResult",
    "StaleExportDeniedError",
    "StoredNode",
    "compose_derived_hashes",
    "dependent_closure",
    "frontier_of",
    "output_identity",
    "parse_node_kind",
    "parse_node_state",
    "render_graph_html",
    "render_node_html",
    "render_node_text",
    "stale_closure_from_scratch",
    "topological_order",
    "would_create_cycle",
]
