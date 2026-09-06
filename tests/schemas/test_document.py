"""ScreenplayDocument: a typed, closed block tree with stable IDs.

Covers MM-002 acceptance criteria 3 and 7: minimum block types, stable IDs
for document/sequence/block/inline-span/scene/character-cue/dialogue-pair/
note/revision-mark/production-tag/attachment, and rejection of malformed
trees rather than silently accepting arbitrary rich text.
"""

from __future__ import annotations

import pytest

from movie_muse.schemas import ids, validators
from movie_muse.schemas.document import (
    Attachment,
    Block,
    BlockKind,
    InlineSpan,
    Note,
    ProductionTag,
    RevisionMark,
    ScreenplayDocument,
    Sequence,
)

ALL_BLOCK_KINDS = {
    "scene_heading",
    "action",
    "character",
    "parenthetical",
    "dialogue",
    "transition",
    "shot",
    "general",
    "lyrics",
    "page_break",
    "title_page_element",
}


def test_block_kind_enum_matches_the_architecture_minimum_set() -> None:
    assert {kind.value for kind in BlockKind} == ALL_BLOCK_KINDS


def _sample_document() -> ScreenplayDocument:
    scene_id = ids.new_id("scene")
    cue_id = ids.new_id("character_cue")
    dialogue_pair_id = ids.new_id("dialogue_pair")
    heading = Block(id=ids.new_id("block"), kind=BlockKind.SCENE_HEADING, text="INT. KITCHEN - DAY", scene_id=scene_id)
    action = Block(id=ids.new_id("block"), kind=BlockKind.ACTION, text="Ada studies the lock.")
    character = Block(
        id=ids.new_id("block"), kind=BlockKind.CHARACTER, text="ADA", character_cue_id=cue_id,
        dialogue_pair_id=dialogue_pair_id,
    )
    dialogue = Block(
        id=ids.new_id("block"), kind=BlockKind.DIALOGUE, text="It's not locked.", dialogue_pair_id=dialogue_pair_id,
    )
    note = Note(
        id=ids.new_id("note"), block_id=heading.id, author_actor_id=ids.new_id("actor"),
        text="confirm this is the right kitchen", created_at="2026-09-01T00:00:00Z",
    )
    return ScreenplayDocument(
        id=ids.new_id("document"),
        project_id=ids.new_id("project"),
        title="Pilot",
        sequences=(Sequence(id=ids.new_id("sequence"), title="Act One", order=0, scene_ids=(scene_id,)),),
        blocks=(heading, action, character, dialogue),
        notes=(note,),
    )


def test_valid_document_passes_python_and_schema_validation() -> None:
    document = _sample_document()
    document.validate()
    validators.validate_payload("screenplay_document", document.to_dict())


def test_round_trip_through_dict_preserves_structure() -> None:
    document = _sample_document()
    restored = ScreenplayDocument.from_dict(document.to_dict())
    assert restored == document


def test_scene_heading_without_scene_id_is_rejected() -> None:
    block = Block(id=ids.new_id("block"), kind=BlockKind.SCENE_HEADING, text="INT. X")
    with pytest.raises(ValueError, match="scene_id"):
        block.validate()


def test_character_block_without_cue_id_is_rejected() -> None:
    block = Block(id=ids.new_id("block"), kind=BlockKind.CHARACTER, text="ADA")
    with pytest.raises(ValueError, match="character_cue_id"):
        block.validate()


def test_dialogue_block_without_pair_id_is_rejected() -> None:
    block = Block(id=ids.new_id("block"), kind=BlockKind.DIALOGUE, text="Hello.")
    with pytest.raises(ValueError, match="dialogue_pair_id"):
        block.validate()


def test_page_break_block_must_not_carry_body_text() -> None:
    block = Block(id=ids.new_id("block"), kind=BlockKind.PAGE_BREAK, text="unexpected text")
    with pytest.raises(ValueError, match="page_break"):
        block.validate()


def test_dual_dialogue_requires_a_group_id() -> None:
    block = Block(id=ids.new_id("block"), kind=BlockKind.DIALOGUE, text="Hi", dialogue_pair_id=ids.new_id("dialogue_pair"), is_dual_dialogue=True)
    with pytest.raises(ValueError, match="dual_dialogue_group_id"):
        block.validate()


def test_duplicate_block_ids_are_rejected() -> None:
    document = _sample_document()
    duplicated = document.blocks + (document.blocks[0],)
    broken = ScreenplayDocument(
        id=document.id, project_id=document.project_id, title=document.title,
        sequences=document.sequences, blocks=duplicated,
    )
    with pytest.raises(ValueError, match="duplicate block ids"):
        broken.validate()


def test_note_referencing_unknown_block_is_rejected() -> None:
    document = _sample_document()
    dangling_note = Note(
        id=ids.new_id("note"), block_id=ids.new_id("block"), author_actor_id=ids.new_id("actor"),
        text="orphaned", created_at="2026-09-01T00:00:00Z",
    )
    broken = ScreenplayDocument(
        id=document.id, project_id=document.project_id, title=document.title,
        sequences=document.sequences, blocks=document.blocks, notes=(dangling_note,),
    )
    with pytest.raises(ValueError, match="unknown block"):
        broken.validate()


def test_revision_mark_and_production_tag_and_attachment_reference_stable_ids() -> None:
    document = _sample_document()
    target_block_id = document.blocks[0].id
    mark = RevisionMark(
        id=ids.new_id("revision_mark"), block_id=target_block_id, revision_color="blue",
        revision_label="2nd Blue Revision", created_at="2026-09-01T00:00:00Z",
    )
    tag = ProductionTag(
        id=ids.new_id("production_tag"), block_id=target_block_id, department="props",
        tag_type="required_prop", value="lockpick set",
    )
    attachment = Attachment(
        id=ids.new_id("attachment"), block_id=target_block_id, kind="reference_image",
        uri="local://ref/kitchen.png", checksum="sha256:abc",
    )
    enriched = ScreenplayDocument(
        id=document.id, project_id=document.project_id, title=document.title,
        sequences=document.sequences, blocks=document.blocks,
        revision_marks=(mark,), production_tags=(tag,), attachments=(attachment,),
    )
    enriched.validate()
    validators.validate_payload("screenplay_document", enriched.to_dict())


def test_inline_span_offsets_must_be_ordered() -> None:
    with pytest.raises(ValueError):
        InlineSpan(id=ids.new_id("inline_span"), start_offset=5, end_offset=1, span_kind="note")


def test_block_unknown_extensions_are_recursively_immutable() -> None:
    block = Block(
        id=ids.new_id("block"),
        kind=BlockKind.ACTION,
        text="Ada studies the lock.",
        unknown_extensions={"vendor": {"flag": "before"}},
    )
    with pytest.raises(TypeError):
        block.unknown_extensions["vendor"]["flag"] = "after"  # type: ignore[index]
