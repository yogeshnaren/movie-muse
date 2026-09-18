"""ShotIR is provider-independent; scene/intent changes mark shots stale."""

from __future__ import annotations

import pytest

from movie_muse.authorization.api import AuthorizationError
from movie_muse.director.api import AnnotationRole, SubjectPosition
from movie_muse.identity.api import Role, make_human_actor
from movie_muse.schemas.api import CameraSpec
from movie_muse.shot_ir.api import LockedAttributeError


def default_camera() -> CameraSpec:
    return CameraSpec(
        position_x=0.0,
        position_y=4.0,
        height_m=1.6,
        orientation_degrees=180.0,
        sensor="super35",
        lens_mm=35.0,
        movement="static",
    )


def open_space(shot_stack, scene_id: str | None = None):
    return shot_stack.director.create_scene_space(
        project_id=shot_stack.project.id,
        scene_id=scene_id or shot_stack.scene_ids[0],
        geometry_description="Kitchen 8m x 5m, island center.",
        principal=shot_stack.principal,
        acl_epoch=shot_stack.epoch,
        subject_positions=(
            SubjectPosition(subject_id="ada", x=1.5, y=2.0, orientation_degrees=90.0),
        ),
    )


def _shot(shot_stack, space=None):
    space = space or open_space(shot_stack)
    return shot_stack.shots.create_shot(
        scene_space_id=space.space.id,
        camera=default_camera(),
        composition_notes="Ada mid-frame at the island, brass lock in the background.",
        light_direction="window-left",
        performance_intent="restrained, listening",
        principal=shot_stack.principal,
        acl_epoch=shot_stack.epoch,
        eyeline_subject_ids=("ada",),
        color_intent="tungsten-warm",
        continuity_notes="Match day kitchen eyeline.",
        coverage_purpose="master",
    )


def test_shot_identity_and_diagrammatic_card_without_generation(shot_stack) -> None:
    stored = _shot(shot_stack)
    assert stored.record.id.startswith("sht_")
    assert stored.record.camera.lens_mm == 35.0
    assert stored.color_intent == "tungsten-warm"
    card = shot_stack.shots.shot_card(
        stored.record.id,
        principal=shot_stack.principal,
        acl_epoch=shot_stack.epoch,
    )
    assert card.generation_used is False
    assert card.mode == "diagrammatic"
    assert card.generation_enabled is False
    assert "generation_used=false" in card.diagram
    shot_stack.director.set_generation_enabled(
        shot_stack.project.id,
        True,
        principal=shot_stack.principal,
        acl_epoch=shot_stack.epoch,
    )
    enabled = shot_stack.shots.shot_card(
        stored.record.id,
        principal=shot_stack.principal,
        acl_epoch=shot_stack.epoch,
    )
    assert enabled.generation_enabled is True
    assert enabled.generation_used is False
    graph = shot_stack.director.graph(
        shot_stack.project.id,
        principal=shot_stack.principal,
        acl_epoch=shot_stack.epoch,
    )
    assert stored.record.id in graph.shot_ids


def test_locked_camera_attribute_blocks_edit(shot_stack) -> None:
    stored = _shot(shot_stack)
    locked = shot_stack.shots.lock_attribute(
        stored.record.id,
        "lens_mm",
        principal=shot_stack.principal,
        acl_epoch=shot_stack.epoch,
    )
    assert "lens_mm" in locked.record.locked_attributes
    with pytest.raises(LockedAttributeError):
        shot_stack.shots.update_camera(
            stored.record.id,
            principal=shot_stack.principal,
            acl_epoch=shot_stack.epoch,
            camera=CameraSpec(
                position_x=0.0,
                position_y=4.0,
                height_m=1.6,
                orientation_degrees=180.0,
                sensor="super35",
                lens_mm=50.0,
                movement="static",
            ),
        )
    unlocked = shot_stack.shots.unlock_attribute(
        stored.record.id,
        "lens_mm",
        principal=shot_stack.principal,
        acl_epoch=shot_stack.epoch,
    )
    changed = shot_stack.shots.update_camera(
        unlocked.record.id,
        principal=shot_stack.principal,
        acl_epoch=shot_stack.epoch,
        camera=CameraSpec(
            position_x=0.0,
            position_y=4.0,
            height_m=1.6,
            orientation_degrees=180.0,
            sensor="super35",
            lens_mm=50.0,
            movement="dolly",
        ),
    )
    assert changed.record.camera.lens_mm == 50.0
    assert changed.record.camera.movement == "dolly"


def test_scene_and_intent_changes_mark_shots_stale(shot_stack) -> None:
    space = open_space(shot_stack)
    stored = _shot(shot_stack, space)
    fresh = shot_stack.shots.get_shot(
        stored.record.id,
        principal=shot_stack.principal,
        acl_epoch=shot_stack.epoch,
    )
    assert fresh.labeled_stale is False
    shot_stack.director.notify_scene_changed(
        space.space.scene_id,
        principal=shot_stack.principal,
        acl_epoch=shot_stack.epoch,
        project_id=shot_stack.project.id,
    )
    stale = shot_stack.shots.get_shot(
        stored.record.id,
        principal=shot_stack.principal,
        acl_epoch=shot_stack.epoch,
    )
    assert stale.labeled_stale is True
    other = open_space(shot_stack, shot_stack.scene_ids[1])
    other_shot = _shot(shot_stack, other)
    shot_stack.director.notify_intent_changed(
        space.space.scene_id,
        principal=shot_stack.principal,
        acl_epoch=shot_stack.epoch,
        project_id=shot_stack.project.id,
    )
    still_other = shot_stack.shots.get_shot(
        other_shot.record.id,
        principal=shot_stack.principal,
        acl_epoch=shot_stack.epoch,
    )
    assert still_other.labeled_stale is False


def test_annotations_attach_and_viewer_cannot_create(shot_stack) -> None:
    stored = _shot(shot_stack)
    note = shot_stack.director.annotate(
        project_id=shot_stack.project.id,
        target_kind="shot",
        target_id=stored.record.id,
        role=AnnotationRole.DIRECTOR,
        body="Hold the eyeline.",
        principal=shot_stack.principal,
        acl_epoch=shot_stack.epoch,
        page_id="card-a",
    )
    attached = shot_stack.shots.attach_annotation(
        stored.record.id,
        note.id,
        principal=shot_stack.principal,
        acl_epoch=shot_stack.epoch,
    )
    assert note.id in attached.record.annotations
    moved = shot_stack.director.transfer_annotation(
        note.id,
        page_id="card-b",
        principal=shot_stack.principal,
        acl_epoch=shot_stack.epoch,
    )
    assert moved.anchor.token == note.anchor.token
    actor = make_human_actor(
        organization_id=shot_stack.project.organization_id, display_name="Viewer"
    )
    shot_stack.identity.register_actor(actor)
    invitation = shot_stack.identity.invite(
        inviter_actor_id=shot_stack.owner.id,
        invitee_actor_id=actor.id,
        project_id=shot_stack.project.id,
        role=Role.VIEWER,
    )
    shot_stack.identity.accept_invitation(invitation.id, actor_id=actor.id)
    viewer = shot_stack.identity.principal(actor.id)
    epoch = shot_stack.identity.acl_epoch()
    with pytest.raises(AuthorizationError):
        shot_stack.shots.create_shot(
            scene_space_id=stored.record.scene_space_id,
            camera=default_camera(),
            composition_notes="Forbidden.",
            light_direction="front",
            performance_intent="none",
            principal=viewer,
            acl_epoch=epoch,
        )
    readable = shot_stack.shots.get_shot(
        stored.record.id, principal=viewer, acl_epoch=epoch
    )
    assert readable.record.id == stored.record.id
