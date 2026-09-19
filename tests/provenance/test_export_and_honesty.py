"""Export disclosures, honesty labels, ACL, and offline provenance."""

from __future__ import annotations

import pytest

from movie_muse.authorization.api import AuthorizationError
from movie_muse.identity.api import Role
from movie_muse.provenance.api import (
    FORECAST_DISCLAIMER,
    SYNTHETIC_AUDIENCE_DISCLAIMER,
    CitationInput,
    ClaimKind,
    ExportDisclosureError,
    HumanValidationState,
    MethodProvenance,
)
from movie_muse.rights.api import PermittedUse, SourceClassification

LICENSED_USES = (
    PermittedUse.RETRIEVAL,
    PermittedUse.CITATION,
    PermittedUse.GENERATION,
    PermittedUse.FORECAST,
    PermittedUse.EXPORT_DISCLOSURE,
)


def sample_provenance() -> MethodProvenance:
    return MethodProvenance(
        provider="deterministic-double",
        model="fixture-extractor",
        model_version="1.0.0",
        prompt_version="1.0.0",
        policy_version="1.0.0",
        timestamp="2026-09-01T16:00:00Z",
        prompt_id="prompt.extract",
        method="structured extraction",
    )


def _build(stack, source, *, claim_kind=ClaimKind.CLAIM, claim="Keep the night scene."):
    return stack.provenance.build_bundle(
        project_id=stack.project.id,
        claim=claim,
        method_summary="Permitted-source comparison",
        provenance=sample_provenance(),
        principal=stack.principal,
        acl_epoch=stack.epoch,
        citations=(CitationInput(source_id=source.source_id, excerpt_summary="licensed still"),),
        claim_kind=claim_kind,
        uncertainty="scenario band, not a guarantee",
        alternatives=("Shoot day-for-night.",),
        counter_evidence=("Weather report is stale.",),
    )


def test_owner_can_export_disclosure_with_license_and_validation(
    provenance_stack, licensed_source
) -> None:
    source = licensed_source
    stored = _build(provenance_stack, source)
    packet = provenance_stack.provenance.export_disclosure(
        stored.bundle.id,
        principal=provenance_stack.principal,
        acl_epoch=provenance_stack.epoch,
    )
    payload = packet.to_dict()
    assert payload["bundle_id"] == stored.bundle.id
    assert payload["source_disclosures"][0]["license_summary"] == "licensed for citation"
    assert payload["source_disclosures"][0]["validation_state"] == "validated"
    assert payload["human_validation_state"] == HumanValidationState.UNREVIEWED.value
    assert "chain_of_thought" not in payload
    assert "chain-of-thought" not in str(payload).lower()
    digest = provenance_stack.workspace.store.get_meta("provenance.index_digest")
    assert digest is not None


def test_producer_cannot_export_disclosure(provenance_stack, licensed_source, member) -> None:
    source = licensed_source
    stored = _build(provenance_stack, source)
    producer = member(Role.PRODUCER)
    with pytest.raises(AuthorizationError):
        provenance_stack.provenance.export_disclosure(
            stored.bundle.id, principal=producer, acl_epoch=provenance_stack.epoch
        )


def test_export_fails_closed_after_source_loses_permission(
    provenance_stack, licensed_source
) -> None:
    source = licensed_source
    stored = _build(provenance_stack, source)
    provenance_stack.rights.update_source(
        source.source_id,
        principal=provenance_stack.principal,
        acl_epoch=provenance_stack.epoch,
        permitted_uses=(PermittedUse.CITATION,),
        classification=SourceClassification.LICENSED,
    )
    with pytest.raises(ExportDisclosureError):
        provenance_stack.provenance.export_disclosure(
            stored.bundle.id,
            principal=provenance_stack.principal,
            acl_epoch=provenance_stack.epoch,
        )


def test_forecasts_and_synthetic_audiences_are_labeled_honestly(
    provenance_stack, licensed_source
) -> None:
    source = licensed_source
    forecast = _build(
        provenance_stack,
        source,
        claim_kind=ClaimKind.FORECAST_SCENARIO,
        claim="P50 opening weekend under the stated assumptions",
    )
    audience = _build(
        provenance_stack,
        source,
        claim_kind=ClaimKind.SYNTHETIC_AUDIENCE_HYPOTHESIS,
        claim="A synthetic persona hypothesizes confusion in scene 1",
    )
    assert forecast.epistemic_disclaimer == FORECAST_DISCLAIMER
    assert audience.epistemic_disclaimer == SYNTHETIC_AUDIENCE_DISCLAIMER
    forecast_view = forecast.public_view()
    audience_view = audience.public_view()
    assert "not guarantees" in forecast_view["epistemic_disclaimer"]
    assert "not human samples" in audience_view["epistemic_disclaimer"]
    assert "guarantee" not in forecast_view["claim_kind"]
    assert "human_sample" not in audience_view["claim_kind"]
    packet = provenance_stack.provenance.export_disclosure(
        forecast.bundle.id,
        principal=provenance_stack.principal,
        acl_epoch=provenance_stack.epoch,
    )
    assert packet.epistemic_disclaimer == FORECAST_DISCLAIMER
    assert packet.claim_kind is ClaimKind.FORECAST_SCENARIO


def test_offline_bundle_build_and_export(provenance_stack) -> None:
    provenance_stack.workspace.set_airplane_mode(True)
    provenance_stack.workspace.set_outage("auth_outage", True)
    provenance_stack.workspace.set_outage("subscription_outage", True)
    source = provenance_stack.rights.register_source(
        project_id=provenance_stack.project.id,
        title="Offline licensed notes",
        classification=SourceClassification.LICENSED,
        principal=provenance_stack.principal,
        acl_epoch=provenance_stack.epoch,
        permitted_uses=LICENSED_USES,
        license_summary="licensed for citation",
        license_expiry="2099-01-01T00:00:00Z",
    )
    stored = _build(provenance_stack, source)
    packet = provenance_stack.provenance.export_disclosure(
        stored.bundle.id,
        principal=provenance_stack.principal,
        acl_epoch=provenance_stack.epoch,
    )
    assert packet.bundle_id == stored.bundle.id
    assert provenance_stack.workspace.store.get_meta("provenance.index_digest")


def test_provenance_adds_no_sqlite_tables(provenance_stack, licensed_source) -> None:
    before = {
        str(row["name"])
        for row in provenance_stack.workspace.store.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    source = licensed_source
    _build(provenance_stack, source)
    after = {
        str(row["name"])
        for row in provenance_stack.workspace.store.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert after == before
