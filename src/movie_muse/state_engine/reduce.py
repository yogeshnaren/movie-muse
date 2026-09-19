"""Deterministic interval reduction over FilmIR scene order."""

from __future__ import annotations

import hashlib
from dataclasses import replace

from movie_muse.schemas.api import EpistemicLevel, FilmIR, new_ulid
from movie_muse.state_engine.types import (
    AUTHORITY_RANK,
    INCOMPATIBLE_POLARITIES,
    Contradiction,
    Polarity,
    Reduction,
    StateDimension,
    StateFact,
    StateTransition,
)


def _scene_index(film_ir: FilmIR) -> dict[str, int]:
    return {scene_id: index for index, scene_id in enumerate(film_ir.scene_order)}


def _covers(fact: StateFact, scene_id: str, order: dict[str, int]) -> bool:
    start = order[fact.valid_from_scene_id]
    here = order[scene_id]
    if here < start:
        return False
    if fact.valid_until_scene_id is None:
        return True
    return here < order[fact.valid_until_scene_id]


def _polarity_conflict(left: Polarity, right: Polarity) -> bool:
    return (left, right) in INCOMPATIBLE_POLARITIES


def _should_contradict(current: StateFact, transition: StateTransition) -> bool:
    """Temporal succession is not a contradiction.

    A later scene may change location, possession, or knowledge without
    recording a conflict. Contradictions are reserved for (a) a lower-authority
    claim that cannot override an open fact, (b) two claims that start on the
    same scene and disagree, or (c) an incompatible polarity pair.
    """

    if current.value == transition.value and current.polarity == transition.polarity:
        return False
    incoming_rank = AUTHORITY_RANK[transition.source_kind]
    current_rank = AUTHORITY_RANK[current.source_kind]
    if incoming_rank > current_rank:
        return True
    same_scene = current.valid_from_scene_id == transition.scene_id
    if same_scene and (
        current.value != transition.value
        or _polarity_conflict(current.polarity, transition.polarity)
    ):
        return True
    return _polarity_conflict(current.polarity, transition.polarity)


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).digest()[:10]
    return f"{prefix}_{new_ulid(_time_ms=0, _random_bytes=digest)}"


def _fact_id(*parts: str) -> str:
    return _stable_id("stf", *parts)


def _contradiction_id(*parts: str) -> str:
    return _stable_id("stc", *parts)


def reduce_transitions(
    film_ir: FilmIR,
    transitions: tuple[StateTransition, ...],
) -> Reduction:
    order = _scene_index(film_ir)
    ranked = sorted(
        transitions,
        key=lambda item: (
            order.get(item.scene_id, 10**9),
            AUTHORITY_RANK[item.source_kind],
            item.dimension.value,
            item.attribute,
            item.subject_id,
            item.source_id,
        ),
    )
    open_facts: dict[tuple[str, str, str, str], StateFact] = {}
    closed: list[StateFact] = []
    contradictions: list[Contradiction] = []

    for transition in ranked:
        if transition.scene_id not in order:
            continue
        key = transition.key()
        current = open_facts.get(key)
        if current is None:
            open_facts[key] = StateFact(
                id=_fact_id(
                    transition.subject_id,
                    transition.dimension.value,
                    transition.attribute,
                    transition.scene_id,
                    transition.source_id,
                ),
                subject_id=transition.subject_id,
                subject_name=transition.subject_name,
                dimension=transition.dimension,
                attribute=transition.attribute,
                value=transition.value,
                polarity=transition.polarity,
                valid_from_scene_id=transition.scene_id,
                source_kind=transition.source_kind,
                source_id=transition.source_id,
                evidence_ids=transition.evidence_ids,
                revision_id=film_ir.source_revision_id,
                about_subject_id=transition.about_subject_id,
            )
            continue
        same = current.value == transition.value and current.polarity == transition.polarity
        if same:
            continue
        current_rank = AUTHORITY_RANK[current.source_kind]
        incoming_rank = AUTHORITY_RANK[transition.source_kind]
        if _should_contradict(current, transition):
            incoming = StateFact(
                id=_fact_id(
                    "incoming",
                    transition.subject_id,
                    transition.dimension.value,
                    transition.attribute,
                    transition.scene_id,
                    transition.source_id,
                ),
                subject_id=transition.subject_id,
                subject_name=transition.subject_name,
                dimension=transition.dimension,
                attribute=transition.attribute,
                value=transition.value,
                polarity=transition.polarity,
                valid_from_scene_id=transition.scene_id,
                source_kind=transition.source_kind,
                source_id=transition.source_id,
                evidence_ids=transition.evidence_ids,
                revision_id=film_ir.source_revision_id,
                about_subject_id=transition.about_subject_id,
            )
            contradictions.append(
                Contradiction(
                    id=_contradiction_id(
                        current.id, transition.source_id, transition.scene_id
                    ),
                    scene_id=transition.scene_id,
                    subject_id=transition.subject_id,
                    dimension=transition.dimension,
                    attribute=transition.attribute,
                    left_fact_id=current.id,
                    right_fact_id=incoming.id,
                    evidence_ids=tuple(
                        dict.fromkeys((*current.evidence_ids, *transition.evidence_ids))
                    ),
                    reason=(
                        f"{current.source_kind.value}:{current.value}/{current.polarity.value} "
                        f"vs {transition.source_kind.value}:{transition.value}/{transition.polarity.value}"
                    ),
                )
            )
            if incoming_rank < current_rank:
                closed.append(replace(current, valid_until_scene_id=transition.scene_id))
                open_facts[key] = incoming
            elif incoming_rank == current_rank:
                closed.append(replace(current, valid_until_scene_id=transition.scene_id))
                open_facts[key] = incoming
            else:
                closed.append(
                    replace(incoming, valid_until_scene_id=transition.scene_id)
                )
            continue
        closed.append(replace(current, valid_until_scene_id=transition.scene_id))
        open_facts[key] = StateFact(
            id=_fact_id(
                "next",
                transition.subject_id,
                transition.dimension.value,
                transition.attribute,
                transition.scene_id,
                transition.source_id,
            ),
            subject_id=transition.subject_id,
            subject_name=transition.subject_name,
            dimension=transition.dimension,
            attribute=transition.attribute,
            value=transition.value,
            polarity=transition.polarity,
            valid_from_scene_id=transition.scene_id,
            source_kind=transition.source_kind,
            source_id=transition.source_id,
            evidence_ids=transition.evidence_ids,
            revision_id=film_ir.source_revision_id,
            about_subject_id=transition.about_subject_id,
        )

    facts = tuple(
        sorted(
            (*closed, *open_facts.values()),
            key=lambda item: (item.key(), item.valid_from_scene_id, item.id),
        )
    )
    misunderstandings = _derive_misunderstandings(facts, order, film_ir.source_revision_id)
    return Reduction(
        revision_id=film_ir.source_revision_id,
        facts=facts,
        contradictions=tuple(sorted(contradictions, key=lambda item: item.id)),
        misunderstandings=misunderstandings,
    )


def facts_at_scene(
    facts: tuple[StateFact, ...],
    scene_id: str,
    film_ir: FilmIR,
) -> tuple[StateFact, ...]:
    order = _scene_index(film_ir)
    if scene_id not in order:
        return ()
    covering = [fact for fact in facts if _covers(fact, scene_id, order)]
    return tuple(sorted(covering, key=lambda item: (item.key(), item.id)))


def _derive_misunderstandings(
    facts: tuple[StateFact, ...],
    order: dict[str, int],
    revision_id: str,
) -> tuple[StateFact, ...]:
    derived: list[StateFact] = []
    second = [
        fact
        for fact in facts
        if fact.dimension is StateDimension.SECOND_ORDER_BELIEF
        and fact.about_subject_id
        and fact.polarity in {Polarity.BELIEVES, Polarity.KNOWS, Polarity.CONFIRMED}
    ]
    knowledge = [
        fact
        for fact in facts
        if fact.dimension is StateDimension.KNOWLEDGE
    ]
    for belief in second:
        about = next(
            (
                fact
                for fact in knowledge
                if fact.subject_id == belief.about_subject_id
                and fact.attribute == belief.attribute
                and _overlaps(belief, fact, order)
            ),
            None,
        )
        if about is None or about.polarity in {Polarity.DENIED, Polarity.UNKNOWN}:
            derived.append(
                StateFact(
                    id=_fact_id("mis", belief.id),
                    subject_id=belief.subject_id,
                    subject_name=belief.subject_name,
                    dimension=StateDimension.MISUNDERSTANDING,
                    attribute=belief.attribute,
                    value=belief.value,
                    polarity=Polarity.CONFIRMED,
                    valid_from_scene_id=belief.valid_from_scene_id,
                    valid_until_scene_id=belief.valid_until_scene_id,
                    source_kind=EpistemicLevel.STRUCTURAL,
                    source_id=belief.id,
                    evidence_ids=(*belief.evidence_ids, *(about.evidence_ids if about else ())),
                    revision_id=revision_id,
                    about_subject_id=belief.about_subject_id,
                )
            )
    return tuple(sorted(derived, key=lambda item: item.id))


def _overlaps(left: StateFact, right: StateFact, order: dict[str, int]) -> bool:
    start = max(order[left.valid_from_scene_id], order[right.valid_from_scene_id])
    left_end = order.get(left.valid_until_scene_id or "", 10**9)
    right_end = order.get(right.valid_until_scene_id or "", 10**9)
    if left.valid_until_scene_id is None:
        left_end = 10**9
    if right.valid_until_scene_id is None:
        right_end = 10**9
    return start < min(left_end, right_end)
