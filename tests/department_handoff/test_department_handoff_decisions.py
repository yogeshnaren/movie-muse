"""Craft-owner confirm/correct/N-A emit canonical ProjectEvents."""

from __future__ import annotations

import pytest

from movie_muse.authorization.api import AuthorizationError
from movie_muse.breakdown.api import ElementKind
from movie_muse.department_handoff.api import CraftAction, DepartmentDeniedError
from movie_muse.identity.api import Role, make_human_actor, make_integration_actor


def _invite(stack, role: Role, name: str, department: str | None = None, *, integration=False):
    actor = (
        make_integration_actor(organization_id=stack.project.organization_id, display_name=name)
        if integration
        else make_human_actor(organization_id=stack.project.organization_id, display_name=name)
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


def test_costume_confirm_emits_department_decision_event(
    derived_breakdown, handoff_stack
) -> None:
    costume, epoch = _invite(
        handoff_stack, Role.DEPARTMENT_CONTRIBUTOR, "Costume", department="costume"
    )
    wardrobe = next(
        item for item in derived_breakdown.elements if item.kind is ElementKind.WARDROBE
    )
    decision = handoff_stack.handoff.craft_action(
        derived_breakdown.projection.id,
        wardrobe.id,
        CraftAction.CONFIRM,
        principal=costume,
        acl_epoch=epoch,
        note="coat is hero wardrobe",
    )
    assert decision.action is CraftAction.CONFIRM
    assert decision.department == "costume"
    events = handoff_stack.handoff.list_events(
        handoff_stack.project.id,
        principal=handoff_stack.principal,
        acl_epoch=handoff_stack.epoch,
    )
    assert any(item.event_type == "DepartmentDecisionConfirmed" for item in events)
    assert decision.event_id == events[-1].id


def test_correct_and_ask_director_use_closed_event_types(
    derived_breakdown, handoff_stack
) -> None:
    costume, epoch = _invite(
        handoff_stack, Role.DEPARTMENT_CONTRIBUTOR, "Costume", department="costume"
    )
    wardrobe = next(
        item for item in derived_breakdown.elements if item.kind is ElementKind.WARDROBE
    )
    correction = handoff_stack.handoff.craft_action(
        derived_breakdown.projection.id,
        wardrobe.id,
        CraftAction.CORRECT,
        principal=costume,
        acl_epoch=epoch,
        note="coat is navy, not black",
    )
    question = handoff_stack.handoff.craft_action(
        derived_breakdown.projection.id,
        wardrobe.id,
        CraftAction.ASK_DIRECTOR,
        principal=costume,
        acl_epoch=epoch,
        note="is the coat wet in scene two?",
    )
    assert correction.action is CraftAction.CORRECT
    assert question.action is CraftAction.ASK_DIRECTOR
    types = {
        item.event_type
        for item in handoff_stack.handoff.list_events(
            handoff_stack.project.id,
            principal=handoff_stack.principal,
            acl_epoch=handoff_stack.epoch,
        )
    }
    assert "DepartmentDecisionConfirmed" in types
    assert "ProductionRequirementConfirmed" in types


def test_assumption_and_na_use_closed_event_types(derived_breakdown, handoff_stack) -> None:
    costume, epoch = _invite(
        handoff_stack, Role.DEPARTMENT_CONTRIBUTOR, "Costume", department="costume"
    )
    wardrobe = next(
        item for item in derived_breakdown.elements if item.kind is ElementKind.WARDROBE
    )
    handoff_stack.handoff.craft_action(
        derived_breakdown.projection.id,
        wardrobe.id,
        CraftAction.ADD_ASSUMPTION,
        principal=costume,
        acl_epoch=epoch,
        note="daylight interior",
    )
    handoff_stack.handoff.craft_action(
        derived_breakdown.projection.id,
        wardrobe.id,
        CraftAction.NOT_APPLICABLE,
        principal=costume,
        acl_epoch=epoch,
        note="no aging makeup in this scene",
    )
    types = {
        item.event_type
        for item in handoff_stack.handoff.list_events(
            handoff_stack.project.id,
            principal=handoff_stack.principal,
            acl_epoch=handoff_stack.epoch,
        )
    }
    assert "AssumptionChanged" in types
    assert "ProductionRequirementConfirmed" in types


def test_integration_cannot_confirm_craft(derived_breakdown, handoff_stack) -> None:
    bot, epoch = _invite(
        handoff_stack, Role.INTEGRATION_SERVICE, "bot", integration=True
    )
    wardrobe = next(
        item for item in derived_breakdown.elements if item.kind is ElementKind.WARDROBE
    )
    with pytest.raises((DepartmentDeniedError, AuthorizationError)):
        handoff_stack.handoff.craft_action(
            derived_breakdown.projection.id,
            wardrobe.id,
            CraftAction.CONFIRM,
            principal=bot,
            acl_epoch=epoch,
        )


def test_props_cannot_confirm_costume_element(derived_breakdown, handoff_stack) -> None:
    props, epoch = _invite(
        handoff_stack, Role.DEPARTMENT_CONTRIBUTOR, "Props", department="props"
    )
    wardrobe = next(
        item for item in derived_breakdown.elements if item.kind is ElementKind.WARDROBE
    )
    with pytest.raises((DepartmentDeniedError, AuthorizationError)):
        handoff_stack.handoff.craft_action(
            derived_breakdown.projection.id,
            wardrobe.id,
            CraftAction.CONFIRM,
            principal=props,
            acl_epoch=epoch,
        )
