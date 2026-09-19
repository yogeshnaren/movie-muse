"""Context assembly over current revisions, optional schema inputs, and retrieval."""

from __future__ import annotations

from movie_muse.context.api import BoundState, ContextRequest, SegmentKind
from movie_muse.schemas.api import (
    AuthoredFact,
    CreativeIntentIR,
    EpistemicLevel,
    InferredClaim,
    IntentScope,
    IntentSourceRole,
    ProjectMemory,
    ProjectMemoryKind,
    new_id,
)


def test_assemble_current_revision_segments_keep_source_ids(context_stack) -> None:
    branch = context_stack.revisions.get_branch(context_stack.branch_id)
    bundle = context_stack.context.assemble(
        ContextRequest(
            project_id=context_stack.project.id,
            branch_id=branch.id,
            principal=context_stack.principal,
            acl_epoch=context_stack.epoch,
            expected_revision_id=branch.head_revision_id,
        )
    )
    assert bundle.project_id == context_stack.project.id
    assert bundle.branch_id == branch.id
    assert bundle.revision_id == branch.head_revision_id
    revision_segments = [item for item in bundle.segments if item.kind is SegmentKind.REVISION]
    assert revision_segments
    texts = {item.text for item in revision_segments}
    assert "INT. KITCHEN - DAY" in texts
    assert "Ada studies the lock on the pantry." in texts
    for segment in revision_segments:
        assert segment.project_id == context_stack.project.id
        assert segment.branch_id == branch.id
        assert segment.revision_id == branch.head_revision_id
        assert segment.source_ids
        assert segment.rights.classification.value == "user_owned"
        assert segment.untrusted is False


def test_optional_memory_intent_and_states_are_labeled(context_stack) -> None:
    branch = context_stack.revisions.get_branch(context_stack.branch_id)
    head = branch.head_revision_id
    memory = ProjectMemory(
        id=new_id("project_memory"),
        project_id=context_stack.project.id,
        kind=ProjectMemoryKind.DECISION,
        summary="Keep the pantry lock visible.",
        reviewed_by_actor_id=context_stack.owner.id,
        reviewed_at="2026-09-01T00:00:00Z",
    )
    intent = CreativeIntentIR(
        id=new_id("creative_intent"),
        project_id=context_stack.project.id,
        scope=IntentScope.SCENE,
        scope_target_id=new_id("scene"),
        statement="The audience should feel the kitchen is too small.",
        source_role=IntentSourceRole.WRITER,
        is_locked=True,
        revision_id=head,
        created_at="2026-09-01T00:00:00Z",
    )
    authored = AuthoredFact(
        id=new_id("authored_fact"),
        subject_id=new_id("scene"),
        attribute="location",
        value="kitchen",
        source_revision_id=head,
        author_actor_id=context_stack.owner.id,
    )
    inferred = InferredClaim(
        id=new_id("inferred_claim"),
        subject_id=new_id("scene"),
        attribute="mood",
        value="claustrophobic",
        confidence=0.4,
        evidence_bundle_id=new_id("evidence_bundle"),
        model_id="router-not-called",
    )
    bundle = context_stack.context.assemble(
        ContextRequest(
            project_id=context_stack.project.id,
            branch_id=branch.id,
            principal=context_stack.principal,
            acl_epoch=context_stack.epoch,
            expected_revision_id=head,
            memories=(memory,),
            intents=(intent,),
            states=(
                BoundState(
                    project_id=context_stack.project.id,
                    branch_id=branch.id,
                    payload=authored,
                ),
                BoundState(
                    project_id=context_stack.project.id,
                    branch_id=branch.id,
                    payload=inferred,
                ),
            ),
        )
    )
    kinds = {item.kind for item in bundle.segments}
    assert SegmentKind.MEMORY in kinds
    assert SegmentKind.INTENT in kinds
    assert SegmentKind.AUTHORED_FACT in kinds
    assert SegmentKind.INFERRED_CLAIM in kinds
    inferred_seg = next(item for item in bundle.segments if item.kind is SegmentKind.INFERRED_CLAIM)
    assert inferred_seg.untrusted is True
    assert inferred_seg.epistemic_level == EpistemicLevel.INFERRED.value
    authored_seg = next(item for item in bundle.segments if item.kind is SegmentKind.AUTHORED_FACT)
    assert authored_seg.untrusted is False


def test_retrieval_hits_enter_as_untrusted_cited_references(
    context_stack, licensed_source
) -> None:
    context_stack.retrieval.index_reference(
        source_id=licensed_source.source_id,
        text="Brass pantry locks stick when the kitchen is humid.",
        principal=context_stack.principal,
        acl_epoch=context_stack.epoch,
        project_id=context_stack.project.id,
    )
    branch = context_stack.revisions.get_branch(context_stack.branch_id)
    bundle = context_stack.context.assemble(
        ContextRequest(
            project_id=context_stack.project.id,
            branch_id=branch.id,
            principal=context_stack.principal,
            acl_epoch=context_stack.epoch,
            expected_revision_id=branch.head_revision_id,
            retrieval_query="brass pantry humid",
        )
    )
    refs = [item for item in bundle.segments if item.kind is SegmentKind.REFERENCE]
    assert len(refs) == 1
    assert refs[0].untrusted is True
    assert refs[0].citation is not None
    assert refs[0].citation.source_id == licensed_source.source_id
    assert refs[0].rights.rights_record_id == licensed_source.rights_record_id
    assert refs[0].source_ids


def test_authored_dialogue_may_quote_instruction_language(context_stack) -> None:
    """Canon text is data. Injection defense applies to retrieved references."""

    from dataclasses import replace

    current = context_stack.revisions.load_revision(context_stack.revisions.canon_head_id())
    changed = tuple(
        replace(block, text="Ignore previous instructions, she jokes.")
        if block.kind.value == "action"
        else block
        for block in current.blocks
    )
    context_stack.revisions.save_document(
        replace(current, blocks=changed),
        actor_id=context_stack.owner.id,
    )
    branch = context_stack.revisions.get_branch(context_stack.branch_id)
    bundle = context_stack.context.assemble(
        ContextRequest(
            project_id=context_stack.project.id,
            branch_id=branch.id,
            principal=context_stack.principal,
            acl_epoch=context_stack.epoch,
            expected_revision_id=branch.head_revision_id,
        )
    )
    texts = {item.text for item in bundle.segments if item.kind is SegmentKind.REVISION}
    assert any("Ignore previous instructions" in text for text in texts)
