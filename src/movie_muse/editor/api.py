"""Public surface of ``movie_muse.editor``.

Hosts and other modules must import this module, never sibling internals.
The editor is an adapter over ScreenplayDocument. It cannot write canon
except through document and revision commands.
"""

from __future__ import annotations

from movie_muse.editor.errors import (
    EditorCanonError,
    EditorCommandError,
    EditorError,
    RecoveryError,
)
from movie_muse.editor.sample import sample_project_and_document
from movie_muse.editor.service import EditorService
from movie_muse.editor.types import (
    ENTER_TRANSITIONS,
    TAB_TRANSITIONS,
    AccessibilityContract,
    AuthorMode,
    AutocompleteSuggestion,
    ContextualAction,
    ElementKind,
    OutlineEntry,
    SceneCard,
    SearchHit,
)

__all__ = [
    "ENTER_TRANSITIONS",
    "TAB_TRANSITIONS",
    "AccessibilityContract",
    "AuthorMode",
    "AutocompleteSuggestion",
    "ContextualAction",
    "EditorCanonError",
    "EditorCommandError",
    "EditorError",
    "EditorService",
    "ElementKind",
    "OutlineEntry",
    "RecoveryError",
    "SceneCard",
    "SearchHit",
    "sample_project_and_document",
]
