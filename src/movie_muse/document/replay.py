"""Replay a ChangeSet onto a document. Deterministic: same inputs, same tree."""

from __future__ import annotations

from movie_muse.document.normalize import normalize
from movie_muse.document.operations import apply_change_set
from movie_muse.schemas.api import ChangeSet, ScreenplayDocument


def replay(document: ScreenplayDocument, change_set: ChangeSet) -> ScreenplayDocument:
    """Apply, then normalize, so replay and serialization share one canonical form."""

    return normalize(apply_change_set(document, change_set))
