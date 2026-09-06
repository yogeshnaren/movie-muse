"""Context never mixes tenants or branches."""

from __future__ import annotations

from dataclasses import replace

import pytest

from movie_muse.context.api import (
    BoundState,
    BranchIsolationError,
    ContextRequest,
    SegmentKind,
    TenantIsolationError,
)
from movie_muse.schemas.api import (
    AuthoredFact,
    CreativeIntentIR,
    IntentScope,
    IntentSourceRole,
    ProjectMemory,
    ProjectMemoryKind,
    new_id,
)


def test_foreign_project_memory_is_rejected(context_stack) -> None:
    branch = context_stack.revisions.get_branch(context_stack.branch_id)
    foreign = ProjectMemory(
        id=new_id("project_memory"),
        project_id=new_id("project"),
        kind=ProjectMemoryKind.FACT,
        summary="belongs to another tenant",
        reviewed_by_actor_id=context_stack.owner.id,
        reviewed_at="2026-09-01T00:00:00Z",
    )
    with pytest.raises(TenantIsolationError):
        context_stack.context.assemble(
            ContextRequest(
                project_id=context_stack.project.id,
                branch_id=branch.id,
                principal=context_stack.principal,
                acl_epoch=context_stack.epoch,
                memories=(foreign,),
            )
        )


def test_foreign_intent_is_rejected(context_stack) -> None:
    branch = context_stack.revisions.get_branch(context_stack.branch_id)
    intent = CreativeIntentIR(
        id=new_id("creative_intent"),
        project_id=new_id("project"),
        scope=IntentScope.FILM,
        scope_target_id=new_id("scene"),
        statement="other tenant intent",
        source_role=IntentSourceRole.WRITER,
        is_locked=False,
        revision_id=branch.head_revision_id,
        created_at="2026-09-01T00:00:00Z",
    )
    with pytest.raises(TenantIsolationError):
        context_stack.context.assemble(
            ContextRequest(
                project_id=context_stack.project.id,
                branch_id=branch.id,
                principal=context_stack.principal,
                acl_epoch=context_stack.epoch,
                intents=(intent,),
            )
        )


def test_branches_do_not_mix_document_text(context_stack) -> None:
    main = context_stack.revisions.get_branch(context_stack.branch_id)
    alt = context_stack.revisions.create_branch(
        "alt",
        actor_id=context_stack.owner.id,
        from_branch=main.id,
    )
    current = context_stack.revisions.load_revision(alt.head_revision_id)
    changed = tuple(
        replace(block, text="INT. HARBOR - NIGHT")
        if block.kind.value == "scene_heading"
        else block
        for block in current.blocks
    )
    context_stack.revisions.save_document(
        replace(current, blocks=changed),
        actor_id=context_stack.owner.id,
        branch_ref=alt.id,
    )
    main_bundle = context_stack.context.assemble(
        ContextRequest(
            project_id=context_stack.project.id,
            branch_id=main.id,
            principal=context_stack.principal,
            acl_epoch=context_stack.epoch,
            expected_revision_id=main.head_revision_id,
        )
    )
    alt_head = context_stack.revisions.get_branch(alt.id).head_revision_id
    alt_bundle = context_stack.context.assemble(
        ContextRequest(
            project_id=context_stack.project.id,
            branch_id=alt.id,
            principal=context_stack.principal,
            acl_epoch=context_stack.epoch,
            expected_revision_id=alt_head,
        )
    )
    main_text = {item.text for item in main_bundle.segments if item.kind is SegmentKind.REVISION}
    alt_text = {item.text for item in alt_bundle.segments if item.kind is SegmentKind.REVISION}
    assert "INT. KITCHEN - DAY" in main_text
    assert "INT. HARBOR - NIGHT" not in main_text
    assert "INT. HARBOR - NIGHT" in alt_text
    assert main_bundle.revision_id != alt_bundle.revision_id
    fact = AuthoredFact(
        id=new_id("authored_fact"),
        subject_id=new_id("scene"),
        attribute="location",
        value="harbor",
        source_revision_id=alt_head,
        author_actor_id=context_stack.owner.id,
    )
    with pytest.raises(BranchIsolationError):
        context_stack.context.assemble(
            ContextRequest(
                project_id=context_stack.project.id,
                branch_id=main.id,
                principal=context_stack.principal,
                acl_epoch=context_stack.epoch,
                states=(
                    BoundState(
                        project_id=context_stack.project.id,
                        branch_id=alt.id,
                        payload=fact,
                    ),
                ),
            )
        )
