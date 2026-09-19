"""DirectorVisionGraph owns SceneSpace, coverage, constraints, and annotations."""

from __future__ import annotations

import pytest

from movie_muse.authorization.api import AuthorizationError
from movie_muse.director.api import (
    AnnotationRole,
    CoveragePurpose,
    LockedGeometryError,
    SubjectPosition,
)
from movie_muse.identity.api import Role, make_human_actor


def _space(director_stack, scene_id: str | None = None):
    return director_stack.director.create_scene_space(
        project_id=director_stack.project.id,
        scene_id=scene_id or director_stack.scene_ids[0],
        geometry_description="Kitchen 8m x 5m, island center, window stage left.",
        principal=director_stack.principal,
        acl_epoch=director_stack.epoch,
        subject_positions=(
            SubjectPosition(subject_id="ada", x=1.5, y=2.0, orientation_degrees=90.0),
        ),
        continuity_notes="Day interior, brass lock visible.",
    )


def _invite(director_stack, role: Role, name: str):
    actor = make_human_actor(
        organization_id=director_stack.project.organization_id, display_name=name
    )
    director_stack.identity.register_actor(actor)
    invitation = director_stack.identity.invite(
        inviter_actor_id=director_stack.owner.id,
        invitee_actor_id=actor.id,
        project_id=director_stack.project.id,
        role=role,
    )
    director_stack.identity.accept_invitation(invitation.id, actor_id=actor.id)
    return director_stack.identity.principal(actor.id), director_stack.identity.acl_epoch()


def test_graph_defaults_to_generation_disabled(director_stack) -> None:
    graph = director_stack.director.graph(
        director_stack.project.id,
        principal=director_stack.principal,
        acl_epoch=director_stack.epoch,
    )
    assert graph.generation_enabled is False
    assert graph.provider_independent is True
    space = _space(director_stack)
    assert space.space.id.startswith("ssp_")
    assert space.space.scene_id == director_stack.scene_ids[0]
    listed = director_stack.director.graph(
        director_stack.project.id,
        principal=director_stack.principal,
        acl_epoch=director_stack.epoch,
    )
    assert space.space.id in listed.scene_space_ids


def test_coverage_and_producer_constraints(director_stack) -> None:
    space = _space(director_stack)
    coverage = director_stack.director.add_coverage(
        project_id=director_stack.project.id,
        scene_space_id=space.space.id,
        purpose=CoveragePurpose.MASTER,
        principal=director_stack.principal,
        acl_epoch=director_stack.epoch,
        notes="Hold the island in frame.",
    )
    assert coverage.id.startswith("cov_")
    constraint = director_stack.director.add_producer_constraint(
        project_id=director_stack.project.id,
        target_kind="scene_space",
        target_id=space.space.id,
        statement="No company move before lunch.",
        principal=director_stack.principal,
        acl_epoch=director_stack.epoch,
    )
    assert constraint.id.startswith("pcn_")
    fetched = director_stack.director.get_constraint(
        constraint.id,
        principal=director_stack.principal,
        acl_epoch=director_stack.epoch,
    )
    assert fetched.statement == "No company move before lunch."


def test_role_annotations_transfer_semantic_anchors(director_stack) -> None:
    space = _space(director_stack)
    director_note = director_stack.director.annotate(
        project_id=director_stack.project.id,
        target_kind="scene_space",
        target_id=space.space.id,
        role=AnnotationRole.DIRECTOR,
        body="Keep Ada's eyeline at the brass lock.",
        principal=director_stack.principal,
        acl_epoch=director_stack.epoch,
        kind="eyeline",
        page_id="page-1",
    )
    writer, epoch = _invite(director_stack, Role.WRITER, "Writer")
    writer_note = director_stack.director.annotate(
        project_id=director_stack.project.id,
        target_kind="scene_space",
        target_id=space.space.id,
        role=AnnotationRole.WRITER,
        body="The note on the table stays unread.",
        principal=writer,
        acl_epoch=epoch,
        page_id="page-1",
    )
    producer, epoch = _invite(director_stack, Role.PRODUCER, "Producer")
    producer_note = director_stack.director.annotate(
        project_id=director_stack.project.id,
        target_kind="scene_space",
        target_id=space.space.id,
        role=AnnotationRole.PRODUCER,
        body="Lock practicals for continuity stills.",
        principal=producer,
        acl_epoch=epoch,
        page_id="page-1",
    )
    moved = director_stack.director.transfer_annotation(
        director_note.id,
        page_id="page-2",
        principal=director_stack.principal,
        acl_epoch=epoch,
    )
    assert moved.anchor.token == director_note.anchor.token
    assert moved.anchor.id == director_note.anchor.id
    assert moved.anchor.page_id == "page-2"
    listed = director_stack.director.list_annotations(
        space.space.id,
        principal=director_stack.principal,
        project_id=director_stack.project.id,
        acl_epoch=epoch,
    )
    roles = {item.role for item in listed}
    assert roles == {
        AnnotationRole.DIRECTOR,
        AnnotationRole.WRITER,
        AnnotationRole.PRODUCER,
    }
    assert writer_note.role is AnnotationRole.WRITER
    assert producer_note.role is AnnotationRole.PRODUCER


def test_locked_geometry_and_writer_cannot_lock(director_stack) -> None:
    space = _space(director_stack)
    locked = director_stack.director.lock_space_attribute(
        space.space.id,
        "geometry_description",
        principal=director_stack.principal,
        acl_epoch=director_stack.epoch,
    )
    assert "geometry_description" in locked.space.locked_attributes
    with pytest.raises(LockedGeometryError):
        director_stack.director.update_blocking(
            space.space.id,
            principal=director_stack.principal,
            acl_epoch=director_stack.epoch,
            geometry_description="A different room.",
        )
    writer, epoch = _invite(director_stack, Role.WRITER, "Writer")
    with pytest.raises(AuthorizationError):
        director_stack.director.lock_space_attribute(
            space.space.id,
            "subject_positions",
            principal=writer,
            acl_epoch=epoch,
        )


def test_viewer_cannot_create_space(director_stack) -> None:
    viewer, epoch = _invite(director_stack, Role.VIEWER, "Viewer")
    with pytest.raises(AuthorizationError):
        director_stack.director.create_scene_space(
            project_id=director_stack.project.id,
            scene_id=director_stack.scene_ids[0],
            geometry_description="Hidden set.",
            principal=viewer,
            acl_epoch=epoch,
        )
