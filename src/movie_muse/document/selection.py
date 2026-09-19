"""Selection anchors over the typed block tree, not editor pixel coordinates."""

from __future__ import annotations

from dataclasses import dataclass

from movie_muse.document.errors import SelectionError
from movie_muse.schemas.api import ChangeSetOperation, OperationType, ScreenplayDocument


@dataclass(frozen=True, slots=True)
class SelectionAnchor:
    block_id: str
    offset: int
    affinity: str = "before"

    def __post_init__(self) -> None:
        if self.offset < 0:
            raise SelectionError("selection offset must be >= 0")
        if self.affinity not in {"before", "after"}:
            raise SelectionError("affinity must be 'before' or 'after'")


def resolve_anchor(document: ScreenplayDocument, anchor: SelectionAnchor) -> str:
    """Return the slice of block text at the anchor, proving it still resolves."""

    for block in document.blocks:
        if block.id != anchor.block_id:
            continue
        if anchor.offset > len(block.text):
            raise SelectionError("selection offset exceeds block text")
        return block.text[: anchor.offset]
    raise SelectionError(f"anchor references unknown block {anchor.block_id}")


def transform_anchor(anchor: SelectionAnchor, operation: ChangeSetOperation) -> SelectionAnchor | None:
    """Map an anchor through one operation. Deleted targets return None."""

    if operation.op_type is OperationType.DELETE_BLOCK and operation.target_id == anchor.block_id:
        return None
    if operation.op_type is OperationType.UPDATE_BLOCK and operation.target_id == anchor.block_id:
        text = operation.payload.get("text")
        if isinstance(text, str) and anchor.offset > len(text):
            return SelectionAnchor(block_id=anchor.block_id, offset=len(text), affinity=anchor.affinity)
    return anchor
