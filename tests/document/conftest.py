"""Pytest fixtures for the document kernel."""

from __future__ import annotations

import pytest

from movie_muse.schemas.api import (
    Block,
    BlockKind,
    Note,
    ProductionTag,
    RevisionMark,
    ScreenplayDocument,
    Sequence,
    new_id,
)


def make_sample_document() -> ScreenplayDocument:
    scene_id = new_id("scene")
    cue_id = new_id("character_cue")
    pair_id = new_id("dialogue_pair")
    heading = Block(
        id=new_id("block"),
        kind=BlockKind.SCENE_HEADING,
        text="INT. KITCHEN - DAY",
        scene_id=scene_id,
        scene_number="1",
    )
    action = Block(id=new_id("block"), kind=BlockKind.ACTION, text="Ada studies the lock.")
    character = Block(
        id=new_id("block"),
        kind=BlockKind.CHARACTER,
        text="ADA",
        character_cue_id=cue_id,
        dialogue_pair_id=pair_id,
    )
    dialogue = Block(
        id=new_id("block"),
        kind=BlockKind.DIALOGUE,
        text="It's not locked.",
        dialogue_pair_id=pair_id,
    )
    note = Note(
        id=new_id("note"),
        block_id=heading.id,
        author_actor_id=new_id("actor"),
        text="confirm kitchen",
        created_at="2026-09-01T00:00:00Z",
    )
    tag = ProductionTag(
        id=new_id("production_tag"),
        block_id=heading.id,
        department="props",
        tag_type="required_prop",
        value="lockpick set",
    )
    mark = RevisionMark(
        id=new_id("revision_mark"),
        block_id=action.id,
        revision_color="blue",
        revision_label="2nd Blue",
        created_at="2026-09-01T00:00:00Z",
    )
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=new_id("project"),
        title="Pilot",
        sequences=(Sequence(id=new_id("sequence"), title="Act One", order=0, scene_ids=(scene_id,)),),
        blocks=(heading, action, character, dialogue),
        notes=(note,),
        production_tags=(tag,),
        revision_marks=(mark,),
        base_revision_id=new_id("revision"),
    )
    document.validate()
    return document


@pytest.fixture()
def sample_document() -> ScreenplayDocument:
    return make_sample_document()
