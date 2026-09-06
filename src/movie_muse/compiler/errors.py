"""Typed failures for the deterministic compiler."""

from __future__ import annotations


class CompilerError(RuntimeError):
    """Base class for compiler failures."""


class CompileValidationError(CompilerError):
    """The document failed kernel validation before compile."""
