"""Typed failures for production-impact analysis."""

from __future__ import annotations


class ImpactError(RuntimeError):
    """Base class for impact-analysis failures."""
