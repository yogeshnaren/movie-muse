"""Accessibility contract for the authoring surface."""

from __future__ import annotations

from movie_muse.document.api import to_editor
from movie_muse.editor.types import AccessibilityContract
from movie_muse.layout.api import LayoutService, reading_order_text
from movie_muse.schemas.api import ScreenplayDocument


def accessibility_contract(document: ScreenplayDocument) -> AccessibilityContract:
    projection = to_editor(document)
    reading = tuple(node.text for node in projection.nodes if node.text)
    layout = LayoutService().layout(document)
    order = reading_order_text(layout)
    labels = tuple(line for line in order.split("\n") if line) if order else reading
    return AccessibilityContract(
        role="application",
        label="Movie Muse screenplay editor",
        reading_order=labels or reading,
        live_region="polite",
    )
