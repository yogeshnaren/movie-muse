"""Model-independent budget tests. Segments keep source ids when truncated."""

from __future__ import annotations

import pytest

from movie_muse.context.api import (
    ContextBudget,
    ContextBudgetExceededError,
    ContextRequest,
    SegmentKind,
)


def test_small_budget_truncates_but_keeps_source_ids(context_stack) -> None:
    branch = context_stack.revisions.get_branch(context_stack.branch_id)
    bundle = context_stack.context.assemble(
        ContextRequest(
            project_id=context_stack.project.id,
            branch_id=branch.id,
            principal=context_stack.principal,
            acl_epoch=context_stack.epoch,
            expected_revision_id=branch.head_revision_id,
            budget=ContextBudget(max_chars=12, max_bytes=48, max_segments=2),
        )
    )
    assert bundle.segments
    assert bundle.char_count <= 12
    assert bundle.byte_count <= 48
    assert len(bundle.segments) <= 2
    for segment in bundle.segments:
        assert segment.source_ids
        assert segment.project_id == context_stack.project.id
        assert segment.revision_id == branch.head_revision_id
        assert segment.rights.classification.value == "user_owned"


def test_impossible_budget_fails_closed() -> None:
    with pytest.raises(ValueError):
        ContextBudget(max_chars=0, max_bytes=10, max_segments=1)


def test_single_segment_budget_still_revision_kind(context_stack) -> None:
    branch = context_stack.revisions.get_branch(context_stack.branch_id)
    bundle = context_stack.context.assemble(
        ContextRequest(
            project_id=context_stack.project.id,
            branch_id=branch.id,
            principal=context_stack.principal,
            acl_epoch=context_stack.epoch,
            budget=ContextBudget(max_chars=20, max_bytes=80, max_segments=1),
        )
    )
    assert len(bundle.segments) == 1
    assert bundle.segments[0].kind is SegmentKind.REVISION
    assert bundle.segments[0].source_ids
    if len("INT. KITCHEN - DAY") > 20:
        assert bundle.segments[0].truncated is True


def test_budget_exceeded_when_required_revision_cannot_fit() -> None:
    from movie_muse.context.api import ContextSegment, Freshness, SegmentRights, fit_segments
    from movie_muse.persistence.api import utc_now
    from movie_muse.rights.api import PermittedUse, SourceClassification, SourceValidationState
    from movie_muse.schemas.api import new_id, new_ulid

    rights = SegmentRights(
        classification=SourceClassification.USER_OWNED,
        permitted_uses=(PermittedUse.RETRIEVAL,),
        rights_record_id=None,
        validation_state=SourceValidationState.VALIDATED,
    )
    freshness = Freshness(
        revision_id=new_id("revision"),
        expected_revision_id=None,
        as_of=utc_now(),
    )
    segment = ContextSegment(
        id=f"ctxseg_{new_ulid()}",
        kind=SegmentKind.REVISION,
        text="🙂",
        project_id=new_id("project"),
        branch_id=new_id("branch"),
        revision_id=freshness.revision_id,
        source_id=new_id("block"),
        source_ids=(new_id("block"),),
        rights=rights,
        citation=None,
        freshness=freshness,
        redacted=False,
        untrusted=False,
    )
    with pytest.raises(ContextBudgetExceededError):
        fit_segments((segment,), ContextBudget(max_chars=8, max_bytes=1, max_segments=1))
