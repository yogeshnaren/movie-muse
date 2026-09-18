"""Declared high-severity recall and measured false-positive budget."""

from __future__ import annotations

from movie_muse.authorization.api import Mode
from movie_muse.continuity.api import DECLARED_THRESHOLDS, Materiality
from movie_muse.schemas.api import EpistemicLevel, FilmIrEntityKind, new_id
from movie_muse.state_engine.api import Polarity, StateDimension, StateTransition


def _ada_and_scenes(film_ir):
    ada = next(
        entity
        for entity in film_ir.entities
        if entity.kind is FilmIrEntityKind.CHARACTER and entity.canonical_name == "ADA"
    )
    kitchen, harbor = film_ir.scene_order
    return ada, kitchen, harbor


def _film_ir(stack):
    return stack.film_ir_service.project(
        stack.document,
        principal=stack.principal,
        acl_epoch=stack.epoch,
    )


def _same_scene_conflict(
    subject_id: str,
    scene_id: str,
    dimension: StateDimension,
    attribute: str,
    left: str,
    right: str,
) -> tuple[StateTransition, ...]:
    return (
        StateTransition(
            subject_id=subject_id,
            subject_name="ADA",
            dimension=dimension,
            attribute=attribute,
            value=left,
            polarity=Polarity.KNOWS,
            scene_id=scene_id,
            source_kind=EpistemicLevel.INFERRED,
            source_id=new_id("inferred_claim"),
            evidence_ids=(new_id("evidence_bundle"),),
        ),
        StateTransition(
            subject_id=subject_id,
            subject_name="ADA",
            dimension=dimension,
            attribute=attribute,
            value=right,
            polarity=Polarity.DENIED,
            scene_id=scene_id,
            source_kind=EpistemicLevel.AUTHORED,
            source_id=new_id("authored_fact"),
            evidence_ids=(new_id("block"),),
        ),
    )


def test_high_severity_recall_meets_declared_threshold(continuity_stack) -> None:
    film_ir = _film_ir(continuity_stack)
    ada, kitchen, _harbor = _ada_and_scenes(film_ir)
    expected = {StateDimension.POSSESSION, StateDimension.KNOWLEDGE, StateDimension.SECRET}
    extras = (
        *_same_scene_conflict(ada.id, kitchen, StateDimension.POSSESSION, "key", "brass_key", "none"),
        *_same_scene_conflict(ada.id, kitchen, StateDimension.KNOWLEDGE, "lock_open", "true", "false"),
        *_same_scene_conflict(ada.id, kitchen, StateDimension.SECRET, "letter", "hidden", "none"),
    )
    report = continuity_stack.continuity.analyze(
        film_ir,
        continuity_stack.document,
        principal=continuity_stack.principal,
        acl_epoch=continuity_stack.epoch,
        extra_transitions=extras,
        mode=(Mode.WRITER,),
    )
    caught = {item.dimension for item in report.findings if item.materiality is Materiality.HIGH}
    recall = len(expected & caught) / len(expected)
    assert recall >= DECLARED_THRESHOLDS["high_severity_recall"]


def test_false_positive_budget_on_clean_temporal_corpus(continuity_stack) -> None:
    film_ir = _film_ir(continuity_stack)
    ada, kitchen, harbor = _ada_and_scenes(film_ir)
    extras = (
        StateTransition(
            subject_id=ada.id,
            subject_name="ADA",
            dimension=StateDimension.POSSESSION,
            attribute="key",
            value="brass_key",
            polarity=Polarity.CONFIRMED,
            scene_id=kitchen,
            source_kind=EpistemicLevel.AUTHORED,
            source_id=new_id("authored_fact"),
            evidence_ids=(new_id("block"),),
        ),
        StateTransition(
            subject_id=ada.id,
            subject_name="ADA",
            dimension=StateDimension.POSSESSION,
            attribute="key",
            value="none",
            polarity=Polarity.CONFIRMED,
            scene_id=harbor,
            source_kind=EpistemicLevel.AUTHORED,
            source_id=new_id("authored_fact"),
            evidence_ids=(new_id("block"),),
        ),
    )
    report = continuity_stack.continuity.analyze(
        film_ir,
        continuity_stack.document,
        principal=continuity_stack.principal,
        acl_epoch=continuity_stack.epoch,
        extra_transitions=extras,
        mode=(Mode.WRITER,),
    )
    high = [item for item in report.findings if item.materiality is Materiality.HIGH]
    rate = 0.0 if not high else 1.0
    assert rate <= DECLARED_THRESHOLDS["false_positive_rate"]


def test_analyze_is_deterministic(continuity_stack) -> None:
    film_ir = _film_ir(continuity_stack)
    ada, kitchen, _harbor = _ada_and_scenes(film_ir)
    extras = _same_scene_conflict(
        ada.id, kitchen, StateDimension.POSSESSION, "key", "brass_key", "none"
    )
    first = continuity_stack.continuity.analyze(
        film_ir,
        continuity_stack.document,
        principal=continuity_stack.principal,
        acl_epoch=continuity_stack.epoch,
        extra_transitions=extras,
    )
    second = continuity_stack.continuity.analyze(
        film_ir,
        continuity_stack.document,
        principal=continuity_stack.principal,
        acl_epoch=continuity_stack.epoch,
        extra_transitions=extras,
    )
    left = [item.to_dict() for item in first.findings]
    right = [item.to_dict() for item in second.findings]
    agreement = 1.0 if left == right else 0.0
    assert agreement >= DECLARED_THRESHOLDS["determinism"]
