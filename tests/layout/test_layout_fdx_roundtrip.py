"""FDX round-trip must not drift layout hashes under the Movie Muse profile."""

from __future__ import annotations

from movie_muse.fdx.api import FdxService
from movie_muse.layout.api import LayoutService
from movie_muse.testkit.api import FixtureCatalog


def test_fdx_round_trip_preserves_layout_hash() -> None:
    catalog = FixtureCatalog()
    layout = LayoutService()
    fdx = FdxService()
    for fixture in catalog.fixtures():
        original = layout.layout(fixture.document)
        imported, report, _digest = fdx.round_trip(fixture.document)
        assert report.lossless, fixture.manifest.id
        fdx.assert_lossless(fixture.document, imported)
        again = layout.layout(imported)
        assert original.layout_hash == again.layout_hash, fixture.manifest.id
        assert original.input_hash == again.input_hash, fixture.manifest.id
