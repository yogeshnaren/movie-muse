"""Human data requires consent and rights provenance; calibration is not a population claim."""

from __future__ import annotations

import pytest

from movie_muse.audience_lab.api import (
    ConsentRequiredError,
    EvidenceTier,
    HumanProvenanceError,
    InsufficientCalibrationError,
    PopulationClaimError,
    RunNotFoundError,
)
from movie_muse.creative_intent.api import (
    IntentAction,
    IntentKind,
    IntentOrigin,
    IntentScope,
    IntentSourceRole,
)
from movie_muse.identity.api import make_integration_actor
from movie_muse.rights.api import PermittedUse, SourceClassification
from movie_muse.rights.errors import SourceNotFoundError, UnlicensedSourceError


def _register_panel_source(lab_stack):
    return lab_stack.rights.register_source(
        project_id=lab_stack.project.id,
        title="Kitchen table-read notes",
        classification=SourceClassification.USER_OWNED,
        principal=lab_stack.principal,
        acl_epoch=lab_stack.epoch,
        permitted_uses=(PermittedUse.CITATION,),
    )


def test_human_record_without_consent_fails_closed(lab_stack) -> None:
    source = _register_panel_source(lab_stack)
    with pytest.raises(ConsentRequiredError, match="granted consent"):
        lab_stack.lab.record_human(
            lab_stack.project.id,
            principal=lab_stack.principal,
            acl_epoch=lab_stack.epoch,
            tier=EvidenceTier.TABLE_READ_PANEL,
            segment="kitchen",
            source_id=source.source_id,
            responses=({"reading": "The lock felt cheap.", "score": 0.4},),
        )


def test_human_record_without_source_fails_closed(lab_stack) -> None:
    lab_stack.lab.grant_consent(
        lab_stack.project.id, principal=lab_stack.principal, acl_epoch=lab_stack.epoch
    )
    with pytest.raises(HumanProvenanceError, match="rights source"):
        lab_stack.lab.record_human(
            lab_stack.project.id,
            principal=lab_stack.principal,
            acl_epoch=lab_stack.epoch,
            tier=EvidenceTier.EXPERT_READER,
            segment="kitchen",
            source_id="",
            responses=({"reading": "Claustrophobic.", "score": 0.8},),
        )
    with pytest.raises((SourceNotFoundError, UnlicensedSourceError, HumanProvenanceError)):
        lab_stack.lab.record_human(
            lab_stack.project.id,
            principal=lab_stack.principal,
            acl_epoch=lab_stack.epoch,
            tier=EvidenceTier.EXPERT_READER,
            segment="kitchen",
            source_id="src_missing",
            responses=({"reading": "Claustrophobic.", "score": 0.8},),
        )


def test_human_record_stores_consent_and_rights_provenance(lab_stack) -> None:
    source = _register_panel_source(lab_stack)
    lab_stack.lab.grant_consent(
        lab_stack.project.id, principal=lab_stack.principal, acl_epoch=lab_stack.epoch
    )
    run = lab_stack.lab.record_human(
        lab_stack.project.id,
        principal=lab_stack.principal,
        acl_epoch=lab_stack.epoch,
        tier=EvidenceTier.TABLE_READ_PANEL,
        segment="kitchen",
        source_id=source.source_id,
        responses=(
            {"reading": "The lock felt cheap and loud.", "score": 0.35},
            {"reading": "Ada still owned the beat.", "score": 0.7},
        ),
    )
    assert run.tier is EvidenceTier.TABLE_READ_PANEL
    assert run.is_synthetic is False
    assert run.non_independent is False
    assert run.rights_source_id == source.source_id
    assert run.samples[0].provenance["rights_source_id"] == source.source_id
    assert run.samples[0].provenance["consent_actor_id"] == lab_stack.owner.id
    released = lab_stack.lab.record_human(
        lab_stack.project.id,
        principal=lab_stack.principal,
        acl_epoch=lab_stack.epoch,
        tier=EvidenceTier.RELEASED_OUTCOME,
        segment="kitchen",
        source_id=source.source_id,
        responses=({"reading": "Festival Q&A: lock beat played.", "score": 0.6},),
    )
    assert released.tier is EvidenceTier.RELEASED_OUTCOME


def test_synthetic_cannot_be_recorded_as_human(lab_stack) -> None:
    lab_stack.lab.grant_consent(
        lab_stack.project.id, principal=lab_stack.principal, acl_epoch=lab_stack.epoch
    )
    source = _register_panel_source(lab_stack)
    with pytest.raises(HumanProvenanceError, match="human evidence"):
        lab_stack.lab.record_human(
            lab_stack.project.id,
            principal=lab_stack.principal,
            acl_epoch=lab_stack.epoch,
            tier=EvidenceTier.SYNTHETIC_LLM,
            segment="kitchen",
            source_id=source.source_id,
            responses=({"reading": "fake panel", "score": 0.5},),
        )


def test_calibration_requires_human_tier(lab_stack) -> None:
    first = lab_stack.lab.run_synthetic(
        lab_stack.project.id,
        principal=lab_stack.principal,
        acl_epoch=lab_stack.epoch,
        segment="kitchen",
        prompt="How does the lock beat land?",
        sample_count=2,
    )
    second = lab_stack.lab.perturb(
        first.id,
        principal=lab_stack.principal,
        acl_epoch=lab_stack.epoch,
        prompt_delta="Shift the ask toward cheapness.",
    )
    with pytest.raises(InsufficientCalibrationError, match="human evidence"):
        lab_stack.lab.calibrate(
            first.id,
            second.id,
            principal=lab_stack.principal,
            acl_epoch=lab_stack.epoch,
        )


def test_calibration_residual_is_not_a_population_estimate(lab_stack) -> None:
    synthetic = lab_stack.lab.run_synthetic(
        lab_stack.project.id,
        principal=lab_stack.principal,
        acl_epoch=lab_stack.epoch,
        segment="kitchen",
        prompt="How does the lock beat land?",
        sample_count=2,
    )
    source = _register_panel_source(lab_stack)
    lab_stack.lab.grant_consent(
        lab_stack.project.id, principal=lab_stack.principal, acl_epoch=lab_stack.epoch
    )
    human = lab_stack.lab.record_human(
        lab_stack.project.id,
        principal=lab_stack.principal,
        acl_epoch=lab_stack.epoch,
        tier=EvidenceTier.PREVIS_SCREENING,
        segment="kitchen",
        source_id=source.source_id,
        responses=({"reading": "Screening notes: lock still lands.", "score": 0.55},),
    )
    report = lab_stack.lab.calibrate(
        synthetic.id,
        human.id,
        principal=lab_stack.principal,
        acl_epoch=lab_stack.epoch,
    )
    assert report.id.startswith("auc_")
    assert report.population_estimate is False
    assert "population estimate" in report.disclaimer
    assert report.coverage > 0.0


def test_intended_effect_comparison_is_advisory(lab_stack) -> None:
    envelope = lab_stack.intents.apply_direct(
        lab_stack.intents.command(
            action=IntentAction.SET,
            kind=IntentKind.AUDIENCE_EXPERIENCE,
            scope=IntentScope.FILM,
            scope_target_id=lab_stack.project.id,
            statement="Keep the kitchen claustrophobic for first-time viewers.",
            source_role=IntentSourceRole.WRITER,
            origin=IntentOrigin.DIRECT,
            expected_revision_id=lab_stack.head,
            branch_id=lab_stack.branch_id,
            project_id=lab_stack.project.id,
        ),
        principal=lab_stack.principal,
        acl_epoch=lab_stack.epoch,
    )
    run = lab_stack.lab.run_synthetic(
        lab_stack.project.id,
        principal=lab_stack.principal,
        acl_epoch=lab_stack.epoch,
        segment="kitchen",
        prompt="Does the kitchen feel claustrophobic?",
        sample_count=2,
    )
    comparison = lab_stack.lab.compare_intended_effect(
        run.id,
        envelope.intent.id,
        principal=lab_stack.principal,
        acl_epoch=lab_stack.epoch,
    )
    assert comparison.advisory is True
    assert comparison.intent_id == envelope.intent.id
    assert 0.0 <= comparison.overlap <= 1.0
    assert "advisory" in comparison.disclaimer


def test_intended_effect_rejects_non_audience_intent(lab_stack) -> None:
    envelope = lab_stack.intents.apply_direct(
        lab_stack.intents.command(
            action=IntentAction.SET,
            kind=IntentKind.THEME,
            scope=IntentScope.FILM,
            scope_target_id=lab_stack.project.id,
            statement="Authorship stays with Ada.",
            source_role=IntentSourceRole.WRITER,
            origin=IntentOrigin.DIRECT,
            expected_revision_id=lab_stack.head,
            branch_id=lab_stack.branch_id,
            project_id=lab_stack.project.id,
        ),
        principal=lab_stack.principal,
        acl_epoch=lab_stack.epoch,
    )
    run = lab_stack.lab.run_synthetic(
        lab_stack.project.id,
        principal=lab_stack.principal,
        acl_epoch=lab_stack.epoch,
        segment="kitchen",
        prompt="How does the lock beat land?",
        sample_count=1,
    )
    with pytest.raises(PopulationClaimError, match="audience_experience"):
        lab_stack.lab.compare_intended_effect(
            run.id,
            envelope.intent.id,
            principal=lab_stack.principal,
            acl_epoch=lab_stack.epoch,
        )


def test_missing_run_fails_closed(lab_stack) -> None:
    with pytest.raises(RunNotFoundError):
        lab_stack.lab.get_run(
            "arl_missing",
            principal=lab_stack.principal,
            acl_epoch=lab_stack.epoch,
        )


def test_expert_reader_and_list_runs(lab_stack) -> None:
    source = _register_panel_source(lab_stack)
    lab_stack.lab.grant_consent(
        lab_stack.project.id, principal=lab_stack.principal, acl_epoch=lab_stack.epoch
    )
    synthetic = lab_stack.lab.run_synthetic(
        lab_stack.project.id,
        principal=lab_stack.principal,
        acl_epoch=lab_stack.epoch,
        segment="kitchen",
        prompt="How does the lock beat land?",
        sample_count=1,
    )
    human = lab_stack.lab.record_human(
        lab_stack.project.id,
        principal=lab_stack.principal,
        acl_epoch=lab_stack.epoch,
        tier=EvidenceTier.EXPERT_READER,
        segment="kitchen",
        source_id=source.source_id,
        responses=({"reading": "Reader notes: lock still Ada's.", "score": 0.62},),
    )
    listed = lab_stack.lab.list_runs(
        lab_stack.project.id, principal=lab_stack.principal, acl_epoch=lab_stack.epoch
    )
    assert {item.id for item in listed} == {synthetic.id, human.id}
    assert human.tier is EvidenceTier.EXPERT_READER


def test_integration_cannot_grant_human_consent(lab_stack) -> None:
    actor = make_integration_actor(
        organization_id=lab_stack.project.organization_id,
        display_name="Panel Bot",
    )
    lab_stack.identity.register_actor(actor)
    bot = lab_stack.identity.principal(actor.id)
    with pytest.raises(ConsentRequiredError, match="human"):
        lab_stack.lab.grant_consent(
            lab_stack.project.id,
            principal=bot,
            acl_epoch=lab_stack.identity.acl_epoch(),
        )
