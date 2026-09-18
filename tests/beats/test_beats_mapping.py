"""Manual override wins; not-applicable is supported; mapping invalidates analysis."""

from __future__ import annotations

import pytest

from movie_muse.authorization.api import AuthorizationError
from movie_muse.beats.api import (
    ADVISORY_DISCLAIMER,
    ColorTheme,
    ColorToken,
    FrameworkKind,
    MappingStatus,
    SlotFill,
    ThemeContrastError,
)
from movie_muse.dependencies.api import NodeState
from movie_muse.identity.api import Role, make_human_actor


def _three_act(beat_stack):
    return beat_stack.beats.instantiate_framework(
        project_id=beat_stack.project.id,
        kind=FrameworkKind.THREE_ACT,
        principal=beat_stack.principal,
        acl_epoch=beat_stack.epoch,
    )


def test_manual_override_wins_over_suggestion(beat_stack) -> None:
    framework = _three_act(beat_stack)
    opening, harbor, studio = beat_stack.scene_ids
    suggested = beat_stack.beats.suggest_mapping(
        framework.id,
        "opening_movement",
        scene_id=opening,
        principal=beat_stack.principal,
        acl_epoch=beat_stack.epoch,
        confidence=0.4,
    )
    assert suggested.status is MappingStatus.SUGGESTED
    assert suggested.scene_id is None
    mapped = beat_stack.beats.map_scene(
        framework.id,
        "opening_movement",
        scene_id=harbor,
        principal=beat_stack.principal,
        acl_epoch=beat_stack.epoch,
        confidence=0.9,
    )
    assert mapped.status is MappingStatus.OVERRIDDEN
    assert mapped.scene_id == harbor
    assert mapped.suggested_scene_id == opening
    explicit = beat_stack.beats.override_mapping(
        framework.id,
        "rising_movement",
        scene_id=studio,
        reason="harbor night is the turn, not the opening",
        principal=beat_stack.principal,
        acl_epoch=beat_stack.epoch,
    )
    assert explicit.status is MappingStatus.OVERRIDDEN
    assert explicit.override_reason
    later_suggestion = beat_stack.beats.suggest_mapping(
        framework.id,
        "opening_movement",
        scene_id=opening,
        principal=beat_stack.principal,
        acl_epoch=beat_stack.epoch,
    )
    assert later_suggestion.status is MappingStatus.OVERRIDDEN
    assert later_suggestion.scene_id == harbor


def test_not_applicable_is_excluded_from_completion_ratio(beat_stack) -> None:
    framework = _three_act(beat_stack)
    beat_stack.beats.map_scene(
        framework.id,
        "opening_movement",
        scene_id=beat_stack.scene_ids[0],
        principal=beat_stack.principal,
        acl_epoch=beat_stack.epoch,
    )
    marked = beat_stack.beats.mark_not_applicable(
        framework.id,
        "rising_movement",
        principal=beat_stack.principal,
        acl_epoch=beat_stack.epoch,
        reason="this short does not use a rising movement",
    )
    assert marked.status is MappingStatus.NOT_APPLICABLE
    view = beat_stack.beats.completion_view(
        framework.id,
        principal=beat_stack.principal,
        acl_epoch=beat_stack.epoch,
    )
    assert view.guidance_not_truth is True
    assert view.formula_score is None
    assert view.disclaimer == ADVISORY_DISCLAIMER
    fills = {item.slot_key: item.fill for item in view.slots}
    assert fills["rising_movement"] is SlotFill.NOT_APPLICABLE
    assert view.mapped_ratio == 0.5
    na = next(item for item in view.slots if item.slot_key == "rising_movement")
    assert na.text_status == "Not applicable"
    remapped = beat_stack.beats.override_mapping(
        framework.id,
        "rising_movement",
        scene_id=beat_stack.scene_ids[1],
        reason="restored after review",
        principal=beat_stack.principal,
        acl_epoch=beat_stack.epoch,
    )
    assert remapped.status is MappingStatus.OVERRIDDEN


def test_mapping_change_invalidates_dependent_analysis(beat_stack) -> None:
    framework = _three_act(beat_stack)
    assert framework.config_node_id
    assert framework.analysis_node_id
    before = beat_stack.engine.view_node(
        framework.analysis_node_id,
        principal=beat_stack.principal,
        acl_epoch=beat_stack.epoch,
    )
    assert before.state is NodeState.CURRENT
    beat_stack.beats.map_scene(
        framework.id,
        "opening_movement",
        scene_id=beat_stack.scene_ids[0],
        principal=beat_stack.principal,
        acl_epoch=beat_stack.epoch,
    )
    after = beat_stack.engine.view_node(
        framework.analysis_node_id,
        principal=beat_stack.principal,
        acl_epoch=beat_stack.epoch,
    )
    assert after.state is NodeState.STALE
    assert after.current is False
    assert after.labeled_stale is True
    config = beat_stack.engine.view_node(
        framework.config_node_id,
        principal=beat_stack.principal,
        acl_epoch=beat_stack.epoch,
    )
    assert config.state is NodeState.CURRENT


def test_accessible_theme_rejects_low_contrast(beat_stack) -> None:
    with pytest.raises(ThemeContrastError):
        beat_stack.beats.register_theme(
            ColorTheme(
                id="thm_low_contrast",
                name="Low contrast",
                tokens=(
                    ColorToken(
                        key="mapped",
                        background="#888888",
                        foreground="#999999",
                        pattern="solid",
                        label="Mapped",
                    ),
                ),
            ),
            principal=beat_stack.principal,
            project_id=beat_stack.project.id,
            acl_epoch=beat_stack.epoch,
        )
    applied = beat_stack.beats.apply_theme(
        _three_act(beat_stack).id,
        "thm_deuteranopia_safe",
        principal=beat_stack.principal,
        acl_epoch=beat_stack.epoch,
    )
    assert applied.theme_id == "thm_deuteranopia_safe"


def test_viewer_cannot_map_and_stale_epoch_fails(beat_stack) -> None:
    framework = _three_act(beat_stack)
    actor = make_human_actor(
        organization_id=beat_stack.project.organization_id, display_name="Viewer"
    )
    beat_stack.identity.register_actor(actor)
    invitation = beat_stack.identity.invite(
        inviter_actor_id=beat_stack.owner.id,
        invitee_actor_id=actor.id,
        project_id=beat_stack.project.id,
        role=Role.VIEWER,
    )
    beat_stack.identity.accept_invitation(invitation.id, actor_id=actor.id)
    viewer = beat_stack.identity.principal(actor.id)
    epoch = beat_stack.identity.acl_epoch()
    with pytest.raises(AuthorizationError):
        beat_stack.beats.map_scene(
            framework.id,
            "opening_movement",
            scene_id=beat_stack.scene_ids[0],
            principal=viewer,
            acl_epoch=epoch,
        )
    readable = beat_stack.beats.get_framework(
        framework.id,
        principal=viewer,
        acl_epoch=epoch,
    )
    assert readable.id == framework.id
    with pytest.raises(AuthorizationError):
        beat_stack.beats.map_scene(
            framework.id,
            "opening_movement",
            scene_id=beat_stack.scene_ids[0],
            principal=beat_stack.principal,
            acl_epoch=epoch + 1,
        )


def test_licensed_mapping_still_advisory(beat_stack, licensed_source) -> None:
    source = licensed_source
    framework = beat_stack.beats.instantiate_framework(
        project_id=beat_stack.project.id,
        kind=FrameworkKind.SAVE_THE_CAT,
        principal=beat_stack.principal,
        acl_epoch=beat_stack.epoch,
        source_id=source.source_id,
    )
    beat_stack.beats.map_scene(
        framework.id,
        "opening_condition",
        scene_id=beat_stack.scene_ids[0],
        principal=beat_stack.principal,
        acl_epoch=beat_stack.epoch,
    )
    view = beat_stack.beats.completion_view(
        framework.id,
        principal=beat_stack.principal,
        acl_epoch=beat_stack.epoch,
    )
    assert view.formula_score is None
    assert view.guidance_not_truth is True
    assert "not prescriptive truth" in view.disclaimer.lower()
