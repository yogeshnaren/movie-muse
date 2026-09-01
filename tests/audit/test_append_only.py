"""Append-only audit records, integrity hashes, and authorize() audit trail."""

from __future__ import annotations

from movie_muse.audit.api import AuditImmutableError, PolicyDecision
from movie_muse.authorization.api import Action, Resource, ResourceKind


def test_append_only_and_hashes(audit_stack) -> None:
    _workspace, _identity, _authorization, audit, _project, owner = audit_stack
    first = audit.append(
        actor_id=owner.id,
        effective_principal_id=owner.id,
        operation="read",
        object_kind="project",
        object_id="proj_demo",
        policy_decision=PolicyDecision.ALLOW,
        acl_epoch=0,
        reason="allow",
        before_revision_id=None,
        after_revision_id=None,
        correlation_id="corr_1",
    )
    second = audit.append(
        actor_id=owner.id,
        effective_principal_id=owner.id,
        operation="export",
        object_kind="document",
        object_id="doc_demo",
        policy_decision=PolicyDecision.DENY,
        acl_epoch=0,
        reason="role_denied",
        before_revision_id=first.id,
        after_revision_id=None,
        correlation_id="corr_2",
    )
    assert first.integrity_hash == first.expected_hash()
    assert second.integrity_hash == second.expected_hash()
    assert second.previous_hash == first.integrity_hash
    replayed = audit.replay()
    assert [record.id for record in replayed] == [first.id, second.id]
    listed = audit.list_records()
    assert listed == replayed
    try:
        audit.update(first.id, reason="tamper")
        raise AssertionError("update must fail closed")
    except AuditImmutableError:
        pass
    try:
        audit.delete(first.id)
        raise AssertionError("delete must fail closed")
    except AuditImmutableError:
        pass
    still = audit.get(first.id)
    assert still.reason == "allow"
    assert still.integrity_hash == first.integrity_hash


def test_authorize_allow_and_deny_are_audited(audit_stack) -> None:
    _workspace, identity, authorization, audit, project, owner = audit_stack
    principal = identity.principal(owner.id)
    resource = authorization.resource_for_project(project.id)
    allow = authorization.authorize(
        principal, Action.READ, resource, acl_epoch=identity.acl_epoch()
    )
    craft = authorization.resource_for_project(
        project.id,
        kind=ResourceKind.OPERATION,
        resource_id="op_costume",
        department="costume",
    )
    deny = authorization.authorize(
        principal, Action.CONFIRM_CRAFT_DECISION, craft, acl_epoch=identity.acl_epoch()
    )
    assert allow.allowed
    assert deny.denied
    records = audit.list_records()
    effects = {(record.operation, record.policy_decision) for record in records}
    assert ("read", PolicyDecision.ALLOW) in effects
    assert ("confirm_craft_decision", PolicyDecision.DENY) in effects
    for record in records:
        assert record.integrity_hash == record.expected_hash()
        assert record.actor_id == owner.id
        assert record.effective_principal_id == owner.id


def test_confused_deputy_probe_is_audited(audit_stack) -> None:
    _workspace, identity, authorization, audit, project, owner = audit_stack
    principal = identity.principal(owner.id)
    smuggled = Resource(
        kind=ResourceKind.PROJECT,
        id=project.id,
        organization_id="org_other",
        project_id=project.id,
    )
    decision = authorization.authorize(
        principal, Action.READ, smuggled, acl_epoch=identity.acl_epoch()
    )
    assert decision.denied
    reasons = {record.reason for record in audit.list_records()}
    assert "tenant_isolation" in reasons or "confused_deputy" in reasons
