"""Airplane/outage: authorize() remains a local authority with no network."""

from __future__ import annotations

from movie_muse.authorization.api import Action


def test_authorize_works_in_airplane_and_provider_outages(acl_stack) -> None:
    acl_stack.workspace.set_airplane_mode(True)
    acl_stack.workspace.set_outage("auth_outage", True)
    acl_stack.workspace.set_outage("subscription_outage", True)
    acl_stack.workspace.set_outage("sync_outage", True)
    acl_stack.workspace.set_outage("ai_outage", True)
    principal = acl_stack.identity.principal(acl_stack.owner.id)
    resource = acl_stack.authorization.resource_for_project(acl_stack.project.id)
    decision = acl_stack.authorization.authorize(
        principal, Action.READ, resource, acl_epoch=acl_stack.identity.acl_epoch()
    )
    assert decision.allowed
    status = acl_stack.workspace.status()
    assert status.connectivity_offline is True
    assert status.auth_outage is True
    assert status.subscription_outage is True
    assert status.sync_outage is True
    assert status.ai_outage is True
