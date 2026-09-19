"""Local complete is labeled previs, never canon; timeline and intended-effect review."""

from __future__ import annotations

import pytest

from movie_muse.identity.api import make_integration_actor
from movie_muse.video_previs.api import (
    DISCLAIMER,
    CanonPromotionError,
    ClipNotFoundError,
    TimelineKind,
    VideoPrevisAcceptError,
)


def test_local_complete_is_labeled_previs_and_not_canon(previs_stack, stored_shot) -> None:
    camera_before = stored_shot.record.camera.to_dict()
    color_before = stored_shot.color_intent
    previs_stack.previs.grant_consent(
        previs_stack.project.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    clip = previs_stack.previs.enqueue_clip(
        stored_shot.record.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    assert clip.artifact_id == ""
    completed = previs_stack.previs.complete_local(
        clip.id, principal=previs_stack.principal, acl_epoch=previs_stack.epoch
    )
    assert completed.id.startswith("vpv_")
    assert completed.shot_id == stored_shot.record.id
    assert completed.source_revision_id == previs_stack.revisions.canon_head_id()
    assert completed.artifact_id.startswith("art_")
    assert completed.artifact_version_id.startswith("avr_")
    assert completed.video_provider_used is False
    assert completed.labeled_previs is True
    assert completed.canon is False
    assert DISCLAIMER in completed.prompt
    assert completed.provenance.get("prompt_id")
    assert completed.actual_cost >= 0.0
    after = previs_stack.shots.get_shot(
        stored_shot.record.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    assert after.record.camera.to_dict() == camera_before
    assert after.color_intent == color_before
    boards = previs_stack.storyboard.list_frames(
        previs_stack.project.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
        shot_id=stored_shot.record.id,
    )
    assert boards == ()


def test_storyboard_sequence_links_without_mutating_frames(previs_stack, stored_shot) -> None:
    frame = previs_stack.storyboard.render_frame(
        stored_shot.record.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    previs_stack.previs.grant_consent(
        previs_stack.project.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    clip = previs_stack.previs.enqueue_clip(
        stored_shot.record.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
        storyboard_frame_id=frame.id,
    )
    completed = previs_stack.previs.complete_local(
        clip.id, principal=previs_stack.principal, acl_epoch=previs_stack.epoch
    )
    assert completed.storyboard_frame_id == frame.id
    reread = previs_stack.storyboard.get_frame(
        frame.id, principal=previs_stack.principal, acl_epoch=previs_stack.epoch
    )
    assert reread.artifact_version_id == frame.artifact_version_id
    assert reread.accepted is False


def test_regenerate_compare_and_scene_stale(previs_stack, stored_shot) -> None:
    previs_stack.previs.grant_consent(
        previs_stack.project.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    first = previs_stack.previs.enqueue_clip(
        stored_shot.record.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    first = previs_stack.previs.complete_local(
        first.id, principal=previs_stack.principal, acl_epoch=previs_stack.epoch
    )
    second = previs_stack.previs.regenerate(
        first.id, principal=previs_stack.principal, acl_epoch=previs_stack.epoch
    )
    assert second.parent_id == first.id
    assert second.regeneration_count == 1
    second = previs_stack.previs.complete_local(
        second.id, principal=previs_stack.principal, acl_epoch=previs_stack.epoch
    )
    comparison = previs_stack.previs.compare_clips(
        first.id,
        second.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    assert comparison.inputs_changed is True
    space = previs_stack.director.get_scene_space(
        stored_shot.record.scene_space_id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    previs_stack.director.notify_scene_changed(
        space.space.scene_id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
        project_id=previs_stack.project.id,
    )
    stale = previs_stack.previs.get_clip(
        first.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    assert stale.labeled_stale is True


def test_timeline_and_animatic_assembly(previs_stack, stored_shot) -> None:
    previs_stack.previs.grant_consent(
        previs_stack.project.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    first = previs_stack.previs.enqueue_clip(
        stored_shot.record.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    first = previs_stack.previs.complete_local(
        first.id, principal=previs_stack.principal, acl_epoch=previs_stack.epoch
    )
    second = previs_stack.previs.regenerate(
        first.id, principal=previs_stack.principal, acl_epoch=previs_stack.epoch
    )
    second = previs_stack.previs.complete_local(
        second.id, principal=previs_stack.principal, acl_epoch=previs_stack.epoch
    )
    timeline = previs_stack.previs.assemble_timeline(
        (first.id, second.id),
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
        kind=TimelineKind.ANIMATIC,
    )
    assert timeline.id.startswith("vtl_")
    assert timeline.kind is TimelineKind.ANIMATIC
    assert timeline.clip_ids == (first.id, second.id)
    assert timeline.artifact_id.startswith("art_")
    assert timeline.labeled_previs is True
    assert timeline.canon is False
    assert "not the finished film" in timeline.disclaimer
    after = previs_stack.shots.get_shot(
        stored_shot.record.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    assert after.record.id == stored_shot.record.id


def test_intended_effect_review_does_not_promote_canon(previs_stack, stored_shot) -> None:
    previs_stack.previs.grant_consent(
        previs_stack.project.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    clip = previs_stack.previs.enqueue_clip(
        stored_shot.record.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    completed = previs_stack.previs.complete_local(
        clip.id, principal=previs_stack.principal, acl_epoch=previs_stack.epoch
    )
    with pytest.raises(CanonPromotionError, match="never canon"):
        previs_stack.previs.review_intended_effect(
            completed.id,
            notes="Hold the lock-off.",
            principal=previs_stack.principal,
            acl_epoch=previs_stack.epoch,
            promote_to_canon=True,
        )
    review = previs_stack.previs.review_intended_effect(
        completed.id,
        notes="Hold the lock-off through the beat.",
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    assert review.id.startswith("vie_")
    assert review.promotes_to_canon is False
    assert completed.canon is False
    after = previs_stack.shots.get_shot(
        stored_shot.record.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    assert after.color_intent == stored_shot.color_intent


def test_integration_cannot_review_intended_effect(previs_stack, stored_shot) -> None:
    previs_stack.previs.grant_consent(
        previs_stack.project.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    clip = previs_stack.previs.enqueue_clip(
        stored_shot.record.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    completed = previs_stack.previs.complete_local(
        clip.id, principal=previs_stack.principal, acl_epoch=previs_stack.epoch
    )
    actor = make_integration_actor(
        organization_id=previs_stack.project.organization_id,
        display_name="Review Bot",
    )
    previs_stack.identity.register_actor(actor)
    bot = previs_stack.identity.principal(actor.id)
    with pytest.raises(VideoPrevisAcceptError, match="human"):
        previs_stack.previs.review_intended_effect(
            completed.id,
            notes="Looks expensive.",
            principal=bot,
            acl_epoch=previs_stack.identity.acl_epoch(),
        )


def test_missing_clip_fails_closed(previs_stack) -> None:
    with pytest.raises(ClipNotFoundError):
        previs_stack.previs.get_clip(
            "vpv_missing",
            principal=previs_stack.principal,
            acl_epoch=previs_stack.epoch,
        )
