"""Typed failures for FilmIR projection and extraction."""

from __future__ import annotations


class FilmIrError(RuntimeError):
    """Base class for FilmIR failures."""


class FilmIrNotFoundError(FilmIrError):
    """A stored FilmIR projection is missing."""


class ExtractionRepairError(FilmIrError):
    """Structured model output could not be repaired into candidate claims."""


class AuthoredPromotionError(FilmIrError):
    """An inferred extraction was treated as authored or structural FilmIR."""
