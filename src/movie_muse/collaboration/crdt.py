"""Deterministic CRDT merge for comments, cursors, presence, and patches.

Document patches on distinct targets commute. Concurrent patches on the
same target surface a conflict instead of last-writer-wins.
"""

from __future__ import annotations

from movie_muse.collaboration.types import CollabOp, CollabOpKind, ConflictView


def sort_ops(ops: tuple[CollabOp, ...]) -> tuple[CollabOp, ...]:
    return tuple(sorted(ops, key=lambda item: (item.lamport, item.actor_id, item.id)))


def concurrent_same_target(left: CollabOp, right: CollabOp) -> bool:
    if left.id == right.id:
        return False
    if left.kind is not CollabOpKind.DOCUMENT_PATCH:
        return False
    if right.kind is not CollabOpKind.DOCUMENT_PATCH:
        return False
    if left.target_id != right.target_id:
        return False
    return left.base_revision_id == right.base_revision_id


def merge_ops(local: tuple[CollabOp, ...], incoming: tuple[CollabOp, ...]) -> tuple[CollabOp, ...]:
    """Idempotent union. Duplicate ids keep the first seen payload."""

    by_id: dict[str, CollabOp] = {item.id: item for item in local}
    for item in incoming:
        by_id.setdefault(item.id, item)
    return sort_ops(tuple(by_id.values()))


def conflicts_in(ops: tuple[CollabOp, ...]) -> tuple[ConflictView, ...]:
    patches = [item for item in ops if item.kind is CollabOpKind.DOCUMENT_PATCH]
    found: list[ConflictView] = []
    seen: set[tuple[str, str]] = set()
    for index, left in enumerate(patches):
        for right in patches[index + 1 :]:
            if not concurrent_same_target(left, right):
                continue
            pair = (left.id, right.id) if left.id < right.id else (right.id, left.id)
            if pair in seen:
                continue
            seen.add(pair)
            found.append(
                ConflictView(
                    left_op_id=left.id,
                    right_op_id=right.id,
                    target_id=left.target_id,
                    reason="concurrent document_patch on the same target",
                    left_payload=dict(left.payload),
                    right_payload=dict(right.payload),
                )
            )
    return tuple(found)


def apply_order(ops: tuple[CollabOp, ...]) -> tuple[CollabOp, ...]:
    """Ops that commute, minus either side of an unresolved same-target conflict."""

    blocked = {item.left_op_id for item in conflicts_in(ops)} | {
        item.right_op_id for item in conflicts_in(ops)
    }
    return tuple(item for item in sort_ops(ops) if item.id not in blocked)
