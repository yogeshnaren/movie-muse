"""Public surface of ``movie_muse.project_memory``.

Hosts and other modules must import this module, never sibling internals.
Candidates never become ProjectMemory without explicit human review.
"""

from __future__ import annotations

from movie_muse.project_memory.errors import (
    AutoPromoteError,
    CandidateClosedError,
    CandidateNotFoundError,
    DuplicateCandidateError,
    HumanRequiredError,
    ProjectMemoryError,
    UnpromotableKindError,
)
from movie_muse.project_memory.service import ProjectMemoryService
from movie_muse.project_memory.types import (
    PROMOTABLE_KINDS,
    MemoryCandidate,
    MemoryCandidateKind,
    MemoryStatus,
    ProvenanceEntry,
)
from movie_muse.schemas.api import ProjectMemory, ProjectMemoryKind

__all__ = [
    "PROMOTABLE_KINDS",
    "AutoPromoteError",
    "CandidateClosedError",
    "CandidateNotFoundError",
    "DuplicateCandidateError",
    "HumanRequiredError",
    "MemoryCandidate",
    "MemoryCandidateKind",
    "MemoryStatus",
    "ProjectMemory",
    "ProjectMemoryError",
    "ProjectMemoryKind",
    "ProjectMemoryService",
    "ProvenanceEntry",
    "UnpromotableKindError",
]
