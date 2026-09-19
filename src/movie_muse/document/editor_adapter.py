"""Editor projection adapter.

The editor tree is a *projection* of ScreenplayDocument. Round-tripping must
not use editor JSON as canonical state: the kernel always reconstructs a
typed ScreenplayDocument and validates it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from movie_muse.document.normalize import normalize
from movie_muse.schemas.api import (
    Attachment,
    Block,
    BlockKind,
    Note,
    ProductionTag,
    RevisionMark,
    ScreenplayDocument,
    Sequence,
    dataclass_to_dict,
)

EDITOR_FORMAT = "movie-muse.editor.projection.v1"

_KIND_TO_EDITOR = {
    BlockKind.SCENE_HEADING: "sceneHeading",
    BlockKind.ACTION: "action",
    BlockKind.CHARACTER: "character",
    BlockKind.PARENTHETICAL: "parenthetical",
    BlockKind.DIALOGUE: "dialogue",
    BlockKind.TRANSITION: "transition",
    BlockKind.SHOT: "shot",
    BlockKind.GENERAL: "general",
    BlockKind.LYRICS: "lyrics",
    BlockKind.PAGE_BREAK: "pageBreak",
    BlockKind.TITLE_PAGE_ELEMENT: "titlePageElement",
}
_EDITOR_TO_KIND = {value: key for key, value in _KIND_TO_EDITOR.items()}


def _freeze_attrs(value: Any) -> Any:
    if isinstance(value, MappingProxyType):
        return MappingProxyType({str(key): _freeze_attrs(item) for key, item in value.items()})
    if isinstance(value, dict):
        return MappingProxyType({str(key): _freeze_attrs(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze_attrs(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class EditorNode:
    id: str
    type: str
    text: str
    attrs: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "attrs", _freeze_attrs(self.attrs))


@dataclass(frozen=True, slots=True)
class EditorProjection:
    """Non-canonical editor tree. Must not be persisted as source of truth."""

    format: str
    document_id: str
    project_id: str
    title: str
    nodes: tuple[EditorNode, ...]
    sequences: tuple[Sequence, ...]
    notes: tuple[Note, ...]
    revision_marks: tuple[RevisionMark, ...]
    production_tags: tuple[ProductionTag, ...]
    attachments: tuple[Attachment, ...]
    paper_size: str
    style: str
    base_revision_id: str | None
    schema_version: str = "1.0"


def to_editor(document: ScreenplayDocument) -> EditorProjection:
    document.validate()
    nodes = tuple(
        EditorNode(
            id=block.id,
            type=_KIND_TO_EDITOR[block.kind],
            text=block.text,
            attrs={
                "scene_id": block.scene_id,
                "scene_number": block.scene_number,
                "character_cue_id": block.character_cue_id,
                "dialogue_pair_id": block.dialogue_pair_id,
                "is_dual_dialogue": block.is_dual_dialogue,
                "dual_dialogue_group_id": block.dual_dialogue_group_id,
                "is_forced": block.is_forced,
                "is_continued": block.is_continued,
                "is_extension": block.is_extension,
                "is_boneyard": block.is_boneyard,
                "spans": [span.to_dict() for span in block.spans],
                "unknown_extensions": dict(block.unknown_extensions),
                "production_tag_ids": list(block.production_tag_ids),
                "note_ids": list(block.note_ids),
                "revision_mark_ids": list(block.revision_mark_ids),
                "attachment_ids": list(block.attachment_ids),
            },
        )
        for block in document.blocks
    )
    return EditorProjection(
        format=EDITOR_FORMAT,
        document_id=document.id,
        project_id=document.project_id,
        title=document.title,
        nodes=nodes,
        sequences=document.sequences,
        notes=document.notes,
        revision_marks=document.revision_marks,
        production_tags=document.production_tags,
        attachments=document.attachments,
        paper_size=document.paper_size,
        style=document.style,
        base_revision_id=document.base_revision_id,
        schema_version=document.schema_version,
    )


def from_editor(projection: EditorProjection) -> ScreenplayDocument:
    if projection.format != EDITOR_FORMAT:
        raise ValueError(f"unknown editor format: {projection.format!r}")
    blocks = tuple(_node_to_block(node) for node in projection.nodes)
    document = ScreenplayDocument(
        id=projection.document_id,
        project_id=projection.project_id,
        title=projection.title,
        sequences=projection.sequences,
        blocks=blocks,
        notes=projection.notes,
        revision_marks=projection.revision_marks,
        production_tags=projection.production_tags,
        attachments=projection.attachments,
        paper_size=projection.paper_size,
        style=projection.style,
        base_revision_id=projection.base_revision_id,
        schema_version=projection.schema_version,
    )
    return normalize(document)


def projection_to_dict(projection: EditorProjection) -> dict[str, Any]:
    return dataclass_to_dict(projection)


def _node_to_block(node: EditorNode) -> Block:
    kind = _EDITOR_TO_KIND.get(node.type)
    if kind is None:
        raise ValueError(f"unknown editor node type: {node.type!r}")
    attrs = dict(node.attrs)
    return Block.from_dict(
        {
            "id": node.id,
            "kind": kind.value,
            "text": node.text,
            **{key: value for key, value in attrs.items() if key != "spans" or value},
            "spans": attrs.get("spans") or (),
        }
    )
