"""Public surface of ``movie_muse.rights``.

Other modules must import this surface rather than rights internals.
"""

from __future__ import annotations

from movie_muse.rights.errors import (
    HumanValidationError,
    PermittedUseDeniedError,
    RightsError,
    SourceImmutableError,
    SourceNotFoundError,
    UnlicensedSourceError,
)
from movie_muse.rights.service import RightsService
from movie_muse.rights.types import (
    PermittedUse,
    PermittedUseDecision,
    SourceClassification,
    SourceDisclosure,
    SourceOrigin,
    SourceValidationState,
    SourceVersion,
    classification_basis,
    parse_classification,
    parse_permitted_use,
)
from movie_muse.schemas.api import RightsBasis, RightsRecord

__all__ = [
    "HumanValidationError",
    "PermittedUse",
    "PermittedUseDecision",
    "PermittedUseDeniedError",
    "RightsBasis",
    "RightsError",
    "RightsRecord",
    "RightsService",
    "SourceClassification",
    "SourceDisclosure",
    "SourceImmutableError",
    "SourceNotFoundError",
    "SourceOrigin",
    "SourceValidationState",
    "SourceVersion",
    "UnlicensedSourceError",
    "classification_basis",
    "parse_classification",
    "parse_permitted_use",
]
