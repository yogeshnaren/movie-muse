"""Human approve, current evidence, and local delivery. Recipients stay real."""

from __future__ import annotations

from pathlib import Path

import pytest

from movie_muse.authorization.api import AuthorizationError
from movie_muse.identity.api import Role, make_integration_actor
from movie_muse.investor_artifacts.api import (
    DISCLAIMER,
    ApprovalRequiredError,
    FabricatedDeliveryError,
    PackPreview,
    StaleEvidenceError,
)


def _preview_and_approve(stack, pack, *, recipient: str = "producer@example.invalid"):
    preview = stack.investor.preview(
        pack.id,
        principal=stack.principal,
        acl_epoch=stack.epoch,
        recipient=recipient,
    )
    approved = stack.investor.approve(
        pack.id,
        principal=stack.principal,
        acl_epoch=stack.epoch,
    )
    return preview, approved


def test_preview_approve_export_and_local_deliver(
    compiled_pack, investor_stack, tmp_path: Path
) -> None:
    preview, approved = _preview_and_approve(investor_stack, compiled_pack)
    assert DISCLAIMER in preview.content
    assert "not a guarantee" in preview.content
    assert approved.previewed is True
    assert approved.approved is True
    exported = investor_stack.investor.export_pack(
        compiled_pack.id,
        tmp_path / "deck.json",
        principal=investor_stack.principal,
        acl_epoch=investor_stack.epoch,
    )
    text = exported.read_text(encoding="utf-8")
    assert DISCLAIMER in text
    delivery = investor_stack.investor.deliver(
        compiled_pack.id,
        preview=preview,
        confirm=True,
        principal=investor_stack.principal,
        acl_epoch=investor_stack.epoch,
    )
    assert delivery.network_sent is False
    assert delivery.recipient == "producer@example.invalid"
    operations = {record.operation for record in investor_stack.audit.list_records()}
    assert "investor.preview" in operations
    assert "investor.approve" in operations
    assert "investor.export" in operations
    assert "investor.deliver" in operations


def test_export_requires_creator_approval(
    compiled_pack, investor_stack, tmp_path: Path
) -> None:
    with pytest.raises(ApprovalRequiredError, match="creator approval"):
        investor_stack.investor.export_pack(
            compiled_pack.id,
            tmp_path / "blocked.json",
            principal=investor_stack.principal,
            acl_epoch=investor_stack.epoch,
        )


def test_approve_requires_preview_and_human(compiled_pack, investor_stack) -> None:
    with pytest.raises(ApprovalRequiredError, match="preview"):
        investor_stack.investor.approve(
            compiled_pack.id,
            principal=investor_stack.principal,
            acl_epoch=investor_stack.epoch,
        )
    investor_stack.investor.preview(
        compiled_pack.id,
        principal=investor_stack.principal,
        acl_epoch=investor_stack.epoch,
        recipient="producer@example.invalid",
    )
    actor = make_integration_actor(
        organization_id=investor_stack.project.organization_id,
        display_name="Deck Bot",
    )
    investor_stack.identity.register_actor(actor)
    principal = investor_stack.identity.principal(actor.id)
    with pytest.raises(ApprovalRequiredError, match="human principal"):
        investor_stack.investor.approve(
            compiled_pack.id,
            principal=principal,
            acl_epoch=investor_stack.identity.acl_epoch(),
        )


def test_fabricated_recipient_fail_closed(compiled_pack, investor_stack) -> None:
    with pytest.raises(FabricatedDeliveryError, match="real address"):
        investor_stack.investor.preview(
            compiled_pack.id,
            principal=investor_stack.principal,
            acl_epoch=investor_stack.epoch,
            recipient="guaranteed investor",
        )
    with pytest.raises(FabricatedDeliveryError, match="fabricate"):
        investor_stack.investor.preview(
            compiled_pack.id,
            principal=investor_stack.principal,
            acl_epoch=investor_stack.epoch,
            recipient="guaranteed investor@example.invalid",
        )


def test_stale_budget_blocks_approve_and_export(
    compiled_pack, compiled_budget, investor_stack, tmp_path: Path
) -> None:
    preview, _approved = _preview_and_approve(investor_stack, compiled_pack)
    investor_stack.budget.notify_schedule_changed(
        compiled_budget.schedule_id,
        principal=investor_stack.principal,
        acl_epoch=investor_stack.epoch,
    )
    reloaded = investor_stack.investor.get_pack(
        compiled_pack.id,
        principal=investor_stack.principal,
        acl_epoch=investor_stack.epoch,
    )
    assert reloaded.labeled_stale is True
    with pytest.raises(StaleEvidenceError):
        investor_stack.investor.approve(
            compiled_pack.id,
            principal=investor_stack.principal,
            acl_epoch=investor_stack.epoch,
        )
    with pytest.raises(StaleEvidenceError):
        investor_stack.investor.export_pack(
            compiled_pack.id,
            tmp_path / "stale.json",
            principal=investor_stack.principal,
            acl_epoch=investor_stack.epoch,
        )
    with pytest.raises(StaleEvidenceError):
        investor_stack.investor.deliver(
            compiled_pack.id,
            preview=preview,
            confirm=True,
            principal=investor_stack.principal,
            acl_epoch=investor_stack.epoch,
        )


def test_revise_resets_approval_and_creates_new_version(
    compiled_pack, investor_stack, tmp_path: Path
) -> None:
    _preview_and_approve(investor_stack, compiled_pack)
    revised = investor_stack.investor.revise(
        compiled_pack.id,
        principal=investor_stack.principal,
        acl_epoch=investor_stack.epoch,
        note="Tighten the one-pager header to the current P50 range.",
    )
    assert revised.artifact_version_id != compiled_pack.artifact_version_id
    assert revised.previewed is False
    assert revised.approved is False
    with pytest.raises(ApprovalRequiredError, match="creator approval"):
        investor_stack.investor.export_pack(
            compiled_pack.id,
            tmp_path / "revised.json",
            principal=investor_stack.principal,
            acl_epoch=investor_stack.epoch,
        )
    preview, approved = _preview_and_approve(investor_stack, revised)
    assert approved.approved is True
    exported = investor_stack.investor.export_pack(
        compiled_pack.id,
        tmp_path / "revised.json",
        principal=investor_stack.principal,
        acl_epoch=investor_stack.epoch,
    )
    assert DISCLAIMER in exported.read_text(encoding="utf-8")
    assert preview.pack_id == compiled_pack.id


def test_deliver_requires_confirm_and_matching_preview(
    compiled_pack, investor_stack
) -> None:
    preview, _approved = _preview_and_approve(investor_stack, compiled_pack)
    with pytest.raises(ApprovalRequiredError, match="confirm=True"):
        investor_stack.investor.deliver(
            compiled_pack.id,
            preview=preview,
            confirm=False,
            principal=investor_stack.principal,
            acl_epoch=investor_stack.epoch,
        )
    forged = PackPreview(
        pack_id=preview.pack_id,
        recipient=preview.recipient,
        content="sure-thing return for a fabricated credential",
        render_id=preview.render_id,
        checksum=preview.checksum,
        channel=preview.channel,
    )
    with pytest.raises(FabricatedDeliveryError):
        investor_stack.investor.deliver(
            compiled_pack.id,
            preview=forged,
            confirm=True,
            principal=investor_stack.principal,
            acl_epoch=investor_stack.epoch,
        )
    mismatched = PackPreview(
        pack_id="ivp_other",
        recipient=preview.recipient,
        content=preview.content,
        render_id=preview.render_id,
        checksum=preview.checksum,
        channel=preview.channel,
    )
    with pytest.raises(FabricatedDeliveryError, match="does not match"):
        investor_stack.investor.deliver(
            compiled_pack.id,
            preview=mismatched,
            confirm=True,
            principal=investor_stack.principal,
            acl_epoch=investor_stack.epoch,
        )


def test_writer_cannot_export_pack(
    compiled_pack, investor_stack, member, tmp_path: Path
) -> None:
    _preview_and_approve(investor_stack, compiled_pack)
    writer = member(Role.WRITER)
    with pytest.raises(AuthorizationError):
        investor_stack.investor.export_pack(
            compiled_pack.id,
            tmp_path / "writer.json",
            principal=writer,
            acl_epoch=investor_stack.identity.acl_epoch(),
        )
