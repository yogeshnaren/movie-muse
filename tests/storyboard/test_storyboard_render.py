"""Storyboard renders link ShotIR, reuse accepted assets, and fail-close live image."""

from __future__ import annotations

import pytest

from movie_muse.authorization.api import AuthorizationError
from movie_muse.identity.api import Role, make_integration_actor
from movie_muse.storyboard.api import (
    DISCLAIMER,
    IMAGE_PROVIDER_ENV,
    FrameNotFoundError,
    ImageProviderUnavailableError,
    LockedAttributeDriftError,
    StoryboardAcceptError,
)


def test_render_links_shot_and_source_revision(storyboard_stack, stored_shot) -> None:
    frame = storyboard_stack.storyboard.render_frame(
        stored_shot.record.id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
        style_key="tungsten-kitchen",
    )
    assert frame.id.startswith("stb_")
    assert frame.shot_id == stored_shot.record.id
    assert frame.source_revision_id == storyboard_stack.revisions.canon_head_id()
    assert frame.artifact_id.startswith("art_")
    assert frame.artifact_version_id.startswith("avr_")
    assert frame.image_provider_used is False
    assert DISCLAIMER in frame.prompt
    assert "not photographic coverage" in frame.disclaimer
    assert frame.provenance.get("prompt_id")
    assert frame.style_key == "tungsten-kitchen"
    assert frame.character_key == "ada"
    assert "Kitchen" in frame.location_key
    assert frame.accepted is False
    assert frame.labeled_stale is False


def test_locked_attribute_drift_is_rejected(storyboard_stack, stored_shot) -> None:
    storyboard_stack.shots.lock_attribute(
        stored_shot.record.id,
        "lens_mm",
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
    )
    with pytest.raises(LockedAttributeDriftError, match="lens_mm"):
        storyboard_stack.storyboard.render_frame(
            stored_shot.record.id,
            principal=storyboard_stack.principal,
            acl_epoch=storyboard_stack.epoch,
            camera_overrides={"lens_mm": 85.0},
        )
    frame = storyboard_stack.storyboard.render_frame(
        stored_shot.record.id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
        camera_overrides={"lens_mm": 35.0},
    )
    assert "LOCKED lens_mm" in frame.prompt
    assert "lens_mm=35.0" in frame.prompt


def test_accepted_asset_is_reused_on_identical_render(storyboard_stack, stored_shot) -> None:
    first = storyboard_stack.storyboard.render_frame(
        stored_shot.record.id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
    )
    accepted = storyboard_stack.storyboard.accept_frame(
        first.id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
    )
    assert accepted.accepted is True
    reused = storyboard_stack.storyboard.render_frame(
        stored_shot.record.id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
    )
    assert reused.id == accepted.id
    assert reused.reused_accepted_asset is True
    assert reused.artifact_version_id == accepted.artifact_version_id


def test_regenerate_compare_and_correction_burden(storyboard_stack, stored_shot) -> None:
    first = storyboard_stack.storyboard.render_frame(
        stored_shot.record.id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
    )
    second = storyboard_stack.storyboard.regenerate(
        first.id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
    )
    assert second.parent_id == first.id
    assert second.regeneration_count == 1
    assert second.correction_count == 0
    comparison = storyboard_stack.storyboard.compare_frames(
        first.id,
        second.id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
    )
    assert comparison.inputs_changed is True
    assert "regeneration_count" in comparison.changed_input_keys
    accepted = storyboard_stack.storyboard.accept_frame(
        second.id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
    )
    third = storyboard_stack.storyboard.regenerate(
        accepted.id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
    )
    assert third.correction_count == 1
    metrics = storyboard_stack.storyboard.metrics(
        third.id, principal=storyboard_stack.principal, acl_epoch=storyboard_stack.epoch
    )
    assert metrics.regeneration_count == 2
    assert metrics.accept_count == 1
    assert metrics.correction_count == 1
    assert metrics.regeneration_to_acceptance == 2.0


def test_scene_change_marks_storyboard_stale(storyboard_stack, stored_shot) -> None:
    frame = storyboard_stack.storyboard.render_frame(
        stored_shot.record.id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
    )
    space = storyboard_stack.director.get_scene_space(
        stored_shot.record.scene_space_id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
    )
    storyboard_stack.director.notify_scene_changed(
        space.space.scene_id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
        project_id=storyboard_stack.project.id,
    )
    stale = storyboard_stack.storyboard.get_frame(
        frame.id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
    )
    assert stale.labeled_stale is True


def test_live_image_provider_unset_fails_closed(
    storyboard_stack, stored_shot, monkeypatch
) -> None:
    monkeypatch.delenv(IMAGE_PROVIDER_ENV, raising=False)
    frame = storyboard_stack.storyboard.render_frame(
        stored_shot.record.id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
    )
    with pytest.raises(ImageProviderUnavailableError, match="unset"):
        storyboard_stack.storyboard.live_render(
            frame.id,
            principal=storyboard_stack.principal,
            acl_epoch=storyboard_stack.epoch,
        )


def test_live_image_provider_env_still_does_not_claim_the_gate(
    storyboard_stack, stored_shot, monkeypatch
) -> None:
    monkeypatch.setenv(IMAGE_PROVIDER_ENV, "https://image.example.invalid/v1")
    frame = storyboard_stack.storyboard.render_frame(
        stored_shot.record.id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
    )
    with pytest.raises(ImageProviderUnavailableError, match="stays NOT_RUN"):
        storyboard_stack.storyboard.live_render(
            frame.id,
            principal=storyboard_stack.principal,
            acl_epoch=storyboard_stack.epoch,
        )
    assert frame.image_provider_used is False


def test_integration_cannot_accept(storyboard_stack, stored_shot) -> None:
    frame = storyboard_stack.storyboard.render_frame(
        stored_shot.record.id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
    )
    actor = make_integration_actor(
        organization_id=storyboard_stack.project.organization_id,
        display_name="Board Bot",
    )
    storyboard_stack.identity.register_actor(actor)
    bot = storyboard_stack.identity.principal(actor.id)
    with pytest.raises(StoryboardAcceptError, match="human"):
        storyboard_stack.storyboard.accept_frame(
            frame.id, principal=bot, acl_epoch=storyboard_stack.identity.acl_epoch()
        )


def test_viewer_cannot_render(storyboard_stack, stored_shot, member) -> None:
    viewer = member(Role.VIEWER)
    with pytest.raises(AuthorizationError):
        storyboard_stack.storyboard.render_frame(
            stored_shot.record.id,
            principal=viewer,
            acl_epoch=storyboard_stack.epoch,
        )


def test_missing_frame_fails_closed(storyboard_stack) -> None:
    with pytest.raises(FrameNotFoundError):
        storyboard_stack.storyboard.get_frame(
            "stb_missing",
            principal=storyboard_stack.principal,
            acl_epoch=storyboard_stack.epoch,
        )
