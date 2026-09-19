"""Page breaking, MORE/CONT'D, title pages, and wrap."""

from __future__ import annotations

from movie_muse.layout.api import LayoutService
from movie_muse.layout.wrap import wrap_text
from movie_muse.schemas.api import Block, BlockKind, ScreenplayDocument, Sequence, new_id
from movie_muse.testkit.api import FixtureCatalog


def test_wrap_is_width_bounded() -> None:
    lines = wrap_text("alpha beta gamma delta epsilon", 10)
    assert all(len(line) <= 10 for line in lines)
    assert "alpha" in " ".join(lines)


def test_forced_page_break_splits_pages() -> None:
    scene = new_id("scene")
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=new_id("project"),
        title="Breaks",
        sequences=(Sequence(id=new_id("sequence"), title="A", order=0, scene_ids=(scene,)),),
        blocks=(
            Block(
                id=new_id("block"),
                kind=BlockKind.SCENE_HEADING,
                text="INT. ROOM - DAY",
                scene_id=scene,
                scene_number="1",
            ),
            Block(id=new_id("block"), kind=BlockKind.ACTION, text="Ada waits.", scene_id=scene),
            Block(id=new_id("block"), kind=BlockKind.PAGE_BREAK, text="", is_forced=True),
            Block(id=new_id("block"), kind=BlockKind.ACTION, text="Night falls.", scene_id=scene),
        ),
    )
    result = LayoutService().layout(document)
    script = result.script_pages()
    assert len(script) >= 2
    texts = [[line.text for line in page.lines] for page in script]
    assert any("Ada waits." in page for page in texts)
    assert any("Night falls." in page for page in texts)


def test_long_dialogue_emits_more_and_contd() -> None:
    scene = new_id("scene")
    cue = new_id("character_cue")
    pair = new_id("dialogue_pair")
    speech = " ".join(["word"] * 400)
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=new_id("project"),
        title="Speech",
        sequences=(Sequence(id=new_id("sequence"), title="A", order=0, scene_ids=(scene,)),),
        blocks=(
            Block(
                id=new_id("block"),
                kind=BlockKind.SCENE_HEADING,
                text="INT. HALL - DAY",
                scene_id=scene,
                scene_number="1",
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.CHARACTER,
                text="ADA",
                scene_id=scene,
                character_cue_id=cue,
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.DIALOGUE,
                text=speech,
                scene_id=scene,
                dialogue_pair_id=pair,
                character_cue_id=cue,
            ),
        ),
    )
    result = LayoutService().layout(document)
    kinds = [line.line_kind for line in result.lines]
    assert "more" in kinds
    assert "contd" in kinds
    assert any(line.text == "(MORE)" for line in result.lines)
    assert any("(CONT'D)" in line.text for line in result.lines)
    assert any(line.line_kind == "footer" and line.text == "(CONTINUED)" for line in result.lines)


def test_harbor_title_page_is_separate() -> None:
    document = FixtureCatalog().get("feature_complete_harbor").document
    result = LayoutService().layout(document)
    assert result.pages[0].is_title_page
    assert result.script_pages()
    assert any(line.line_kind == "title" for line in result.pages[0].lines)
    assert any(line.line_kind == "dual" for line in result.lines)
    assert any(line.line_kind == "header" for line in result.script_pages()[0].lines)
