"""Role-filtered department views, notices, assignments, and exports."""

from __future__ import annotations

import pytest

from movie_muse.authorization.api import AuthorizationError
from movie_muse.breakdown.api import ElementKind
from movie_muse.department_handoff.api import DepartmentDeniedError
from movie_muse.identity.api import Role, make_human_actor


def _invite(stack, role: Role, name: str, department: str | None = None):
    actor = make_human_actor(
        organization_id=stack.project.organization_id, display_name=name
    )
    stack.identity.register_actor(actor)
    invitation = stack.identity.invite(
        inviter_actor_id=stack.owner.id,
        invitee_actor_id=actor.id,
        project_id=stack.project.id,
        role=role,
        department=department,
    )
    stack.identity.accept_invitation(invitation.id, actor_id=actor.id)
    return stack.identity.principal(actor.id), stack.identity.acl_epoch()


def test_costume_sees_only_wardrobe_elements(derived_breakdown, handoff_stack) -> None:
    costume, epoch = _invite(
        handoff_stack, Role.DEPARTMENT_CONTRIBUTOR, "Costume", department="costume"
    )
    packet = handoff_stack.handoff.department_view(
        derived_breakdown.projection.id,
        "costume",
        principal=costume,
        acl_epoch=epoch,
    )
    assert packet.department == "costume"
    assert packet.source_revision_id == derived_breakdown.locked_revision_id
    assert all(item.kind is ElementKind.WARDROBE for item in packet.elements)
    assert packet.elements
    with pytest.raises(DepartmentDeniedError):
        handoff_stack.handoff.department_view(
            derived_breakdown.projection.id,
            "props",
            principal=costume,
            acl_epoch=epoch,
        )


def test_viewer_cannot_open_department_packet(derived_breakdown, handoff_stack) -> None:
    viewer, epoch = _invite(handoff_stack, Role.VIEWER, "Viewer")
    with pytest.raises(DepartmentDeniedError):
        handoff_stack.handoff.department_view(
            derived_breakdown.projection.id,
            "costume",
            principal=viewer,
            acl_epoch=epoch,
        )


def test_screenplay_change_creates_targeted_notices(derived_breakdown, handoff_stack) -> None:
    scene_id = handoff_stack.document.blocks[0].scene_id
    notices = handoff_stack.handoff.notify_screenplay_changed(
        derived_breakdown.projection.id,
        principal=handoff_stack.principal,
        acl_epoch=handoff_stack.epoch,
        scene_ids=(scene_id,),
    )
    departments = {item.department for item in notices}
    assert "costume" in departments
    assert "casting" in departments
    costume, epoch = _invite(
        handoff_stack, Role.DEPARTMENT_CONTRIBUTOR, "Costume", department="costume"
    )
    costume_notices = [item for item in notices if item.department == "costume"]
    assert costume_notices
    acked = handoff_stack.handoff.acknowledge_notice(
        costume_notices[0].id, principal=costume, acl_epoch=epoch
    )
    assert acked.acknowledged_by_actor_id == costume.actor_id


def test_owner_assigns_and_exports(derived_breakdown, handoff_stack) -> None:
    costume, _epoch = _invite(
        handoff_stack, Role.DEPARTMENT_CONTRIBUTOR, "Costume", department="costume"
    )
    wardrobe = next(
        item for item in derived_breakdown.elements if item.kind is ElementKind.WARDROBE
    )
    assignment = handoff_stack.handoff.assign(
        derived_breakdown.projection.id,
        wardrobe.id,
        assignee_actor_id=costume.actor_id,
        principal=handoff_stack.principal,
        acl_epoch=handoff_stack.epoch,
    )
    assert assignment.department == "costume"
    exported = handoff_stack.handoff.export_packet(
        derived_breakdown.projection.id,
        "costume",
        principal=handoff_stack.principal,
        acl_epoch=handoff_stack.epoch,
    )
    assert derived_breakdown.locked_revision_id in exported
    assert "wardrobe" in exported
    with pytest.raises((DepartmentDeniedError, AuthorizationError)):
        handoff_stack.handoff.export_packet(
            derived_breakdown.projection.id,
            "costume",
            principal=costume,
            acl_epoch=handoff_stack.identity.acl_epoch(),
        )
