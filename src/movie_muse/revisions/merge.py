"""Structural three-way merge: compose non-overlapping ops or fail closed."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from movie_muse.document.api import InvalidOperationError, apply_change_set, structural_diff
from movie_muse.schemas.api import (
    ChangeSet,
    ChangeSetOperation,
    OperationType,
    ScreenplayDocument,
    new_id,
    new_ulid,
    to_json_dict,
)


def snapshot_for_diff(document: ScreenplayDocument) -> ScreenplayDocument:
    """Equalize revision identity so diffs compare content, not revision ids."""

    return replace(document, base_revision_id=None)


def content_equal(left: ScreenplayDocument, right: ScreenplayDocument) -> bool:
    return snapshot_for_diff(left) == snapshot_for_diff(right)


def _block_index(document: ScreenplayDocument, block_id: str) -> int | None:
    for index, block in enumerate(document.blocks):
        if block.id == block_id:
            return index
    return None


def _payload_dict(operation: ChangeSetOperation) -> dict[str, Any]:
    raw = to_json_dict(operation.payload) if operation.payload is not None else {}
    return raw if isinstance(raw, dict) else {}


def is_noop_move(operation: ChangeSetOperation, base_document: ScreenplayDocument) -> bool:
    if operation.op_type is not OperationType.MOVE_BLOCK:
        return False
    payload = _payload_dict(operation)
    if "index" not in payload:
        return False
    current = _block_index(base_document, operation.target_id)
    if current is None:
        # Insert in this same diff already placed the block; restated move is a no-op.
        return True
    return int(payload["index"]) == current


def is_revision_id_metadata(operation: ChangeSetOperation) -> bool:
    if operation.op_type is not OperationType.UPDATE_METADATA:
        return False
    payload = _payload_dict(operation)
    remaining = {key: value for key, value in payload.items() if key != "base_revision_id"}
    return not remaining


def effective_operations(
    change_set: ChangeSet, base_document: ScreenplayDocument
) -> tuple[ChangeSetOperation, ...]:
    """Drop no-op moves and revision-id-only metadata so concurrent edits can merge."""

    kept: list[ChangeSetOperation] = []
    for operation in change_set.operations:
        if is_noop_move(operation, base_document):
            continue
        if is_revision_id_metadata(operation):
            continue
        kept.append(operation)
    return tuple(kept)


def operation_target_keys(operation: ChangeSetOperation) -> frozenset[str]:
    keys = {operation.target_id}
    payload = _payload_dict(operation)
    for field_name in ("after_id", "scene_id", "sequence_id"):
        raw = payload.get(field_name)
        if raw:
            keys.add(str(raw))
    return frozenset(keys)


def overlapping_targets(
    source_ops: tuple[ChangeSetOperation, ...],
    target_ops: tuple[ChangeSetOperation, ...],
) -> frozenset[str]:
    source_keys: set[str] = set()
    for operation in source_ops:
        source_keys.update(operation_target_keys(operation))
    target_keys: set[str] = set()
    for operation in target_ops:
        target_keys.update(operation_target_keys(operation))
    return frozenset(source_keys & target_keys)


def copy_operation(operation: ChangeSetOperation, *, order: int) -> ChangeSetOperation:
    return ChangeSetOperation(
        id=f"op-{new_ulid()}",
        order=order,
        op_type=operation.op_type,
        target_id=operation.target_id,
        payload=_payload_dict(operation),
    )


def compose_operations(
    source_ops: tuple[ChangeSetOperation, ...],
    target_ops: tuple[ChangeSetOperation, ...],
    *,
    base_revision_id: str,
    author_actor_id: str,
    created_at: str,
) -> ChangeSet:
    operations = []
    order = 0
    for operation in (*source_ops, *target_ops):
        operations.append(copy_operation(operation, order=order))
        order += 1
    return ChangeSet(
        id=new_id("change_set"),
        base_revision_id=base_revision_id,
        author_actor_id=author_actor_id,
        created_at=created_at,
        operations=tuple(operations),
    )


def diff_against_base(
    base_document: ScreenplayDocument,
    other_document: ScreenplayDocument,
    *,
    author_actor_id: str,
    created_at: str,
    base_revision_id: str,
) -> ChangeSet:
    return structural_diff(
        snapshot_for_diff(base_document),
        snapshot_for_diff(other_document),
        author_actor_id=author_actor_id,
        created_at=created_at,
        base_revision_id=base_revision_id,
    )


def try_apply(document: ScreenplayDocument, change_set: ChangeSet) -> ScreenplayDocument:
    try:
        return apply_change_set(document, change_set)
    except (InvalidOperationError, ValueError) as exc:
        raise InvalidOperationError(str(exc)) from exc
