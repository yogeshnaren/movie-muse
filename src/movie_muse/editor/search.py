"""Search and replace over the typed block tree."""

from __future__ import annotations

from movie_muse.editor.errors import EditorCommandError
from movie_muse.editor.types import SearchHit
from movie_muse.schemas.api import (
    ChangeSet,
    ChangeSetOperation,
    OperationType,
    ScreenplayDocument,
    new_id,
    new_ulid,
)


def search(document: ScreenplayDocument, query: str) -> tuple[SearchHit, ...]:
    if not query:
        raise EditorCommandError("search query must not be empty")
    hits: list[SearchHit] = []
    needle = query
    for block in document.blocks:
        start = 0
        text = block.text
        while True:
            index = text.find(needle, start)
            if index < 0:
                break
            hits.append(SearchHit(block_id=block.id, offset=index, text=block.text[index : index + len(needle)]))
            start = index + max(len(needle), 1)
    return tuple(hits)


def replace_change_set(
    document: ScreenplayDocument,
    *,
    query: str,
    replacement: str,
    actor_id: str,
    created_at: str,
    block_id: str | None = None,
) -> ChangeSet:
    if not document.base_revision_id:
        raise EditorCommandError("document has no base revision; cannot author")
    operations: list[ChangeSetOperation] = []
    order = 0
    for block in document.blocks:
        if block_id is not None and block.id != block_id:
            continue
        if query not in block.text:
            continue
        operations.append(
            ChangeSetOperation(
                id=new_ulid(),
                order=order,
                op_type=OperationType.UPDATE_BLOCK,
                target_id=block.id,
                payload={"text": block.text.replace(query, replacement)},
            )
        )
        order += 1
    if not operations:
        raise EditorCommandError("replace found no matching blocks")
    return ChangeSet(
        id=new_id("change_set"),
        base_revision_id=document.base_revision_id,
        author_actor_id=actor_id,
        created_at=created_at,
        operations=tuple(operations),
    )
