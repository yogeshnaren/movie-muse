"""Accepted proposals invalidate dependent derived nodes."""

from __future__ import annotations

from movie_muse.dependencies.api import NodeKind, NodeState
from movie_muse.proposals.api import ProposalOrigin
from movie_muse.schemas.api import ChangeSet, ChangeSetOperation, OperationType, new_id


def test_accept_invalidates_dependent_closure(proposal_stack) -> None:
    head = proposal_stack.head
    source = proposal_stack.graph.add_node(
        project_id=proposal_stack.project.id,
        kind=NodeKind.SOURCE_REVISION,
        principal=proposal_stack.principal,
        acl_epoch=proposal_stack.epoch,
        subject_id=head,
        content_hash=head,
    )
    derived = proposal_stack.graph.add_node(
        project_id=proposal_stack.project.id,
        kind=NodeKind.DERIVED_PROJECTION,
        principal=proposal_stack.principal,
        acl_epoch=proposal_stack.epoch,
        input_ids=(source.id,),
        content_hash="derived-v1",
    )
    change = ChangeSet(
        id=new_id("change_set"),
        base_revision_id=head,
        author_actor_id=proposal_stack.owner.id,
        created_at="2026-09-01T00:00:00Z",
        operations=(
            ChangeSetOperation(
                id="cop_0",
                order=0,
                op_type=OperationType.UPDATE_BLOCK,
                target_id=proposal_stack.action_id,
                payload={"text": "Ada maps the lock."},
            ),
        ),
    )
    envelope = proposal_stack.proposals.submit(
        change,
        principal=proposal_stack.principal,
        acl_epoch=proposal_stack.epoch,
        project_id=proposal_stack.project.id,
        intent="lock beat",
        rationale_summary="invalidates derived projection",
        provenance="human-author",
        origin=ProposalOrigin.HUMAN,
    )
    result = proposal_stack.proposals.accept(
        envelope.proposal.id,
        principal=proposal_stack.principal,
        acl_epoch=proposal_stack.epoch,
    )
    assert result.revision_id
    view = proposal_stack.graph.view_node(
        derived.id,
        principal=proposal_stack.principal,
        acl_epoch=proposal_stack.epoch,
    )
    assert view.state is NodeState.STALE
    assert view.current is False
    assert view.labeled_stale is True
    assert derived.id in result.invalidated_node_ids
