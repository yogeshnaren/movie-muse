"""mypy fixture: passing a StructuralFact where AuthoredFact is required MUST fail.

This is the static half of "authored, structural, inferred, operational, and
scenario epistemic types are distinct types and cannot be silently
promoted/interchanged" (MM-002 acceptance criterion 2). mypy must reject this
file; see ``tests/schemas/test_typecheck_fixtures.py``.
"""

from __future__ import annotations

from movie_muse.schemas.epistemic import AuthoredFact, StructuralFact


def take_authored_fact(fact: AuthoredFact) -> str:
    return fact.attribute


structural = StructuralFact(
    id="fcs_01ARZ3NDEKTSV4RRFFQ69G5FAV",
    subject_id="char-ada",
    attribute="scene_count",
    value=12,
    derived_from_revision_id="rev_01ARZ3NDEKTSV4RRFFQ69G5FAV",
    extractor_version="1.0.0",
)

# This is exactly the "silent promotion" the domain model forbids: a
# structural (deterministically derived) fact used where an authored
# (creator-authored) fact is required. It must be a type error.
take_authored_fact(structural)
