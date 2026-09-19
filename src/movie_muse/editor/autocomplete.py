"""Deterministic autocomplete from the authored document, never a remote model."""

from __future__ import annotations

from movie_muse.editor.types import AutocompleteSuggestion
from movie_muse.schemas.api import BlockKind, ScreenplayDocument

_SCENE_PREFIXES = ("INT.", "EXT.", "INT./EXT.", "I/E.")


def suggestions(document: ScreenplayDocument, *, prefix: str, kind: str) -> tuple[AutocompleteSuggestion, ...]:
    needle = prefix.strip().upper()
    found: list[AutocompleteSuggestion] = []
    seen: set[str] = set()
    if kind == "character":
        for block in document.blocks:
            if block.kind is not BlockKind.CHARACTER:
                continue
            name = block.text.strip()
            if not name or name in seen:
                continue
            if needle and not name.upper().startswith(needle):
                continue
            seen.add(name)
            found.append(AutocompleteSuggestion(kind="character", text=name, source="authored"))
    elif kind == "scene_heading":
        for starter in _SCENE_PREFIXES:
            if not needle or starter.startswith(needle) or needle.startswith(starter[: max(len(needle), 1)]):
                found.append(AutocompleteSuggestion(kind="scene_heading", text=starter + " ", source="catalog"))
        for block in document.blocks:
            if block.kind is not BlockKind.SCENE_HEADING:
                continue
            text = block.text.strip()
            if not text or text in seen:
                continue
            if needle and needle not in text.upper():
                continue
            seen.add(text)
            found.append(AutocompleteSuggestion(kind="scene_heading", text=text, source="authored"))
    return tuple(found)
