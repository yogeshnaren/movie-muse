"""Fail-closed errors for production revision operations."""

from __future__ import annotations


class ProductionRevisionError(RuntimeError):
    """Base class for production revision failures."""


class UnlockDeniedError(ProductionRevisionError):
    """Unlocking or repagination was requested without manage_production_locks."""


class ExportError(ProductionRevisionError):
    """A clean/revision export could not be produced."""


class SidesError(ProductionRevisionError):
    """A sides packet could not be assembled from the layout."""
