"""Precision/recall of FilmIR entities against compiler ground truth."""

from __future__ import annotations

from dataclasses import dataclass

from movie_muse.compiler.api import CompiledScreenplay
from movie_muse.schemas.api import FilmIR


@dataclass(frozen=True, slots=True)
class ExtractionScores:
    precision: float
    recall: float
    true_positives: int
    false_positives: int
    false_negatives: int

    def meets(self, *, min_precision: float, min_recall: float) -> bool:
        return self.precision >= min_precision and self.recall >= min_recall


def _keys(names_and_kinds: list[tuple[str, str]]) -> set[tuple[str, str]]:
    return {(kind, name.casefold()) for kind, name in names_and_kinds}


def score_against_compiler(film_ir: FilmIR, compiled: CompiledScreenplay) -> ExtractionScores:
    predicted = _keys([(entity.kind.value, entity.canonical_name) for entity in film_ir.entities])
    truth = _keys([(entity.kind, entity.canonical_name) for entity in compiled.entities])
    tp = len(predicted & truth)
    fp = len(predicted - truth)
    fn = len(truth - predicted)
    precision = 1.0 if not predicted else tp / len(predicted)
    recall = 1.0 if not truth else tp / len(truth)
    return ExtractionScores(
        precision=precision,
        recall=recall,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
    )
