"""MM-013 FDX tests; helpers are local to this package."""

from __future__ import annotations

from movie_muse.fdx.api import FdxService
from movie_muse.testkit.api import FixtureCatalog


def catalog() -> FixtureCatalog:
    return FixtureCatalog()


def service() -> FdxService:
    return FdxService()
