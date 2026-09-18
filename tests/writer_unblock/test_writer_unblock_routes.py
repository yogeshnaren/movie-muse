"""Divergence routes stay non-canonical. Executor is required for prose."""

from __future__ import annotations

import pytest

from movie_muse.proposals.api import ProposalStatus
from movie_muse.writer_unblock.api import (
    CombineError,
    ConsentRequiredError,
    ExecutorRequiredError,
    HiddenAuthorityError,
    MetricKind,
    RouteKind,
    assert_no_hidden_authority,
)


def test_routes_are_pending_proposals_and_do_not_move_canon(unblock_stack) -> None:
    before = unblock_stack.head
    session = unblock_stack.unblock.generate_routes(
        principal=unblock_stack.principal,
        acl_epoch=unblock_stack.epoch,
        project_id=unblock_stack.project.id,
        permission_snapshot_id=unblock_stack.snapshot,
        invariants=("Ada remains the investigator",),
        rejected_ideas=("explode the kitchen",),
    )
    kinds = {route.kind for route in session.routes}
    assert kinds == set(RouteKind)
    assert len(session.routes) == 8
    assert unblock_stack.head == before
    for route in session.routes:
        proposal = unblock_stack.revisions.get_proposal(route.proposal_id)
        assert proposal.status is ProposalStatus.PENDING
        assert route.branch_id != unblock_stack.revisions.canon_branch().id
        assert "Ada remains the investigator" in route.preserved
        assert_no_hidden_authority(route.rationale)
        assert_no_hidden_authority(route.candidate_text)


def test_executor_mode_is_required_for_prose(unblock_stack) -> None:
    session = unblock_stack.unblock.generate_routes(
        principal=unblock_stack.principal,
        acl_epoch=unblock_stack.epoch,
        project_id=unblock_stack.project.id,
        permission_snapshot_id=unblock_stack.snapshot,
    )
    route = session.routes[0]
    with pytest.raises(ExecutorRequiredError):
        unblock_stack.unblock.generate_prose(
            session.id,
            route.id,
            principal=unblock_stack.principal,
            acl_epoch=unblock_stack.epoch,
            permission_snapshot_id=unblock_stack.snapshot,
            executor_mode=False,
        )
    before = unblock_stack.head
    updated = unblock_stack.unblock.generate_prose(
        session.id,
        route.id,
        principal=unblock_stack.principal,
        acl_epoch=unblock_stack.epoch,
        permission_snapshot_id=unblock_stack.snapshot,
        executor_mode=True,
    )
    assert updated.prose
    assert unblock_stack.head == before
    assert_no_hidden_authority(updated.prose)


def test_writer_can_combine_edit_and_reject(unblock_stack) -> None:
    session = unblock_stack.unblock.generate_routes(
        principal=unblock_stack.principal,
        acl_epoch=unblock_stack.epoch,
        project_id=unblock_stack.project.id,
        permission_snapshot_id=unblock_stack.snapshot,
    )
    first, second = session.routes[0], session.routes[1]
    with pytest.raises(CombineError):
        unblock_stack.unblock.combine(
            session.id,
            (first.id,),
            principal=unblock_stack.principal,
            acl_epoch=unblock_stack.epoch,
        )
    combined = unblock_stack.unblock.combine(
        session.id,
        (first.id, second.id),
        principal=unblock_stack.principal,
        acl_epoch=unblock_stack.epoch,
    )
    assert combined.proposal_id != first.proposal_id
    edited = unblock_stack.unblock.edit(
        session.id,
        first.id,
        "Ada waits beside the lock.",
        principal=unblock_stack.principal,
        acl_epoch=unblock_stack.epoch,
    )
    assert edited.candidate_text == "Ada waits beside the lock."
    with pytest.raises(HiddenAuthorityError):
        unblock_stack.unblock.edit(
            session.id,
            first.id,
            "You should obviously pick the correct lock beat.",
            principal=unblock_stack.principal,
            acl_epoch=unblock_stack.epoch,
        )
    rejected = unblock_stack.unblock.reject(
        session.id,
        second.id,
        principal=unblock_stack.principal,
        acl_epoch=unblock_stack.epoch,
    )
    assert (
        unblock_stack.revisions.get_proposal(rejected.proposal_id).status
        is ProposalStatus.REJECTED
    )
    assert unblock_stack.head == session.base_revision_id


def test_metrics_require_consent_and_never_train(unblock_stack) -> None:
    session = unblock_stack.unblock.generate_routes(
        principal=unblock_stack.principal,
        acl_epoch=unblock_stack.epoch,
        project_id=unblock_stack.project.id,
        permission_snapshot_id=unblock_stack.snapshot,
    )
    route = session.routes[0]
    with pytest.raises(ConsentRequiredError):
        unblock_stack.unblock.record_metric(
            session.id,
            kind=MetricKind.USEFULNESS,
            target_id=route.id,
            consent=False,
            payload={"score": 1},
        )
    retained = unblock_stack.unblock.record_metric(
        session.id,
        kind=MetricKind.RETAINED_SUGGESTION,
        target_id=route.proposal_id,
        consent=True,
        payload={"retained": True},
    )
    usefulness = unblock_stack.unblock.record_metric(
        session.id,
        kind=MetricKind.USEFULNESS,
        target_id=route.id,
        consent=True,
        payload={"score": 4},
    )
    assert retained.training_eligible is False
    assert usefulness.training_eligible is False
    listed = unblock_stack.unblock.list_metrics(session.id)
    assert {item.kind for item in listed} == {
        MetricKind.RETAINED_SUGGESTION,
        MetricKind.USEFULNESS,
    }
