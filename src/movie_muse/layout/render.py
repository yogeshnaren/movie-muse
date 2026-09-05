"""Structured reference renders. Browser-native measurement is never canonical.

Zero-loss fields (text, block type, scene identity, production locks, revision
semantics) have tolerance 0. Positional grid comparison also uses 0 because
metrics are pinned; the constants exist so later raster checks can document a
non-zero pixel band without weakening those fields.
"""

from __future__ import annotations

from movie_muse.layout.metrics import CPI
from movie_muse.layout.types import LayoutPage, LayoutResult, PaperProfile

ZERO_LOSS_FIELDS = (
    "text",
    "block_kind",
    "scene_id",
    "scene_number",
    "locked",
    "revision_mark",
    "continuation",
)
CHAR_POSITION_TOLERANCE = 0
LINE_INDEX_TOLERANCE = 0
RASTER_PIXEL_TOLERANCE = 1  # documented for future bitmap compares; traces stay exact


def reading_order_text(result: LayoutResult) -> str:
    """Accessibility/reading-order stream. Omits headers/footers/blanks."""

    parts: list[str] = []
    for line in result.lines:
        if line.line_kind in {"header", "footer", "blank", "scene_number"}:
            continue
        if line.text:
            parts.append(line.text)
    return "\n".join(parts)


def render_page_grid(page: LayoutPage, paper: PaperProfile) -> str:
    width = int(round(paper.width_in * CPI))
    body = [line for line in page.lines if line.line_kind not in {"header", "footer"}]
    height = max((line.y_line for line in body), default=-1) + 1
    rows = [" " * width for _ in range(max(height, 0))]
    for line in body:
        if line.y_line < 0 or line.y_line >= len(rows):
            continue
        row = list(rows[line.y_line])
        text = line.text[: line.width_chars]
        start = max(0, line.x_chars)
        for offset, char in enumerate(text):
            index = start + offset
            if 0 <= index < width:
                row[index] = char
        if line.revision_mark:
            mark_at = width - 2
            if 0 <= mark_at < width:
                row[mark_at] = "*"
        rows[line.y_line] = "".join(row)
    header = page.header.rjust(width) if page.header else ""
    footer = page.footer if page.footer else ""
    chunks = [header, *rows]
    if footer:
        chunks.append(footer)
    return "\n".join(chunks)


def render_result(result: LayoutResult, paper: PaperProfile) -> str:
    pages = [render_page_grid(page, paper) for page in result.pages]
    return "\n\x0c\n".join(pages)
