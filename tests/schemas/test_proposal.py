"""Proposal: an immutable candidate ChangeSet against ``base_revision_id``."""

from __future__ import annotations

import pytest

from movie_muse.schemas import ids, validators
from movie_muse.schemas.change_set import ChangeSet, ChangeSetOperation, OperationType
from movie_muse.schemas.proposal import ImpactSummary, Proposal, ProposalStatus, RevalidationRecord


def _change_set(base_revision_id: str, *, ops: tuple[ChangeSetOperation, ...] = ()) -> ChangeSet:
    return ChangeSet(
        id=ids.new_id("change_set"),
        base_revision_id=base_revision_id,
        author_actor_id=ids.new_id("actor"),
        created_at="2026-09-01T00:00:00Z",
        operations=ops,
    )


def test_change_set_operations_must_be_ordered_and_unique() -> None:
    base = ids.new_id("revision")
    op0 = ChangeSetOperation(id="op-0", order=0, op_type=OperationType.INSERT_BLOCK, target_id="blk_x")
    op1 = ChangeSetOperation(id="op-1", order=1, op_type=OperationType.UPDATE_BLOCK, target_id="blk_x")
    _change_set(base, ops=(op0, op1))

    with pytest.raises(ValueError, match="unique order"):
        _change_set(
            base,
            ops=(op0, ChangeSetOperation(id="op-2", order=0, op_type=OperationType.DELETE_BLOCK, target_id="blk_y")),
        )

    with pytest.raises(ValueError, match="ascending order"):
        _change_set(base, ops=(op1, op0))


def test_proposal_base_revision_must_match_its_change_set() -> None:
    base = ids.new_id("revision")
    other_base = ids.new_id("revision")
    with pytest.raises(ValueError, match="base_revision_id"):
        Proposal(
            id=ids.new_id("proposal"),
            project_id=ids.new_id("project"),
            change_set=_change_set(base),
            base_revision_id=other_base,
            intent="test",
            rationale_summary="because",
            provenance="human",
            created_at="2026-09-01T00:00:00Z",
        )


def test_proposal_payload_is_recursively_immutable() -> None:
    base = ids.new_id("revision")
    proposal = Proposal(
        id=ids.new_id("proposal"),
        project_id=ids.new_id("project"),
        change_set=_change_set(
            base,
            ops=(
                ChangeSetOperation(
                    id="op-0",
                    order=0,
                    op_type=OperationType.UPDATE_BLOCK,
                    target_id="blk_x",
                    payload={"text": "before"},
                ),
            ),
        ),
        base_revision_id=base,
        intent="lock",
        rationale_summary="immutable",
        provenance="human",
        created_at="2026-09-01T00:00:00Z",
    )
    with pytest.raises(TypeError):
        proposal.change_set.operations[0].payload["text"] = "after"  # type: ignore[index]


def test_proposal_schema_rejects_mismatched_nested_base_revision() -> None:
    base = ids.new_id("revision")
    other = ids.new_id("revision")
    proposal = Proposal(
        id=ids.new_id("proposal"),
        project_id=ids.new_id("project"),
        change_set=_change_set(base),
        base_revision_id=base,
        intent="ok",
        rationale_summary="ok",
        provenance="human",
        created_at="2026-09-01T00:00:00Z",
    )
    payload = proposal.to_dict()
    payload["base_revision_id"] = other
    with pytest.raises(validators.ValidationError, match="base_revision_id"):
        validators.validate_payload("proposal", payload)


def test_valid_proposal_passes_schema_validation_and_round_trips() -> None:
    base = ids.new_id("revision")
    proposal = Proposal(
        id=ids.new_id("proposal"),
        project_id=ids.new_id("project"),
        change_set=_change_set(base),
        base_revision_id=base,
        intent="unblock scene 4",
        rationale_summary="resolves a contradiction the writer flagged",
        provenance="human",
        created_at="2026-09-01T00:00:00Z",
        status=ProposalStatus.PENDING,
        impact=ImpactSummary(continuity=("scene 4 timeline",)),
        revalidation=RevalidationRecord(checked_at="2026-09-01T00:05:00Z", base_revision_id=base, is_current=True),
    )
    proposal.validate()
    validators.validate_payload("proposal", proposal.to_dict())
    restored = Proposal.from_dict(proposal.to_dict())
    assert restored == proposal


def test_stale_proposal_status_is_representable() -> None:
    base = ids.new_id("revision")
    proposal = Proposal(
        id=ids.new_id("proposal"),
        project_id=ids.new_id("project"),
        change_set=_change_set(base),
        base_revision_id=base,
        intent="x",
        rationale_summary="y",
        provenance="ai:continuity-checker-v1",
        created_at="2026-09-01T00:00:00Z",
        status=ProposalStatus.STALE,
        revalidation=RevalidationRecord(
            checked_at="2026-09-02T00:00:00Z", base_revision_id=base, is_current=False,
            notes="branch head moved past this proposal's base revision",
        ),
    )
    proposal.validate()
    validators.validate_payload("proposal", proposal.to_dict())
