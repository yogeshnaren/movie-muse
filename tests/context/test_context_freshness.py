"""Stale canon and stale bound inputs fail closed."""

from __future__ import annotations

from dataclasses import replace

import pytest

from movie_muse.context.api import BoundState, ContextRequest, StaleCanonError
from movie_muse.schemas.api import (
    AuthoredFact,
    CreativeIntentIR,
    IntentScope,
    IntentSourceRole,
    OperationalAssumption,
    new_id,
)


def _revise_action(context_stack) -> str:
    current = context_stack.revisions.load_revision(context_stack.revisions.canon_head_id())
    changed = tuple(
        replace(block, text=f"{block.text} Again.")
        if block.kind.value == "action"
        else block
        for block in current.blocks
    )
    ack = context_stack.revisions.save_document(
        replace(current, blocks=changed),
        actor_id=context_stack.owner.id,
    )
    return ack.revision_id


def test_expected_revision_mismatch_is_stale(context_stack) -> None:
    branch = context_stack.revisions.get_branch(context_stack.branch_id)
    stale = branch.head_revision_id
    _revise_action(context_stack)
    with pytest.raises(StaleCanonError):
        context_stack.context.assemble(
            ContextRequest(
                project_id=context_stack.project.id,
                branch_id=branch.id,
                principal=context_stack.principal,
                acl_epoch=context_stack.epoch,
                expected_revision_id=stale,
            )
        )


def test_stale_intent_is_rejected(context_stack) -> None:
    branch = context_stack.revisions.get_branch(context_stack.branch_id)
    stale_head = branch.head_revision_id
    _revise_action(context_stack)
    live = context_stack.revisions.get_branch(branch.id)
    intent = CreativeIntentIR(
        id=new_id("creative_intent"),
        project_id=context_stack.project.id,
        scope=IntentScope.FILM,
        scope_target_id=new_id("scene"),
        statement="Keep the lock.",
        source_role=IntentSourceRole.WRITER,
        is_locked=False,
        revision_id=stale_head,
        created_at="2026-09-01T00:00:00Z",
    )
    with pytest.raises(StaleCanonError):
        context_stack.context.assemble(
            ContextRequest(
                project_id=context_stack.project.id,
                branch_id=live.id,
                principal=context_stack.principal,
                acl_epoch=context_stack.epoch,
                expected_revision_id=live.head_revision_id,
                intents=(intent,),
            )
        )


def test_stale_authored_fact_is_rejected(context_stack) -> None:
    branch = context_stack.revisions.get_branch(context_stack.branch_id)
    stale_head = branch.head_revision_id
    _revise_action(context_stack)
    live = context_stack.revisions.get_branch(branch.id)
    fact = AuthoredFact(
        id=new_id("authored_fact"),
        subject_id=new_id("scene"),
        attribute="prop",
        value="lock",
        source_revision_id=stale_head,
        author_actor_id=context_stack.owner.id,
    )
    with pytest.raises(StaleCanonError):
        context_stack.context.assemble(
            ContextRequest(
                project_id=context_stack.project.id,
                branch_id=live.id,
                principal=context_stack.principal,
                acl_epoch=context_stack.epoch,
                expected_revision_id=live.head_revision_id,
                states=(
                    BoundState(
                        project_id=context_stack.project.id,
                        branch_id=live.id,
                        payload=fact,
                    ),
                ),
            )
        )


def test_expired_operational_assumption_is_rejected(context_stack) -> None:
    branch = context_stack.revisions.get_branch(context_stack.branch_id)
    assumption = OperationalAssumption(
        id=new_id("operational_assumption"),
        subject_id=new_id("scene"),
        attribute="company_move",
        value="false",
        assumed_by_actor_id=context_stack.owner.id,
        valid_until_revision_id=new_id("revision"),
    )
    with pytest.raises(StaleCanonError):
        context_stack.context.assemble(
            ContextRequest(
                project_id=context_stack.project.id,
                branch_id=branch.id,
                principal=context_stack.principal,
                acl_epoch=context_stack.epoch,
                expected_revision_id=branch.head_revision_id,
                states=(
                    BoundState(
                        project_id=context_stack.project.id,
                        branch_id=branch.id,
                        payload=assumption,
                    ),
                ),
            )
        )
