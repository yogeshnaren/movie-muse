"""Deterministic word wrap using pinned monospaced cell widths."""

from __future__ import annotations

from movie_muse.layout.errors import LayoutEngineError
from movie_muse.layout.metrics import cells_for


def wrap_text(text: str, width: int) -> tuple[str, ...]:
    if width < 1:
        raise LayoutEngineError("wrap width must be at least 1 cell")
    if text == "":
        return ("",)
    lines: list[str] = []
    for paragraph in text.split("\n"):
        lines.extend(_wrap_paragraph(paragraph, width))
    return tuple(lines)


def _wrap_paragraph(paragraph: str, width: int) -> list[str]:
    if paragraph == "":
        return [""]
    words = paragraph.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        pieces = _split_long_word(word, width) if cells_for(word) > width else (word,)
        for piece in pieces:
            candidate = piece if current == "" else f"{current} {piece}"
            if current != "" and cells_for(candidate) > width:
                lines.append(current)
                current = piece
            else:
                current = candidate
    if current != "" or not lines:
        lines.append(current)
    return lines


def _split_long_word(word: str, width: int) -> tuple[str, ...]:
    chunks: list[str] = []
    remaining = word
    while cells_for(remaining) > width:
        take = width
        while take > 0 and cells_for(remaining[:take]) > width:
            take -= 1
        if take <= 0:
            take = 1
        chunks.append(remaining[:take])
        remaining = remaining[take:]
    if remaining:
        chunks.append(remaining)
    return tuple(chunks) if chunks else (word,)
