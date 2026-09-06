"""Regression corpus: every declared dimension reduces and queries deterministically."""

from __future__ import annotations

import pytest

from movie_muse.schemas.api import EpistemicLevel, FilmIrEntityKind, new_id
from movie_muse.state_engine.api import (
    DECLARED_THRESHOLDS,
    Polarity,
    StateDimension,
    StateTransition,
    UnknownSceneError,
)


def test_every_declared_dimension_is_queryable(state_stack) -> None:
    film_ir = state_stack.film_ir_service.project(
        state_stack.document,
        principal=state_stack.principal,
        acl_epoch=state_stack.epoch,
    )
    ada = next(
        entity
        for entity in film_ir.entities
        if entity.kind is FilmIrEntityKind.CHARACTER and entity.canonical_name == "ADA"
    )
    kitchen = film_ir.scene_order[0]
    extras = tuple(
        StateTransition(
            subject_id=ada.id,
            subject_name="ADA",
            dimension=dimension,
            attribute=dimension.value,
            value=f"{dimension.value}_value",
            polarity=Polarity.CONFIRMED,
            scene_id=kitchen,
            source_kind=EpistemicLevel.AUTHORED,
            source_id=new_id("authored_fact"),
            evidence_ids=(new_id("block"),),
        )
        for dimension in StateDimension
        if dimension not in {StateDimension.LOCATION, StateDimension.WORLD}
    )
    first = state_stack.engine.reduce(
        film_ir,
        state_stack.document,
        principal=state_stack.principal,
        acl_epoch=state_stack.epoch,
        extra_transitions=extras,
    )
    second = state_stack.engine.reduce(
        film_ir,
        state_stack.document,
        principal=state_stack.principal,
        acl_epoch=state_stack.epoch,
        extra_transitions=extras,
    )
    assert first.to_dict() == second.to_dict()
    seen = {fact.dimension for fact in first.facts}
    for dimension in StateDimension:
        snapshot = state_stack.engine.query(
            film_ir,
            first,
            scene_id=kitchen,
            subject_id=ada.id if dimension is not StateDimension.WORLD else film_ir.id,
            dimension=dimension,
        )
        assert snapshot.facts, f"missing {dimension.value}"
        seen.add(dimension)
    assert seen == set(StateDimension)
    assert 1.0 >= DECLARED_THRESHOLDS["determinism"]


def test_unknown_scene_is_fail_closed(state_stack) -> None:
    film_ir = state_stack.film_ir_service.project(
        state_stack.document,
        principal=state_stack.principal,
        acl_epoch=state_stack.epoch,
    )
    reduction = state_stack.engine.reduce(
        film_ir,
        state_stack.document,
        principal=state_stack.principal,
        acl_epoch=state_stack.epoch,
    )
    with pytest.raises(UnknownSceneError):
        state_stack.engine.query(film_ir, reduction, scene_id=new_id("scene"))
