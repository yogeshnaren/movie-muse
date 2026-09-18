"""CRDT document patches converge without silent loss; stale/forbidden fail closed."""

from __future__ import annotations

import pytest

from movie_muse.collaboration.api import (
    CollabOp,
    CollabOpKind,
    ForbiddenDomainError,
    apply_order,
    conflicts_in,
    merge_ops,
)


def _action_blocks(stack):
    return [block for block in stack.revisions.replay_head().blocks if block.kind.value == "action"]


def test_distinct_block_patches_commute(collab_stack) -> None:
    kitchen, harbor = _action_blocks(collab_stack)
    first = collab_stack.collab.patch_block(
        project_id=collab_stack.project.id,
        branch_id=collab_stack.revisions.canon_branch().id,
        block_id=kitchen.id,
        text="Ada studies the brass lock.",
        principal=collab_stack.principal,
        acl_epoch=collab_stack.epoch,
        device_id="dev_a",
    )
    second = collab_stack.collab.patch_block(
        project_id=collab_stack.project.id,
        branch_id=collab_stack.revisions.canon_branch().id,
        block_id=harbor.id,
        text="Ada watches a black tide.",
        principal=collab_stack.principal,
        acl_epoch=collab_stack.epoch,
        device_id="dev_a",
    )
    assert first.applied and second.applied
    document = collab_stack.revisions.replay_head()
    texts = [block.text for block in document.blocks if block.kind.value == "action"]
    assert "brass lock" in texts[0]
    assert "black tide" in texts[1]


def test_concurrent_same_target_surfaces_conflict_without_silent_loss(collab_stack) -> None:
    kitchen = _action_blocks(collab_stack)[0]
    head = collab_stack.revisions.canon_branch().head_revision_id
    branch_id = collab_stack.revisions.canon_branch().id
    left = CollabOp(
        id="cop_left00000000000000000000000",
        kind=CollabOpKind.DOCUMENT_PATCH,
        project_id=collab_stack.project.id,
        branch_id=branch_id,
        actor_id=collab_stack.owner.id,
        device_id="dev_a",
        lamport=1,
        acl_epoch=collab_stack.epoch,
        base_revision_id=head,
        target_id=kitchen.id,
        payload={"text": "Ada picks the lock.", "domain": "document"},
        created_at="2026-09-18T22:00:00Z",
    )
    right = CollabOp(
        id="cop_right0000000000000000000000",
        kind=CollabOpKind.DOCUMENT_PATCH,
        project_id=collab_stack.project.id,
        branch_id=branch_id,
        actor_id=collab_stack.owner.id,
        device_id="dev_b",
        lamport=1,
        acl_epoch=collab_stack.epoch,
        base_revision_id=head,
        target_id=kitchen.id,
        payload={"text": "Ada leaves the lock.", "domain": "document"},
        created_at="2026-09-18T22:00:00Z",
    )
    first = collab_stack.collab.ingest_ops(
        (left,), principal=collab_stack.principal, acl_epoch=collab_stack.epoch
    )[0]
    second = collab_stack.collab.ingest_ops(
        (right,), principal=collab_stack.principal, acl_epoch=collab_stack.epoch
    )[0]
    assert first.applied is True
    assert second.applied is False
    assert second.conflicts
    assert "Ada leaves the lock." in second.conflicts[0].right_payload["text"]
    document = collab_stack.revisions.replay_head()
    kitchen_now = next(block for block in document.blocks if block.id == kitchen.id)
    assert kitchen_now.text == "Ada picks the lock."
    assert collab_stack.collab.conflicts()


def test_merge_ops_is_commutative_and_idempotent() -> None:
    def make(op_id: str, lamport: int, target: str, text: str) -> CollabOp:
        return CollabOp(
            id=op_id,
            kind=CollabOpKind.COMMENT,
            project_id="proj_x",
            branch_id="brn_x",
            actor_id="act_a",
            device_id="dev_a",
            lamport=lamport,
            acl_epoch=0,
            base_revision_id="rev_a",
            target_id=target,
            payload={"text": text},
            created_at="2026-09-18T22:00:00Z",
        )

    left = (make("cop_a", 1, "blk_1", "one"), make("cop_b", 2, "blk_2", "two"))
    right = (make("cop_b", 2, "blk_2", "two"), make("cop_c", 3, "blk_3", "three"))
    ab = merge_ops(left, right)
    ba = merge_ops(right, left)
    assert [item.id for item in ab] == [item.id for item in ba]
    assert merge_ops(ab, right) == ab
    assert conflicts_in(ab) == ()
    assert [item.id for item in apply_order(ab)] == [item.id for item in ab]


def test_partition_reorder_converges_without_drop() -> None:
    ops = tuple(
        CollabOp(
            id=f"cop_{index:026d}",
            kind=CollabOpKind.CURSOR,
            project_id="proj_x",
            branch_id="brn_x",
            actor_id="act_a",
            device_id="dev_a",
            lamport=index,
            acl_epoch=0,
            base_revision_id="rev_a",
            target_id="act_a",
            payload={"cursor_block_id": f"blk_{index}"},
            created_at="2026-09-18T22:00:00Z",
        )
        for index in (1, 2, 3)
    )
    shuffled = (ops[2], ops[0], ops[1])
    assert merge_ops((), ops) == merge_ops((), shuffled)
    assert merge_ops(ops[:2], ops[2:]) == merge_ops(ops[1:], ops[:1])


def test_forbidden_domain_fail_closed(collab_stack) -> None:
    kitchen = _action_blocks(collab_stack)[0]
    with pytest.raises(ForbiddenDomainError):
        collab_stack.collab.patch_block(
            project_id=collab_stack.project.id,
            branch_id=collab_stack.revisions.canon_branch().id,
            block_id=kitchen.id,
            text="do not touch FilmIR",
            principal=collab_stack.principal,
            acl_epoch=collab_stack.epoch,
            device_id="dev_a",
            domain="film_ir",
        )
