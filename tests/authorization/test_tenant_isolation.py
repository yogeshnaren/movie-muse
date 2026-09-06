"""Tenant isolation and confused-deputy probes."""

from __future__ import annotations

from movie_muse.authorization.api import Action, AuthContext, DecisionEffect, Resource, ResourceKind
from movie_muse.identity.api import Actor, Organization, PrincipalKind
from movie_muse.schemas.api import Project, new_id


def _bind_foreign_project(acl_stack) -> Project:
    owner_b = new_id("actor")
    project_b = Project(
        id=new_id("project"),
        organization_id="org_b",
        title="Secret",
        owner_actor_id=owner_b,
        created_at="2026-09-01T00:00:00Z",
    )
    acl_stack.identity.bind_project(
        organization=Organization(id="org_b", name="B", created_at="2026-09-01T00:00:00Z"),
        project=project_b,
        owner=Actor(
            id=owner_b,
            display_name="B Owner",
            principal_kind=PrincipalKind.HUMAN,
            organization_id="org_b",
            created_at="2026-09-01T00:00:00Z",
        ),
    )
    return project_b


def test_principal_in_org_a_cannot_read_org_b_project(acl_stack) -> None:
    project_b = _bind_foreign_project(acl_stack)
    principal_a = acl_stack.identity.principal(acl_stack.owner.id)
    foreign = Resource(
        kind=ResourceKind.PROJECT,
        id=project_b.id,
        organization_id="org_b",
        project_id=project_b.id,
    )
    decision = acl_stack.authorization.authorize(
        principal_a, Action.READ, foreign, acl_epoch=acl_stack.identity.acl_epoch()
    )
    assert decision.denied
    assert decision.reason == "tenant_isolation"
    assert decision.effect is DecisionEffect.DENY
    denials = [record for record in acl_stack.audit.list_records() if record.reason == "tenant_isolation"]
    assert denials


def test_confused_deputy_copied_project_id_with_org_a_token_is_denied(acl_stack) -> None:
    project_b = _bind_foreign_project(acl_stack)
    principal_a = acl_stack.identity.principal(acl_stack.owner.id)
    smuggled = Resource(
        kind=ResourceKind.PROJECT,
        id=project_b.id,
        organization_id=acl_stack.project.organization_id,
        project_id=project_b.id,
    )
    decision = acl_stack.authorization.authorize(
        principal_a,
        Action.READ,
        smuggled,
        acl_epoch=acl_stack.identity.acl_epoch(),
        context=AuthContext(claimed_organization_id=acl_stack.project.organization_id),
    )
    assert decision.denied
    assert decision.reason == "confused_deputy"
    denials = [record for record in acl_stack.audit.list_records() if record.reason == "confused_deputy"]
    assert denials
