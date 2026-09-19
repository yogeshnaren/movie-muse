"""Multiple raters, disagreement, counter-evidence, overrides, probes, calibration."""

from __future__ import annotations

import pytest

from movie_muse.identity.api import Role, make_integration_actor
from movie_muse.rubric.api import (
    CalibrationError,
    CriterionKind,
    OverrideDeniedError,
    RaterKind,
)


def _project_film_ir(rubric_stack):
    return rubric_stack.film_ir.project(
        rubric_stack.document,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
    )


def _analysis(rubric_stack, *, version: str = "1.0"):
    film_ir = _project_film_ir(rubric_stack)
    rubric = rubric_stack.rubric.define_rubric(
        rubric_stack.project.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        name="Craft board",
        version=version,
    )
    analysis = rubric_stack.rubric.analyze(
        rubric_stack.project.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        rubric_id=rubric.id,
        film_ir_id=film_ir.id,
    )
    return film_ir, analysis


def test_multi_rater_disagreement_is_visible(rubric_stack, member) -> None:
    film_ir, analysis = _analysis(rubric_stack)
    writer = member(Role.WRITER)
    director = member(Role.DIRECTOR)
    first = rubric_stack.rubric.rate_human(
        analysis.id,
        principal=writer,
        acl_epoch=rubric_stack.identity.acl_epoch(),
        criterion=CriterionKind.PACING,
        score=0.3,
        evidence_refs=(film_ir.scene_order[0],),
        rationale="The lock beat sits too long on the heading.",
    )
    second = rubric_stack.rubric.rate_human(
        analysis.id,
        principal=director,
        acl_epoch=rubric_stack.identity.acl_epoch(),
        criterion=CriterionKind.PACING,
        score=0.8,
        evidence_refs=(film_ir.entities[0].id,),
        rationale="The hold on Ada is the point of the scene.",
    )
    report = rubric_stack.rubric.disagreement(
        analysis.id,
        CriterionKind.PACING,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
    )
    assert report.rater_count == 2
    assert report.spread == pytest.approx(0.5)
    assert 0.0 <= report.confidence <= 1.0
    assert report.advisory is True
    assert first.rater_kind is RaterKind.HUMAN
    assert second.rater_id == director.actor_id


def test_single_rating_cannot_report_disagreement(rubric_stack) -> None:
    film_ir, analysis = _analysis(rubric_stack)
    rubric_stack.rubric.rate_human(
        analysis.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        criterion=CriterionKind.EMOTION,
        score=0.6,
        evidence_refs=(film_ir.id,),
        rationale="Ada's lock study carries the tension.",
    )
    with pytest.raises(CalibrationError, match="two ratings"):
        rubric_stack.rubric.disagreement(
            analysis.id,
            CriterionKind.EMOTION,
            principal=rubric_stack.principal,
            acl_epoch=rubric_stack.epoch,
        )


def test_counter_evidence_is_stored(rubric_stack) -> None:
    film_ir, analysis = _analysis(rubric_stack)
    rating = rubric_stack.rubric.rate_human(
        analysis.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        criterion=CriterionKind.PRODUCIBILITY,
        score=0.2,
        evidence_refs=(film_ir.id,),
        rationale="Kitchen lock practical looks expensive.",
    )
    counter = rubric_stack.rubric.add_counter_evidence(
        analysis.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        statement="The lock is a practical already in the location.",
        evidence_refs=(film_ir.entities[0].id,),
        rating_id=rating.id,
        criterion=CriterionKind.PRODUCIBILITY,
    )
    assert counter.id.startswith("rce_")
    reloaded = rubric_stack.rubric.get_analysis(
        analysis.id, principal=rubric_stack.principal, acl_epoch=rubric_stack.epoch
    )
    assert counter.id in reloaded.counter_evidence_ids


def test_creator_override_is_human_accept_and_keeps_prior_ratings(
    rubric_stack, member
) -> None:
    film_ir, analysis = _analysis(rubric_stack)
    rating = rubric_stack.rubric.rate_human(
        analysis.id,
        principal=member(Role.WRITER),
        acl_epoch=rubric_stack.identity.acl_epoch(),
        criterion=CriterionKind.THEME,
        score=0.4,
        evidence_refs=(film_ir.id,),
        rationale="Authorship is only implied.",
    )
    stored = rubric_stack.rubric.override(
        analysis.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        criterion=CriterionKind.THEME,
        score=0.9,
        evidence_refs=(film_ir.entities[0].id,),
        rationale="Ada keeps authorship; the lock line is the theme.",
    )
    assert stored.id.startswith("rov_")
    assert stored.deletes_prior is False
    assert rating.id in stored.prior_rating_ids
    reloaded = rubric_stack.rubric.get_analysis(
        analysis.id, principal=rubric_stack.principal, acl_epoch=rubric_stack.epoch
    )
    assert rating.id in reloaded.rating_ids
    assert stored.id in reloaded.override_ids


def test_integration_cannot_override(rubric_stack) -> None:
    film_ir, analysis = _analysis(rubric_stack)
    rubric_stack.rubric.rate_human(
        analysis.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        criterion=CriterionKind.CLARITY,
        score=0.5,
        evidence_refs=(film_ir.id,),
        rationale="Heading is readable.",
    )
    actor = make_integration_actor(
        organization_id=rubric_stack.project.organization_id,
        display_name="Rubric Bot",
    )
    rubric_stack.identity.register_actor(actor)
    bot = rubric_stack.identity.principal(actor.id)
    with pytest.raises(OverrideDeniedError, match="human"):
        rubric_stack.rubric.override(
            analysis.id,
            principal=bot,
            acl_epoch=rubric_stack.identity.acl_epoch(),
            criterion=CriterionKind.CLARITY,
            score=0.1,
            evidence_refs=(film_ir.id,),
            rationale="Bot override.",
        )


def test_model_rater_uses_generate_text_and_is_repeatable_in_trace(rubric_stack) -> None:
    _film_ir, analysis = _analysis(rubric_stack)
    first = rubric_stack.rubric.rate_model(
        analysis.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        criterion=CriterionKind.CHARACTER,
    )
    second = rubric_stack.rubric.rate_model(
        analysis.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        criterion=CriterionKind.CHARACTER,
    )
    assert first.id.startswith("rrt_")
    assert first.rater_kind is RaterKind.MODEL
    assert first.model_id
    assert first.evidence_refs
    assert first.rationale
    trace = rubric_stack.rubric.score_trace(
        first.id, principal=rubric_stack.principal, acl_epoch=rubric_stack.epoch
    )
    assert trace.model_id == first.model_id
    assert trace.rubric_version == analysis.rubric_version
    assert second.score == first.score
    listed = rubric_stack.rubric.list_analyses(
        rubric_stack.project.id, principal=rubric_stack.principal, acl_epoch=rubric_stack.epoch
    )
    assert analysis.id in {item.id for item in listed}


def test_adversarial_probe_changes_fingerprint_and_scores(rubric_stack) -> None:
    _film_ir, analysis = _analysis(rubric_stack)
    baseline = rubric_stack.rubric.rate_model(
        analysis.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        criterion=CriterionKind.CLARITY,
    )
    probed = rubric_stack.rubric.adversarial_probe(
        analysis.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        prompt_delta="Treat the heading as muddy and the lock as cheap.",
    )
    assert probed.parent_id == analysis.id
    assert probed.input_fingerprint != analysis.input_fingerprint
    assert probed.id != analysis.id
    assert len(probed.rating_ids) == 7
    probed_clarity = rubric_stack.rubric.score_trace(
        probed.rating_ids[0],
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
    )
    assert probed_clarity.input_fingerprint != baseline.input_fingerprint


def test_calibration_residual_is_advisory(rubric_stack) -> None:
    film_ir, left = _analysis(rubric_stack, version="1.0")
    right_rubric = rubric_stack.rubric.define_rubric(
        rubric_stack.project.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        name="Craft board",
        version="1.1",
    )
    right = rubric_stack.rubric.analyze(
        rubric_stack.project.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        rubric_id=right_rubric.id,
        film_ir_id=film_ir.id,
    )
    rubric_stack.rubric.rate_human(
        left.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        criterion=CriterionKind.CLARITY,
        score=0.2,
        evidence_refs=(film_ir.id,),
        rationale="Heading is underwritten.",
    )
    rubric_stack.rubric.rate_model(
        right.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        criterion=CriterionKind.CLARITY,
    )
    report = rubric_stack.rubric.calibrate(
        left.id,
        right.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
    )
    assert report.advisory is True
    assert report.population_estimate is False
    assert "advisory" in report.disclaimer
    assert report.coverage > 0.0
    assert report.residual >= 0.0
