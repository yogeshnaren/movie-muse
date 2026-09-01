"""Apply immutable typed operations to a ScreenplayDocument.

Each function returns a new document. The input is never mutated. Editor JSON
is not accepted here — callers must already hold a typed ScreenplayDocument.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from movie_muse.document.errors import InvalidOperationError
from movie_muse.schemas.api import (
    Block,
    ChangeSet,
    ChangeSetOperation,
    OperationType,
    ScreenplayDocument,
    Sequence,
)


def apply_change_set(document: ScreenplayDocument, change_set: ChangeSet) -> ScreenplayDocument:
    """Apply every operation in order. Replay of the same ChangeSet is deterministic."""

    current = document
    for operation in change_set.operations:
        current = apply_operation(current, operation)
    current.validate()
    return current


def apply_operation(document: ScreenplayDocument, operation: ChangeSetOperation) -> ScreenplayDocument:
    handlers = {
        OperationType.INSERT_BLOCK: _insert_block,
        OperationType.DELETE_BLOCK: _delete_block,
        OperationType.UPDATE_BLOCK: _update_block,
        OperationType.MOVE_BLOCK: _move_block,
        OperationType.INSERT_SCENE: _insert_scene,
        OperationType.UPDATE_METADATA: _update_metadata,
    }
    handler = handlers.get(operation.op_type)
    if handler is None:
        raise InvalidOperationError(f"unsupported operation type: {operation.op_type!r}")
    return handler(document, operation)


def _payload(operation: ChangeSetOperation) -> Mapping[str, Any]:
    return operation.payload or {}


def _index_of(document: ScreenplayDocument, block_id: str) -> int:
    for index, block in enumerate(document.blocks):
        if block.id == block_id:
            return index
    raise InvalidOperationError(f"unknown block id: {block_id}")


def _insert_block(document: ScreenplayDocument, operation: ChangeSetOperation) -> ScreenplayDocument:
    payload = _payload(operation)
    raw_block = payload.get("block")
    if not isinstance(raw_block, Mapping):
        raise InvalidOperationError("insert_block requires payload.block")
    block = Block.from_dict(dict(raw_block))
    if block.id != operation.target_id:
        raise InvalidOperationError("insert_block target_id must match payload.block.id")
    if any(existing.id == block.id for existing in document.blocks):
        raise InvalidOperationError(f"duplicate block id: {block.id}")

    blocks = list(document.blocks)
    if "index" in payload:
        index = int(payload["index"])
        if index < 0 or index > len(blocks):
            raise InvalidOperationError("insert_block index out of range")
        blocks.insert(index, block)
    elif "after_id" in payload:
        after = str(payload["after_id"])
        blocks.insert(_index_of(document, after) + 1, block)
    else:
        blocks.append(block)
    return replace(document, blocks=tuple(blocks))


def _delete_block(document: ScreenplayDocument, operation: ChangeSetOperation) -> ScreenplayDocument:
    index = _index_of(document, operation.target_id)
    removed = document.blocks[index]
    blocks = document.blocks[:index] + document.blocks[index + 1 :]
    notes = tuple(note for note in document.notes if note.block_id != removed.id)
    marks = tuple(mark for mark in document.revision_marks if mark.block_id != removed.id)
    tags = tuple(tag for tag in document.production_tags if tag.block_id != removed.id)
    attachments = tuple(
        attachment
        for attachment in document.attachments
        if attachment.block_id != removed.id
    )
    return replace(
        document,
        blocks=blocks,
        notes=notes,
        revision_marks=marks,
        production_tags=tags,
        attachments=attachments,
    )


def _update_block(document: ScreenplayDocument, operation: ChangeSetOperation) -> ScreenplayDocument:
    index = _index_of(document, operation.target_id)
    current = document.blocks[index]
    merged = current.to_dict()
    for key, value in _payload(operation).items():
        if key in {"id", "schema_version"}:
            raise InvalidOperationError("update_block cannot change id or schema_version")
        merged[key] = value
    updated = Block.from_dict(merged)
    if updated.id != current.id:
        raise InvalidOperationError("update_block cannot reassign block id")
    blocks = document.blocks[:index] + (updated,) + document.blocks[index + 1 :]
    return replace(document, blocks=blocks)


def _move_block(document: ScreenplayDocument, operation: ChangeSetOperation) -> ScreenplayDocument:
    payload = _payload(operation)
    if "index" not in payload:
        raise InvalidOperationError("move_block requires payload.index")
    source = _index_of(document, operation.target_id)
    dest = int(payload["index"])
    blocks = list(document.blocks)
    block = blocks.pop(source)
    if dest < 0 or dest > len(blocks):
        raise InvalidOperationError("move_block index out of range")
    blocks.insert(dest, block)
    return replace(document, blocks=tuple(blocks))


def _insert_scene(document: ScreenplayDocument, operation: ChangeSetOperation) -> ScreenplayDocument:
    payload = _payload(operation)
    scene_id = str(payload.get("scene_id") or operation.target_id)
    sequence_id = payload.get("sequence_id")
    if not sequence_id:
        raise InvalidOperationError("insert_scene requires payload.sequence_id")
    sequences: list[Sequence] = []
    found = False
    for sequence in document.sequences:
        if sequence.id == sequence_id:
            if scene_id in sequence.scene_ids:
                raise InvalidOperationError(f"scene already present: {scene_id}")
            sequences.append(replace(sequence, scene_ids=sequence.scene_ids + (scene_id,)))
            found = True
        else:
            sequences.append(sequence)
    if not found:
        raise InvalidOperationError(f"unknown sequence id: {sequence_id}")
    return replace(document, sequences=tuple(sequences))


def _update_metadata(document: ScreenplayDocument, operation: ChangeSetOperation) -> ScreenplayDocument:
    payload = dict(_payload(operation))
    allowed = {"title", "paper_size", "style", "base_revision_id"}
    unknown = set(payload) - allowed
    if unknown:
        raise InvalidOperationError(f"update_metadata unknown fields: {sorted(unknown)}")
    return replace(document, **payload)
