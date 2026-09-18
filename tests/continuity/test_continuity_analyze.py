"""Continuity analysis catches high-severity defects without flooding logistics."""

from __future__ import annotations

import pytest

from movie_muse.authorization.api import Mode
from movie_muse.continuity.api import (
    FindingClosedError,
    FindingNotFoundError,
    FindingStatus,
    HumanRequiredError,
    Materiality,
)
from movie_muse.identity.api import make_integration_actor
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


def _conflict(
    subject_id: str,
    scene_id: str,
    *,
    dimension: StateDimension,
    attribute: str,
    left_value: str,
    right_value: str,
) -> tuple[StateTransition, ...]:
    return (
        StateTransition(
            subject_id=subject_id,
            subject_name="ADA",
            dimension=dimension,
            attribute=attribute,
            value=left_value,
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
            value=right_value,
            polarity=Polarity.DENIED,
            scene_id=scene_id,
            source_kind=EpistemicLevel.AUTHORED,
            source_id=new_id("authored_fact"),
            evidence_ids=(new_id("block"),),
        ),
    )


def _high_severity(subject_id: str, scene_id: str) -> tuple[StateTransition, ...]:
    return (
        *_conflict(
            subject_id,
            scene_id,
            dimension=StateDimension.POSSESSION,
            attribute="key",
            left_value="brass_key",
            right_value="none",
        ),
        *_conflict(
            subject_id,
            scene_id,
            dimension=StateDimension.KNOWLEDGE,
            attribute="lock_open",
            left_value="true",
            right_value="false",
        ),
    )


def test_high_severity_defects_are_caught_with_evidence(continuity_stack) -> None:
    film_ir = _film_ir(continuity_stack)
    ada, kitchen, _harbor = _ada_and_scenes(film_ir)
    report = continuity_stack.continuity.analyze(
        film_ir,
        continuity_stack.document,
        principal=continuity_stack.principal,
        acl_epoch=continuity_stack.epoch,
        extra_transitions=_high_severity(ada.id, kitchen),
        mode=(Mode.WRITER,),
    )
    dimensions = {item.dimension for item in report.findings}
    assert StateDimension.POSSESSION in dimensions
    assert StateDimension.KNOWLEDGE in dimensions
    assert all(item.evidence_ids for item in report.findings)
    assert all(item.materiality is Materiality.HIGH for item in report.findings)
    assert all(item.status is FindingStatus.OPEN for item in report.findings)


def test_writer_mode_does_not_flood_low_materiality_logistics(continuity_stack) -> None:
    film_ir = _film_ir(continuity_stack)
    ada, kitchen, _harbor = _ada_and_scenes(film_ir)
    extras = (
        *_high_severity(ada.id, kitchen),
        *_conflict(
            ada.id,
            kitchen,
            dimension=StateDimension.LOCATION,
            attribute="place",
            left_value="KITCHEN",
            right_value="HARBOR",
        ),
    )
    writer = continuity_stack.continuity.analyze(
        film_ir,
        continuity_stack.document,
        principal=continuity_stack.principal,
        acl_epoch=continuity_stack.epoch,
        extra_transitions=extras,
        mode=(Mode.WRITER,),
    )
    assert all(item.dimension is not StateDimension.LOCATION for item in writer.findings)
    assert writer.hidden_finding_ids
    inspected = continuity_stack.continuity.inspect(
        writer.revision_id,
        principal=continuity_stack.principal,
        acl_epoch=continuity_stack.epoch,
        project_id=continuity_stack.project.id,
    )
    assert any(item.dimension is StateDimension.LOCATION for item in inspected)
    producer = continuity_stack.continuity.analyze(
        film_ir,
        continuity_stack.document,
        principal=continuity_stack.principal,
        acl_epoch=continuity_stack.epoch,
        extra_transitions=extras,
        mode=(Mode.PRODUCER,),
    )
    assert any(
        item.dimension is StateDimension.LOCATION and item.materiality is Materiality.HIGH
        for item in producer.findings
    )


def test_inspect_all_returns_logistics_without_changing_default(continuity_stack) -> None:
    film_ir = _film_ir(continuity_stack)
    ada, kitchen, _harbor = _ada_and_scenes(film_ir)
    extras = _conflict(
        ada.id,
        kitchen,
        dimension=StateDimension.LOCATION,
        attribute="place",
        left_value="KITCHEN",
        right_value="HARBOR",
    )
    default = continuity_stack.continuity.analyze(
        film_ir,
        continuity_stack.document,
        principal=continuity_stack.principal,
        acl_epoch=continuity_stack.epoch,
        extra_transitions=extras,
        mode=(Mode.WRITER,),
    )
    assert default.findings == ()
    full = continuity_stack.continuity.analyze(
        film_ir,
        continuity_stack.document,
        principal=continuity_stack.principal,
        acl_epoch=continuity_stack.epoch,
        extra_transitions=extras,
        mode=(Mode.WRITER,),
        inspect_all=True,
    )
    assert full.findings
    assert all(item.materiality is Materiality.LOW for item in full.findings)


def test_resolve_and_suppress_are_audited_and_durable(continuity_stack) -> None:
    film_ir = _film_ir(continuity_stack)
    ada, kitchen, _harbor = _ada_and_scenes(film_ir)
    extras = _conflict(
        ada.id,
        kitchen,
        dimension=StateDimension.POSSESSION,
        attribute="key",
        left_value="brass_key",
        right_value="none",
    )
    report = continuity_stack.continuity.analyze(
        film_ir,
        continuity_stack.document,
        principal=continuity_stack.principal,
        acl_epoch=continuity_stack.epoch,
        extra_transitions=extras,
    )
    finding = report.findings[0]
    resolved = continuity_stack.continuity.resolve(
        finding.id,
        principal=continuity_stack.principal,
        acl_epoch=continuity_stack.epoch,
        note="prop master confirmed",
    )
    assert resolved.status is FindingStatus.RESOLVED
    rerun = continuity_stack.continuity.analyze(
        film_ir,
        continuity_stack.document,
        principal=continuity_stack.principal,
        acl_epoch=continuity_stack.epoch,
        extra_transitions=extras,
    )
    assert rerun.findings == ()
    inspected = continuity_stack.continuity.inspect(
        rerun.revision_id,
        principal=continuity_stack.principal,
        acl_epoch=continuity_stack.epoch,
        project_id=continuity_stack.project.id,
    )
    assert inspected[0].status is FindingStatus.RESOLVED
    operations = [record.operation for record in continuity_stack.audit.list_records()]
    assert "continuity.resolve" in operations
    with pytest.raises(FindingClosedError):
        continuity_stack.continuity.suppress(
            finding.id,
            principal=continuity_stack.principal,
            acl_epoch=continuity_stack.epoch,
        )


def test_integration_cannot_resolve_findings(continuity_stack) -> None:
    film_ir = _film_ir(continuity_stack)
    ada, kitchen, _harbor = _ada_and_scenes(film_ir)
    extras = _conflict(
        ada.id,
        kitchen,
        dimension=StateDimension.POSSESSION,
        attribute="key",
        left_value="brass_key",
        right_value="none",
    )
    report = continuity_stack.continuity.analyze(
        film_ir,
        continuity_stack.document,
        principal=continuity_stack.principal,
        acl_epoch=continuity_stack.epoch,
        extra_transitions=extras,
    )
    bot = make_integration_actor(
        organization_id=continuity_stack.project.organization_id,
        display_name="Lens Bot",
    )
    continuity_stack.identity.register_actor(bot)
    with pytest.raises(HumanRequiredError):
        continuity_stack.continuity.resolve(
            report.findings[0].id,
            principal=continuity_stack.identity.principal(bot.id),
            acl_epoch=continuity_stack.epoch,
        )


def test_unknown_finding_fails_closed(continuity_stack) -> None:
    with pytest.raises(FindingNotFoundError):
        continuity_stack.continuity.suppress(
            "cnf_missing",
            principal=continuity_stack.principal,
            acl_epoch=continuity_stack.epoch,
        )


def test_continuity_projection_id_is_a_production_projection(continuity_stack) -> None:
    film_ir = _film_ir(continuity_stack)
    report = continuity_stack.continuity.analyze(
        film_ir,
        continuity_stack.document,
        principal=continuity_stack.principal,
        acl_epoch=continuity_stack.epoch,
    )
    assert report.projection_id.startswith("opj_")
