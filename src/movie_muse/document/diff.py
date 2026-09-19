"""Structural diff: produce a ChangeSet that transforms one document into another.

The diff is ID-based, not a text LCS over editor JSON. Blocks with the same
stable id are updated in place; missing ids are deleted; new ids are inserted.
"""

from __future__ import annotations

from typing import Any

from movie_muse.schemas.api import (
    ChangeSet,
    ChangeSetOperation,
    OperationType,
    ScreenplayDocument,
    new_id,
)


def structural_diff(
    source: ScreenplayDocument,
    target: ScreenplayDocument,
    *,
    author_actor_id: str,
    created_at: str,
    base_revision_id: str | None = None,
) -> ChangeSet:
    """Return operations that turn ``source`` into ``target`` when applied in order."""

    source.validate()
    target.validate()
    operations: list[ChangeSetOperation] = []
    order = 0

    if (
        source.title != target.title
        or source.paper_size != target.paper_size
        or source.style != target.style
        or source.base_revision_id != target.base_revision_id
    ):
        payload: dict[str, Any] = {}
        if source.title != target.title:
            payload["title"] = target.title
        if source.paper_size != target.paper_size:
            payload["paper_size"] = target.paper_size
        if source.style != target.style:
            payload["style"] = target.style
        if source.base_revision_id != target.base_revision_id:
            payload["base_revision_id"] = target.base_revision_id
        operations.append(
            ChangeSetOperation(
                id=f"op-meta-{order}",
                order=order,
                op_type=OperationType.UPDATE_METADATA,
                target_id=source.id,
                payload=payload,
            )
        )
        order += 1

    if source.sequences != target.sequences:
        operations.append(
            ChangeSetOperation(
                id=f"op-seq-{order}",
                order=order,
                op_type=OperationType.UPDATE_METADATA,
                target_id=source.id,
                payload={"sequences": [sequence.to_dict() for sequence in target.sequences]},
            )
        )
        order += 1

    source_ids = [block.id for block in source.blocks]
    target_ids = [block.id for block in target.blocks]
    source_by_id = {block.id: block for block in source.blocks}
    target_by_id = {block.id: block for block in target.blocks}

    for block_id in source_ids:
        if block_id not in target_by_id:
            operations.append(
                ChangeSetOperation(
                    id=f"op-del-{order}",
                    order=order,
                    op_type=OperationType.DELETE_BLOCK,
                    target_id=block_id,
                )
            )
            order += 1

    for index, block_id in enumerate(target_ids):
        if block_id not in source_by_id:
            insert_payload: dict[str, Any] = {"block": target_by_id[block_id].to_dict(), "index": index}
            operations.append(
                ChangeSetOperation(
                    id=f"op-ins-{order}",
                    order=order,
                    op_type=OperationType.INSERT_BLOCK,
                    target_id=block_id,
                    payload=insert_payload,
                )
            )
            order += 1
            continue
        if source_by_id[block_id] != target_by_id[block_id]:
            updated = target_by_id[block_id].to_dict()
            current = source_by_id[block_id].to_dict()
            patch = {key: value for key, value in updated.items() if current.get(key) != value and key != "id"}
            operations.append(
                ChangeSetOperation(
                    id=f"op-upd-{order}",
                    order=order,
                    op_type=OperationType.UPDATE_BLOCK,
                    target_id=block_id,
                    payload=patch,
                )
            )
            order += 1

    # Moves: align remaining shared ids to target order after inserts/deletes.
    # Applying insert at explicit index already places new blocks. Shared blocks
    # that drifted are moved last so replay does not depend on editor order.
    for dest, block_id in enumerate(target_ids):
        operations.append(
            ChangeSetOperation(
                id=f"op-mov-{order}",
                order=order,
                op_type=OperationType.MOVE_BLOCK,
                target_id=block_id,
                payload={"index": dest},
            )
        )
        order += 1

    return ChangeSet(
        id=new_id("change_set"),
        base_revision_id=base_revision_id or source.base_revision_id or source.id,
        author_actor_id=author_actor_id,
        created_at=created_at,
        operations=tuple(operations),
    )
