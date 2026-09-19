"""Typed failures for Director Mode."""

from __future__ import annotations


class DirectorError(RuntimeError):
    """Base class for Director Mode failures."""


class SceneSpaceNotFoundError(DirectorError):
    """The named SceneSpace is not in the vision graph."""


class AnnotationNotFoundError(DirectorError):
    """The named annotation is not in the vision graph."""


class CoverageNotFoundError(DirectorError):
    """The named coverage beat is not in the vision graph."""


class ConstraintNotFoundError(DirectorError):
    """The named producer constraint is not in the vision graph."""


class LockedGeometryError(DirectorError):
    """A locked SceneSpace attribute cannot change without unlock."""


class GenerationRequiredError(DirectorError):
    """Diagrammatic shot-card mode does not require generation."""
