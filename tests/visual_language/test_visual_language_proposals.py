"""ShotIR color updates stay proposals until a human accepts them."""

from __future__ import annotations

import pytest

from movie_muse.identity.api import Role, make_integration_actor
from movie_muse.shot_ir.api import ShotNotFoundError
from movie_muse.visual_language.api import ShotProposalError


def test_propose_does_not_mutate_shotir_color_intent(
    visual_stack, recorded_language, make_shot
) -> None:
    language = recorded_language()
    shot = make_shot(color_intent="unspecified")
    proposal = visual_stack.visual.propose_shot_color(
        language.id,
        shot.record.id,
        principal=visual_stack.principal,
        acl_epoch=visual_stack.epoch,
    )
    assert proposal.id.startswith("vpr_")
    assert proposal.accepted is False
    assert "tungsten-warm" in proposal.color_intent
    fresh = visual_stack.shots.get_shot(
        shot.record.id,
        principal=visual_stack.principal,
        acl_epoch=visual_stack.epoch,
    )
    assert fresh.color_intent == "unspecified"
    assert fresh.color_intent != proposal.color_intent


def test_human_accept_updates_shotir_color_intent(
    visual_stack, recorded_language, make_shot
) -> None:
    language = recorded_language()
    shot = make_shot(color_intent="unspecified")
    proposal = visual_stack.visual.propose_shot_color(
        language.id,
        shot.record.id,
        principal=visual_stack.principal,
        acl_epoch=visual_stack.epoch,
    )
    updated = visual_stack.visual.accept_shot_proposal(
        proposal.id,
        principal=visual_stack.principal,
        acl_epoch=visual_stack.epoch,
    )
    assert updated.color_intent == proposal.color_intent
    assert "tungsten-warm" in updated.color_intent
    stored = visual_stack.shots.get_shot(
        shot.record.id,
        principal=visual_stack.principal,
        acl_epoch=visual_stack.epoch,
    )
    assert stored.color_intent == proposal.color_intent
    operations = {record.operation for record in visual_stack.audit.list_records()}
    assert "visual_language.propose_shot" in operations
    assert "visual_language.accept_shot" in operations


def test_integration_principal_cannot_accept_shot_proposal(
    visual_stack, recorded_language, make_shot, member
) -> None:
    language = recorded_language()
    shot = make_shot()
    proposal = visual_stack.visual.propose_shot_color(
        language.id,
        shot.record.id,
        principal=visual_stack.principal,
        acl_epoch=visual_stack.epoch,
    )
    actor = make_integration_actor(
        organization_id=visual_stack.project.organization_id,
        display_name="Color Bot",
    )
    visual_stack.identity.register_actor(actor)
    bot = visual_stack.identity.principal(actor.id)
    with pytest.raises(ShotProposalError, match="human"):
        visual_stack.visual.accept_shot_proposal(
            proposal.id, principal=bot, acl_epoch=visual_stack.identity.acl_epoch()
        )
    invited = member(Role.INTEGRATION_SERVICE, integration=True)
    with pytest.raises(ShotProposalError, match="human"):
        visual_stack.visual.accept_shot_proposal(
            proposal.id, principal=invited, acl_epoch=visual_stack.epoch
        )
    fresh = visual_stack.shots.get_shot(
        shot.record.id,
        principal=visual_stack.principal,
        acl_epoch=visual_stack.epoch,
    )
    assert fresh.color_intent == "unspecified"


def test_already_accepted_proposal_fails_closed(
    visual_stack, recorded_language, make_shot
) -> None:
    language = recorded_language()
    shot = make_shot()
    proposal = visual_stack.visual.propose_shot_color(
        language.id,
        shot.record.id,
        principal=visual_stack.principal,
        acl_epoch=visual_stack.epoch,
    )
    visual_stack.visual.accept_shot_proposal(
        proposal.id,
        principal=visual_stack.principal,
        acl_epoch=visual_stack.epoch,
    )
    with pytest.raises(ShotProposalError, match="already accepted"):
        visual_stack.visual.accept_shot_proposal(
            proposal.id,
            principal=visual_stack.principal,
            acl_epoch=visual_stack.epoch,
        )


def test_missing_proposal_fails_closed(visual_stack) -> None:
    with pytest.raises(ShotProposalError):
        visual_stack.visual.accept_shot_proposal(
            "vpr_missing",
            principal=visual_stack.principal,
            acl_epoch=visual_stack.epoch,
        )


def test_unknown_shot_cannot_receive_color_proposal(
    visual_stack, recorded_language
) -> None:
    language = recorded_language()
    with pytest.raises(ShotNotFoundError):
        visual_stack.visual.propose_shot_color(
            language.id,
            "sht_missing",
            principal=visual_stack.principal,
            acl_epoch=visual_stack.epoch,
        )
