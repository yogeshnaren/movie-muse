"""Preview, human approval, and local broker handoff. Live partner stays NOT_RUN."""

from __future__ import annotations

import pytest

from movie_muse.identity.api import make_integration_actor
from movie_muse.insurance_readiness.api import (
    DISCLAIMER,
    CoverageClaimError,
    HandoffNotAuthorizedError,
    HandoffPreview,
    StaleInputsError,
)


def _preview_and_approve(stack, packet):
    preview = stack.insurance.preview(
        packet.id,
        principal=stack.principal,
        acl_epoch=stack.epoch,
        recipient="broker@example.invalid",
    )
    approved = stack.insurance.approve(
        packet.id,
        principal=stack.principal,
        acl_epoch=stack.epoch,
    )
    return preview, approved


def test_preview_leads_with_disclaimer_and_handoff_is_local_record(
    compiled_packet, insurance_stack
) -> None:
    preview, approved = _preview_and_approve(insurance_stack, compiled_packet)
    assert DISCLAIMER in preview.content
    assert "readiness support only" in preview.content.casefold()
    assert approved.previewed is True
    assert approved.approved is True
    delivery = insurance_stack.insurance.handoff(
        compiled_packet.id,
        preview=preview,
        confirm=True,
        principal=insurance_stack.principal,
        acl_epoch=insurance_stack.epoch,
    )
    assert delivery.network_sent is False
    assert delivery.channel == "broker_sandbox"
    operations = {record.operation for record in insurance_stack.audit.list_records()}
    assert "insurance.preview" in operations
    assert "insurance.approve" in operations
    assert "insurance.handoff" in operations


def test_handoff_requires_preview_approve_and_confirm(
    compiled_packet, insurance_stack
) -> None:
    preview = insurance_stack.insurance.preview(
        compiled_packet.id,
        principal=insurance_stack.principal,
        acl_epoch=insurance_stack.epoch,
        recipient="broker@example.invalid",
    )
    with pytest.raises(HandoffNotAuthorizedError):
        insurance_stack.insurance.handoff(
            compiled_packet.id,
            preview=preview,
            confirm=True,
            principal=insurance_stack.principal,
            acl_epoch=insurance_stack.epoch,
        )
    insurance_stack.insurance.approve(
        compiled_packet.id,
        principal=insurance_stack.principal,
        acl_epoch=insurance_stack.epoch,
    )
    with pytest.raises(HandoffNotAuthorizedError):
        insurance_stack.insurance.handoff(
            compiled_packet.id,
            preview=preview,
            confirm=False,
            principal=insurance_stack.principal,
            acl_epoch=insurance_stack.epoch,
        )


def test_integration_principal_cannot_approve(compiled_packet, insurance_stack) -> None:
    insurance_stack.insurance.preview(
        compiled_packet.id,
        principal=insurance_stack.principal,
        acl_epoch=insurance_stack.epoch,
        recipient="broker@example.invalid",
    )
    actor = make_integration_actor(
        organization_id=insurance_stack.project.organization_id,
        display_name="Broker Bot",
    )
    insurance_stack.identity.register_actor(actor)
    principal = insurance_stack.identity.principal(actor.id)
    with pytest.raises(HandoffNotAuthorizedError):
        insurance_stack.insurance.approve(
            compiled_packet.id,
            principal=principal,
            acl_epoch=insurance_stack.identity.acl_epoch(),
        )


def test_forbidden_coverage_phrase_blocks_handoff(compiled_packet, insurance_stack) -> None:
    preview, _approved = _preview_and_approve(insurance_stack, compiled_packet)
    forged = HandoffPreview(
        packet_id=preview.packet_id,
        recipient=preview.recipient,
        content="policy is bound",
        render_id=preview.render_id,
        checksum=preview.checksum,
        channel=preview.channel,
    )
    with pytest.raises(CoverageClaimError):
        insurance_stack.insurance.handoff(
            compiled_packet.id,
            preview=forged,
            confirm=True,
            principal=insurance_stack.principal,
            acl_epoch=insurance_stack.epoch,
        )


def test_stale_packet_cannot_be_handed_off_as_current(compiled_packet, insurance_stack) -> None:
    preview, _approved = _preview_and_approve(insurance_stack, compiled_packet)
    insurance_stack.insurance.notify_inputs_changed(
        budget_id=compiled_packet.budget_id,
        principal=insurance_stack.principal,
        acl_epoch=insurance_stack.epoch,
    )
    with pytest.raises(StaleInputsError):
        insurance_stack.insurance.approve(
            compiled_packet.id,
            principal=insurance_stack.principal,
            acl_epoch=insurance_stack.epoch,
        )
    with pytest.raises(StaleInputsError):
        insurance_stack.insurance.handoff(
            compiled_packet.id,
            preview=preview,
            confirm=True,
            principal=insurance_stack.principal,
            acl_epoch=insurance_stack.epoch,
        )


def test_live_partner_flag_still_records_local_delivery_only(
    compiled_live_packet, live_insurance_stack
) -> None:
    preview, _approved = _preview_and_approve(live_insurance_stack, compiled_live_packet)
    delivery = live_insurance_stack.insurance.handoff(
        compiled_live_packet.id,
        preview=preview,
        confirm=True,
        principal=live_insurance_stack.principal,
        acl_epoch=live_insurance_stack.epoch,
    )
    assert live_insurance_stack.insurance.live_partner_configured is True
    assert delivery.network_sent is False
