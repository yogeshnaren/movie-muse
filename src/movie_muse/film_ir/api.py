"""Public surface of ``movie_muse.film_ir``.

Hosts and other modules must import this module, never sibling internals.
Every AI extraction call is owned by ModelRouter. FilmIR entities are
structural facts from the compiler, never inferred promotions.
"""

from __future__ import annotations

from movie_muse.film_ir.errors import (
    AuthoredPromotionError,
    ExtractionRepairError,
    FilmIrError,
    FilmIrNotFoundError,
)
from movie_muse.film_ir.ids import EXTRACTOR_VERSION
from movie_muse.film_ir.metrics import ExtractionScores, score_against_compiler
from movie_muse.film_ir.repair import repair_extraction_output
from movie_muse.film_ir.service import FilmIrService
from movie_muse.film_ir.types import CandidateSet, FilmIrProjection
from movie_muse.schemas.api import FilmIR, FilmIrEntity, FilmIrEntityKind

__all__ = [
    "EXTRACTOR_VERSION",
    "AuthoredPromotionError",
    "CandidateSet",
    "ExtractionRepairError",
    "ExtractionScores",
    "FilmIR",
    "FilmIrEntity",
    "FilmIrEntityKind",
    "FilmIrError",
    "FilmIrNotFoundError",
    "FilmIrProjection",
    "FilmIrService",
    "repair_extraction_output",
    "score_against_compiler",
]
