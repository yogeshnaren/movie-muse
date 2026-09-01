"""mypy fixture: passing the correct epistemic type must type-check cleanly."""

from __future__ import annotations

from movie_muse.schemas.epistemic import AuthoredFact


def take_authored_fact(fact: AuthoredFact) -> str:
    return fact.attribute


take_authored_fact(
    AuthoredFact(
        id="fca_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        subject_id="char-ada",
        attribute="occupation",
        value="locksmith",
        source_revision_id="rev_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        author_actor_id="act_01ARZ3NDEKTSV4RRFFQ69G5FAV",
    )
)
