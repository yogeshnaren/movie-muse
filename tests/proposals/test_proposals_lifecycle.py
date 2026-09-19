"""AI may propose; only humans write canon. Partial accept is explicit."""

from __future__ import annotations

import pytest

from movie_muse.authorization.api import AuthorizationError
from movie_muse.proposals.api import (
    DirectCanonWriteError,
    ImpactSummary,
    PartialAcceptError,
    ProposalOrigin,
    ProposalStatus,
)
from movie_muse.revisions.api import StaleProposalError
from movie_muse.schemas.api import (
    ChangeSet,
    ChangeSetOperation,
    OperationType,
    new_id,
)


def _ops(*pairs: tuple[str, str], base_revision_id: str, actor_id: str) -> ChangeSet:
    operations = tuple(
        ChangeSetOperation(
            id=f"cop_{index}",
            order=index,
            op_type=OperationType.UPDATE_BLOCK,
            target_id=block_id,
            payload={"text": text},
        )
        for index, (block_id, text) in enumerate(pairs)
    )
    return ChangeSet(
        id=new_id("change_set"),
        base_revision_id=base_revision_id,
        author_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
        operations=operations,
    )


def test_ai_can_propose_but_cannot_accept(
    proposal_stack, integration_principal
) -> None:
    change = _ops(
        (proposal_stack.action_id, "Ada studies the lock twice."),
        base_revision_id=proposal_stack.head,
        actor_id=integration_principal.actor_id,
    )
    envelope = proposal_stack.proposals.submit(
        change,
        principal=integration_principal,
        acl_epoch=proposal_stack.epoch,
        project_id=proposal_stack.project.id,
        intent="tighten the action beat",
        rationale_summary="model suggestion",
        provenance="ai:extract_structure",
        origin=ProposalOrigin.AI,
        impact=ImpactSummary(semantic=("action wording",), continuity=(), production=()),
        evidence_ids=("evb_probe",),
    )
    assert envelope.proposal.status is ProposalStatus.PENDING
    assert envelope.origin is ProposalOrigin.AI
    with pytest.raises(DirectCanonWriteError):
        proposal_stack.proposals.accept(
            envelope.proposal.id,
            principal=integration_principal,
            acl_epoch=proposal_stack.epoch,
        )
    result = proposal_stack.proposals.accept(
        envelope.proposal.id,
        principal=proposal_stack.principal,
        acl_epoch=proposal_stack.epoch,
    )
    assert result.proposal.status is ProposalStatus.ACCEPTED
    assert result.revision_id != proposal_stack.document.base_revision_id
    replayed = proposal_stack.revisions.replay_head()
    action = next(block for block in replayed.blocks if block.id == proposal_stack.action_id)
    assert action.text == "Ada studies the lock twice."
    assert any(record.operation == "proposal.accept" for record in proposal_stack.audit.list_records())


def test_partial_acceptance_is_explicit(proposal_stack) -> None:
    change = _ops(
        (proposal_stack.action_id, "Ada studies the lock twice."),
        (proposal_stack.dialogue_id, "It might be locked."),
        base_revision_id=proposal_stack.head,
        actor_id=proposal_stack.owner.id,
    )
    envelope = proposal_stack.proposals.submit(
        change,
        principal=proposal_stack.principal,
        acl_epoch=proposal_stack.epoch,
        project_id=proposal_stack.project.id,
        intent="two independent edits",
        rationale_summary="bundle",
        provenance="human-author",
        origin=ProposalOrigin.HUMAN,
    )
    with pytest.raises(PartialAcceptError):
        proposal_stack.proposals.accept_partial(
            envelope.proposal.id,
            (),
            principal=proposal_stack.principal,
            acl_epoch=proposal_stack.epoch,
        )
    result = proposal_stack.proposals.accept_partial(
        envelope.proposal.id,
        ("cop_0",),
        principal=proposal_stack.principal,
        acl_epoch=proposal_stack.epoch,
    )
    assert result.proposal.status is ProposalStatus.ACCEPTED
    assert result.remainder is not None
    assert result.remainder.status is ProposalStatus.PENDING
    replayed = proposal_stack.revisions.replay_head()
    action = next(block for block in replayed.blocks if block.id == proposal_stack.action_id)
    dialogue = next(block for block in replayed.blocks if block.id == proposal_stack.dialogue_id)
    assert action.text == "Ada studies the lock twice."
    assert dialogue.text == "It's not locked."
    assert result.remainder.change_set.operations[0].target_id == proposal_stack.dialogue_id


def test_stale_proposal_rebases_or_conflicts(proposal_stack) -> None:
    change = _ops(
        (proposal_stack.action_id, "Ada studies the lock in silence."),
        base_revision_id=proposal_stack.head,
        actor_id=proposal_stack.owner.id,
    )
    envelope = proposal_stack.proposals.submit(
        change,
        principal=proposal_stack.principal,
        acl_epoch=proposal_stack.epoch,
        project_id=proposal_stack.project.id,
        intent="quiet beat",
        rationale_summary="candidate",
        provenance="human-author",
    )
    competing = _ops(
        (proposal_stack.dialogue_id, "Maybe it is."),
        base_revision_id=proposal_stack.head,
        actor_id=proposal_stack.owner.id,
    )
    other = proposal_stack.proposals.submit(
        competing,
        principal=proposal_stack.principal,
        acl_epoch=proposal_stack.epoch,
        project_id=proposal_stack.project.id,
        intent="dialogue tweak",
        rationale_summary="other",
        provenance="human-author",
    )
    proposal_stack.proposals.accept(
        other.proposal.id,
        principal=proposal_stack.principal,
        acl_epoch=proposal_stack.epoch,
    )
    review = proposal_stack.proposals.review(envelope.proposal.id)
    assert review.stale is True
    with pytest.raises(StaleProposalError):
        proposal_stack.proposals.accept(
            envelope.proposal.id,
            principal=proposal_stack.principal,
            acl_epoch=proposal_stack.epoch,
        )
    rebased = proposal_stack.proposals.rebase(
        envelope.proposal.id,
        principal=proposal_stack.principal,
        acl_epoch=proposal_stack.epoch,
    )
    assert rebased.proposal.base_revision_id == proposal_stack.head
    original = proposal_stack.revisions.get_proposal(envelope.proposal.id)
    assert original.status is ProposalStatus.SUPERSEDED
    accepted = proposal_stack.proposals.accept(
        rebased.proposal.id,
        principal=proposal_stack.principal,
        acl_epoch=proposal_stack.epoch,
    )
    assert accepted.proposal.status is ProposalStatus.ACCEPTED


def test_alternatives_are_inspectable(proposal_stack) -> None:
    primary = _ops(
        (proposal_stack.action_id, "Ada ignores the lock."),
        base_revision_id=proposal_stack.head,
        actor_id=proposal_stack.owner.id,
    )
    alt = _ops(
        (proposal_stack.action_id, "Ada pockets the key."),
        base_revision_id=proposal_stack.head,
        actor_id=proposal_stack.owner.id,
    )
    envelope = proposal_stack.proposals.submit(
        primary,
        principal=proposal_stack.principal,
        acl_epoch=proposal_stack.epoch,
        project_id=proposal_stack.project.id,
        intent="beat options",
        rationale_summary="A or B",
        provenance="human-author",
        alternatives=(alt,),
    )
    review = proposal_stack.proposals.review(envelope.proposal.id)
    assert len(review.envelope.alternative_change_sets) == 1
    result = proposal_stack.proposals.accept_alternative(
        envelope.proposal.id,
        0,
        principal=proposal_stack.principal,
        acl_epoch=proposal_stack.epoch,
    )
    action = next(
        block
        for block in proposal_stack.revisions.replay_head().blocks
        if block.id == proposal_stack.action_id
    )
    assert action.text == "Ada pockets the key."
    assert result.proposal.status is ProposalStatus.ACCEPTED
    assert isinstance(alt, ChangeSet)
    rejected = proposal_stack.revisions.get_proposal(envelope.proposal.id)
    assert rejected.status is ProposalStatus.REJECTED


def test_ai_alternative_is_accepted_by_a_human(
    proposal_stack, integration_principal
) -> None:
    primary = _ops(
        (proposal_stack.action_id, "Ada ignores the lock."),
        base_revision_id=proposal_stack.head,
        actor_id=integration_principal.actor_id,
    )
    alt = _ops(
        (proposal_stack.action_id, "Ada pockets the key."),
        base_revision_id=proposal_stack.head,
        actor_id=integration_principal.actor_id,
    )
    envelope = proposal_stack.proposals.submit(
        primary,
        principal=integration_principal,
        acl_epoch=proposal_stack.epoch,
        project_id=proposal_stack.project.id,
        intent="beat options",
        rationale_summary="A or B",
        provenance="ai:extract_structure",
        origin=ProposalOrigin.AI,
        alternatives=(alt,),
    )
    with pytest.raises(DirectCanonWriteError):
        proposal_stack.proposals.accept_alternative(
            envelope.proposal.id,
            0,
            principal=integration_principal,
            acl_epoch=proposal_stack.epoch,
        )
    result = proposal_stack.proposals.accept_alternative(
        envelope.proposal.id,
        0,
        principal=proposal_stack.principal,
        acl_epoch=proposal_stack.epoch,
    )
    action = next(
        block
        for block in proposal_stack.revisions.replay_head().blocks
        if block.id == proposal_stack.action_id
    )
    assert action.text == "Ada pockets the key."
    assert result.proposal.status is ProposalStatus.ACCEPTED


def test_reject_leaves_proposal_searchable(proposal_stack) -> None:
    change = _ops(
        (proposal_stack.action_id, "Ada walks away."),
        base_revision_id=proposal_stack.head,
        actor_id=proposal_stack.owner.id,
    )
    envelope = proposal_stack.proposals.submit(
        change,
        principal=proposal_stack.principal,
        acl_epoch=proposal_stack.epoch,
        project_id=proposal_stack.project.id,
        intent="cut the beat",
        rationale_summary="not yet",
        provenance="human-author",
        impact=ImpactSummary(semantic=("action wording",), continuity=(), production=()),
    )
    review = proposal_stack.proposals.review(envelope.proposal.id)
    assert review.impact.semantic == ("action wording",)
    rejected = proposal_stack.proposals.reject(
        envelope.proposal.id,
        principal=proposal_stack.principal,
        acl_epoch=proposal_stack.epoch,
    )
    assert rejected.status is ProposalStatus.REJECTED
    loaded = proposal_stack.revisions.get_proposal(envelope.proposal.id)
    assert loaded.status is ProposalStatus.REJECTED
    assert loaded.change_set.operations[0].payload["text"] == "Ada walks away."
    replayed = proposal_stack.revisions.replay_head()
    action = next(block for block in replayed.blocks if block.id == proposal_stack.action_id)
    assert action.text == "Ada studies the lock."
    assert any(record.operation == "proposal.reject" for record in proposal_stack.audit.list_records())


def test_viewer_cannot_propose_or_accept(proposal_stack, viewer_principal) -> None:
    change = _ops(
        (proposal_stack.action_id, "Ada studies the lock twice."),
        base_revision_id=proposal_stack.head,
        actor_id=viewer_principal.actor_id,
    )
    with pytest.raises(AuthorizationError):
        proposal_stack.proposals.submit(
            change,
            principal=viewer_principal,
            acl_epoch=proposal_stack.epoch,
            project_id=proposal_stack.project.id,
            intent="viewer edit",
            rationale_summary="denied",
            provenance="human-viewer",
        )
