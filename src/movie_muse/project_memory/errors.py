"""Typed failures for project memory."""

from __future__ import annotations


class ProjectMemoryError(RuntimeError):
    """Base class for project-memory failures."""


class CandidateNotFoundError(ProjectMemoryError):
    """A named candidate is not in the index."""


class CandidateClosedError(ProjectMemoryError):
    """The candidate is already rejected or promoted."""


class UnpromotableKindError(ProjectMemoryError):
    """This candidate kind cannot become a schema ProjectMemory record."""


class DuplicateCandidateError(ProjectMemoryError):
    """An open candidate with the same kind, summary, and branch already exists."""


class HumanRequiredError(ProjectMemoryError):
    """Promotion and rejection are human review acts."""


class AutoPromoteError(ProjectMemoryError):
    """Candidate memory cannot become canon automatically."""
