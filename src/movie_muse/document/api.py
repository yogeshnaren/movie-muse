"""Public surface of ``movie_muse.document``.

Hosts and other modules must import this module, never sibling internals.
"""

from __future__ import annotations

from movie_muse.document.diff import structural_diff
from movie_muse.document.editor_adapter import (
    EDITOR_FORMAT,
    EditorNode,
    EditorProjection,
    from_editor,
    projection_to_dict,
    to_editor,
)
from movie_muse.document.errors import (
    DocumentKernelError,
    InvalidOperationError,
    SelectionError,
    SemanticValidationError,
)
from movie_muse.document.normalize import normalize
from movie_muse.document.operations import apply_change_set, apply_operation
from movie_muse.document.replay import replay
from movie_muse.document.selection import SelectionAnchor, resolve_anchor, transform_anchor
from movie_muse.document.validate import semantic_validate

__all__ = [
    "EDITOR_FORMAT",
    "DocumentKernelError",
    "EditorNode",
    "EditorProjection",
    "InvalidOperationError",
    "SelectionAnchor",
    "SelectionError",
    "SemanticValidationError",
    "apply_change_set",
    "apply_operation",
    "from_editor",
    "normalize",
    "projection_to_dict",
    "replay",
    "resolve_anchor",
    "semantic_validate",
    "structural_diff",
    "to_editor",
    "transform_anchor",
]
