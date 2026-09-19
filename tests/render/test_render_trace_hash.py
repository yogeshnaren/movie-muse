"""Reference renders are a deterministic function of layout traces."""

from __future__ import annotations

from movie_muse.layout.api import LayoutService, render_result, resolve_paper_profile
from movie_muse.testkit.api import FixtureCatalog


def test_render_bytes_match_for_identical_layout_hash() -> None:
    service = LayoutService()
    document = FixtureCatalog().get("feature_complete_harbor").document
    first = service.layout(document)
    second = service.layout(document)
    assert first.layout_hash == second.layout_hash
    paper = resolve_paper_profile(first.paper_profile_id)
    assert render_result(first, paper) == render_result(second, paper)
    assert service.render_text(first) == service.render_text(second)
    assert "\x0c" in service.render_text(first) or len(first.pages) == 1
