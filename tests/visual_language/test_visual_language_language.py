"""Cited references, safety review, and correlation-is-not-causation exports."""

from __future__ import annotations

import pytest

from movie_muse.authorization.api import AuthorizationError
from movie_muse.identity.api import Role
from movie_muse.rights.api import PermittedUse, SourceClassification
from movie_muse.visual_language.api import (
    DISCLAIMER,
    CausationClaimError,
    LanguageNotFoundError,
    LanguageRule,
    RuleKind,
    SafetyReviewError,
    UncitedReferenceError,
)


def test_disclaimer_states_correlation_is_not_causation() -> None:
    assert "not claimed as causation" in DISCLAIMER.casefold()
    assert "advisory" in DISCLAIMER.casefold()


def test_cited_licensed_reference_records_language_and_export(
    visual_stack, cited_source, recorded_language
) -> None:
    stored = recorded_language(source_ids=(cited_source.source_id,))
    assert stored.id.startswith("vln_")
    assert stored.reference_source_ids == (cited_source.source_id,)
    assert stored.contrast == "medium-high"
    assert stored.saturation == "restrained"
    assert stored.temperature == "tungsten-warm"
    assert stored.source_motivation == "practicals and window-left daylight"
    assert stored.lighting_ratio == "3:1 key to fill"
    assert stored.production_design == "aged brass, cream plaster"
    assert stored.wardrobe == "amber wool against navy oilskins"
    assert stored.skin_tone_rendering == "protect highlight roll-off"
    assert stored.lens_render_interaction == "35mm super35 mild halation on practicals"
    assert stored.composition == "mid-frame subject, negative space right"
    assert stored.temporal_progression == "warm day interiors to cooler harbor night"
    assert stored.safety.skin_tone_safe is True
    assert stored.safety.accessibility_ok is True
    assert {item.kind for item in stored.rules} == {
        RuleKind.RULE,
        RuleKind.EXCEPTION,
        RuleKind.ANTI_RULE,
    }
    assert stored.evolution
    export = visual_stack.visual.export_language(
        stored.id, principal=visual_stack.principal, acl_epoch=visual_stack.epoch
    )
    assert export.startswith(DISCLAIMER)
    assert "not claimed as causation" in export.casefold()
    assert cited_source.source_id in export
    loaded = visual_stack.visual.get_language(
        stored.id, principal=visual_stack.principal, acl_epoch=visual_stack.epoch
    )
    assert loaded == stored


def test_empty_references_fail_closed(recorded_language) -> None:
    with pytest.raises(UncitedReferenceError):
        recorded_language(source_ids=())


def test_unknown_reference_fails_closed(recorded_language) -> None:
    with pytest.raises(UncitedReferenceError):
        recorded_language(source_ids=("src_missing",))


def test_unlicensed_reference_fails_closed(visual_stack, recorded_language) -> None:
    source = visual_stack.rights.register_source(
        project_id=visual_stack.project.id,
        title="Scraped still dump",
        classification=SourceClassification.UNLICENSED,
        principal=visual_stack.principal,
        acl_epoch=visual_stack.epoch,
        permitted_uses=(),
    )
    with pytest.raises(UncitedReferenceError):
        recorded_language(source_ids=(source.source_id,))


def test_licensed_source_without_citation_fails_closed(
    visual_stack, recorded_language
) -> None:
    source = visual_stack.rights.register_source(
        project_id=visual_stack.project.id,
        title="Generation-only stills",
        classification=SourceClassification.LICENSED,
        principal=visual_stack.principal,
        acl_epoch=visual_stack.epoch,
        permitted_uses=(PermittedUse.GENERATION,),
        license_summary="generation only",
        license_expiry="2099-01-01T00:00:00Z",
    )
    with pytest.raises(UncitedReferenceError):
        recorded_language(source_ids=(source.source_id,))


def test_failed_skin_tone_review_blocks_language(recorded_language, make_safety) -> None:
    with pytest.raises(SafetyReviewError):
        recorded_language(safety=make_safety(skin_tone_safe=False))


def test_failed_accessibility_review_blocks_language(
    recorded_language, make_safety
) -> None:
    with pytest.raises(SafetyReviewError):
        recorded_language(safety=make_safety(accessibility_ok=False))


def test_causation_claim_in_rule_text_is_rejected(recorded_language) -> None:
    rules = (
        LanguageRule(
            id="vru_forbidden",
            kind=RuleKind.RULE,
            dimension="palette",
            text="This palette makes them feel afraid.",
        ),
    )
    with pytest.raises(CausationClaimError):
        recorded_language(rules=rules)


def test_missing_language_raises(visual_stack) -> None:
    with pytest.raises(LanguageNotFoundError):
        visual_stack.visual.get_language(
            "vln_missing",
            principal=visual_stack.principal,
            acl_epoch=visual_stack.epoch,
        )


def test_viewer_cannot_record_language(visual_stack, cited_source, recorded_language, member) -> None:
    viewer = member(Role.VIEWER)
    with pytest.raises(AuthorizationError):
        recorded_language(
            source_ids=(cited_source.source_id,),
            principal=viewer,
            acl_epoch=visual_stack.epoch,
        )


def test_record_and_export_are_audited(visual_stack, recorded_language) -> None:
    stored = recorded_language()
    visual_stack.visual.export_language(
        stored.id, principal=visual_stack.principal, acl_epoch=visual_stack.epoch
    )
    operations = {record.operation for record in visual_stack.audit.list_records()}
    assert "visual_language.record" in operations
    assert "visual_language.export" in operations
