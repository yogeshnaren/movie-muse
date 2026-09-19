"""Public surface of ``movie_muse.director``.

Hosts and other modules must import this module, never sibling internals.
DirectorVisionGraph is provider-independent. Diagrammatic mode does not
require generation.
"""

from __future__ import annotations

from movie_muse.director.errors import (
    AnnotationNotFoundError,
    ConstraintNotFoundError,
    CoverageNotFoundError,
    DirectorError,
    GenerationRequiredError,
    LockedGeometryError,
    SceneSpaceNotFoundError,
)
from movie_muse.director.service import DirectorVisionService
from movie_muse.director.types import (
    AnnotationRole,
    CoverageBeat,
    CoveragePurpose,
    DirectorVisionGraph,
    ProducerConstraint,
    RoleAnnotation,
    SceneSpaceRecord,
    SemanticAnchor,
)
from movie_muse.schemas.api import SceneSpace, SubjectPosition

__all__ = [
    "AnnotationNotFoundError",
    "AnnotationRole",
    "ConstraintNotFoundError",
    "CoverageBeat",
    "CoverageNotFoundError",
    "CoveragePurpose",
    "DirectorError",
    "DirectorVisionGraph",
    "DirectorVisionService",
    "GenerationRequiredError",
    "LockedGeometryError",
    "ProducerConstraint",
    "RoleAnnotation",
    "SceneSpace",
    "SceneSpaceNotFoundError",
    "SceneSpaceRecord",
    "SemanticAnchor",
    "SubjectPosition",
]
