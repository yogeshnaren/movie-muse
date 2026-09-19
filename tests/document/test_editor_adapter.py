"""Editor JSON is a projection, never canonical state."""

from __future__ import annotations

import pytest

from movie_muse.document.api import from_editor, projection_to_dict, to_editor
from movie_muse.schemas.api import Block, BlockKind, ScreenplayDocument, new_id


def test_editor_round_trip_preserves_typed_document(sample_document: ScreenplayDocument) -> None:
    projection = to_editor(sample_document)
    restored = from_editor(projection)
    assert restored.id == sample_document.id
    assert [block.kind for block in restored.blocks] == [block.kind for block in sample_document.blocks]
    assert [block.text for block in restored.blocks] == [block.text for block in sample_document.blocks]


def test_mutating_editor_dict_does_not_mutate_canonical_document(sample_document: ScreenplayDocument) -> None:
    original_text = sample_document.blocks[1].text
    projection = to_editor(sample_document)
    as_dict = projection_to_dict(projection)
    as_dict["nodes"][1]["text"] = "MUTATED EDITOR JSON"
    assert sample_document.blocks[1].text == original_text
    with pytest.raises(TypeError):
        projection.nodes[1].attrs["scene_id"] = "tampered"


def test_from_editor_rejects_unknown_format(sample_document: ScreenplayDocument) -> None:
    projection = to_editor(sample_document)
    object.__setattr__(projection, "format", "prosemirror-json")
    with pytest.raises(ValueError, match="unknown editor format"):
        from_editor(projection)


def test_all_professional_block_types_round_trip_through_editor() -> None:
    scene_id = new_id("scene")
    cue_id = new_id("character_cue")
    pair_id = new_id("dialogue_pair")
    group_id = new_id("dialogue_pair")
    blocks = (
        Block(id=new_id("block"), kind=BlockKind.TITLE_PAGE_ELEMENT, text="PILOT"),
        Block(id=new_id("block"), kind=BlockKind.SCENE_HEADING, text="INT. HALL - NIGHT", scene_id=scene_id, scene_number="2A"),
        Block(id=new_id("block"), kind=BlockKind.ACTION, text="Rain."),
        Block(
            id=new_id("block"),
            kind=BlockKind.CHARACTER,
            text="ADA",
            character_cue_id=cue_id,
            dialogue_pair_id=pair_id,
            is_dual_dialogue=True,
            dual_dialogue_group_id=group_id,
        ),
        Block(
            id=new_id("block"),
            kind=BlockKind.PARENTHETICAL,
            text="(quiet)",
            is_dual_dialogue=True,
            dual_dialogue_group_id=group_id,
        ),
        Block(
            id=new_id("block"),
            kind=BlockKind.DIALOGUE,
            text="Wait.",
            dialogue_pair_id=pair_id,
            is_dual_dialogue=True,
            dual_dialogue_group_id=group_id,
        ),
        Block(id=new_id("block"), kind=BlockKind.TRANSITION, text="CUT TO:"),
        Block(id=new_id("block"), kind=BlockKind.SHOT, text="CLOSE ON"),
        Block(id=new_id("block"), kind=BlockKind.GENERAL, text="Author note"),
        Block(id=new_id("block"), kind=BlockKind.LYRICS, text="la la"),
        Block(id=new_id("block"), kind=BlockKind.PAGE_BREAK, text=""),
        Block(id=new_id("block"), kind=BlockKind.ACTION, text="Omitted beat.", is_boneyard=True),
    )
    # second dual-dialogue column
    cue_b = new_id("character_cue")
    pair_b = new_id("dialogue_pair")
    dual_b = (
        Block(
            id=new_id("block"),
            kind=BlockKind.CHARACTER,
            text="BEN",
            character_cue_id=cue_b,
            dialogue_pair_id=pair_b,
            is_dual_dialogue=True,
            dual_dialogue_group_id=group_id,
        ),
        Block(
            id=new_id("block"),
            kind=BlockKind.DIALOGUE,
            text="Go.",
            dialogue_pair_id=pair_b,
            is_dual_dialogue=True,
            dual_dialogue_group_id=group_id,
        ),
    )
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=new_id("project"),
        title="全景 café",
        sequences=(),
        blocks=blocks[:6] + dual_b + blocks[6:],
    )
    restored = from_editor(to_editor(document))
    assert {block.kind for block in restored.blocks} == set(BlockKind)
    assert any(block.is_boneyard for block in restored.blocks)
    assert any(block.is_dual_dialogue for block in restored.blocks)
    assert restored.title == "全景 café"
