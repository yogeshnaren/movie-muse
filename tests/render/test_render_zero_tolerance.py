"""Text, block type, scene identity, locks, and revision marks have zero tolerance.

Raster pixel compares are not implemented in this package; RASTER_PIXEL_TOLERANCE
is documented for a later bitmap renderer and must not weaken trace comparison.
"""

from __future__ import annotations

from movie_muse.layout.api import (
    CHAR_POSITION_TOLERANCE,
    LINE_INDEX_TOLERANCE,
    RASTER_PIXEL_TOLERANCE,
    ZERO_LOSS_FIELDS,
    LayoutService,
)
from movie_muse.testkit.api import FixtureCatalog


def test_zero_loss_fields_and_grid_tolerances() -> None:
    assert CHAR_POSITION_TOLERANCE == 0
    assert LINE_INDEX_TOLERANCE == 0
    assert RASTER_PIXEL_TOLERANCE >= 0
    assert ZERO_LOSS_FIELDS == (
        "text",
        "block_kind",
        "scene_id",
        "scene_number",
        "locked",
        "revision_mark",
        "continuation",
    )
    document = FixtureCatalog().get("production_locked_sides").document
    first = LayoutService().layout(document)
    second = LayoutService().layout(document)
    for left, right in zip(first.lines, second.lines, strict=True):
        for field in ZERO_LOSS_FIELDS:
            assert getattr(left, field) == getattr(right, field)
        assert abs(left.x_chars - right.x_chars) <= CHAR_POSITION_TOLERANCE
        assert abs(left.y_line - right.y_line) <= LINE_INDEX_TOLERANCE
    assert first.observation.lock_honored is True
