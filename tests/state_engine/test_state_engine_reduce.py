"""Deterministic reduction, temporal queries, and declared thresholds."""

from __future__ import annotations

from movie_muse.schemas.api import EpistemicLevel, FilmIrEntityKind, new_id
from movie_muse.state_engine.api import (
    DECLARED_THRESHOLDS,
    Polarity,
    StateDimension,
    StateTransition,
)


def _ada_and_scenes(film_ir):
    ada = next(
        entity
        for entity in film_ir.entities
        if entity.kind is FilmIrEntityKind.CHARACTER and entity.canonical_name == "ADA"
    )
    kitchen, harbor = film_ir.scene_order
    return ada, kitchen, harbor


def test_location_moves_across_scenes_deterministically(state_stack) -> None:
    film_ir = state_stack.film_ir_service.project(
        state_stack.document,
        principal=state_stack.principal,
        acl_epoch=state_stack.epoch,
    )
    first = state_stack.engine.reduce(
        film_ir,
        state_stack.document,
        principal=state_stack.principal,
        acl_epoch=state_stack.epoch,
    )
    second = state_stack.engine.reduce(
        film_ir,
        state_stack.document,
        principal=state_stack.principal,
        acl_epoch=state_stack.epoch,
    )
    assert first.to_dict() == second.to_dict()
    assert not any(
        item.dimension in {StateDimension.LOCATION, StateDimension.WORLD}
        for item in first.contradictions
    )
    ada, kitchen, harbor = _ada_and_scenes(film_ir)
    at_kitchen = state_stack.engine.query(
        film_ir, first, scene_id=kitchen, subject_id=ada.id, dimension=StateDimension.LOCATION
    )
    at_harbor = state_stack.engine.query(
        film_ir, first, scene_id=harbor, subject_id=ada.id, dimension=StateDimension.LOCATION
    )
    assert [fact.value for fact in at_kitchen.facts] == ["KITCHEN"]
    assert [fact.value for fact in at_harbor.facts] == ["HARBOR"]
    agreement = 1.0 if first.to_dict() == second.to_dict() else 0.0
    assert agreement >= DECLARED_THRESHOLDS["determinism"]
    assert agreement >= DECLARED_THRESHOLDS["temporal_query_agreement"]


def test_contradiction_points_to_evidence(state_stack) -> None:
    film_ir = state_stack.film_ir_service.project(
        state_stack.document,
        principal=state_stack.principal,
        acl_epoch=state_stack.epoch,
    )
    ada, kitchen, _harbor = _ada_and_scenes(film_ir)
    extras = (
        StateTransition(
            subject_id=ada.id,
            subject_name="ADA",
            dimension=StateDimension.POSSESSION,
            attribute="key",
            value="brass_key",
            polarity=Polarity.KNOWS,
            scene_id=kitchen,
            source_kind=EpistemicLevel.INFERRED,
            source_id=new_id("inferred_claim"),
            evidence_ids=(new_id("evidence_bundle"),),
        ),
        StateTransition(
            subject_id=ada.id,
            subject_name="ADA",
            dimension=StateDimension.POSSESSION,
            attribute="key",
            value="none",
            polarity=Polarity.DENIED,
            scene_id=kitchen,
            source_kind=EpistemicLevel.AUTHORED,
            source_id=new_id("authored_fact"),
            evidence_ids=(new_id("block"),),
        ),
    )
    reduction = state_stack.engine.reduce(
        film_ir,
        state_stack.document,
        principal=state_stack.principal,
        acl_epoch=state_stack.epoch,
        extra_transitions=extras,
    )
    assert reduction.contradictions
    contradiction = next(
        item
        for item in reduction.contradictions
        if item.subject_id == ada.id and item.dimension is StateDimension.POSSESSION
    )
    assert contradiction.evidence_ids
    assert contradiction.subject_id == ada.id
    snapshot = state_stack.engine.query(
        film_ir,
        reduction,
        scene_id=kitchen,
        subject_id=ada.id,
        dimension=StateDimension.POSSESSION,
    )
    covering = [fact for fact in snapshot.facts if fact.valid_until_scene_id is None]
    assert covering
    assert covering[0].value == "none"
    assert covering[0].source_kind is EpistemicLevel.AUTHORED
    rate = 1.0 if contradiction.evidence_ids else 0.0
    assert rate >= DECLARED_THRESHOLDS["contradiction_with_evidence"]


def test_second_order_belief_and_misunderstanding(state_stack) -> None:
    film_ir = state_stack.film_ir_service.project(
        state_stack.document,
        principal=state_stack.principal,
        acl_epoch=state_stack.epoch,
    )
    ada, _kitchen, harbor = _ada_and_scenes(film_ir)
    ben_id = new_id("film_ir")
    extras = (
        StateTransition(
            subject_id=ada.id,
            subject_name="ADA",
            dimension=StateDimension.KNOWLEDGE,
            attribute="lock_open",
            value="false",
            polarity=Polarity.DENIED,
            scene_id=harbor,
            source_kind=EpistemicLevel.AUTHORED,
            source_id=new_id("authored_fact"),
            evidence_ids=(new_id("block"),),
        ),
        StateTransition(
            subject_id=ben_id,
            subject_name="BEN",
            dimension=StateDimension.SECOND_ORDER_BELIEF,
            attribute="lock_open",
            value="true",
            polarity=Polarity.BELIEVES,
            scene_id=harbor,
            source_kind=EpistemicLevel.AUTHORED,
            source_id=new_id("authored_fact"),
            evidence_ids=(new_id("block"),),
            about_subject_id=ada.id,
        ),
    )
    reduction = state_stack.engine.reduce(
        film_ir,
        state_stack.document,
        principal=state_stack.principal,
        acl_epoch=state_stack.epoch,
        extra_transitions=extras,
    )
    beliefs = state_stack.engine.query_second_order(
        film_ir,
        reduction,
        scene_id=harbor,
        subject_id=ben_id,
        about_subject_id=ada.id,
    )
    assert beliefs
    assert beliefs[0].value == "true"
    assert reduction.misunderstandings
    recovered = 1.0 if beliefs and reduction.misunderstandings else 0.0
    assert recovered >= DECLARED_THRESHOLDS["second_order_belief_recovery"]
