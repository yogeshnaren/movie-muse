"""Director, producer, and writer storyboard annotations stay distinct."""

from __future__ import annotations

import pytest

from movie_muse.director.api import AnnotationRole
from movie_muse.storyboard.api import AnnotationError, LockedAttributeDriftError


def test_role_annotations_remain_distinct(storyboard_stack, stored_shot) -> None:
    frame = storyboard_stack.storyboard.render_frame(
        stored_shot.record.id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
    )
    director = storyboard_stack.storyboard.annotate(
        frame.id,
        role=AnnotationRole.DIRECTOR,
        body="Hold the brass lock in frame.",
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
    )
    producer = storyboard_stack.storyboard.annotate(
        frame.id,
        role=AnnotationRole.PRODUCER,
        body="Keep the coverage cheap enough to shoot day-one.",
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
    )
    writer = storyboard_stack.storyboard.annotate(
        frame.id,
        role=AnnotationRole.WRITER,
        body="Ada is still listening, not accusing.",
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
    )
    assert director.role is AnnotationRole.DIRECTOR
    assert producer.role is AnnotationRole.PRODUCER
    assert writer.role is AnnotationRole.WRITER
    directors = storyboard_stack.storyboard.list_annotations(
        frame.id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
        role=AnnotationRole.DIRECTOR,
    )
    producers = storyboard_stack.storyboard.list_annotations(
        frame.id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
        role=AnnotationRole.PRODUCER,
    )
    writers = storyboard_stack.storyboard.list_annotations(
        frame.id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
        role=AnnotationRole.WRITER,
    )
    assert [item.id for item in directors] == [director.id]
    assert [item.id for item in producers] == [producer.id]
    assert [item.id for item in writers] == [writer.id]
    all_notes = storyboard_stack.storyboard.list_annotations(
        frame.id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
    )
    assert {item.role for item in all_notes} == {
        AnnotationRole.DIRECTOR,
        AnnotationRole.PRODUCER,
        AnnotationRole.WRITER,
    }


def test_empty_annotation_is_rejected(storyboard_stack, stored_shot) -> None:
    frame = storyboard_stack.storyboard.render_frame(
        stored_shot.record.id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
    )
    with pytest.raises(AnnotationError):
        storyboard_stack.storyboard.annotate(
            frame.id,
            role=AnnotationRole.DIRECTOR,
            body="   ",
            principal=storyboard_stack.principal,
            acl_epoch=storyboard_stack.epoch,
        )


def test_list_frames_for_shot(storyboard_stack, stored_shot) -> None:
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
    listed = storyboard_stack.storyboard.list_frames(
        storyboard_stack.project.id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
        shot_id=stored_shot.record.id,
    )
    assert {item.id for item in listed} == {first.id, second.id}
    all_frames = storyboard_stack.storyboard.list_frames(
        storyboard_stack.project.id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
    )
    assert {item.id for item in all_frames} == {first.id, second.id}


def test_accept_is_idempotent_and_audited(storyboard_stack, stored_shot) -> None:
    frame = storyboard_stack.storyboard.render_frame(
        stored_shot.record.id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
    )
    first = storyboard_stack.storyboard.accept_frame(
        frame.id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
    )
    second = storyboard_stack.storyboard.accept_frame(
        frame.id,
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
    )
    assert first.accepted is True
    assert second.accept_count == first.accept_count == 1
    operations = {record.operation for record in storyboard_stack.audit.list_records()}
    assert "storyboard.render" in operations
    assert "storyboard.accept" in operations


def test_locked_color_intent_drift_is_rejected(storyboard_stack, stored_shot) -> None:
    storyboard_stack.shots.lock_attribute(
        stored_shot.record.id,
        "color_intent",
        principal=storyboard_stack.principal,
        acl_epoch=storyboard_stack.epoch,
    )
    with pytest.raises(LockedAttributeDriftError, match="color_intent"):
        storyboard_stack.storyboard.render_frame(
            stored_shot.record.id,
            principal=storyboard_stack.principal,
            acl_epoch=storyboard_stack.epoch,
            camera_overrides={"color_intent": "daylight-cool"},
        )

