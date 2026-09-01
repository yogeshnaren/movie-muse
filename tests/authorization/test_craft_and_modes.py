"""Department craft ownership, AI deny, and mode projections that never fork canon."""

from __future__ import annotations

from dataclasses import replace

from movie_muse.authorization.api import (
    Action,
    AuthContext,
    AuthorizationError,
    Mode,
    ResourceKind,
    compose_modes,
)
from movie_muse.identity.api import (
    ActorImmutableError,
    PrincipalKind,
    Role,
    make_human_actor,
    make_integration_actor,
)


def _invite(acl_stack, actor, role: Role, *, department: str | None = None):
    invitation = acl_stack.identity.invite(
        inviter_actor_id=acl_stack.owner.id,
        invitee_actor_id=actor.id,
        project_id=acl_stack.project.id,
        role=role,
        department=department,
    )
    acl_stack.identity.accept_invitation(invitation.id, actor_id=actor.id)
    return acl_stack.identity.principal(actor.id)


def test_human_department_role_can_confirm_matching_craft_decision(acl_stack) -> None:
    costume = make_human_actor(
        organization_id=acl_stack.project.organization_id, display_name="Costume"
    )
    acl_stack.identity.register_actor(costume)
    principal = _invite(acl_stack, costume, Role.DEPARTMENT_CONTRIBUTOR, department="costume")
    acl_stack.authorization.declare_operation(
        project_id=acl_stack.project.id,
        operation_id="op_costume_palette",
        department="costume",
    )
    resource = acl_stack.authorization.resource_for_project(
        acl_stack.project.id,
        kind=ResourceKind.OPERATION,
        resource_id="op_costume_palette",
        department="costume",
    )
    decision = acl_stack.authorization.authorize(
        principal,
        Action.CONFIRM_CRAFT_DECISION,
        resource,
        acl_epoch=acl_stack.identity.acl_epoch(),
        context=AuthContext(department="costume"),
    )
    assert decision.allowed
    acl_stack.commands.confirm_craft_decision(
        actor_id=costume.id, department="costume", operation_id="op_costume_palette"
    )


def test_ai_integration_cannot_confirm_department_craft_decision(acl_stack) -> None:
    bot = make_integration_actor(
        organization_id=acl_stack.project.organization_id, display_name="Model"
    )
    acl_stack.identity.register_actor(bot)
    principal = _invite(acl_stack, bot, Role.INTEGRATION_SERVICE)
    acl_stack.authorization.declare_operation(
        project_id=acl_stack.project.id,
        operation_id="op_costume_palette",
        department="costume",
    )
    resource = acl_stack.authorization.resource_for_project(
        acl_stack.project.id,
        kind=ResourceKind.OPERATION,
        resource_id="op_costume_palette",
        department="costume",
    )
    decision = acl_stack.authorization.authorize(
        principal,
        Action.CONFIRM_CRAFT_DECISION,
        resource,
        acl_epoch=acl_stack.identity.acl_epoch(),
        context=AuthContext(department="costume"),
    )
    assert decision.denied
    assert decision.reason == "craft_owner_required"
    try:
        acl_stack.commands.confirm_craft_decision(
            actor_id=bot.id, department="costume", operation_id="op_costume_palette"
        )
        raise AssertionError("integration must not confirm craft decisions")
    except AuthorizationError:
        pass


def test_integration_with_department_role_still_cannot_confirm(acl_stack) -> None:
    bot = make_integration_actor(
        organization_id=acl_stack.project.organization_id, display_name="CostumerBot"
    )
    acl_stack.identity.register_actor(bot)
    principal = _invite(acl_stack, bot, Role.DEPARTMENT_CONTRIBUTOR, department="costume")
    acl_stack.authorization.declare_operation(
        project_id=acl_stack.project.id,
        operation_id="op_costume_palette",
        department="costume",
    )
    resource = acl_stack.authorization.resource_for_project(
        acl_stack.project.id,
        kind=ResourceKind.OPERATION,
        resource_id="op_costume_palette",
        department="costume",
    )
    decision = acl_stack.authorization.authorize(
        principal, Action.CONFIRM_CRAFT_DECISION, resource, acl_epoch=acl_stack.identity.acl_epoch()
    )
    assert decision.denied


def test_integration_actor_cannot_be_reclassified_as_human_for_craft(
    acl_stack,
) -> None:
    bot = make_integration_actor(
        organization_id=acl_stack.project.organization_id, display_name="ReclassBot"
    )
    acl_stack.identity.register_actor(bot)
    _invite(acl_stack, bot, Role.DEPARTMENT_CONTRIBUTOR, department="costume")
    acl_stack.authorization.declare_operation(
        project_id=acl_stack.project.id,
        operation_id="op_costume_reclass",
        department="costume",
    )
    epoch_before = acl_stack.identity.acl_epoch()
    snapshot_before = acl_stack.authorization.permission_snapshot_id()
    try:
        acl_stack.commands.confirm_craft_decision(
            actor_id=bot.id, department="costume", operation_id="op_costume_reclass"
        )
        raise AssertionError("integration must not confirm craft decisions")
    except AuthorizationError:
        pass

    try:
        acl_stack.identity.register_actor(
            replace(bot, principal_kind=PrincipalKind.HUMAN, display_name="Human now")
        )
        raise AssertionError("principal kind must be immutable")
    except ActorImmutableError:
        pass

    assert acl_stack.identity.acl_epoch() == epoch_before
    assert acl_stack.authorization.permission_snapshot_id() == snapshot_before
    stored = acl_stack.identity.get_actor(bot.id)
    assert stored.principal_kind is PrincipalKind.INTEGRATION_SERVICE
    try:
        acl_stack.commands.confirm_craft_decision(
            actor_id=bot.id, department="costume", operation_id="op_costume_reclass"
        )
        raise AssertionError("reclassified integration must still be denied")
    except AuthorizationError:
        pass


def test_modes_do_not_fork_canonical_head(acl_stack) -> None:
    owner = acl_stack.identity.principal(acl_stack.owner.id)
    head = acl_stack.revisions.canon_head_id()
    writer_view = acl_stack.authorization.project_view(Mode.WRITER, owner, acl_stack.project)
    director_view = acl_stack.authorization.project_view(Mode.DIRECTOR, owner, acl_stack.project)
    investor_view = acl_stack.authorization.project_view(Mode.INVESTOR, owner, acl_stack.project)
    composed_view = acl_stack.authorization.project_view(
        (Mode.WRITER, Mode.PRODUCER), owner, acl_stack.project
    )
    assert writer_view.head_revision_id == head
    assert director_view.head_revision_id == head
    assert investor_view.head_revision_id == head
    assert composed_view.head_revision_id == head
    assert writer_view.project_id == director_view.project_id == acl_stack.project.id
    assert "budget" not in writer_view.visible_fields
    assert "budget" in acl_stack.authorization.project_view(
        Mode.PRODUCER, owner, acl_stack.project
    ).visible_fields
    assert investor_view.allowed_actions == ("read",)


def test_custom_mode_composition_unions_actions_and_stays_deny_by_default(acl_stack) -> None:
    composed = compose_modes((Mode.WRITER, Mode.AD))
    assert Action.ACCEPT in composed.allowed_actions
    assert Action.MANAGE_PRODUCTION_LOCKS in composed.allowed_actions
    assert Action.MANAGE_ACL not in composed.allowed_actions
    owner = acl_stack.identity.principal(acl_stack.owner.id)
    resource = acl_stack.authorization.resource_for_project(acl_stack.project.id)
    allowed = acl_stack.authorization.authorize(
        owner,
        Action.ACCEPT,
        resource,
        acl_epoch=acl_stack.identity.acl_epoch(),
        context=AuthContext(modes=(Mode.WRITER, Mode.AD)),
    )
    denied = acl_stack.authorization.authorize(
        owner,
        Action.MANAGE_ACL,
        resource,
        acl_epoch=acl_stack.identity.acl_epoch(),
        context=AuthContext(modes=(Mode.WRITER, Mode.AD)),
    )
    assert allowed.allowed
    assert denied.denied
    assert denied.reason == "mode_denied"
