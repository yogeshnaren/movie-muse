"""Deterministic screenplay fixture builders. IDs are seed-stable."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from movie_muse.schemas.api import (
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
from movie_muse.testkit.ids import IdMint
from movie_muse.testkit.types import FixtureClass

CREATED_AT = "2026-09-01T00:00:00Z"

LICENSE_BODY = """# License and consent

- License: CC0 1.0 Universal (public domain dedication)
- Origin: Original work authored for the Movie Muse golden-fixture corpus.
  Not copied from any commercial screenplay, novel, or competitor file.
- Consent: Explicit dedication to the Movie Muse test corpus. No third-party
  talent, likeness, or private chain-of-thought is included.
- Permitted uses: retrieval, citation, generation tests, export disclosure.
- Training: not permitted. Fixture consent is not training consent.
- Synthetic audiences: any later evaluation using these texts is a hypothesis,
  not a human audience sample.
"""


@dataclass(frozen=True)
class BuiltFixture:
    fixture_id: str
    fixture_class: FixtureClass
    title: str
    edges: tuple[str, ...]
    document: ScreenplayDocument
    rights: dict[str, Any]
    extras: dict[str, Any]


def _rights(*, classification: str, license_name: str = "CC0-1.0") -> dict[str, Any]:
    return {
        "classification": classification,
        "license": license_name,
        "consent": "explicit_fixture_dedication",
        "origin": "original_authored_for_movie_muse",
        "allow_training": False,
        "permitted_uses": [
            "retrieval",
            "citation",
            "generation",
            "export_disclosure",
        ],
    }


def build_small_kitchen() -> BuiltFixture:
    mint = IdMint(0)
    actor_id = mint.schema("actor")
    project_id = mint.schema("project")
    document_id = mint.schema("document")
    revision_id = mint.schema("revision")
    sequence_id = mint.schema("sequence")
    scene_id = mint.schema("scene")
    cue_id = mint.schema("character_cue")
    pair_id = mint.schema("dialogue_pair")
    title = Block(
        id=mint.schema("block"),
        kind=BlockKind.TITLE_PAGE_ELEMENT,
        text="THE LOCK",
    )
    written = Block(
        id=mint.schema("block"),
        kind=BlockKind.TITLE_PAGE_ELEMENT,
        text="Written by Jordan Hale",
    )
    heading = Block(
        id=mint.schema("block"),
        kind=BlockKind.SCENE_HEADING,
        text="INT. KITCHEN - DAY",
        scene_id=scene_id,
        scene_number="1",
    )
    action = Block(
        id=mint.schema("block"),
        kind=BlockKind.ACTION,
        text="Ada studies the lock.",
        scene_id=scene_id,
    )
    character = Block(
        id=mint.schema("block"),
        kind=BlockKind.CHARACTER,
        text="ADA",
        character_cue_id=cue_id,
        dialogue_pair_id=pair_id,
        scene_id=scene_id,
    )
    parenthetical = Block(
        id=mint.schema("block"),
        kind=BlockKind.PARENTHETICAL,
        text="quietly",
        dialogue_pair_id=pair_id,
        scene_id=scene_id,
    )
    dialogue = Block(
        id=mint.schema("block"),
        kind=BlockKind.DIALOGUE,
        text="It's not locked.",
        dialogue_pair_id=pair_id,
        scene_id=scene_id,
    )
    transition = Block(
        id=mint.schema("block"),
        kind=BlockKind.TRANSITION,
        text="CUT TO:",
        scene_id=scene_id,
    )
    document = ScreenplayDocument(
        id=document_id,
        project_id=project_id,
        title="The Lock",
        sequences=(Sequence(id=sequence_id, title="Cold Open", order=0, scene_ids=(scene_id,)),),
        blocks=(title, written, heading, action, character, parenthetical, dialogue, transition),
        base_revision_id=revision_id,
        notes=(
            Note(
                id=mint.schema("note"),
                block_id=heading.id,
                author_actor_id=actor_id,
                text="Keep the kitchen practical.",
                created_at=CREATED_AT,
            ),
        ),
    )
    document.validate()
    return BuiltFixture(
        fixture_id="small_kitchen",
        fixture_class=FixtureClass.SMALL,
        title="The Lock",
        edges=(
            "title_page",
            "scene_heading",
            "action",
            "character",
            "dialogue",
            "parenthetical",
            "transition",
            "notes",
        ),
        document=document,
        rights=_rights(classification="user_owned"),
        extras={"owner_actor_id": actor_id},
    )


def build_feature_complete_harbor() -> BuiltFixture:
    mint = IdMint(100)
    actor_id = mint.schema("actor")
    project_id = mint.schema("project")
    document_id = mint.schema("document")
    revision_id = mint.schema("revision")
    branch_id = mint.schema("branch")
    org_id = mint.prefixed("org")
    sequence_id = mint.schema("sequence")
    scene_office = mint.schema("scene")
    scene_pier = mint.schema("scene")
    cue_jordan = mint.schema("character_cue")
    cue_mira = mint.schema("character_cue")
    pair_jordan = mint.schema("dialogue_pair")
    pair_mira = mint.schema("dialogue_pair")
    dual_group = mint.prefixed("ddg")
    note_id = mint.schema("note")
    tag_id = mint.schema("production_tag")
    mark_id = mint.schema("revision_mark")
    attachment_id = mint.schema("attachment")
    span_id = mint.schema("inline_span")

    title = Block(id=mint.schema("block"), kind=BlockKind.TITLE_PAGE_ELEMENT, text="HARBOR NIGHT")
    credit = Block(
        id=mint.schema("block"),
        kind=BlockKind.TITLE_PAGE_ELEMENT,
        text="Written by Jordan Hale",
    )
    heading_office = Block(
        id=mint.schema("block"),
        kind=BlockKind.SCENE_HEADING,
        text="INT. HARBOR OFFICE - NIGHT",
        scene_id=scene_office,
        scene_number="1",
        note_ids=(note_id,),
        production_tag_ids=(tag_id,),
    )
    action_office = Block(
        id=mint.schema("block"),
        kind=BlockKind.ACTION,
        text="Rain needles the glass. Jordan keeps the ledger closed.",
        scene_id=scene_office,
        revision_mark_ids=(mark_id,),
        spans=(
            InlineSpan(
                id=span_id,
                start_offset=0,
                end_offset=4,
                span_kind="emphasis",
            ),
        ),
    )
    jordan = Block(
        id=mint.schema("block"),
        kind=BlockKind.CHARACTER,
        text="JORDAN",
        character_cue_id=cue_jordan,
        dialogue_pair_id=pair_jordan,
        is_dual_dialogue=True,
        dual_dialogue_group_id=dual_group,
        scene_id=scene_office,
    )
    jordan_line = Block(
        id=mint.schema("block"),
        kind=BlockKind.DIALOGUE,
        text="We leave at first light.",
        dialogue_pair_id=pair_jordan,
        is_dual_dialogue=True,
        dual_dialogue_group_id=dual_group,
        scene_id=scene_office,
    )
    mira = Block(
        id=mint.schema("block"),
        kind=BlockKind.CHARACTER,
        text="MIRA",
        character_cue_id=cue_mira,
        dialogue_pair_id=pair_mira,
        is_dual_dialogue=True,
        dual_dialogue_group_id=dual_group,
        scene_id=scene_office,
    )
    mira_line = Block(
        id=mint.schema("block"),
        kind=BlockKind.DIALOGUE,
        text="The tide will not wait.",
        dialogue_pair_id=pair_mira,
        is_dual_dialogue=True,
        dual_dialogue_group_id=dual_group,
        scene_id=scene_office,
    )
    shot = Block(
        id=mint.schema("block"),
        kind=BlockKind.SHOT,
        text="CLOSE ON the unopened ledger.",
        scene_id=scene_office,
        attachment_ids=(attachment_id,),
    )
    transition = Block(
        id=mint.schema("block"),
        kind=BlockKind.TRANSITION,
        text="CUT TO:",
        scene_id=scene_office,
    )
    heading_pier = Block(
        id=mint.schema("block"),
        kind=BlockKind.SCENE_HEADING,
        text="EXT. PIER - NIGHT",
        scene_id=scene_pier,
        scene_number="2",
    )
    lyrics = Block(
        id=mint.schema("block"),
        kind=BlockKind.LYRICS,
        text="Harbor lights, keep our names.",
        scene_id=scene_pier,
    )
    general = Block(
        id=mint.schema("block"),
        kind=BlockKind.GENERAL,
        text="SUPER: Two hours before the storm.",
        scene_id=scene_pier,
    )
    page_break = Block(id=mint.schema("block"), kind=BlockKind.PAGE_BREAK, text="")
    continued = Block(
        id=mint.schema("block"),
        kind=BlockKind.CHARACTER,
        text="JORDAN",
        character_cue_id=cue_jordan,
        is_continued=True,
        scene_id=scene_pier,
    )
    continued_line = Block(
        id=mint.schema("block"),
        kind=BlockKind.DIALOGUE,
        text="Hold the line.",
        dialogue_pair_id=mint.schema("dialogue_pair"),
        is_continued=True,
        scene_id=scene_pier,
    )
    document = ScreenplayDocument(
        id=document_id,
        project_id=project_id,
        title="Harbor Night",
        sequences=(
            Sequence(
                id=sequence_id,
                title="Night Tide",
                order=0,
                scene_ids=(scene_office, scene_pier),
            ),
        ),
        blocks=(
            title,
            credit,
            heading_office,
            action_office,
            jordan,
            jordan_line,
            mira,
            mira_line,
            shot,
            transition,
            heading_pier,
            lyrics,
            general,
            page_break,
            continued,
            continued_line,
        ),
        base_revision_id=revision_id,
        notes=(
            Note(
                id=note_id,
                block_id=heading_office.id,
                author_actor_id=actor_id,
                text="Keep the rain practical, not decorative.",
                created_at=CREATED_AT,
            ),
        ),
        production_tags=(
            ProductionTag(
                id=tag_id,
                block_id=heading_office.id,
                department="art",
                tag_type="set",
                value="harbor office",
            ),
        ),
        revision_marks=(
            RevisionMark(
                id=mark_id,
                block_id=action_office.id,
                revision_color="blue",
                revision_label="Blue",
                created_at=CREATED_AT,
            ),
        ),
        attachments=(
            Attachment(
                id=attachment_id,
                kind="reference_still",
                uri="fixture://harbor-night/ledger.png",
                checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                block_id=shot.id,
            ),
        ),
    )
    document.validate()
    return BuiltFixture(
        fixture_id="feature_complete_harbor",
        fixture_class=FixtureClass.FEATURE_COMPLETE,
        title="Harbor Night",
        edges=(
            "title_page",
            "scene_heading",
            "action",
            "character",
            "dialogue",
            "dual_dialogue",
            "transition",
            "shot",
            "lyrics",
            "general_text",
            "notes",
            "tags",
            "revisions",
        ),
        document=document,
        rights=_rights(classification="user_owned"),
        extras={
            "owner_actor_id": actor_id,
            "organization_id": org_id,
            "branch_id": branch_id,
            "created_at": CREATED_AT,
            "project_title": "Harbor Night",
            "owner_display_name": "Jordan Hale",
            "organization_name": "Golden Path Studio",
        },
    )


def build_production_locked_sides() -> BuiltFixture:
    mint = IdMint(400)
    actor_id = mint.schema("actor")
    project_id = mint.schema("project")
    document_id = mint.schema("document")
    revision_id = mint.schema("revision")
    sequence_id = mint.schema("sequence")
    scene_locked = mint.schema("scene")
    scene_omitted = mint.schema("scene")
    scene_a = mint.schema("scene")
    scene_b = mint.schema("scene")
    cue_id = mint.schema("character_cue")
    pair_id = mint.schema("dialogue_pair")
    mark_id = mint.schema("revision_mark")
    tag_id = mint.schema("production_tag")

    heading_locked = Block(
        id=mint.schema("block"),
        kind=BlockKind.SCENE_HEADING,
        text="INT. SOUNDSTAGE - DAY",
        scene_id=scene_locked,
        scene_number="10",
        unknown_extensions={
            "locked_scene": True,
            "lock_revision_color": "blue",
        },
        production_tag_ids=(tag_id,),
    )
    action_locked = Block(
        id=mint.schema("block"),
        kind=BlockKind.ACTION,
        text="The set is frozen. No one moves a mark.",
        scene_id=scene_locked,
        unknown_extensions={"locked_page": True, "page_lock": "10"},
        revision_mark_ids=(mark_id,),
    )
    locked_break = Block(
        id=mint.schema("block"),
        kind=BlockKind.PAGE_BREAK,
        text="",
        is_forced=True,
        unknown_extensions={"locked_page": True, "page_number": "10"},
    )
    omitted_heading = Block(
        id=mint.schema("block"),
        kind=BlockKind.SCENE_HEADING,
        text="INT. CUT SCENE - NIGHT",
        scene_id=scene_omitted,
        scene_number="11",
        is_boneyard=True,
        unknown_extensions={"omitted_scene": True, "omitted_reason": "production_cut"},
    )
    omitted_action = Block(
        id=mint.schema("block"),
        kind=BlockKind.ACTION,
        text="OMITTED.",
        scene_id=scene_omitted,
        is_boneyard=True,
        unknown_extensions={"omitted_scene": True},
    )
    heading_a = Block(
        id=mint.schema("block"),
        kind=BlockKind.SCENE_HEADING,
        text="EXT. BACKLOT - DAY",
        scene_id=scene_a,
        scene_number="12A",
        unknown_extensions={"ab_scene": "A"},
    )
    action_a = Block(
        id=mint.schema("block"),
        kind=BlockKind.ACTION,
        text="A second unit covers the insert.",
        scene_id=scene_a,
    )
    heading_b = Block(
        id=mint.schema("block"),
        kind=BlockKind.SCENE_HEADING,
        text="EXT. BACKLOT - DUSK",
        scene_id=scene_b,
        scene_number="12B",
        unknown_extensions={"ab_scene": "B"},
    )
    character = Block(
        id=mint.schema("block"),
        kind=BlockKind.CHARACTER,
        text="AD",
        character_cue_id=cue_id,
        dialogue_pair_id=pair_id,
        scene_id=scene_b,
    )
    dialogue = Block(
        id=mint.schema("block"),
        kind=BlockKind.DIALOGUE,
        text="Scene 12B is the holdover.",
        dialogue_pair_id=pair_id,
        scene_id=scene_b,
    )
    document = ScreenplayDocument(
        id=document_id,
        project_id=project_id,
        title="Locked Sides",
        sequences=(
            Sequence(
                id=sequence_id,
                title="Production Pages",
                order=0,
                scene_ids=(scene_locked, scene_omitted, scene_a, scene_b),
            ),
        ),
        blocks=(
            heading_locked,
            action_locked,
            locked_break,
            omitted_heading,
            omitted_action,
            heading_a,
            action_a,
            heading_b,
            character,
            dialogue,
        ),
        base_revision_id=revision_id,
        production_tags=(
            ProductionTag(
                id=tag_id,
                block_id=heading_locked.id,
                department="ad",
                tag_type="lock",
                value="scene 10 locked",
            ),
        ),
        revision_marks=(
            RevisionMark(
                id=mark_id,
                block_id=action_locked.id,
                revision_color="blue",
                revision_label="Blue",
                created_at=CREATED_AT,
            ),
        ),
        notes=(
            Note(
                id=mint.schema("note"),
                block_id=heading_locked.id,
                author_actor_id=actor_id,
                text="Do not unlock without production.",
                created_at=CREATED_AT,
            ),
        ),
    )
    document.validate()
    return BuiltFixture(
        fixture_id="production_locked_sides",
        fixture_class=FixtureClass.PRODUCTION,
        title="Locked Sides",
        edges=(
            "scene_heading",
            "action",
            "character",
            "dialogue",
            "locked_pages",
            "locked_scenes",
            "omitted_scenes",
            "ab_scenes",
            "revisions",
            "tags",
            "notes",
            "unknown_extensions",
        ),
        document=document,
        rights=_rights(classification="user_owned"),
        extras={"owner_actor_id": actor_id},
    )


def build_adversarial_unicode_rtl() -> BuiltFixture:
    mint = IdMint(700)
    actor_id = mint.schema("actor")
    project_id = mint.schema("project")
    document_id = mint.schema("document")
    revision_id = mint.schema("revision")
    sequence_id = mint.schema("sequence")
    scene_id = mint.schema("scene")
    cue_ada = mint.schema("character_cue")
    cue_noura = mint.schema("character_cue")
    pair_ada = mint.schema("dialogue_pair")
    pair_noura = mint.schema("dialogue_pair")
    dual_group = mint.prefixed("ddg")
    combining = "cafe\u0301"

    heading = Block(
        id=mint.schema("block"),
        kind=BlockKind.SCENE_HEADING,
        text="INT. ARCHIVE - NIGHT",
        scene_id=scene_id,
        scene_number="99",
        is_extension=True,
        unknown_extensions={
            "fdx_unknown_safe": {"element": "CustomTag", "preserve": True},
            "custom_formatting": {"align": "start", "rtl": False},
        },
    )
    action = Block(
        id=mint.schema("block"),
        kind=BlockKind.ACTION,
        text=f"A {combining} sign hangs above Hebrew notes: שלום.",
        scene_id=scene_id,
        unknown_extensions={"unicode_sample": True},
    )
    ada = Block(
        id=mint.schema("block"),
        kind=BlockKind.CHARACTER,
        text="ADA (V.O.)",
        character_cue_id=cue_ada,
        dialogue_pair_id=pair_ada,
        is_extension=True,
        is_dual_dialogue=True,
        dual_dialogue_group_id=dual_group,
        scene_id=scene_id,
    )
    ada_line = Block(
        id=mint.schema("block"),
        kind=BlockKind.DIALOGUE,
        text="The letters keep their order.",
        dialogue_pair_id=pair_ada,
        is_dual_dialogue=True,
        dual_dialogue_group_id=dual_group,
        scene_id=scene_id,
    )
    noura = Block(
        id=mint.schema("block"),
        kind=BlockKind.CHARACTER,
        text="NOURA",
        character_cue_id=cue_noura,
        dialogue_pair_id=pair_noura,
        is_dual_dialogue=True,
        dual_dialogue_group_id=dual_group,
        scene_id=scene_id,
        unknown_extensions={"rtl_character": True},
    )
    noura_line = Block(
        id=mint.schema("block"),
        kind=BlockKind.DIALOGUE,
        text="مرحبا. نقرأ من اليمين.",
        dialogue_pair_id=pair_noura,
        is_dual_dialogue=True,
        dual_dialogue_group_id=dual_group,
        scene_id=scene_id,
        unknown_extensions={"rtl": True, "script": "arab"},
    )
    forced = Block(
        id=mint.schema("block"),
        kind=BlockKind.PAGE_BREAK,
        text="",
        is_forced=True,
        unknown_extensions={"forced_page_break": True},
    )
    document = ScreenplayDocument(
        id=document_id,
        project_id=project_id,
        title=f"Archive {combining}",
        sequences=(Sequence(id=sequence_id, title="Adversary", order=0, scene_ids=(scene_id,)),),
        blocks=(heading, action, ada, ada_line, noura, noura_line, forced),
        base_revision_id=revision_id,
        notes=(
            Note(
                id=mint.schema("note"),
                block_id=heading.id,
                author_actor_id=actor_id,
                text="Preserve unknown-but-safe extension elements.",
                created_at=CREATED_AT,
            ),
        ),
    )
    document.validate()
    return BuiltFixture(
        fixture_id="adversarial_unicode_rtl",
        fixture_class=FixtureClass.ADVERSARIAL,
        title="Archive combining",
        edges=(
            "scene_heading",
            "action",
            "character",
            "dialogue",
            "dual_dialogue",
            "unicode",
            "rtl",
            "unknown_extensions",
            "notes",
        ),
        document=document,
        rights=_rights(classification="user_owned"),
        extras={"owner_actor_id": actor_id},
    )


def all_screenplay_fixtures() -> tuple[BuiltFixture, ...]:
    return (
        build_small_kitchen(),
        build_feature_complete_harbor(),
        build_production_locked_sides(),
        build_adversarial_unicode_rtl(),
    )
