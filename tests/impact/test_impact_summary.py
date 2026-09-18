"""Impact summaries split semantic, continuity, and production consequences."""

from __future__ import annotations

from movie_muse.authorization.api import Mode
from movie_muse.schemas.api import EpistemicLevel, FilmIrEntityKind, ImpactSummary, new_id
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


def _conflict(
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


def test_writer_summary_foregrounds_creative_continuity(impact_stack) -> None:
    film_ir = _film_ir(impact_stack)
    ada, kitchen, _harbor = _ada_and_scenes(film_ir)
    extras = (
        *_conflict(ada.id, kitchen, StateDimension.KNOWLEDGE, "lock_open", "true", "false"),
        *_conflict(ada.id, kitchen, StateDimension.LOCATION, "place", "KITCHEN", "HARBOR"),
    )
    report = impact_stack.continuity.analyze(
        film_ir,
        impact_stack.document,
        principal=impact_stack.principal,
        acl_epoch=impact_stack.epoch,
        extra_transitions=extras,
        mode=(Mode.WRITER,),
    )
    summary = impact_stack.impact.summarize(
        report,
        principal=impact_stack.principal,
        acl_epoch=impact_stack.epoch,
    )
    assert isinstance(summary, ImpactSummary)
    assert summary.semantic
    assert summary.continuity
    assert summary.production == ()
    operations = [record.operation for record in impact_stack.audit.list_records()]
    assert "impact.summarize" in operations


def test_producer_summary_includes_logistics_consequences(impact_stack) -> None:
    film_ir = _film_ir(impact_stack)
    ada, kitchen, _harbor = _ada_and_scenes(film_ir)
    extras = (
        *_conflict(ada.id, kitchen, StateDimension.KNOWLEDGE, "lock_open", "true", "false"),
        *_conflict(ada.id, kitchen, StateDimension.LOCATION, "place", "KITCHEN", "HARBOR"),
    )
    report = impact_stack.continuity.analyze(
        film_ir,
        impact_stack.document,
        principal=impact_stack.principal,
        acl_epoch=impact_stack.epoch,
        extra_transitions=extras,
        mode=(Mode.PRODUCER,),
    )
    summary = impact_stack.impact.summarize(
        report,
        principal=impact_stack.principal,
        acl_epoch=impact_stack.epoch,
    )
    assert summary.continuity
    assert any("location" in line for line in summary.production)
    finding = next(item for item in report.findings if item.dimension is StateDimension.LOCATION)
    consequences = impact_stack.impact.consequences(
        finding,
        principal=impact_stack.principal,
        acl_epoch=impact_stack.epoch,
    )
    assert any(line.startswith("scene:") for line in consequences)
    assert any(line.startswith("evidence:") for line in consequences)


def test_inspect_all_can_surface_compressed_logistics(impact_stack) -> None:
    film_ir = _film_ir(impact_stack)
    ada, kitchen, _harbor = _ada_and_scenes(film_ir)
    extras = _conflict(ada.id, kitchen, StateDimension.LOCATION, "place", "KITCHEN", "HARBOR")
    report = impact_stack.continuity.analyze(
        film_ir,
        impact_stack.document,
        principal=impact_stack.principal,
        acl_epoch=impact_stack.epoch,
        extra_transitions=extras,
        mode=(Mode.WRITER,),
    )
    default = impact_stack.impact.summarize(
        report,
        principal=impact_stack.principal,
        acl_epoch=impact_stack.epoch,
    )
    assert default.production == ()
    full = impact_stack.impact.summarize(
        report,
        principal=impact_stack.principal,
        acl_epoch=impact_stack.epoch,
        inspect_all=True,
    )
    assert any("location" in line for line in full.production)
