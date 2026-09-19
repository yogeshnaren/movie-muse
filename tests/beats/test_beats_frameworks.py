"""Licensed templates, original story functions, and advisory completion."""

from __future__ import annotations

import pytest

from movie_muse.beats.api import (
    ADVISORY_DISCLAIMER,
    FrameworkKind,
    FrameworkRightsError,
    UnlicensedFrameworkError,
    builtin_themes,
    contrast_ratio,
)
from movie_muse.rights.api import PermittedUse, SourceClassification
from movie_muse.toolchain.paths import repo_root

FORBIDDEN_TEMPLATE_PHRASES = (
    "fun and games",
    "bad guys close in",
    "dark night of the soul",
    "break into two",
    "break into three",
    "all is lost",
    "opening image",
    "theme stated",
    "final image",
    "ordinary world",
    "call to adventure",
    "refusal of the call",
    "meeting with the mentor",
    "crossing the first threshold",
    "inmost cave",
    "the road back",
    "return with the elixir",
)


def test_builtin_templates_omit_copyrighted_workbook_prose() -> None:
    package = repo_root() / "src" / "movie_muse" / "beats"
    blob = "\n".join(path.read_text(encoding="utf-8") for path in sorted(package.glob("*.py")))
    lowered = blob.lower()
    for phrase in FORBIDDEN_TEMPLATE_PHRASES:
        assert phrase not in lowered


def test_three_act_is_permitted_without_rights(beat_stack) -> None:
    framework = beat_stack.beats.instantiate_framework(
        project_id=beat_stack.project.id,
        kind=FrameworkKind.THREE_ACT,
        principal=beat_stack.principal,
        acl_epoch=beat_stack.epoch,
    )
    assert framework.kind is FrameworkKind.THREE_ACT
    assert framework.source_id is None
    assert framework.guidance_not_truth is True
    assert framework.disclaimer == ADVISORY_DISCLAIMER
    assert [slot.key for slot in framework.slots] == [
        "opening_movement",
        "rising_movement",
        "closing_movement",
    ]
    catalog = {entry.kind: entry for entry in beat_stack.beats.catalog()}
    assert catalog[FrameworkKind.SAVE_THE_CAT].rights_required is True
    assert catalog[FrameworkKind.HEROS_JOURNEY].rights_required is True
    assert catalog[FrameworkKind.THREE_ACT].rights_required is False


def test_named_licensed_templates_fail_closed_without_rights(beat_stack) -> None:
    with pytest.raises(UnlicensedFrameworkError):
        beat_stack.beats.instantiate_framework(
            project_id=beat_stack.project.id,
            kind=FrameworkKind.SAVE_THE_CAT,
            principal=beat_stack.principal,
            acl_epoch=beat_stack.epoch,
        )
    unlicensed = beat_stack.rights.register_source(
        project_id=beat_stack.project.id,
        title="Unlicensed workbook dump",
        classification=SourceClassification.UNLICENSED,
        principal=beat_stack.principal,
        acl_epoch=beat_stack.epoch,
        permitted_uses=(),
    )
    with pytest.raises(UnlicensedFrameworkError):
        beat_stack.beats.instantiate_framework(
            project_id=beat_stack.project.id,
            kind=FrameworkKind.HEROS_JOURNEY,
            principal=beat_stack.principal,
            acl_epoch=beat_stack.epoch,
            source_id=unlicensed.source_id,
        )


def test_licensed_source_allows_named_templates(beat_stack, licensed_source) -> None:
    source = licensed_source
    stc = beat_stack.beats.instantiate_framework(
        project_id=beat_stack.project.id,
        kind=FrameworkKind.SAVE_THE_CAT,
        principal=beat_stack.principal,
        acl_epoch=beat_stack.epoch,
        source_id=source.source_id,
    )
    journey = beat_stack.beats.instantiate_framework(
        project_id=beat_stack.project.id,
        kind=FrameworkKind.HEROS_JOURNEY,
        principal=beat_stack.principal,
        acl_epoch=beat_stack.epoch,
        source_id=source.source_id,
    )
    assert stc.source_id == source.source_id
    assert len(stc.slots) == 15
    assert journey.source_id == source.source_id
    assert len(journey.slots) == 12
    listed = beat_stack.beats.list_frameworks(
        beat_stack.project.id,
        principal=beat_stack.principal,
        acl_epoch=beat_stack.epoch,
    )
    assert {item.id for item in listed} == {stc.id, journey.id}


def test_licensed_source_without_citation_is_denied(beat_stack) -> None:
    source = beat_stack.rights.register_source(
        project_id=beat_stack.project.id,
        title="Retrieval-only catalog",
        classification=SourceClassification.LICENSED,
        principal=beat_stack.principal,
        acl_epoch=beat_stack.epoch,
        permitted_uses=(PermittedUse.RETRIEVAL,),
    )
    with pytest.raises(FrameworkRightsError):
        beat_stack.beats.instantiate_framework(
            project_id=beat_stack.project.id,
            kind=FrameworkKind.SAVE_THE_CAT,
            principal=beat_stack.principal,
            acl_epoch=beat_stack.epoch,
            source_id=source.source_id,
        )


def test_custom_framework_uses_author_slots(beat_stack) -> None:
    framework = beat_stack.beats.instantiate_framework(
        project_id=beat_stack.project.id,
        kind=FrameworkKind.CUSTOM,
        principal=beat_stack.principal,
        acl_epoch=beat_stack.epoch,
        custom_slots=(
            ("hook", "Hook", "Open on the distinctive problem."),
            ("turn", "Turn", "The pursuit changes cost."),
            ("landing", "Landing", "Show the new condition."),
        ),
    )
    assert [slot.key for slot in framework.slots] == ["hook", "turn", "landing"]


def test_builtin_themes_meet_contrast_floor() -> None:
    for theme in builtin_themes():
        assert theme.accessible is True
        for token in theme.tokens:
            assert contrast_ratio(token.foreground, token.background) >= 4.5
            assert token.pattern
            assert token.label


