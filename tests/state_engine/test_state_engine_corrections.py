"""Human corrections persist as higher-authority claims."""

from __future__ import annotations

from movie_muse.schemas.api import EpistemicLevel, FilmIrEntityKind, InferredClaim, new_id
from movie_muse.state_engine.api import (
    DECLARED_THRESHOLDS,
    Polarity,
    StateDimension,
    StateTransition,
)


def test_human_correction_overrides_inferred_and_persists(state_stack) -> None:
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
    inferred = InferredClaim(
        id=new_id("inferred_claim"),
        subject_id=ada.id,
        attribute="secret",
        value="pantry_code",
        confidence=0.4,
        evidence_bundle_id=new_id("evidence_bundle"),
        model_id="not-called-by-reducer",
    )
    first = state_stack.engine.reduce(
        film_ir,
        state_stack.document,
        principal=state_stack.principal,
        acl_epoch=state_stack.epoch,
        inferred_claims=(inferred,),
        inferred_scene_id=kitchen,
        inferred_subject_id=ada.id,
    )
    inferred_snap = state_stack.engine.query(
        film_ir,
        first,
        scene_id=kitchen,
        subject_id=ada.id,
        dimension=StateDimension.KNOWLEDGE,
    )
    assert any(fact.value == "pantry_code" for fact in inferred_snap.facts)
    state_stack.engine.correct(
        StateTransition(
            subject_id=ada.id,
            subject_name="ADA",
            dimension=StateDimension.KNOWLEDGE,
            attribute="secret",
            value="none",
            polarity=Polarity.DENIED,
            scene_id=kitchen,
            source_kind=EpistemicLevel.INFERRED,
            source_id=new_id("authored_fact"),
            evidence_ids=(new_id("note"),),
        ),
        principal=state_stack.principal,
        acl_epoch=state_stack.epoch,
        project_id=state_stack.project.id,
    )
    assert state_stack.engine.list_corrections()
    rerun = state_stack.engine.reduce(
        film_ir,
        state_stack.document,
        principal=state_stack.principal,
        acl_epoch=state_stack.epoch,
        inferred_claims=(inferred,),
        inferred_scene_id=kitchen,
        inferred_subject_id=ada.id,
    )
    corrected = state_stack.engine.query(
        film_ir,
        rerun,
        scene_id=kitchen,
        subject_id=ada.id,
        dimension=StateDimension.KNOWLEDGE,
    )
    covering = [fact for fact in corrected.facts if fact.attribute == "secret"]
    assert covering
    assert covering[0].value == "none"
    assert covering[0].source_kind is EpistemicLevel.AUTHORED
    score = 1.0 if covering[0].value == "none" else 0.0
    assert score >= DECLARED_THRESHOLDS["correction_overrides_inferred"]
