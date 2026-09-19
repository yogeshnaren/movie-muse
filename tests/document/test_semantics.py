"""Normalization, semantic validation, selection, and Unicode."""

from __future__ import annotations

import pytest

from movie_muse.document.api import (
    SelectionAnchor,
    SemanticValidationError,
    normalize,
    resolve_anchor,
    semantic_validate,
    transform_anchor,
)
from movie_muse.schemas.api import (
    Block,
    BlockKind,
    ChangeSetOperation,
    OperationType,
    ScreenplayDocument,
    new_id,
)


def test_normalize_applies_nfc_and_trims(sample_document: ScreenplayDocument) -> None:
    cafe = "cafe\u0301   "
    mutated = type(sample_document).from_dict({**sample_document.to_dict(), "title": cafe})
    normalized = normalize(mutated)
    assert normalized.title == "caf\u00e9"


def test_semantic_validate_rejects_orphan_dialogue(sample_document: ScreenplayDocument) -> None:
    orphan = Block(id=new_id("block"), kind=BlockKind.DIALOGUE, text="Nope.", dialogue_pair_id=new_id("dialogue_pair"))
    broken = type(sample_document).from_dict(
        {**sample_document.to_dict(), "blocks": [block.to_dict() for block in (orphan, *sample_document.blocks)]}
    )
    with pytest.raises(SemanticValidationError, match="dialogue must follow"):
        semantic_validate(broken)


def test_selection_anchor_resolves_and_transforms(sample_document: ScreenplayDocument) -> None:
    action = sample_document.blocks[1]
    anchor = SelectionAnchor(block_id=action.id, offset=3)
    assert resolve_anchor(sample_document, anchor) == action.text[:3]
    deleted = transform_anchor(
        anchor,
        ChangeSetOperation(id="op-0", order=0, op_type=OperationType.DELETE_BLOCK, target_id=action.id),
    )
    assert deleted is None
    shortened = transform_anchor(
        anchor,
        ChangeSetOperation(
            id="op-1",
            order=0,
            op_type=OperationType.UPDATE_BLOCK,
            target_id=action.id,
            payload={"text": "Hi"},
        ),
    )
    assert shortened is not None
    assert shortened.offset == 2
