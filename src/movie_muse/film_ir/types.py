"""Candidate extraction records. Inferred claims never become FilmIR entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from movie_muse.schemas.api import FilmIR, InferredClaim


@dataclass(frozen=True, slots=True)
class CandidateSet:
    film_ir_id: str
    source_revision_id: str
    model_id: str
    claims: tuple[InferredClaim, ...]
    raw_entities: tuple[dict[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "film_ir_id": self.film_ir_id,
            "source_revision_id": self.source_revision_id,
            "model_id": self.model_id,
            "claims": [claim.to_dict() for claim in self.claims],
            "raw_entities": [dict(row) for row in self.raw_entities],
        }


@dataclass(frozen=True, slots=True)
class FilmIrProjection:
    film_ir: FilmIR
    candidates: CandidateSet | None = None
