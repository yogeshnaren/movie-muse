"""Deterministic FDX export hashes."""

from __future__ import annotations

from movie_muse.fdx.api import FdxService
from movie_muse.testkit.api import FixtureCatalog


def test_repeated_export_bytes_are_identical() -> None:
    service = FdxService()
    document = FixtureCatalog().get("feature_complete_harbor").document
    first = service.export_document(document)
    second = service.export_document(document)
    assert first == second
    assert service.export_digest(document) == service.export_digest(document)


def test_round_trip_helper_returns_stable_digest() -> None:
    service = FdxService()
    document = FixtureCatalog().get("small_kitchen").document
    imported, report, digest = service.round_trip(document)
    assert report.lossless
    assert digest == service.export_digest(document)
    service.assert_lossless(document, imported)
