"""Explicit role matrix: writer/viewer/producer/admin/owner grants and denials."""

from __future__ import annotations

from movie_muse.authorization.api import Action, DecisionEffect, ResourceKind
from movie_muse.identity.api import Role, make_human_actor


def _member(acl_stack, role: Role, *, department: str | None = None):
    actor = make_human_actor(
        organization_id=acl_stack.project.organization_id, display_name=role.value
    )
    acl_stack.identity.register_actor(actor)
    invitation = acl_stack.identity.invite(
        inviter_actor_id=acl_stack.owner.id,
        invitee_actor_id=actor.id,
        project_id=acl_stack.project.id,
        role=role,
        department=department,
    )
    acl_stack.identity.accept_invitation(invitation.id, actor_id=actor.id)
    return acl_stack.identity.principal(actor.id)


def _decide(acl_stack, principal, action: Action, *, protected: bool = False):
    resource = acl_stack.authorization.resource_for_project(
        acl_stack.project.id,
        kind=ResourceKind.PROJECT if not protected else ResourceKind.BRANCH,
        protected=protected,
    )
    return acl_stack.authorization.authorize(
        principal, action, resource, acl_epoch=acl_stack.identity.acl_epoch()
    )


def test_writer_can_propose_cannot_manage_acl(acl_stack) -> None:
    writer = _member(acl_stack, Role.WRITER)
    assert _decide(acl_stack, writer, Action.PROPOSE).allowed
    assert _decide(acl_stack, writer, Action.ACCEPT).allowed
    assert _decide(acl_stack, writer, Action.READ).allowed
    assert _decide(acl_stack, writer, Action.MANAGE_ACL).denied
    assert _decide(acl_stack, writer, Action.MANAGE_ACL).reason == "role_denied"
    assert _decide(acl_stack, writer, Action.EXPORT).denied
    assert _decide(acl_stack, writer, Action.MERGE).denied


def test_viewer_cannot_export(acl_stack) -> None:
    viewer = _member(acl_stack, Role.VIEWER)
    assert _decide(acl_stack, viewer, Action.READ).allowed
    assert _decide(acl_stack, viewer, Action.EXPORT).denied
    assert _decide(acl_stack, viewer, Action.COMMENT).denied
    assert _decide(acl_stack, viewer, Action.PROPOSE).denied


def test_sensitive_financial_and_rights_are_separate_from_read(acl_stack) -> None:
    writer = _member(acl_stack, Role.WRITER)
    viewer = _member(acl_stack, Role.VIEWER)
    producer = _member(acl_stack, Role.PRODUCER)
    admin = _member(acl_stack, Role.ADMINISTRATOR)
    owner = acl_stack.identity.principal(acl_stack.owner.id)

    for principal in (writer, viewer):
        assert _decide(acl_stack, principal, Action.READ).allowed
        financial = _decide(acl_stack, principal, Action.VIEW_SENSITIVE_FINANCIAL)
        rights = _decide(acl_stack, principal, Action.VIEW_RIGHTS)
        assert financial.denied
        assert rights.denied
        assert financial.effect is DecisionEffect.DENY

    assert _decide(acl_stack, producer, Action.VIEW_SENSITIVE_FINANCIAL).allowed
    assert _decide(acl_stack, producer, Action.VIEW_RIGHTS).denied
    assert _decide(acl_stack, admin, Action.VIEW_RIGHTS).allowed
    assert _decide(acl_stack, admin, Action.VIEW_SENSITIVE_FINANCIAL).denied
    assert _decide(acl_stack, owner, Action.VIEW_SENSITIVE_FINANCIAL).allowed
    assert _decide(acl_stack, owner, Action.VIEW_RIGHTS).allowed


def test_reviewer_comment_only_plus_read(acl_stack) -> None:
    reviewer = _member(acl_stack, Role.REVIEWER)
    assert _decide(acl_stack, reviewer, Action.READ).allowed
    assert _decide(acl_stack, reviewer, Action.COMMENT).allowed
    assert _decide(acl_stack, reviewer, Action.ACCEPT).denied
    assert _decide(acl_stack, reviewer, Action.MANAGE_ACL).denied
