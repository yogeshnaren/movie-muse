"""Pinned Courier Prime metrics. Live OS fonts are never the source of truth.

Courier Prime is an SIL Open Font License face used as the screenplay
reference. This module stores numeric advances only — not a font binary,
and not competitor fonts or dumped commercial metrics.

At 12pt the design advance 1229/2048 em equals 10 pitch (10 characters per
inch) and 6 lines per inch, matching professional US letter pagination.
Unlisted code points use the same monospaced advance so Unicode/RTL fixtures
paginate deterministically without HarfBuzz or browser measurement.
"""

from __future__ import annotations

from typing import Final

LAYOUT_ENGINE_VERSION: Final[str] = "1.0.0"
FONT_METRICS_VERSION: Final[str] = "courier-prime-10cpi-v1"
FONT_FAMILY: Final[str] = "Courier Prime"
FONT_LICENSE: Final[str] = "SIL Open Font License 1.1"
POINT_SIZE: Final[int] = 12
CPI: Final[float] = 10.0
LPI: Final[float] = 6.0
CHAR_WIDTH_IN: Final[float] = 1.0 / CPI
LINE_HEIGHT_IN: Final[float] = 1.0 / LPI
UNITS_PER_EM: Final[int] = 2048
ADVANCE_UNITS: Final[int] = 1229
TAB_CELLS: Final[int] = 4

ASCII_ADVANCES_UNITS: Final[dict[str, int]] = {chr(code): ADVANCE_UNITS for code in range(32, 127)}


def cells_for(text: str) -> int:
    """Return the pinned grid width of ``text`` in character cells."""

    cells = 0
    for char in text:
        if char == "\t":
            cells += TAB_CELLS
            continue
        cells += 1
    return cells


def advance_units_for(char: str) -> int:
    if not char:
        return 0
    if char == "\t":
        return ADVANCE_UNITS * TAB_CELLS
    return ASCII_ADVANCES_UNITS.get(char, ADVANCE_UNITS)


def inches_for_cells(cells: int) -> float:
    return cells * CHAR_WIDTH_IN
