"""ScreenplayDocument — a typed block tree, never arbitrary rich text.

Architecture §3.1 requires the eleven minimum block types below plus stable
IDs for document, sequence, block, inline span, scene, character cue,
dialogue pair, note, revision mark, production tag, and attachment. This
module defines the schema-level shape of that tree; the full typed
operations/normalization/diff kernel belongs to MM-003, which depends on this
package.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar

from movie_muse.schemas.serialization import (
    dataclass_from_dict,
    dataclass_to_dict,
    sealed,
    tuple_of,
)


class BlockKind(str, Enum):
    SCENE_HEADING = "scene_heading"
    ACTION = "action"
    CHARACTER = "character"
    PARENTHETICAL = "parenthetical"
    DIALOGUE = "dialogue"
    TRANSITION = "transition"
    SHOT = "shot"
    GENERAL = "general"
    LYRICS = "lyrics"
    PAGE_BREAK = "page_break"
    TITLE_PAGE_ELEMENT = "title_page_element"


#: Block kinds that carry no free-form body text of their own.
_TEXTLESS_KINDS = frozenset({BlockKind.PAGE_BREAK})


@sealed
@dataclass(frozen=True, slots=True)
class InlineSpan:
    """An annotation over a text range within a block (note/emphasis/etc.)."""

    id: str
    start_offset: int
    end_offset: int
    span_kind: str
    ref_id: str | None = None
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        if self.start_offset < 0 or self.end_offset < self.start_offset:
            raise ValueError("inline span offsets must satisfy 0 <= start <= end")

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InlineSpan:
        return dataclass_from_dict(cls, data)


@sealed
@dataclass(frozen=True, slots=True)
class Block:
    """One node of the screenplay's typed block tree.

    ``kind`` is restricted to :class:`BlockKind`, which closes the tree to
    the eleven professional element types instead of allowing arbitrary rich
    text. ``unknown_extensions`` preserves lossless round-trip of
    non-standard FDX/Fountain extensions the kernel does not model yet,
    without smuggling them into typed fields.
    """

    id: str
    kind: BlockKind
    text: str
    spans: tuple[InlineSpan, ...] = ()
    scene_id: str | None = None
    scene_number: str | None = None
    character_cue_id: str | None = None
    dialogue_pair_id: str | None = None
    is_dual_dialogue: bool = False
    dual_dialogue_group_id: str | None = None
    is_forced: bool = False
    is_continued: bool = False
    is_extension: bool = False
    is_boneyard: bool = False
    production_tag_ids: tuple[str, ...] = ()
    note_ids: tuple[str, ...] = ()
    revision_mark_ids: tuple[str, ...] = ()
    attachment_ids: tuple[str, ...] = ()
    unknown_extensions: dict[str, Any] = field(default_factory=dict)
    schema_version: str = "1.0"

    def validate(self) -> None:
        if self.kind == BlockKind.SCENE_HEADING and not self.scene_id:
            raise ValueError("scene_heading block requires scene_id")
        if self.kind == BlockKind.CHARACTER and not self.character_cue_id:
            raise ValueError("character block requires character_cue_id")
        if self.kind == BlockKind.DIALOGUE and not self.dialogue_pair_id:
            raise ValueError("dialogue block requires dialogue_pair_id")
        if self.kind in _TEXTLESS_KINDS and self.text:
            raise ValueError(f"{self.kind.value} block must not carry body text")
        if self.is_dual_dialogue and not self.dual_dialogue_group_id:
            raise ValueError("dual dialogue block requires dual_dialogue_group_id")

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Block:
        return dataclass_from_dict(
            cls,
            data,
            converters={
                "kind": BlockKind,
                "spans": tuple_of(InlineSpan.from_dict),
                "production_tag_ids": tuple,
                "note_ids": tuple,
                "revision_mark_ids": tuple,
                "attachment_ids": tuple,
            },
        )


@sealed
@dataclass(frozen=True, slots=True)
class Note:
    id: str
    block_id: str
    author_actor_id: str
    text: str
    created_at: str
    resolved: bool = False
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Note:
        return dataclass_from_dict(cls, data)


@sealed
@dataclass(frozen=True, slots=True)
class RevisionMark:
    id: str
    block_id: str
    revision_color: str
    revision_label: str
    created_at: str
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RevisionMark:
        return dataclass_from_dict(cls, data)


@sealed
@dataclass(frozen=True, slots=True)
class ProductionTag:
    id: str
    block_id: str
    department: str
    tag_type: str
    value: str
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProductionTag:
        return dataclass_from_dict(cls, data)


@sealed
@dataclass(frozen=True, slots=True)
class Attachment:
    id: str
    kind: str
    uri: str
    checksum: str
    block_id: str | None = None
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Attachment:
        return dataclass_from_dict(cls, data)


@sealed
@dataclass(frozen=True, slots=True)
class Sequence:
    id: str
    title: str
    order: int
    scene_ids: tuple[str, ...] = ()
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Sequence:
        return dataclass_from_dict(cls, data, converters={"scene_ids": tuple})


@sealed
@dataclass(frozen=True, slots=True)
class ScreenplayDocument:
    """The canonical, typed screenplay tree. Editor state is an adapter over
    this shape, never the other way around (architecture §3.1 and AGENTS.md).
    """

    SCHEMA_NAME: ClassVar[str] = "screenplay_document"

    id: str
    project_id: str
    title: str
    sequences: tuple[Sequence, ...]
    blocks: tuple[Block, ...]
    base_revision_id: str | None = None
    notes: tuple[Note, ...] = ()
    revision_marks: tuple[RevisionMark, ...] = ()
    production_tags: tuple[ProductionTag, ...] = ()
    attachments: tuple[Attachment, ...] = ()
    paper_size: str = "us_letter"
    style: str = "standard_screenplay"
    schema_version: str = "1.0"

    def validate(self) -> None:
        block_ids = [block.id for block in self.blocks]
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("duplicate block ids in screenplay document")
        for block in self.blocks:
            block.validate()
        block_id_set = set(block_ids)
        for note in self.notes:
            if note.block_id not in block_id_set:
                raise ValueError(f"note {note.id} references unknown block {note.block_id}")
        for mark in self.revision_marks:
            if mark.block_id not in block_id_set:
                raise ValueError(f"revision mark {mark.id} references unknown block {mark.block_id}")
        for tag in self.production_tags:
            if tag.block_id not in block_id_set:
                raise ValueError(f"production tag {tag.id} references unknown block {tag.block_id}")
        for attachment in self.attachments:
            if attachment.block_id is not None and attachment.block_id not in block_id_set:
                raise ValueError(
                    f"attachment {attachment.id} references unknown block {attachment.block_id}"
                )

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScreenplayDocument:
        return dataclass_from_dict(
            cls,
            data,
            converters={
                "sequences": tuple_of(Sequence.from_dict),
                "blocks": tuple_of(Block.from_dict),
                "notes": tuple_of(Note.from_dict),
                "revision_marks": tuple_of(RevisionMark.from_dict),
                "production_tags": tuple_of(ProductionTag.from_dict),
                "attachments": tuple_of(Attachment.from_dict),
            },
        )
