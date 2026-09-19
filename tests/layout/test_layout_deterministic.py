"""Deterministic layout hashes and traces."""

from __future__ import annotations

import pytest

from movie_muse.layout.api import (
    A4,
    FONT_METRICS_VERSION,
    LAYOUT_ENGINE_VERSION,
    US_LETTER,
    LayoutEngineError,
    LayoutService,
    UnknownProfileError,
)
from movie_muse.testkit.api import FixtureCatalog


def test_repeated_layout_hash_is_identical() -> None:
    service = LayoutService()
    document = FixtureCatalog().get("feature_complete_harbor").document
    first = service.layout(document)
    second = service.layout(document)
    assert first.layout_hash == second.layout_hash
    assert first.input_hash == second.input_hash
    assert first.to_dict() == second.to_dict()
    assert first.engine_version == LAYOUT_ENGINE_VERSION
    assert first.font_metrics_version == FONT_METRICS_VERSION


def test_all_catalog_fixtures_layout() -> None:
    service = LayoutService()
    hashes = []
    for fixture in FixtureCatalog().fixtures():
        result = service.layout(fixture.document)
        assert result.pages
        assert result.layout_hash
        hashes.append(result.layout_hash)
    assert len(set(hashes)) == len(hashes)


def test_paper_profile_changes_hash() -> None:
    service = LayoutService()
    document = FixtureCatalog().get("small_kitchen").document
    letter = service.layout(document, paper_profile=US_LETTER)
    a4 = service.layout(document, paper_profile=A4)
    assert letter.layout_hash != a4.layout_hash
    assert letter.paper_profile_id == "us_letter"
    assert a4.paper_profile_id == "a4"


def test_unknown_profile_and_engine_fail_closed() -> None:
    service = LayoutService()
    document = FixtureCatalog().get("small_kitchen").document
    with pytest.raises(UnknownProfileError):
        service.layout(document, style_profile="final_draft_dump")
    with pytest.raises(UnknownProfileError):
        service.layout(document, paper_profile="tabloid")
    with pytest.raises(LayoutEngineError):
        service.layout(document, engine_version="0.0.0")
