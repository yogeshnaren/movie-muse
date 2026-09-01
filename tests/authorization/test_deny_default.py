"""Deny-by-default unknown principal, action, resource, and unbound authorize()."""

from __future__ import annotations

from movie_muse.authorization.api import (
    Action,
    DecisionEffect,
    Resource,
    ResourceKind,
    authorize,
)
from movie_muse.identity.api import Principal, PrincipalKind, make_human_actor


def test_unbound_authorize_is_denied(acl_stack) -> None:
    principal = acl_stack.identity.principal(acl_stack.owner.id)
    resource = Resource(
        kind=ResourceKind.PROJECT,
        id=acl_stack.project.id,
        organization_id=acl_stack.project.organization_id,
        project_id=acl_stack.project.id,
    )
    decision = authorize(
        principal,
        Action.READ,
        resource,
        acl_epoch=acl_stack.identity.acl_epoch(),
    )
    assert decision.denied
    assert decision.reason == "no_authority"


def test_unknown_action_is_denied(acl_stack) -> None:
    principal = acl_stack.identity.principal(acl_stack.owner.id)
    resource = acl_stack.authorization.resource_for_project(acl_stack.project.id)
    decision = acl_stack.authorization.authorize(
        principal,
        "launch_missiles",
        resource,
        acl_epoch=acl_stack.identity.acl_epoch(),
    )
    assert decision.effect is DecisionEffect.DENY
    assert decision.reason == "unknown_action"


def test_unknown_principal_is_denied(acl_stack) -> None:
    ghost = Principal(
        actor_id="act_00000000000000000000000000",
        kind=PrincipalKind.HUMAN,
        organization_id=acl_stack.project.organization_id,
        display_name="Ghost",
    )
    resource = acl_stack.authorization.resource_for_project(acl_stack.project.id)
    decision = acl_stack.authorization.authorize(
        ghost, Action.READ, resource, acl_epoch=acl_stack.identity.acl_epoch()
    )
    assert decision.denied
    assert decision.reason == "unknown_principal"


def test_unknown_resource_is_denied(acl_stack) -> None:
    principal = acl_stack.identity.principal(acl_stack.owner.id)
    resource = Resource(
        kind=ResourceKind.PROJECT,
        id="proj_00000000000000000000000000",
        organization_id=acl_stack.project.organization_id,
        project_id="proj_00000000000000000000000000",
    )
    decision = acl_stack.authorization.authorize(
        principal, Action.READ, resource, acl_epoch=acl_stack.identity.acl_epoch()
    )
    assert decision.denied
    assert decision.reason == "unknown_resource"


def test_registered_actor_without_membership_is_denied(acl_stack) -> None:
    stranger = make_human_actor(
        organization_id=acl_stack.project.organization_id, display_name="Stranger"
    )
    acl_stack.identity.register_actor(stranger)
    principal = acl_stack.identity.principal(stranger.id)
    resource = acl_stack.authorization.resource_for_project(acl_stack.project.id)
    decision = acl_stack.authorization.authorize(
        principal, Action.READ, resource, acl_epoch=acl_stack.identity.acl_epoch()
    )
    assert decision.denied
    assert decision.reason == "no_membership"
