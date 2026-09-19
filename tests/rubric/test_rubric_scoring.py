"""Scores require evidence; analysis is advisory and never a canon write."""

from __future__ import annotations

import pytest

from movie_muse.authorization.api import AuthorizationError
from movie_muse.creative_intent.api import (
    IntentAction,
    IntentKind,
    IntentOrigin,
    IntentScope,
    IntentSourceRole,
)
from movie_muse.identity.api import Role
from movie_muse.rubric.api import (
    DISCLAIMER,
    REQUIRED_CRITERIA,
    AnalysisNotFoundError,
    CriterionKind,
    EvidenceLinkError,
    UnexplainedScoreError,
    default_criteria,
)


def _project_film_ir(rubric_stack):
    return rubric_stack.film_ir.project(
        rubric_stack.document,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
    )


def _define(rubric_stack, *, version: str = "1.0"):
    return rubric_stack.rubric.define_rubric(
        rubric_stack.project.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        name="Scene craft",
        version=version,
    )


def _intent(rubric_stack):
    return rubric_stack.intents.apply_direct(
        rubric_stack.intents.command(
            action=IntentAction.SET,
            kind=IntentKind.AUDIENCE_EXPERIENCE,
            scope=IntentScope.FILM,
            scope_target_id=rubric_stack.project.id,
            statement="Keep the kitchen claustrophobic for first-time viewers.",
            source_role=IntentSourceRole.WRITER,
            origin=IntentOrigin.DIRECT,
            expected_revision_id=rubric_stack.head,
            branch_id=rubric_stack.branch_id,
            project_id=rubric_stack.project.id,
        ),
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
    )


def test_default_rubric_covers_required_criteria() -> None:
    kinds = {item.kind.value for item in default_criteria()}
    assert kinds == set(REQUIRED_CRITERIA)


def test_unexplained_scalar_without_evidence_fails_closed(rubric_stack) -> None:
    film_ir = _project_film_ir(rubric_stack)
    rubric = _define(rubric_stack)
    analysis = rubric_stack.rubric.analyze(
        rubric_stack.project.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        rubric_id=rubric.id,
        film_ir_id=film_ir.id,
    )
    with pytest.raises(UnexplainedScoreError, match="evidence_refs"):
        rubric_stack.rubric.rate_human(
            analysis.id,
            principal=rubric_stack.principal,
            acl_epoch=rubric_stack.epoch,
            criterion=CriterionKind.CLARITY,
            score=0.9,
            evidence_refs=(),
            rationale="Kitchen heading is readable.",
        )


def test_unexplained_scalar_without_rationale_fails_closed(rubric_stack) -> None:
    film_ir = _project_film_ir(rubric_stack)
    rubric = _define(rubric_stack)
    analysis = rubric_stack.rubric.analyze(
        rubric_stack.project.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        rubric_id=rubric.id,
        film_ir_id=film_ir.id,
    )
    with pytest.raises(UnexplainedScoreError, match="rationale"):
        rubric_stack.rubric.rate_human(
            analysis.id,
            principal=rubric_stack.principal,
            acl_epoch=rubric_stack.epoch,
            criterion=CriterionKind.PACING,
            score=0.4,
            evidence_refs=(film_ir.id,),
            rationale="   ",
        )


def test_unknown_evidence_ref_fails_closed(rubric_stack) -> None:
    film_ir = _project_film_ir(rubric_stack)
    rubric = _define(rubric_stack)
    analysis = rubric_stack.rubric.analyze(
        rubric_stack.project.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        rubric_id=rubric.id,
        film_ir_id=film_ir.id,
    )
    with pytest.raises(EvidenceLinkError, match="unknown evidence"):
        rubric_stack.rubric.rate_human(
            analysis.id,
            principal=rubric_stack.principal,
            acl_epoch=rubric_stack.epoch,
            criterion=CriterionKind.THEME,
            score=0.5,
            evidence_refs=("missing_entity",),
            rationale="Theme is unsupported.",
        )


def test_score_change_traces_to_rubric_version(rubric_stack) -> None:
    film_ir = _project_film_ir(rubric_stack)
    first_rubric = _define(rubric_stack, version="1.0")
    second_rubric = _define(rubric_stack, version="2.0")
    first = rubric_stack.rubric.analyze(
        rubric_stack.project.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        rubric_id=first_rubric.id,
        film_ir_id=film_ir.id,
    )
    second = rubric_stack.rubric.analyze(
        rubric_stack.project.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        rubric_id=second_rubric.id,
        film_ir_id=film_ir.id,
    )
    left = rubric_stack.rubric.rate_model(
        first.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        criterion=CriterionKind.CLARITY,
    )
    right = rubric_stack.rubric.rate_model(
        second.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        criterion=CriterionKind.CLARITY,
    )
    assert first.input_fingerprint != second.input_fingerprint
    assert left.rubric_version == "1.0"
    assert right.rubric_version == "2.0"
    trace = rubric_stack.rubric.score_trace(
        right.id, principal=rubric_stack.principal, acl_epoch=rubric_stack.epoch
    )
    assert trace.rubric_version == "2.0"
    assert trace.film_ir_id == film_ir.id
    assert trace.model_id
    assert left.score != right.score or left.input_fingerprint != right.input_fingerprint


def test_analysis_does_not_write_film_ir_or_intent(rubric_stack) -> None:
    film_ir = _project_film_ir(rubric_stack)
    before_entities = tuple(entity.id for entity in film_ir.entities)
    envelope = _intent(rubric_stack)
    before_statement = envelope.intent.statement
    rubric = _define(rubric_stack)
    analysis = rubric_stack.rubric.analyze(
        rubric_stack.project.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        rubric_id=rubric.id,
        film_ir_id=film_ir.id,
        intent_ids=(envelope.intent.id,),
    )
    rubric_stack.rubric.rate_model(
        analysis.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        criterion=CriterionKind.INTENDED_EFFECT,
    )
    reloaded = rubric_stack.film_ir.get(film_ir.id)
    assert tuple(entity.id for entity in reloaded.entities) == before_entities
    record = rubric_stack.intents.get(envelope.intent.id)
    assert record.intent.statement == before_statement
    assert analysis.advisory is True
    assert analysis.intent_ids == (envelope.intent.id,)


def test_export_is_labeled_advisory(rubric_stack) -> None:
    film_ir = _project_film_ir(rubric_stack)
    rubric = _define(rubric_stack)
    analysis = rubric_stack.rubric.analyze(
        rubric_stack.project.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        rubric_id=rubric.id,
        film_ir_id=film_ir.id,
    )
    rubric_stack.rubric.rate_human(
        analysis.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        criterion=CriterionKind.CHARACTER,
        score=0.72,
        evidence_refs=(film_ir.entities[0].id,),
        rationale="Ada's lock beat is evidenced on the heading and cue.",
    )
    summary = rubric_stack.rubric.export_summary(
        analysis.id, principal=rubric_stack.principal, acl_epoch=rubric_stack.epoch
    )
    assert DISCLAIMER in summary
    assert "ADVISORY" in summary
    assert analysis.id in summary
    assert rubric.version in summary


def test_repeatable_analysis_reuses_fingerprint(rubric_stack) -> None:
    film_ir = _project_film_ir(rubric_stack)
    rubric = _define(rubric_stack)
    first = rubric_stack.rubric.analyze(
        rubric_stack.project.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        rubric_id=rubric.id,
        film_ir_id=film_ir.id,
    )
    second = rubric_stack.rubric.analyze(
        rubric_stack.project.id,
        principal=rubric_stack.principal,
        acl_epoch=rubric_stack.epoch,
        rubric_id=rubric.id,
        film_ir_id=film_ir.id,
    )
    assert first.id == second.id
    assert first.input_fingerprint == second.input_fingerprint


def test_missing_analysis_fails_closed(rubric_stack) -> None:
    with pytest.raises(AnalysisNotFoundError):
        rubric_stack.rubric.get_analysis(
            "rba_missing",
            principal=rubric_stack.principal,
            acl_epoch=rubric_stack.epoch,
        )


def test_viewer_cannot_define_rubric(rubric_stack, member) -> None:
    viewer = member(Role.VIEWER)
    with pytest.raises(AuthorizationError):
        rubric_stack.rubric.define_rubric(
            rubric_stack.project.id,
            principal=viewer,
            acl_epoch=rubric_stack.epoch,
            name="Viewer rubric",
            version="1.0",
        )
