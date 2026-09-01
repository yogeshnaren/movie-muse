"""Typed failures for FDX import, export, and profile validation."""

from __future__ import annotations


class FdxError(RuntimeError):
    """Base class for fail-closed FDX operations."""


class FdxProfileError(FdxError):
    """XML does not match the Movie Muse FDX profile."""


class FdxParseError(FdxError):
    """FDX XML could not be parsed."""


class SilentLossError(FdxError):
    """A conversion would drop data without a LossReport disclosure."""


class FountainParseError(FdxError):
    """Fountain/plain-text input could not be interpreted as a screenplay."""


class PdfImportUnavailableError(FdxError):
    """PDF import is an explicitly lossy, not-yet-available pathway."""


class FinalDraftUnavailableError(FdxError):
    """Final Draft is not installed or MOVIE_MUSE_FINAL_DRAFT_BIN is unset.

    EXT-FDX-FINAL-DRAFT stays NOT_RUN. This is fail-closed, not a skip.
    """
