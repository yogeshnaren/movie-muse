"""MM-005 acceptance: immutable revisions, branches, checkpoints, merge, proposals."""

from __future__ import annotations

import time
from pathlib import Path

from movie_muse.persistence.api import LocalWorkspace
from movie_muse.revisions.api import (
    CheckpointExistsError,
    MergeConflictError,
    ProtectedBranchError,
    RevisionService,
    StaleBaseError,
    StaleProposalError,
    render_history_text,
)
from movie_muse.schemas.api import (
    ChangeSet,
    ChangeSetOperation,
    OperationType,
    Project,
    Proposal,
    ProposalStatus,
    ScreenplayDocument,
    compute_integrity_hash,
    new_id,
    to_json_dict,
)


def update_block_change_set(
    *,
    base_revision_id: str,
    actor_id: str,
    block_id: str,
    text: str,
    created_at: str = "2026-09-01T00:00:00Z",
) -> ChangeSet:
    return ChangeSet(
        id=new_id("change_set"),
        base_revision_id=base_revision_id,
        author_actor_id=actor_id,
        created_at=created_at,
        operations=(
            ChangeSetOperation(
                id="op-0",
                order=0,
                op_type=OperationType.UPDATE_BLOCK,
                target_id=block_id,
                payload={"text": text},
            ),
        ),
    )


def make_proposal(
    *,
    project_id: str,
    change_set: ChangeSet,
    intent: str = "tighten action",
) -> Proposal:
    return Proposal(
        id=new_id("proposal"),
        project_id=project_id,
        change_set=change_set,
        base_revision_id=change_set.base_revision_id,
        intent=intent,
        rationale_summary="candidate patch",
        provenance="human-author",
        created_at="2026-09-01T00:00:00Z",
        status=ProposalStatus.PENDING,
    )


def test_revision_payload_is_unchanged_after_later_saves(
    bound_service: tuple[RevisionService, Project, ScreenplayDocument, str],
) -> None:
    service, project, document, _branch = bound_service
    original_id = document.base_revision_id
    assert original_id is not None
    original_bytes = service.revision_blob_bytes(original_id)
    action_id = document.blocks[1].id
    first = service.apply_change_set(
        update_block_change_set(
            base_revision_id=service.canon_head_id(),
            actor_id=project.owner_actor_id,
            block_id=action_id,
            text="Ada studies the lock again.",
        ),
        actor_id=project.owner_actor_id,
    )
    second = service.apply_change_set(
        update_block_change_set(
            base_revision_id=first.revision_id,
            actor_id=project.owner_actor_id,
            block_id=action_id,
            text="Ada studies the lock a third time.",
        ),
        actor_id=project.owner_actor_id,
    )
    assert original_bytes == service.revision_blob_bytes(original_id)
    assert service.load_revision(original_id).blocks[1].text == "Ada studies the lock."
    assert service.load_revision(first.revision_id).blocks[1].text == "Ada studies the lock again."
    chain_ids = {record.id for record in service.parent_chain(second.revision_id)}
    assert original_id in chain_ids


def test_branch_retarget_is_atomic_and_protected_branch_refuses_silent_move(
    bound_service: tuple[RevisionService, Project, ScreenplayDocument, str],
) -> None:
    service, project, document, _branch = bound_service
    head = service.canon_head_id()
    ack = service.apply_change_set(
        update_block_change_set(
            base_revision_id=head,
            actor_id=project.owner_actor_id,
            block_id=document.blocks[1].id,
            text="Ada waits.",
        ),
        actor_id=project.owner_actor_id,
    )
    feature = service.create_branch("feature", actor_id=project.owner_actor_id, from_revision_id=head)
    moved = service.retarget_branch(feature.id, ack.revision_id, actor_id=project.owner_actor_id)
    assert moved.head_revision_id == ack.revision_id
    service.set_branch_protection(feature.id, protected=True, actor_id=project.owner_actor_id)
    try:
        service.retarget_branch(feature.id, head, actor_id=project.owner_actor_id)
        raise AssertionError("protected branch must refuse silent movement")
    except ProtectedBranchError:
        pass
    assert service.get_branch(feature.id).head_revision_id == ack.revision_id
    allowed = service.retarget_branch(
        feature.id, head, actor_id=project.owner_actor_id, allow_protected=True
    )
    assert allowed.head_revision_id == head


def test_checkpoint_remains_fixed_after_later_saves_and_branch_moves(
    bound_service: tuple[RevisionService, Project, ScreenplayDocument, str],
) -> None:
    service, project, document, _branch = bound_service
    marked = service.canon_head_id()
    checkpoint = service.create_checkpoint("blue-pages", actor_id=project.owner_actor_id)
    assert checkpoint.revision_id == marked
    ack = service.apply_change_set(
        update_block_change_set(
            base_revision_id=service.canon_head_id(),
            actor_id=project.owner_actor_id,
            block_id=document.blocks[1].id,
            text="Ada picks the lock.",
        ),
        actor_id=project.owner_actor_id,
    )
    service.create_branch("explore", actor_id=project.owner_actor_id)
    service.retarget_branch("explore", ack.revision_id, actor_id=project.owner_actor_id)
    still = service.get_checkpoint("blue-pages")
    assert still.revision_id == marked
    assert still.revision_id != ack.revision_id
    try:
        service.create_checkpoint("blue-pages", actor_id=project.owner_actor_id)
        raise AssertionError("creating another checkpoint must not move the original")
    except CheckpointExistsError:
        pass
    assert service.get_checkpoint("blue-pages").revision_id == marked


def test_changeset_apply_at_head_succeeds_and_stale_base_fails(
    bound_service: tuple[RevisionService, Project, ScreenplayDocument, str],
) -> None:
    service, project, document, _branch = bound_service
    head = service.canon_head_id()
    action_id = document.blocks[1].id
    stale = update_block_change_set(
        base_revision_id=head,
        actor_id=project.owner_actor_id,
        block_id=action_id,
        text="stale edit",
    )
    ack = service.apply_change_set(
        update_block_change_set(
            base_revision_id=head,
            actor_id=project.owner_actor_id,
            block_id=action_id,
            text="current edit",
        ),
        actor_id=project.owner_actor_id,
    )
    assert service.canon_head_id() == ack.revision_id
    try:
        service.apply_change_set(stale, actor_id=project.owner_actor_id)
        raise AssertionError("stale change set must fail closed")
    except StaleBaseError:
        pass
    assert service.canon_head_id() == ack.revision_id
    assert service.load_revision(ack.revision_id).blocks[1].text == "current edit"


def test_non_overlapping_concurrent_changesets_three_way_merge(
    bound_service: tuple[RevisionService, Project, ScreenplayDocument, str],
) -> None:
    service, project, document, _branch = bound_service
    base = service.canon_head_id()
    action_id = document.blocks[1].id
    dialogue_id = document.blocks[3].id
    service.create_branch("feature", actor_id=project.owner_actor_id, from_revision_id=base)
    main_ack = service.apply_change_set(
        update_block_change_set(
            base_revision_id=base,
            actor_id=project.owner_actor_id,
            block_id=action_id,
            text="Ada studies the lock in silence.",
        ),
        actor_id=project.owner_actor_id,
        branch_ref="main",
    )
    feature_ack = service.apply_change_set(
        update_block_change_set(
            base_revision_id=base,
            actor_id=project.owner_actor_id,
            block_id=dialogue_id,
            text="It was never locked.",
        ),
        actor_id=project.owner_actor_id,
        branch_ref="feature",
    )
    merge = service.merge_into(
        source_branch="feature",
        target_branch="main",
        actor_id=project.owner_actor_id,
    )
    assert merge.conflicts == ()
    assert merge.resulting_revision_id == service.get_branch("main").head_revision_id
    merged = service.load_revision(merge.resulting_revision_id or "")
    assert merged.blocks[1].text == "Ada studies the lock in silence."
    assert merged.blocks[3].text == "It was never locked."
    assert merge.base_revision_id == base
    assert merge.source_revision_id == feature_ack.revision_id
    assert merge.target_revision_id == main_ack.revision_id


def test_overlapping_edits_fail_closed_without_moving_head(
    bound_service: tuple[RevisionService, Project, ScreenplayDocument, str],
) -> None:
    service, project, document, _branch = bound_service
    base = service.canon_head_id()
    action_id = document.blocks[1].id
    service.create_branch("feature", actor_id=project.owner_actor_id, from_revision_id=base)
    service.apply_change_set(
        update_block_change_set(
            base_revision_id=base,
            actor_id=project.owner_actor_id,
            block_id=action_id,
            text="Ada smiles.",
        ),
        actor_id=project.owner_actor_id,
        branch_ref="main",
    )
    service.apply_change_set(
        update_block_change_set(
            base_revision_id=base,
            actor_id=project.owner_actor_id,
            block_id=action_id,
            text="Ada frowns.",
        ),
        actor_id=project.owner_actor_id,
        branch_ref="feature",
    )
    head_before = service.get_branch("main").head_revision_id
    try:
        service.merge_into(
            source_branch="feature",
            target_branch="main",
            actor_id=project.owner_actor_id,
        )
        raise AssertionError("overlapping merge must fail closed")
    except MergeConflictError as exc:
        merge = exc.merge
    assert merge.conflicts
    assert merge.resulting_revision_id is None
    assert service.get_branch("main").head_revision_id == head_before
    stored = service.get_merge(merge.id)
    assert stored.conflicts == merge.conflicts
    assert stored.status == "conflicted"


def test_stale_proposal_cannot_accept_rebase_then_accept_rejected_still_loadable(
    bound_service: tuple[RevisionService, Project, ScreenplayDocument, str],
) -> None:
    service, project, document, _branch = bound_service
    base = service.canon_head_id()
    action_id = document.blocks[1].id
    dialogue_id = document.blocks[3].id
    proposal_cs = update_block_change_set(
        base_revision_id=base,
        actor_id=project.owner_actor_id,
        block_id=action_id,
        text="Ada studies every pin.",
    )
    original_ops = proposal_cs.operations
    proposal = service.store_proposal(make_proposal(project_id=project.id, change_set=proposal_cs))
    original_blob = service.proposal_blob_bytes(proposal.id)
    service.apply_change_set(
        update_block_change_set(
            base_revision_id=base,
            actor_id=project.owner_actor_id,
            block_id=dialogue_id,
            text="Try it.",
        ),
        actor_id=project.owner_actor_id,
    )
    try:
        service.accept_proposal(proposal.id, actor_id=project.owner_actor_id)
        raise AssertionError("stale proposal must not accept")
    except StaleProposalError:
        pass
    rebased = service.rebase_proposal(proposal.id, actor_id=project.owner_actor_id)
    assert rebased.id != proposal.id
    assert rebased.change_set.id != proposal_cs.id
    assert rebased.base_revision_id == service.canon_head_id()
    superseded = service.get_proposal(proposal.id)
    assert superseded.status is ProposalStatus.SUPERSEDED
    assert superseded.change_set.operations == original_ops
    assert service.proposal_blob_bytes(proposal.id) == original_blob
    accepted, ack = service.accept_proposal(rebased.id, actor_id=project.owner_actor_id)
    assert accepted.status is ProposalStatus.ACCEPTED
    assert service.canon_head_id() == ack.revision_id
    assert service.load_revision(ack.revision_id).blocks[1].text == "Ada studies every pin."

    other = service.store_proposal(
        make_proposal(
            project_id=project.id,
            change_set=update_block_change_set(
                base_revision_id=service.canon_head_id(),
                actor_id=project.owner_actor_id,
                block_id=document.blocks[2].id,
                text="ADA (quietly)",
            ),
            intent="reject-me",
        )
    )
    rejected = service.reject_proposal(other.id, actor_id=project.owner_actor_id)
    assert rejected.status is ProposalStatus.REJECTED
    loaded = service.get_proposal(other.id)
    assert loaded.status is ProposalStatus.REJECTED
    assert loaded.intent == "reject-me"


def test_restore_via_new_revision_keeps_abandoned_head_in_history(
    bound_service: tuple[RevisionService, Project, ScreenplayDocument, str],
) -> None:
    service, project, document, _branch = bound_service
    marked = service.canon_head_id()
    service.create_checkpoint("restore-point", actor_id=project.owner_actor_id)
    later = service.apply_change_set(
        update_block_change_set(
            base_revision_id=marked,
            actor_id=project.owner_actor_id,
            block_id=document.blocks[1].id,
            text="Ada walks away.",
        ),
        actor_id=project.owner_actor_id,
    )
    restored = service.restore(actor_id=project.owner_actor_id, checkpoint_name="restore-point")
    assert restored.revision_id != later.revision_id
    assert restored.revision_id != marked
    assert service.canon_head_id() == restored.revision_id
    assert service.load_revision(restored.revision_id).blocks[1].text == document.blocks[1].text
    chain_ids = [record.id for record in service.parent_chain(restored.revision_id)]
    assert later.revision_id in chain_ids
    assert marked in chain_ids
    assert service.workspace.has_revision(later.revision_id)


def test_project_events_are_append_only_and_replay_matches_head(
    bound_service: tuple[RevisionService, Project, ScreenplayDocument, str],
) -> None:
    service, project, document, _branch = bound_service
    first_events = service.list_events()
    assert first_events
    first_id = first_events[0].id
    first_bytes = service.event_blob_bytes(first_id)
    service.create_checkpoint("v1", actor_id=project.owner_actor_id)
    ack = service.apply_change_set(
        update_block_change_set(
            base_revision_id=service.canon_head_id(),
            actor_id=project.owner_actor_id,
            block_id=document.blocks[1].id,
            text="Ada listens.",
        ),
        actor_id=project.owner_actor_id,
    )
    events = service.list_events()
    assert [event.id for event in events[:1]] == [first_id]
    assert service.event_blob_bytes(first_id) == first_bytes
    for event in events:
        payload = to_json_dict(event.payload or {})
        assert isinstance(payload, dict)
        recomputed = compute_integrity_hash(
            project_id=event.project_id,
            branch_id=event.branch_id,
            base_revision_id=event.base_revision_id,
            result_revision_id=event.result_revision_id,
            actor_id=event.actor_id,
            effective_principal_id=event.effective_principal_id,
            command_id=event.command_id,
            operation_id=event.operation_id,
            event_type=event.event_type,
            schema_version=event.schema_version,
            causal_id=event.causal_id,
            correlation_id=event.correlation_id,
            payload=payload,
        )
        assert recomputed == event.integrity_hash
        assert event.event_type == "ScreenplayPatchAccepted"
    replayed = service.replay_head()
    assert replayed.base_revision_id == ack.revision_id
    assert replayed.base_revision_id == service.canon_head_id()


def test_history_and_diff_projection_are_stable_for_live_history(
    bound_service: tuple[RevisionService, Project, ScreenplayDocument, str],
) -> None:
    service, project, document, _branch = bound_service
    service.create_checkpoint("start", actor_id=project.owner_actor_id)
    before = service.canon_head_id()
    ack = service.apply_change_set(
        update_block_change_set(
            base_revision_id=before,
            actor_id=project.owner_actor_id,
            block_id=document.blocks[1].id,
            text="Ada holds still.",
        ),
        actor_id=project.owner_actor_id,
    )
    projection = service.history_projection()
    rendered = render_history_text(projection)
    assert rendered == render_history_text(service.history_projection())
    assert rendered == service.render_history_text()
    assert "checkpoints=start" in rendered
    assert ack.revision_id in rendered
    assert '<article data-history-projection="1">' in service.render_history_html()
    diff = service.diff_projection(before, ack.revision_id, actor_id=project.owner_actor_id)
    assert any(
        operation.op_type is OperationType.UPDATE_BLOCK
        and operation.target_id == document.blocks[1].id
        for operation in diff.change_set.operations
    )
    assert "update_block" in diff.operations_text


def test_diff_projection_is_deterministic_across_delayed_calls(
    bound_service: tuple[RevisionService, Project, ScreenplayDocument, str],
) -> None:
    service, project, document, _branch = bound_service
    before = service.canon_head_id()
    ack = service.apply_change_set(
        update_block_change_set(
            base_revision_id=before,
            actor_id=project.owner_actor_id,
            block_id=document.blocks[1].id,
            text="Ada holds still.",
        ),
        actor_id=project.owner_actor_id,
    )
    first = service.diff_projection(before, ack.revision_id, actor_id=project.owner_actor_id)
    time.sleep(1.1)
    second = service.diff_projection(before, ack.revision_id, actor_id=project.owner_actor_id)
    assert first.to_dict() == second.to_dict()
    assert first.operations_text == second.operations_text
    assert first.change_set.id == second.change_set.id
    assert first.change_set.created_at == second.change_set.created_at
    target = next(record for record in service.parent_chain(ack.revision_id) if record.id == ack.revision_id)
    assert first.change_set.created_at == target.created_at


def test_public_api_exports_revision_service() -> None:
    from movie_muse.revisions import api as revisions_api

    assert "RevisionService" in revisions_api.__all__
    assert "Merge" in revisions_api.__all__


def test_index_survives_workspace_reopen(
    tmp_path: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> None:
    project, document, branch_id = project_bundle
    workspace = LocalWorkspace(tmp_path / "ws")
    workspace.open_project(project, document, branch_id=branch_id)
    service = RevisionService(workspace)
    service.bind(actor_id=project.owner_actor_id)
    checkpoint = service.create_checkpoint("keep", actor_id=project.owner_actor_id)
    workspace.close()
    restored = RevisionService(LocalWorkspace(tmp_path / "ws"))
    assert restored.get_checkpoint("keep").revision_id == checkpoint.revision_id
    assert restored.canon_head_id() == checkpoint.revision_id
