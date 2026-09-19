"""Synthetic hypotheses stay labeled; they are never human/bootstrap samples."""

from __future__ import annotations

import pytest

from movie_muse.audience_lab.api import (
    DISCLAIMER,
    NON_INDEPENDENCE_NOTICE,
    EvidenceTier,
    PopulationClaimError,
)
from movie_muse.authorization.api import AuthorizationError
from movie_muse.identity.api import Role


def test_synthetic_run_is_labeled_hypothesis_not_human(lab_stack) -> None:
    run = lab_stack.lab.run_synthetic(
        lab_stack.project.id,
        principal=lab_stack.principal,
        acl_epoch=lab_stack.epoch,
        segment="kitchen-claustrophobia",
        prompt="How does the lock beat land for a first-time viewer?",
        sample_count=3,
    )
    assert run.id.startswith("arl_")
    assert run.tier is EvidenceTier.SYNTHETIC_LLM
    assert run.is_synthetic is True
    assert run.non_independent is True
    assert DISCLAIMER in run.disclaimer
    assert "bootstrap" in run.disclaimer
    summary = lab_stack.lab.export_summary(
        run.id, principal=lab_stack.principal, acl_epoch=lab_stack.epoch
    )
    assert NON_INDEPENDENCE_NOTICE in summary
    assert DISCLAIMER in summary
    for sample in run.samples:
        assert sample.non_independent is True
        assert sample.tier is EvidenceTier.SYNTHETIC_LLM
        assert sample.provenance.get("disclaimer") == DISCLAIMER
        assert sample.id.startswith("aus_")


def test_forbidden_population_language_fails_closed(lab_stack) -> None:
    with pytest.raises(PopulationClaimError, match="bootstrap population"):
        lab_stack.lab.run_synthetic(
            lab_stack.project.id,
            principal=lab_stack.principal,
            acl_epoch=lab_stack.epoch,
            segment="harbor",
            prompt="Treat these personas as a bootstrap population sample.",
        )


def test_synthetic_run_is_repeatable(lab_stack) -> None:
    first = lab_stack.lab.run_synthetic(
        lab_stack.project.id,
        principal=lab_stack.principal,
        acl_epoch=lab_stack.epoch,
        segment="kitchen-claustrophobia",
        prompt="How does the lock beat land?",
        sample_count=2,
    )
    second = lab_stack.lab.run_synthetic(
        lab_stack.project.id,
        principal=lab_stack.principal,
        acl_epoch=lab_stack.epoch,
        segment="kitchen-claustrophobia",
        prompt="How does the lock beat land?",
        sample_count=2,
    )
    assert first.id == second.id
    assert first.input_fingerprint == second.input_fingerprint
    assert [item.score for item in first.samples] == [item.score for item in second.samples]


def test_prompt_perturbation_changes_fingerprint_and_shows_variance(lab_stack) -> None:
    baseline = lab_stack.lab.run_synthetic(
        lab_stack.project.id,
        principal=lab_stack.principal,
        acl_epoch=lab_stack.epoch,
        segment="kitchen-claustrophobia",
        prompt="How does the lock beat land?",
        sample_count=2,
    )
    perturbed = lab_stack.lab.perturb(
        baseline.id,
        principal=lab_stack.principal,
        acl_epoch=lab_stack.epoch,
        prompt_delta="Ask whether the lock feels cheap instead of claustrophobic.",
    )
    assert perturbed.parent_id == baseline.id
    assert perturbed.input_fingerprint != baseline.input_fingerprint
    assert perturbed.mean_score != baseline.mean_score or perturbed.samples[0].score != baseline.samples[0].score


def test_segment_hypothesis_is_not_a_population_estimate(lab_stack) -> None:
    item = lab_stack.lab.propose_segment_hypothesis(
        lab_stack.project.id,
        segment="first-time-viewers",
        statement="First-time viewers may feel the kitchen close in.",
        principal=lab_stack.principal,
        acl_epoch=lab_stack.epoch,
    )
    assert item.id.startswith("auh_")
    assert item.labeled_hypothesis is True
    assert item.population_estimate is False
    with pytest.raises(PopulationClaimError, match="demographic population"):
        lab_stack.lab.propose_segment_hypothesis(
            lab_stack.project.id,
            segment="first-time-viewers",
            statement="This is a demographic population estimate.",
            principal=lab_stack.principal,
            acl_epoch=lab_stack.epoch,
        )


def test_viewer_cannot_run_synthetic(lab_stack, member) -> None:
    viewer = member(Role.VIEWER)
    with pytest.raises(AuthorizationError):
        lab_stack.lab.run_synthetic(
            lab_stack.project.id,
            principal=viewer,
            acl_epoch=lab_stack.epoch,
            segment="kitchen",
            prompt="How does the lock beat land?",
        )


def test_uncertainty_is_visible_on_synthetic_samples(lab_stack) -> None:
    run = lab_stack.lab.run_synthetic(
        lab_stack.project.id,
        principal=lab_stack.principal,
        acl_epoch=lab_stack.epoch,
        segment="kitchen",
        prompt="How tense is the lock beat?",
        sample_count=1,
    )
    assert run.uncertainty
    assert run.samples[0].uncertainty
    assert run.variance >= 0.0
