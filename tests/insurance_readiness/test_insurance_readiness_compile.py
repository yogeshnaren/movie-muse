"""Current schedule and budget compile a readiness packet, never coverage."""

from __future__ import annotations

import pytest

from movie_muse.authorization.api import AuthorizationError
from movie_muse.identity.api import Role, make_human_actor
from movie_muse.insurance_readiness.api import DISCLAIMER, PacketNotFoundError, StaleInputsError
from movie_muse.schemas.api import ProjectionKind


def test_compile_inventory_disclaimer_and_schedule_budget_evidence(
    compiled_packet, insurance_stack
) -> None:
    packet = compiled_packet
    assert packet.projection.kind is ProjectionKind.INSURANCE_READINESS
    assert packet.disclaimer == DISCLAIMER
    assert packet.disclosures[0] == DISCLAIMER
    assert "readiness support only" in packet.disclaimer.casefold()
    assert "not underwriting" in packet.disclaimer.casefold()
    assert "not binding" in packet.disclaimer.casefold()
    assert "not coverage" in packet.disclaimer.casefold()
    kinds = {item.kind for item in packet.risks}
    assert "stunt" in kinds
    assert "minor" in kinds
    assert any(item.code == "unverified_risk" for item in packet.missing)
    evidence_kinds = {item.kind for item in packet.evidence}
    assert {"schedule", "budget", "cast", "location", "stunt"} <= evidence_kinds
    exported = insurance_stack.insurance.export_packet(
        packet.id,
        principal=insurance_stack.principal,
        acl_epoch=insurance_stack.epoch,
    )
    assert exported.startswith(DISCLAIMER)
    assert "EVIDENCE schedule" in exported
    assert "EVIDENCE budget" in exported
    assert "EVIDENCE stunt" in exported
    records = insurance_stack.audit.list_records()
    assert any(record.operation == "insurance.compile" for record in records)
    assert any(record.operation == "insurance.export" for record in records)


def test_stale_budget_cannot_compile_or_export_current_readiness(
    compiled_budget, insurance_stack
) -> None:
    insurance_stack.budget.notify_schedule_changed(
        compiled_budget.schedule_id,
        principal=insurance_stack.principal,
        acl_epoch=insurance_stack.epoch,
    )
    with pytest.raises(StaleInputsError):
        insurance_stack.insurance.compile(
            compiled_budget.id,
            principal=insurance_stack.principal,
            acl_epoch=insurance_stack.epoch,
        )


def test_schedule_change_stales_existing_packet(compiled_packet, insurance_stack) -> None:
    stale_ids = insurance_stack.insurance.notify_inputs_changed(
        schedule_id=compiled_packet.schedule_id,
        principal=insurance_stack.principal,
        acl_epoch=insurance_stack.epoch,
    )
    assert compiled_packet.id in stale_ids
    reloaded = insurance_stack.insurance.get_packet(
        compiled_packet.id,
        principal=insurance_stack.principal,
        acl_epoch=insurance_stack.epoch,
    )
    assert reloaded.labeled_stale is True
    assert reloaded.projection.is_stale is True
    with pytest.raises(StaleInputsError):
        insurance_stack.insurance.export_packet(
            compiled_packet.id,
            principal=insurance_stack.principal,
            acl_epoch=insurance_stack.epoch,
        )


def test_viewer_cannot_read_insurance_packet(compiled_packet, insurance_stack) -> None:
    actor = make_human_actor(
        organization_id=insurance_stack.project.organization_id, display_name="Viewer"
    )
    insurance_stack.identity.register_actor(actor)
    invitation = insurance_stack.identity.invite(
        inviter_actor_id=insurance_stack.owner.id,
        invitee_actor_id=actor.id,
        project_id=insurance_stack.project.id,
        role=Role.VIEWER,
    )
    insurance_stack.identity.accept_invitation(invitation.id, actor_id=actor.id)
    viewer = insurance_stack.identity.principal(actor.id)
    epoch = insurance_stack.identity.acl_epoch()
    with pytest.raises(AuthorizationError):
        insurance_stack.insurance.get_packet(
            compiled_packet.id, principal=viewer, acl_epoch=epoch
        )


def test_unknown_packet_is_not_found(insurance_stack) -> None:
    with pytest.raises(PacketNotFoundError):
        insurance_stack.insurance.get_packet(
            "prj_missing",
            principal=insurance_stack.principal,
            acl_epoch=insurance_stack.epoch,
        )
