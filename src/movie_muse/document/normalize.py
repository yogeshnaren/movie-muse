"""Deterministic normalization of a ScreenplayDocument.

Normalization is a pure function: same input bytes always yield the same
canonical tree. It does not invent story content. It does Unicode NFC, trims
block text, orders sequences, and drops dangling annotation references that
would fail validation after an operation.
"""

from __future__ import annotations

import unicodedata
from dataclasses import replace

from movie_muse.schemas.api import Block, ScreenplayDocument


def normalize(document: ScreenplayDocument) -> ScreenplayDocument:
    sequences = tuple(
        sorted(
            (
                replace(sequence, title=_nfc_strip(sequence.title))
                for sequence in document.sequences
            ),
            key=lambda sequence: (sequence.order, sequence.id),
        )
    )
    blocks = tuple(_normalize_block(block) for block in document.blocks)
    block_ids = {block.id for block in blocks}
    notes = tuple(note for note in document.notes if note.block_id in block_ids)
    marks = tuple(mark for mark in document.revision_marks if mark.block_id in block_ids)
    tags = tuple(tag for tag in document.production_tags if tag.block_id in block_ids)
    attachments = tuple(
        attachment
        for attachment in document.attachments
        if attachment.block_id is None or attachment.block_id in block_ids
    )
    normalized = replace(
        document,
        title=_nfc_strip(document.title),
        sequences=sequences,
        blocks=blocks,
        notes=notes,
        revision_marks=marks,
        production_tags=tags,
        attachments=attachments,
    )
    normalized.validate()
    return normalized


def _nfc_strip(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip()


def _normalize_block(block: Block) -> Block:
    text = "" if block.kind.value == "page_break" else _nfc_strip(block.text)
    scene_number = _nfc_strip(block.scene_number) if block.scene_number else None
    return replace(block, text=text, scene_number=scene_number or None)
