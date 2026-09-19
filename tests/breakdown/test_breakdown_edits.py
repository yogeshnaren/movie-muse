"""Breakdown edits create ChangeSets; source changes label projections stale."""

from __future__ import annotations

import pytest

from movie_muse.authorization.api import AuthorizationError
from movie_muse.breakdown.api import (
    BreakdownService,
    ProposalRequiredError,
    StaleBreakdownError,
    VerificationState,
)
from movie_muse.compiler.api import CompilerService
from movie_muse.identity.api import Role, make_human_actor
from movie_muse.schemas.api import OperationType, ProposalStatus


def test_edits_create_inspectable_changesets(derived_breakdown, breakdown_stack) -> None:
    stored = derived_breakdown
    prop = next(item for item in stored.elements if item.kind.value == "prop")
    envelope = breakdown_stack.breakdown.propose_edit(
        stored.projection.id,
        prop.id,
        principal=breakdown_stack.principal,
        acl_epoch=breakdown_stack.epoch,
        name="BRASS KEY",
        quantity=2,
        notes="hero practical",
    )
    assert envelope.proposal.status is ProposalStatus.PENDING
    assert envelope.proposal.intent == "breakdown.edit"
    assert envelope.proposal.change_set.operations[0].op_type is OperationType.UPDATE_METADATA
    assert "breakdown element" in envelope.proposal.rationale_summary
    applied = breakdown_stack.breakdown.accept_edit(
        envelope.proposal.id,
        principal=breakdown_stack.principal,
        acl_epoch=breakdown_stack.epoch,
    )
    updated = next(item for item in applied.elements if item.id == prop.id)
    assert updated.name == "BRASS KEY"
    assert updated.quantity == 2
    assert updated.notes == "hero practical"
    assert updated.change_set_id == envelope.proposal.change_set.id
    accepted = breakdown_stack.revisions.get_proposal(envelope.proposal.id)
    assert accepted.status is ProposalStatus.ACCEPTED


def test_edits_require_proposal_service(derived_breakdown, breakdown_stack) -> None:
    stored = derived_breakdown
    isolated = BreakdownService(
        breakdown_stack.workspace,
        breakdown_stack.authorization,
        breakdown_stack.audit,
        breakdown_stack.revisions,
        compiler=CompilerService(),
        clock=breakdown_stack.clock.stamp,
    )
    with pytest.raises(ProposalRequiredError):
        isolated.propose_edit(
            stored.projection.id,
            stored.elements[0].id,
            principal=breakdown_stack.principal,
            acl_epoch=breakdown_stack.epoch,
            notes="direct write",
        )


def test_source_change_labels_breakdown_stale(derived_breakdown, breakdown_stack) -> None:
    stored = derived_breakdown
    fresh = breakdown_stack.breakdown.get_breakdown(
        stored.projection.id,
        principal=breakdown_stack.principal,
        acl_epoch=breakdown_stack.epoch,
    )
    assert fresh.labeled_stale is False
    assert fresh.projection.is_stale is False
    stale_ids = breakdown_stack.breakdown.notify_source_changed(
        breakdown_stack.project.id,
        principal=breakdown_stack.principal,
        acl_epoch=breakdown_stack.epoch,
        breakdown_id=stored.projection.id,
    )
    assert stored.projection.id in stale_ids
    stale = breakdown_stack.breakdown.get_breakdown(
        stored.projection.id,
        principal=breakdown_stack.principal,
        acl_epoch=breakdown_stack.epoch,
    )
    assert stale.labeled_stale is True
    assert stale.projection.is_stale is True
    report = breakdown_stack.breakdown.completeness_report(
        stale.projection.id,
        principal=breakdown_stack.principal,
        acl_epoch=breakdown_stack.epoch,
    )
    assert report.current is False
    assert report.labeled_stale is True
    with pytest.raises(StaleBreakdownError):
        breakdown_stack.breakdown.verify_element(
            stale.projection.id,
            stale.elements[0].id,
            principal=breakdown_stack.principal,
            acl_epoch=breakdown_stack.epoch,
            state=VerificationState.VERIFIED,
        )
    with pytest.raises(StaleBreakdownError):
        breakdown_stack.breakdown.propose_edit(
            stale.projection.id,
            stale.elements[0].id,
            principal=breakdown_stack.principal,
            acl_epoch=breakdown_stack.epoch,
            notes="after stale",
        )


def test_viewer_cannot_propose_edit(derived_breakdown, breakdown_stack) -> None:
    stored = derived_breakdown
    actor = make_human_actor(
        organization_id=breakdown_stack.project.organization_id, display_name="Viewer"
    )
    breakdown_stack.identity.register_actor(actor)
    invitation = breakdown_stack.identity.invite(
        inviter_actor_id=breakdown_stack.owner.id,
        invitee_actor_id=actor.id,
        project_id=breakdown_stack.project.id,
        role=Role.VIEWER,
    )
    breakdown_stack.identity.accept_invitation(invitation.id, actor_id=actor.id)
    viewer = breakdown_stack.identity.principal(actor.id)
    epoch = breakdown_stack.identity.acl_epoch()
    with pytest.raises(AuthorizationError):
        breakdown_stack.breakdown.propose_edit(
            stored.projection.id,
            stored.elements[0].id,
            principal=viewer,
            acl_epoch=epoch,
            notes="viewer edit",
        )
